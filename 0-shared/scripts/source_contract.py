"""The link between the two service offerings: the source dataset contract.

Source Dataset Migration publishes, per source, what a data product needs to read it in Fabric:
  source-dataset/<SRC>/source-dataset-contract.json (+ .md)
    lakehouse, workspace, schema, VL_MAIN variable names       => input Lakehouse shortcuts of the product
    tables: DPV1 name => Fabric table, and every DPV1 access path (ADLS folder, SPOT lake database, rpl_ views)
                                                               => how product T-SQL is re-pointed (D2)
    consumers: data products that read this source in DPV1     => analysis only; nothing of a product is built here
    readiness: stages S1-S4 completed                          => gate sources_available of the product
Data Product Migration reads it (frame_scope.py, build_input_lakehouse.py, review_scope.py).

Usage (from the repository root):
  python -I 0-shared/scripts/source_contract.py publish --id GEOS          # source side (run by build_source_dataset.py S4)
  python -I 0-shared/scripts/source_contract.py show --product GSP_ANALYSIS  # product side: inputs, tables used, readiness (read-only)
"""
import argparse, glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, paths, load_map, resolve_scope, write, track_event, project_dir, read_json, exists

READY = ('S1', 'S2', 'S3', 'S4')


def _dpv1_text(kind, name):
    p = os.path.join(paths()['dpv1_export_root'], kind, name + '.json')
    if not exists(p):
        return ''
    j = read_json(p)
    if kind == 'notebook':
        return '\n'.join(''.join(c.get('source', [])) for c in j.get('properties', {}).get('cells', []) if c.get('cell_type') == 'code').lower()
    if kind == 'sqlscript':
        return (((j.get('properties') or {}).get('content') or {}).get('query', '') or '').lower()
    return json.dumps(j).lower()


def product_texts(D):
    for n in set(D['pipelines']) - set(D.get('shared', [])):
        yield f'pipeline {n}', _dpv1_text('pipeline', n)
    for n in D['sqlscripts']:
        yield f'sqlscript {n}', _dpv1_text('sqlscript', n)
    for n in D['notebooks']:
        yield f'notebook {n}', _dpv1_text('notebook', n)


def build(m, scope):
    S = m['sds'][scope]
    src = S['folder']
    toks = S.get('data_tokens', {})
    spot = [t for t, d in toks.items() if d.startswith('SPOT lake database')]
    folders = [t.split('=', 1)[1].upper() for t in toks if t.startswith('datasource=')]
    rpl = {}
    for n in S['sqlscripts']:
        for c in m['objects'].get('sqlscript', {}).get(n, {}).get('creates', []):
            sch, obj = c.split('.', 1)
            if sch.startswith('rpl_'):
                rpl.setdefault(obj, c)
    tables = []
    for c in S['catalog']:
        t = c['table'].lower()
        access = [f"ADLS RAW|CLEANSED/DATASOURCE={f}/{c['schema']}.{c['table']}" for f in folders] + [f'{d}.{t}' for d in spot] + ([rpl[t]] if t in rpl else [])
        tables.append({'dpv1': f"{c['schema']}.{c['table']}", 'fabric': f'dbo.{t}', 'load': 'incremental' if c['incremental'] else 'full', 'dpv1_access': access})
    import ingestion  # files ingested next to the database (mixed source): one table each, read by the product through INP_<schema>.<NAME>_VW
    fi = ingestion.file_inputs(src)
    for t in fi.get('tables', []):
        n = t['name'].lower()
        tables.append({'dpv1': f"{fi.get('schema') or 'FILES'}.{t['name']}", 'fabric': f'dbo.{n}', 'load': 'full', 'dpv1_access': [f"INP_{fi.get('schema') or 'FILES'}/{t['name']}_VW".lower()], 'source': 'files'})
    pd = project_dir('sds', scope)
    lh_plat = glob.glob(os.path.join(pd, '3-build', 'fabric-deployment', '*', '*', f"{S['lakehouse']}.Lakehouse", '.platform'))
    st_p = os.path.join(pd, '0_progress_tracking', 'progress.json')
    st = read_json(st_p) if exists(st_p) else {'stages': {}, 'gates': {}}
    stages = {sid: st['stages'].get(sid, {}).get('status', 'not_started') for sid in ('F1', 'F2', 'F3', 'F4', 'S1', 'S2', 'S3', 'S4', 'S5')}
    consumers = []
    for c in S.get('consumers', []):
        D = m['dp'].get(c['dp'])
        used = tables_used(D, {'tables': tables}) if D else {}
        consumers.append({'data_product': c['dp'], 'evidence': c['evidence'], 'tables_used': sorted(used)})
    return {
        'source': scope, 'service': 'Source Dataset Migration', 'domain': S['domain'], 'workspace': S['ws'], 'folder': src,
        'lakehouse': S['lakehouse'], 'lakehouse_logical_id': read_json(lh_plat[0])['config']['logicalId'] if lh_plat else None,
        'schema': 'dbo',
        'vl_main_for_products': {'lakehouse_id': f'LH_SDS_{src}_ID', 'lakehouse_workspace_id': f'LH_SDS_{src}_WORKSPACE_ID', 'input_lakehouse_id': f'LH_INP_SDS_{src}_ID'},
        'input_lakehouse': f'LH_INP_SDS_{src}',
        'tables': tables,
        'dpv1_access_tokens': toks,
        'consumers': consumers,
        'readiness': readiness(stages, st['gates'], tables),
    }


