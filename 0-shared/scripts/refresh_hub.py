"""Rebuild the Migration Hub from the DPV1 Synapse export and report what changed since the last run.

Usage (from the repository root):
  python -I 0-shared/scripts/refresh_hub.py           # use the DPV1 files as they are
  python -I 0-shared/scripts/refresh_hub.py --pull    # git pull DPV1 first (when it is a git clone)
  python -I 0-shared/scripts/refresh_hub.py --check   # only say whether the hub is older than the DPV1 export (exit 2 when stale)

Outputs in 5-migration-hub/: migration-map.json, knowledge/ (index.json + one JSON per scope: what the page shows, read by
the workflows; see knowledge.py), dpv1-fabric-migration-hub.html, migration-scope-index.md (every scope, its dependencies
and status), estate-coverage.md, refresh-report.md
DPV1 is only read.
"""
import argparse, datetime, json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, paths, write_if_changed

HERE = os.path.dirname(os.path.abspath(__file__))


def summary(d):
    c = lambda s: {'pipelines': len(s['pipelines']), 'objects': len(s['rows'])}
    return {'sds': {k: c(v) for k, v in d['sds'].items()}, 'dp': {k: c(v) for k, v in d['dp'].items()},
            'new': sorted(p['scope'] for p in d['projects'] if p['status'].startswith('new')), 'meta': d['meta']}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pull', action='store_true')
    ap.add_argument('--check', action='store_true', help='only report whether the hub is older than the DPV1 export')
    a = ap.parse_args()
    P = paths()
    src, hub = P['dpv1_export_root'], P['hub_root']
    if not os.path.isdir(os.path.join(src, 'pipeline')):
        sys.exit(f'Not a Synapse export root (no pipeline/ folder): {src}. Fix dpv1_export_root in 2-config/migration/paths.json.')
    if a.pull:
        top = subprocess.run(['git', '-C', src, 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
        print('DPV1 is not a git clone: using the files as they are' if top.returncode else
              subprocess.run(['git', '-C', top.stdout.strip(), 'pull', '--ff-only'], capture_output=True, text=True).stdout)

    if a.check:
        mp = os.path.join(hub, 'migration-map.json')
        meta = json.load(open(mp, encoding='utf-8'))['meta'] if os.path.exists(mp) else {}
        last = f'{datetime.datetime.fromtimestamp(dpv1_last_change(src)):%Y-%m-%d %H:%M}'
        seen = meta.get('dpv1_last_change', '')  # DPV1 state the hub was built from (hub files are rewritten only when their content changes)
        stale = last > seen
        print(f"DPV1 export last changed {last}; hub built from the export as of {seen or 'never'} => {'STALE: run refresh_hub.py' if stale else 'current'}")
        sys.exit(2 if stale else 0)
    os.makedirs(hub, exist_ok=True)
    map_path = os.path.join(hub, 'migration-map.json')
    prev = os.path.join(hub, 'knowledge', 'previous-summary.json')  # counts of the last refresh, for the change report
    old = json.load(open(prev, encoding='utf-8')) if os.path.exists(prev) else (summary(json.load(open(map_path, encoding='utf-8'))) if os.path.exists(map_path) else None)

    cfg = os.path.join(ROOT, '2-config', 'migration')
    engine_out = os.path.join(hub, 'knowledge', 'engine-output.json')  # raw engine output (not tracked); migration-map.json is written only on change
    os.makedirs(os.path.dirname(engine_out), exist_ok=True)
    r = subprocess.run([sys.executable, '-I', os.path.join(HERE, 'dpv1_mapping.py'), src, os.path.join(cfg, 'scope-target-map.json'), engine_out,
                        os.path.join(cfg, 'project-register.json')], capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr[-3000:])

    data = json.load(open(engine_out, encoding='utf-8'))
    import project_inputs  # the workspace chosen at framing wins, as in common.load_map: hub, index and tracking agree
    project_inputs.apply_to_map(data)
    data['meta'].update(generated_at=f'{datetime.datetime.now():%Y-%m-%d %H:%M}', source_root=os.path.relpath(src, ROOT).replace('\\', '/'),
                        dpv1_last_change=f'{datetime.datetime.fromtimestamp(dpv1_last_change(src)):%Y-%m-%d %H:%M}', stale=False)
    sp = json.load(open(os.path.join(cfg, 'shared-platform.json'), encoding='utf-8'))
    from common import catalog_warehouse
    data['meta']['catalog'] = {'warehouse': catalog_warehouse(sp), 'schema': sp['catalog_schema'], 'view_pattern': sp['catalog_view_pattern'],
                               'location': sp['catalog_warehouse_location']}
    write_if_changed(map_path, json.dumps(data, separators=(',', ':'), sort_keys=True))  # sorted: same bytes on every run
    import classify_scenarios  # what each project needs built: on the page, in knowledge/ and in the two scenario catalogs
    data['scenarios'] = classify_scenarios.classify(data)
    data['scenario_defs'] = classify_scenarios.definitions()
    classify_scenarios.write_outputs(data['scenarios'], hub)
    import scope_tree, knowledge  # same trees as 1-framing/03 and 06; on the page and in knowledge/, not in migration-map.json
    cat = {'warehouse': catalog_warehouse(sp), 'schema': sp['catalog_schema']}
    data['trees'] = {k: {s: {'asis': scope_tree.as_is(S, data['objects'], k), 'tobe': scope_tree.to_be(S, k, cat, data['objects'])} for s, S in data[k].items()} for k in ('sds', 'dp')}
    payload = json.dumps(data, separators=(',', ':'), sort_keys=True).replace('</', '<\\/')
    html = open(os.path.join(ROOT, '0-shared', 'templates', 'migration-hub-template.html'), encoding='utf-8').read().replace('/*DATA*/', payload, 1)
    write_if_changed(os.path.join(hub, 'dpv1-fabric-migration-hub.html'), html)

    n_kb = knowledge.build(data, src)
    new = summary(data)
    with open(prev, 'w', encoding='utf-8') as f:
        json.dump(new, f)
    L = [f'# Migration hub refresh · {datetime.datetime.now():%Y-%m-%d %H:%M}', '', f'Source: `{src}`', '',
         f"- Pipelines scanned: {new['meta']['pipelines_total']} · source datasets: {new['meta']['sds_scopes']} · data products: {new['meta']['dp_scopes']}",
         f"- Scopes not in the project register: {', '.join(new['new']) or 'none'}",
         f'- Knowledge base: {n_kb} scope files in `5-migration-hub/knowledge/`', '']
    if old:
        for kind, label in (('sds', 'Source datasets'), ('dp', 'Data products')):
            o, n = old[kind], new[kind]
            ch = [f'`{k}` pipelines {o[k]["pipelines"]} → {n[k]["pipelines"]}, objects {o[k]["objects"]} → {n[k]["objects"]}' for k in sorted(set(o) & set(n)) if o[k] != n[k]]
            L += [f'## {label}', f"- Added: {', '.join(sorted(set(n) - set(o))) or 'none'}", f"- Removed: {', '.join(sorted(set(o) - set(n))) or 'none'}",
                  f"- Changed: {'; '.join(ch) or 'none'}", '']
        L.append(f"New unregistered scopes since last refresh: {', '.join(sorted(set(new['new']) - set(old['new']))) or 'none'}")
    else:
        L.append('First run: nothing to compare with.')
    write_if_changed(os.path.join(hub, 'refresh-report.md'), '\n'.join(L) + '\n')
    write_estate(hub, data)
    write_index(hub, data)
    print('\n'.join(L))


def dpv1_last_change(src):
    """Newest modification time of any file in the DPV1 export (to tell whether the hub is stale)."""
    newest = 0.0
    for root, _, files in os.walk(src):
        if '.git' in root:
            continue
        for f in files:
            newest = max(newest, os.path.getmtime(os.path.join(root, f)))
    return newest


def project_status(service, scope):
    """Migration status of a scope from its tracking (and contract for a source)."""
    import track, source_contract
    from common import project_dir
    if not os.path.exists(project_dir(service, scope, '0_progress_tracking', 'progress.json')):
        return '⚪ not started'
    st = track.load(scope, service)
    if service == 'sds':
        c = source_contract.load(scope)
        if c and c['readiness']['ready']:
            return f'✅ ready for data products ({track.completion(st)}%)'
    return f'🟡 in progress ({track.completion(st)}%, {track.current(st)})'


def write_index(hub, data):
    """5-migration-hub/migration-scope-index.md: one reference for every scope, its dependencies and its status.
    Agents read it to identify the dependencies of a request, then confirm the key inputs with the developer."""
    meta = data['meta']
    sds, dp = data['sds'], data['dp']
    st_s = {s: project_status('sds', s) for s in sds}
    L = ['# Migration Scope Index', '', f"Last update: {meta['generated_at']}", '',
         f"- **DPV1 export**: `{meta['source_root']}`, last changed {meta['dpv1_last_change']}",
         f"- **Hub and index generated**: {meta['generated_at']} => {'✅ current' if not meta['stale'] else '⚠️ older than the export: run refresh_hub.py'}",
         f"- **Scopes**: {len(sds)} source datasets, {len(dp)} data products · estate: `estate-coverage.md`", '',
         '## How agents use this file', '',
         '1. Run `python -I 0-shared/scripts/refresh_hub.py --check`. If it says stale, run `refresh_hub.py` first (or ask the m-scope-refresher).',
         '2. Find the requested scope below. A data product lists the source datasets it is produced from, with their status: all must be ✅ before it starts.',
         '3. Confirm the key inputs with the developer (service, name, domain or group, catalog warehouse). The index proposes values; the developer decides.', '',
         '## Source datasets', '',
         '| Source | Domain | Workspace / Lakehouse | DPV1 objects | Catalog tables | Read by data products | Status |', '| --- | --- | --- | --- | --- | --- | --- |']
    for s, S in sorted(sds.items()):
        L.append(f"| {s} | {S['domain']}{'' if S['domain_confirmed'] else ' (to confirm)'} | `{S['ws']}` / `{S['lakehouse']}` | {len(S['rows'])} | {len(S['catalog'])} | "
                 f"{', '.join(S.get('downstream', [])) or '-'} | {st_s[s]} |")
    L += ['', '## Data products', '', 'Can start = every input source dataset is migrated (✅).', '',
          '| Data product | Group | Workspace | DPV1 objects | Input source datasets | Reads products | Read by products | Can start | Status |',
          '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for g, D in sorted(dp.items()):
        ins = D.get('upstream', [])
        ok = all(st_s.get(u, '').startswith('✅') for u in ins)
        L.append(f"| {g} | {D['group']}{'' if D['group_confirmed'] else ' (to confirm)'} | `{D['ws']}` | {len(D['rows'])} | "
                 + (', '.join(f"{u} {st_s.get(u, '⚪')[:1]}" for u in ins) or '-') + ' | '
                 + (', '.join(x['dp'] for x in D.get('reads_products', [])) or '-') + ' | '
                 + (', '.join(x['dp'] for x in D.get('read_by_products', [])) or '-') + f" | {'✅ yes' if ok else '⚪ no'} | {project_status('dp', g)} |")
    L += ['', '## Other names that resolve to a data product', '', 'Master pipelines and DW / DM schemas accepted as the data product identifier.', '',
          '| Name | Data product |', '| --- | --- |'] + [f'| `{k}` | {v} |' for k, v in sorted(data.get('lookup', {}).items()) if re.match(r'^(DW|DM)_', k) or k in {m.upper() for d in dp.values() for m in d.get('masters', [])}]
    write_if_changed(os.path.join(hub, 'migration-scope-index.md'), '\n'.join(L) + '\n')


def write_estate(hub, data):
    """5-migration-hub/estate-coverage.md: every DPV1 object is in a scope, in the shared framework or platform, or listed with a reason."""
    E = data['estate']
    esc = lambda s: str(s or '').replace('|', '/')
    L = ['# DPV1 Estate Coverage', '', f"Last update: {data['meta']['generated_at']}", '',
         'Every object of the Synapse export is accounted for: in a source dataset or data product scope, in the shared framework, in the platform, '
         'or listed below with a reason. Owner decisions go to `2-config/migration/scope-decisions.json` (key `estate`).', '',
         '| Object type | In the export | In a scope | Shared framework | Unused | To decide |', '| --- | --- | --- | --- | --- | --- |']
    L += [f"| {k} | {v['total']} | {v['in_scope']} | {v['shared']} | {v['unused']} | {v['to_decide']} |" for k, v in E['totals'].items()]
    for cat in sorted({r['cat'] for r in E['rows']}, key=lambda c: (c.startswith('unused'), c)):
        rows = [r for r in E['rows'] if r['cat'] == cat]
        L += ['', f'## {cat} ({len(rows)})', '', '| Type | Object | Folder | Action | Fabric target | Note |', '| --- | --- | --- | --- | --- | --- |']
        L += [f"| {r['kind']} | `{esc(r['name'])}` | {esc(r['folder'])} | {r['a']} | {esc(r['v2'])} | {esc(r['n'])} |" for r in rows]
    write_if_changed(os.path.join(hub, 'estate-coverage.md'), '\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
