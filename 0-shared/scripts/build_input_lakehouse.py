"""wf-3 D3: input Lakehouses of a data product, built from the source dataset contracts of its input sources.

Usage (from the repository root):
  python -I 0-shared/scripts/build_input_lakehouse.py --id GAIA

For each input source dataset with a published contract (source_contract.py):
  LH_INP_SDS_<SRC>.Lakehouse/  .platform, lakehouse.metadata.json, shortcuts.metadata.json
      one OneLake shortcut per table the product reads (all tables when none is found in the DPV1 code);
      target = LH_SDS_<SRC> through VL_MAIN tokens $(/**/VL_MAIN/LH_SDS_<SRC>_ID) and _WORKSPACE_ID (skill-fabric-create-shortcut)
  build-notes.md, section D3-table-mapping: per table, the shortcut in LH_INP_SDS_<SRC> and its target in LH_SDS_<SRC> (no DPV1 reference: the
      source dataset ingests from the source system; D2 re-points the DPV1 reads from the source contract, convert_serverless_sql.py)
Sources without a contract are reported: run Source Dataset Migration for them first (gate sources_available stays open).
Output: 4-migration-project-deliverables/data-product/<PROJECT>/3-build/fabric-deployment/DP_DPG_<GROUP>/ and 3-build/build-notes/build-notes.md (section D3-table-mapping)
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, load_map, resolve_scope, write, track_event, project_dir, deploy_dir, notes_path, write_note
from build_source_dataset import platform, dump
import source_contract


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--id', required=True)
    ap.add_argument('--parallel', action='store_true', help='allow a second project in progress (owner agreed)')
    a = ap.parse_args()
    m = load_map()
    scope, _ = resolve_scope(m, 'dp', a.id)
    import track
    track.ensure_single_active(scope, 'dp', a.parallel)
    source_contract.require_sources(scope)
    import subprocess
    r = subprocess.run([sys.executable, '-I', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resolve_upstream.py'), '--id', scope], capture_output=True, text=True)
    if r.returncode:  # a shortcut needs real GUIDs at import: never write the zero placeholder
        raise SystemExit(f'{scope}: source Lakehouse IDs not resolved, nothing written.\n{(r.stdout + r.stderr).strip()[-600:]}')
    D = m['dp'][scope]
    ws = D['ws'].replace('_<ENV>', '')
    base = deploy_dir('dp', scope, ws)
    built, missing, L = [], [], [f'# Input tables: {scope}', '',
                                    'Each input Lakehouse holds only OneLake shortcuts to the Lakehouse of its source dataset (`LH_SDS_<SRC>`, workspace and item from `VL_MAIN`). '
                                    'The source dataset ingests from the source system itself; nothing is read from DPV1. In the warehouse only the `[INP_<SRC>]` views read these tables.', '',
                                    '| Table | Input Lakehouse (shortcut) | Shortcut target (source dataset) | Read in the warehouse by |', '| --- | --- | --- | --- |']
    for u in D['upstream']:
        c = source_contract.load(u)
        if not c:
            missing.append(u)
            continue
        used = source_contract.tables_used(D, c)
        tables = [t for t in c['tables'] if t['fabric'] in used] or c['tables']
        lh = c['input_lakehouse']
        folder = os.path.join(base, f'{lh}.Lakehouse')
        platform(folder, 'Lakehouse', lh, f"Input Lakehouse: OneLake shortcuts to {c['lakehouse']} ({len(tables)} tables). No copy.")
        write(os.path.join(folder, 'lakehouse.metadata.json'), '{"defaultSchema":"dbo"}\n')
        vl = c['vl_main_for_products']
        write(os.path.join(folder, 'shortcuts.metadata.json'), dump([
            {'name': t['fabric'].split('.', 1)[1], 'path': '/Tables/dbo',
             'target': {'type': 'OneLake', 'oneLake': {'path': f"Tables/{t['fabric'].replace('.', '/')}",
                                                       'itemId': f"$(/**/VL_MAIN/{vl['lakehouse_id']})", 'workspaceId': f"$(/**/VL_MAIN/{vl['lakehouse_workspace_id']})"}}}
            for t in tables]))
        src = u.replace('-', '_').upper()
        for t in tables:
            name = t['fabric'].split('.', 1)[1]
            L.append(f"| {name} | `{lh}.{t['fabric']}` | `{c['lakehouse']}.{t['fabric']}` (`{vl['lakehouse_workspace_id']}`, `{vl['lakehouse_id']}`) | `[INP_{src}].[{name}]` |")
        built.append(f"{lh} ({len(tables)} shortcuts{'' if c['readiness']['ready'] else ', source not ready'})")
    if missing:
        L += ['', '## Input sources without a contract', ''] + [f'- ⚪ `{u}`: run Source Dataset Migration for {u} (wf-1 + wf-2) first.' for u in missing]
    write_note('dp', scope, 'D3-table-mapping', '\n'.join(L) + '\n')
    ok = not missing and all(source_contract.load(u)['readiness']['ready'] for u in D['upstream'])
    track_event(scope, 'dp', 'D3', f"Input Lakehouses from source contracts: {', '.join(built) or 'none'}" + (f"; no contract yet: {', '.join(missing)}" if missing else ''),
                gate='sources_available', gate_ok=ok, evidence='3-build/build-notes/build-notes.md (section D3-table-mapping)')
    print(f"{scope}: {', '.join(built) or 'no input Lakehouse built'}" + (f" · waiting for source datasets: {', '.join(missing)}" if missing else ''))


if __name__ == '__main__':
    main()