def readiness(stages, gates, tables):
    """A source is ready for data products only when it is built, approved, has tables and passed the gap review."""
    gate = lambda g: gates.get(g, {}).get('status') == 'completed'
    blockers = [f'{s} not completed' for s in READY if stages[s] != 'completed']
    blockers += [] if gate('framing_approved') else ['framing not approved']
    blockers += [] if tables else ['no catalog table (catalog script missing)']
    blockers += [] if gate('gap_review_passed') else ['gap review not passed']
    return {'stages': stages, 'ready': not blockers, 'blockers': blockers, 'gap_review_passed': gate('gap_review_passed')}


def tables_used(D, contract):
    """Tables of the contract that the product's DPV1 code references (by any DPV1 access name), with the first evidence."""
    used = {}
    texts = list(product_texts(D))
    for t in contract['tables']:
        short = t['fabric'].split('.', 1)[1]
        names = {short} | {a.split('/')[-1].lower() for a in t['dpv1_access']} | {t['dpv1'].lower()}
        rx = re.compile(r'(?<![a-z0-9_])(' + '|'.join(map(re.escape, sorted(names, key=len, reverse=True))) + r')(?:_vw)?(?![a-z0-9_])')  # INP views are named <TABLE>_VW
        for who, txt in texts:
            if rx.search(txt):
                used[t['fabric']] = who
                break
    return used


def contract_path(scope):
    return project_dir('sds', scope, 'source-dataset-contract.json')


def load(scope):
    p = contract_path(scope)
    return read_json(p) if exists(p) else None


def publish(scope):
    m = load_map()
    scope, _ = resolve_scope(m, 'sds', scope)
    c = build(m, scope)
    write(contract_path(scope), json.dumps(c, indent=1, ensure_ascii=False) + '\n')
    r = c['readiness']
    L = [f'# Source Dataset Contract: {scope}', '', 'What Data Product Migration reuses from this source. Generated by `source_contract.py`; do not edit.', '',
         f"- **Lakehouse**: `{c['workspace']}` / `{c['folder']}` / `{c['lakehouse']}` (schema `{c['schema']}`)",
         f"- **Ready for data products**: {'✅ yes' if r['ready'] else '⚪ not yet: ' + '; '.join(r.get('blockers', []))} (" + ', '.join(f'{k} {v}' for k, v in r['stages'].items() if k.startswith('S')) + ')',
         f"- **In a data product**: input Lakehouse `{c['input_lakehouse']}` with one OneLake shortcut per table used; VL_MAIN of the product holds "
         + ', '.join(f'`{v}`' for v in c['vl_main_for_products'].values()), '',
         '## Tables', '', '| DPV1 table | Fabric table | Load | How DPV1 products read it |', '| --- | --- | --- | --- |']
    L += [f"| `{t['dpv1']}` | `{t['fabric']}` | {t['load']} | {'<br>'.join('`' + a + '`' for a in t['dpv1_access'])} |" for t in c['tables']]
    L += ['', '## Data products that read this source in DPV1 (analysis only, migrated by Data Product Migration)', '']
    if c['consumers']:
        L += ['| Data product | Tables used | Evidence |', '| --- | --- | --- |']
        L += [f"| {x['data_product']} | {len(x['tables_used'])}: {', '.join(x['tables_used'][:8])}{' …' if len(x['tables_used']) > 8 else ''} | {'<br>'.join(x['evidence'][:4])} |" for x in c['consumers']]
    else:
        L.append('- None found in the DPV1 code.')
    from common import write_note  # the readable contract is the hand-over section of build-notes.md; the json stays for data products
    L[0] = f'# Hand-over to Data Product Migration (source dataset contract): {scope}'
    cut = L.index('## Tables')  # summary in the notes; the table list and the consumer evidence in the details
    summary = L[:cut] + [f"- **Tables**: {len(c['tables'])} · **Data products that read it in DPV1**: {', '.join(x['data_product'] for x in c['consumers']) or 'none'}",
                         '- Tables with their DPV1 access paths, and the evidence per data product: `../analysis/build-details.md` (hand-over); machine-readable: `source-dataset-contract.json`.']
    write_note('sds', scope, 'hand-over', '\n'.join(summary) + '\n', '\n'.join([f'# Source dataset contract: {scope}', ''] + L[cut:]) + '\n')
    md_old = contract_path(scope)[:-5] + '.md'
    if exists(md_old):
        os.remove(md_old)
    track_event(scope, 'sds', 'S4', f"Source dataset contract published: {len(c['tables'])} tables, {len(c['consumers'])} consuming data products, ready={r['ready']}")
    return c


