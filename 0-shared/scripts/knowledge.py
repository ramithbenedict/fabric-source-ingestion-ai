"""Migration knowledge base: everything the hub page shows, as JSON, one file per scope.

Written by refresh_hub.py into 5-migration-hub/knowledge/:
  index.json            every scope: service, domain or group, workspace, counts, dependencies (no status: read live)
  sds/<SOURCE>.json     one source dataset: scope record, DPV1 object details, trees, folder layout, owner decisions,
                        the DPV1 files it comes from with their size and time (fingerprint)
  dp/<PRODUCT>.json     one data product, same content
Workflows read the scope file first, then open only the DPV1 files it lists (no full scan of the export).

Usage (from the repository root):
  python -I 0-shared/scripts/knowledge.py show  --service sds --id EASYTENDER     # what the hub knows, plus live status
  python -I 0-shared/scripts/knowledge.py check --service sds --id EASYTENDER     # did the scope's DPV1 files change? (exit 2 = refresh)
  python -I 0-shared/scripts/knowledge.py deps  --service dp  --id GSP_ANALYSIS   # input sources and their status, products read
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, paths, write, write_if_changed, read_json, exists

KINDS = {'pipelines': 'pipeline', 'notebooks': 'notebook', 'dataflows': 'dataflow', 'datasets': 'dataset',
         'linked_services': 'linkedService', 'triggers': 'trigger', 'sqlscripts': 'sqlscript', 'shared': 'pipeline'}
SVC = {'sds': 'Source Dataset Migration', 'dp': 'Data Product Migration'}


def kb_dir(*parts):
    return os.path.join(paths()['hub_root'], 'knowledge', *parts)


def dpv1_file(src, kind, name):
    """Path of a DPV1 object in the Synapse export, relative to the export root, or None."""
    rel = f'{kind}/{name}.json'
    return rel if os.path.exists(os.path.join(src, rel)) else None


def fingerprint(src, files):
    out = {}
    for f in files:
        p = os.path.join(src, f)
        out[f] = [os.path.getsize(p), round(os.path.getmtime(p))] if os.path.exists(p) else None
    return out


def decisions(service, scope):
    p = os.path.join(ROOT, '2-config', 'migration', 'scope-decisions.json')
    d = read_json(p) if exists(p) else {}
    return d.get(service, {}).get(scope, {})


def build(data, src):
    """Write index.json and one file per scope from the refreshed map (data includes 'trees')."""
    import scope_tree
    O = data['objects']
    index = {'meta': {k: data['meta'].get(k) for k in ('generated_at', 'dpv1_last_change', 'source_root', 'pipelines_total', 'notebooks_total',
                                                        'sqlscripts_total', 'linked_services_total', 'sds_scopes', 'dp_scopes', 'catalog')},
             'estate_totals': data['estate']['totals'], 'sds': {}, 'dp': {}, 'lookup': data.get('lookup', {})}
    for kind in ('sds', 'dp'):
        for scope, S in data[kind].items():
            objs, files = {}, []
            for key, okind in KINDS.items():
                for n in S.get(key, []):
                    if n in O.get(okind, {}):
                        objs.setdefault(okind, {})[n] = O[okind][n]
                    f = dpv1_file(src, okind, n)
                    if f and f not in files:
                        files.append(f)
            rec = {'service': kind, 'service_name': SVC[kind], 'scope': S, 'objects': objs,
                   'trees': data.get('trees', {}).get(kind, {}).get(scope, {}),
                   'layout': scope_tree.layout(kind, scope, S), 'decisions': decisions(kind, scope), 'scenario': data.get('scenarios', {}).get(kind, {}).get(scope),
                   'dpv1_files': fingerprint(src, files)}  # no timestamp: an unchanged scope keeps an unchanged file
            write_if_changed(kb_dir(kind, f'{scope.lower()}.json'), json.dumps(rec, ensure_ascii=False, separators=(',', ':'), sort_keys=True))
            row = {'domain' if kind == 'sds' else 'group': S.get('domain') if kind == 'sds' else S.get('group'),
                   'confirmed': S.get('domain_confirmed') if kind == 'sds' else S.get('group_confirmed'),
                   'workspace': S['ws'], 'objects': len(S['rows']), 'counts': S.get('counts', {}), 'dpv1_files': len(files)}
            if kind == 'sds':
                row.update(lakehouse=S['lakehouse'], catalog_tables=len(S['catalog']), read_by=[c['dp'] for c in S.get('consumers', [])])
            else:
                row.update(warehouse=S['warehouse'], inputs=S.get('upstream', []), reads_products=[x['dp'] for x in S.get('reads_products', [])],
                           read_by_products=[x['dp'] for x in S.get('read_by_products', [])])
            index[kind][scope] = row
    write_if_changed(kb_dir('index.json'), json.dumps(index, ensure_ascii=False, indent=1, sort_keys=True))
    return len(index['sds']) + len(index['dp'])


def load(service, ident):
    from common import load_map, resolve_scope
    p = kb_dir(service, f'{ident.lower()}.json')
    if not exists(p):
        scope, _ = resolve_scope(load_map(), service, ident)
        p = kb_dir(service, f'{scope.lower()}.json')
    if not exists(p):
        raise SystemExit(f'No knowledge file for {service} {ident}: run  python -I 0-shared/scripts/refresh_hub.py')
    return read_json(p)


def check(rec):
    """Changed, missing or new-time DPV1 files of one scope since the last refresh."""
    src = paths()['dpv1_export_root']
    now = fingerprint(src, rec['dpv1_files'])
    return [(f, 'missing' if now[f] is None else 'changed') for f, v in rec['dpv1_files'].items() if now[f] != v]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['show', 'check', 'deps'])
    ap.add_argument('--service', choices=['sds', 'dp'], required=True)
    ap.add_argument('--id', required=True)
    a = ap.parse_args()
    rec = load(a.service, a.id)
    S = rec['scope']
    idx = kb_dir('index.json')
    rec['generated_at'] = (read_json(idx).get('meta', {}).get('generated_at') if exists(idx) else None) or '?'
    from refresh_hub import project_status
    if a.cmd == 'check':
        diff = check(rec)
        print(f"{S['scope']}: {len(rec['dpv1_files'])} DPV1 files, knowledge of {rec['generated_at']} => "
              + ('current' if not diff else f'{len(diff)} changed: run refresh_hub.py\n' + '\n'.join(f'  {s}: {f}' for f, s in diff)))
        sys.exit(2 if diff else 0)
    if a.cmd == 'deps':
        if a.service == 'sds':
            print(f"{S['scope']} is read by: " + (', '.join(f"{c['dp']} ({'; '.join(c['evidence'][:1])})" for c in S.get('consumers', [])) or 'no data product'))
        else:
            for u in S.get('upstream', []):
                print(f'input source {u}: {project_status("sds", u)}')
            print('reads products: ' + (', '.join(x['dp'] for x in S.get('reads_products', [])) or '-'))
            print('read by products: ' + (', '.join(x['dp'] for x in S.get('read_by_products', [])) or '-'))
        return
    L = [f"# {rec['service_name']}: {S['scope']}  (knowledge of {rec['generated_at']})",
         f"status: {project_status(a.service, S['scope'])}",
         f"target: {S['ws']} / {S.get('lakehouse') or S.get('warehouse')}",
         ('domain: ' + S['domain'] + ('' if S['domain_confirmed'] else ' (to confirm)')) if a.service == 'sds' else
         ('group: ' + S['group'] + ('' if S['group_confirmed'] else ' (to confirm)')),
         f"objects: {len(S['rows'])} ({', '.join(f'{k} {v}' for k, v in S.get('counts', {}).items())})",
         f"DPV1 files: {len(rec['dpv1_files'])}", f"entry points: {', '.join(S.get('entry', [])) or '-'}"]
    if a.service == 'sds':
        lay = rec['layout']
        L += [f"catalog tables: {len(S['catalog'])}", 'read by: ' + (', '.join(c['dp'] for c in S.get('consumers', [])) or '-'),
              f"DPV1 folder layout: raw date tree {'yes' if lay['raw_dates'] else 'no'}, HISTORY {'yes' if lay['history'] else 'no'}, "
              f"DELETE_LOGS {'yes' if lay['delete_logs'] else 'no'}, delta date tree {'yes' if lay['delta_dates'] else 'no'}"
              + ('' if lay['found'] else ' (legacy code not extracted yet: lakehouse convention)')]
    else:
        L += ['input sources: ' + (', '.join(S.get('upstream', [])) or '-')]
    sc = rec.get('scenario')
    if sc:
        L += [f"scenario: {sc['scenario']}  modifiers: {', '.join(sc['modifiers']) or 'none'}" + (f"  dacpac source: {sc['dacpac_source']}" if sc.get('dacpac_source') else ''),
              '  how it is built: 5-migration-hub/scenario-catalog-' + ('source-dataset' if rec['service'] == 'sds' else 'data-product') + '.md']
        if sc.get('orphans'):
            L += [f"  DPV1 objects named after this scope that no scope lists ({len(sc['orphans'])}): {', '.join(sc['orphans'][:6])}"]
    if rec['decisions']:
        L += ['owner decisions:'] + [f'  {k}: {v.get("action")} - {v.get("reason", "")}' for k, v in rec['decisions'].items()]
    review = [r['v1'] for r in S['rows'] if r['a'] == 'review']
    if review:
        L.append('to decide: ' + ', '.join(review))
    print('\n'.join(L))


if __name__ == '__main__':
    main()