def show(product):
    m = load_map()
    product, _ = resolve_scope(m, 'dp', product)
    D = m['dp'][product]
    out = []
    for u in D['upstream']:
        c = load(u)
        if not c:
            out.append({'source': u, 'contract': False})
            continue
        used = tables_used(D, c)
        out.append({'source': u, 'contract': True, 'ready': c['readiness']['ready'], 'input_lakehouse': c['input_lakehouse'],
                    'tables_used': used, 'tables_total': len(c['tables'])})
    return product, out


def require_sources(product):
    """Data Product Migration starts only when every input source dataset is migrated (contract published, S1-S4 completed).
    Otherwise stop before anything is written, name each missing source and how to migrate it first (in its own source-dataset folder)."""
    product, inputs = show(product)
    missing = [o for o in inputs if not o['contract'] or not o['ready']]
    if not missing:
        return product, inputs
    m = load_map()
    L = [f'Data product {product} cannot start: it is produced from source datasets that are not migrated yet.', '']
    for o in inputs:
        u = o['source']
        if not o['contract']:
            state = 'not migrated (no source dataset contract)'
        elif not o['ready']:
            state = 'migration started, S1-S4 not completed'
        else:
            state = 'migrated ✅'
        L.append(f"  {'⚪' if o in missing else '✅'} {u}: {state}")
    L += ['', 'Ask the owner to confirm, then migrate each missing source first (Source Dataset Migration, one at a time):']
    for o in missing:
        u = o['source']
        dom = m['sds'].get(u, {}).get('domain', '<DOMAIN>')
        L.append(f'  python -I 0-shared/scripts/frame_scope.py --service sds --id {u} --domain {dom}')
    L += ['Its objects are created in 4-migration-project-deliverables/source-dataset/<SOURCE>/ only.',
          f'Then run the data product workflow for {product} again. Read-only check: python -I 0-shared/scripts/source_contract.py show --product {product}']
    raise SystemExit('\n'.join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=['publish', 'show'])
    ap.add_argument('--id')
    ap.add_argument('--product')
    a = ap.parse_args()
    if a.action == 'publish':
        c = publish(a.id)
        print(f"{c['source']}: contract published · {len(c['tables'])} tables · consumers {', '.join(x['data_product'] for x in c['consumers']) or 'none'} · ready {c['readiness']['ready']}")
        return
    product, out = show(a.product)
    print(f'{product}: input source datasets')
    for o in out:
        if not o['contract']:
            print(f"  ⚪ {o['source']}: no contract yet => run Source Dataset Migration for {o['source']} first")
        else:
            print(f"  {'✅' if o['ready'] else '🟡'} {o['source']}: {o['input_lakehouse']} · {len(o['tables_used'])}/{o['tables_total']} tables used: "
                  + ', '.join(f"{t} ({w})" for t, w in list(o['tables_used'].items())[:5]))


if __name__ == '__main__':
    main()
