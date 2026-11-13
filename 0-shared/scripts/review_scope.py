"""Gap review of one migration (m-reviewer, gap review): is everything from DPV1 in DPV2, and will it deploy?

Usage (from the repository root):
  python -I 0-shared/scripts/review_scope.py --service sds --id GEOS
  python -I 0-shared/scripts/review_scope.py --service dp  --id GAIA

Reads the migration map (DPV1 side) and the project folder (DPV2 side) and checks:
  coverage        every DPV1 object in scope has a Fabric target, and the target exists once its stage has run
  name check      no DPV1 object matching the scope name is left out
  catalog         view [CATALOG].[<source>_catalog] exists with the DPV1 rows (source dataset)
  variable library  VL_MAIN complete, DEV / UAT / PRD, nothing that does not belong in it
  fabric items    .platform valid, names allowed in Fabric, logicalId present
  hardcoding      no GUID, ADLS path, mssparkutils or DPV1 environment if-chain in the built items
  lineage         every VL variable, pipeline and notebook referenced exists; sources and products connected
  service rules   no shortcut in a source dataset, input Lakehouse shortcuts in a data product, no cleansed zone
  deployment      T-SQL lint, database project provider, open DEV values
  tracking        stages and gates consistent with the outputs
Writes <project>/review/gap-review.md (for people) and gap-review.json (for the m-bug-fixer), overwritten by each review (history: change log and Git),
logs the result and sets the gate gap_review_passed (no ❌ finding).
"""
import argparse, datetime, glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, load_map, resolve_scope, write, track_event, project_dir, read_json, read_text, exists, walk_files, vl_name, one_sync_findings
from create_variable_library import catalog_view, cfg
from tsql_fabric_lint import lint_text
import track

OK, WARN, FAIL, TODO = '✅', '⚠️', '❌', '⚪'
MIGRATED = {'translate', 'rebuild', 'reuse', 'rewrite', 'merge', 'collapse', 'replace'}
ITEM_RX = re.compile(r'\b((?:PL|NB|LH|WH|VL|LH_INP_SDS)_[A-Z0-9_]+)\b')
STAGE_OF = {'1-SOURCE_TO_RAW': 'S2', '2-RAW_TO_DELTA': 'S3', '0-ORCHESTRATION': 'S4', 'ORCHESTRATION': 'D4'}
FORBIDDEN_VL = [(r'^ADLS_', 'DPV1 ADLS zone: OneLake is built into the Lakehouse'), (r'^DPV1_', 'DPV1 connection: not used in Fabric'),
                (r'_BATCH_COUNT$', 'tuning value: a pipeline parameter, not an environment value'),
                (r'(?:^|_)CATALOG_(?!VIEW_NAME$|WAREHOUSE_NAME$|WAREHOUSE_ID$|WAREHOUSE_SQL_ENDPOINT$|WAREHOUSE_WORKSPACE_ID$|WAREHOUSE_CONN_ID$|WATERMARK_TABLE_NAME$)', 'catalog details belong in the catalog view')]
GUID = re.compile(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', re.I)
SMELLS = [(r'abfss://|\.dfs\.core\.windows\.net|\.blob\.core\.windows\.net', 'ADLS path: use the Lakehouse path (OneLake) or a VL_MAIN variable'),
          (r'\bmssparkutils\b', 'mssparkutils: use notebookutils'), (r'(?:equals|contains|startswith)\(\s*(?:toLower\()?pipeline\(\)\.DataFactory', 'DPV1 environment if-chain: use VL_MAIN'),
          (r'(?i)password\s*=|AccountKey=|SharedAccessSignature', 'secret in code: use a Fabric connection'),
          (r'(?i)/cleansed/|cleansed_zone|(?<![A-Za-z_])CLEANSED\b', 'cleansed zone: Fabric has landing => raw => tables only')]  # a quoted DPV1 name (NTBK_..._TO_CLEANSED) is not a zone


class Review:
    def __init__(self):
        self.items = []

    def add(self, area, check, status, remark, fix='', file='', auto=False):
        self.items.append({'id': f'R{len(self.items) + 1:02d}', 'area': area, 'check': check, 'status': status, 'remark': remark, 'fix': fix, 'file': file, 'auto_fix': auto})


def built_items(pd):
    """displayName -> (type, folder) for every Fabric item under 3-build/ and 4-dacpac/."""
    out = {}
    for plat in list(walk_files(os.path.join(pd, '3-build'), names={'.platform'})) + list(walk_files(os.path.join(pd, '4-dacpac'), names={'.platform'})):
        try:
            meta = read_json(plat)['metadata']
            out[meta['displayName']] = (meta['type'], os.path.dirname(plat))
        except (ValueError, KeyError):
            out[os.path.basename(os.path.dirname(plat)).split('.')[0]] = ('?', os.path.dirname(plat))
    return out


def files(pd, exts, sub=('3-build', '4-dacpac')):
    return [p for s in sub for p in walk_files(os.path.join(pd, s), exts=exts)]


def rel(pd, p):
    return os.path.relpath(p, pd).replace('\\', '/')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--service', choices=['sds', 'dp'], required=True)
    ap.add_argument('--id', required=True)
    a = ap.parse_args()
    m = load_map()
    svc = a.service
    scope, _ = resolve_scope(m, svc, a.id)
    S = (m['sds'] if svc == 'sds' else m['dp'])[scope]
    pd = project_dir(svc, scope)
    if not os.path.isdir(pd):
        sys.exit(f'No deliverables for {scope}: run wf-1-framing first (frame_scope.py --service {svc} --id {scope}).')
    st = track.load(scope, svc) if exists(os.path.join(pd, '0_progress_tracking', 'progress.json')) else {'stages': {}, 'gates': {}}
    done = lambda sid: st['stages'].get(sid, {}).get('status') == 'completed'
    items = built_items(pd)
    R = Review()
    sp = cfg('shared-platform.json')
    src = S.get('folder', scope)
    view = catalog_view(sp, src) if svc == 'sds' else ''

    # VL_MAIN (needed by several checks)
    vl_dir = next(iter(glob.glob(os.path.join(pd, '3-build', 'fabric-deployment', '*', 'VL_MAIN.VariableLibrary'))), None)
    vl = {}
    if vl_dir:
        for v in read_json(os.path.join(vl_dir, 'variables.json'))['variables']:
            vl[v['name']] = v
    sql_text = {p: read_text(p, 'replace') for p in files(pd, ('.sql',))}
    view_file = next((p for p in sql_text if p.replace('\\', '/').endswith(f'/Views/{view}.sql')), None) if view else None

    # 1 coverage
    missing, waiting, covered = [], [], 0
    for r in S['rows']:
        if r['a'] not in MIGRATED:
            continue
        v2 = r['v2']
        if r['v1t'] == 'Source table':
            tbl = r['v1'].split('.')[-1]
            if not view_file:
                waiting.append((r, 'S1', 'catalog view not built'))
            elif re.search(rf"'{re.escape(tbl)}'", sql_text[view_file], re.I):
                covered += 1
            else:
                missing.append((r, 'S1', f'table {tbl} not in the catalog view'))
            continue
        if r['v2t'] == 'Connection':
            var = re.sub(r'^CONN_|_<ENV>$', '', v2.split(' (')[0]) + '_CONN_ID'
            (covered := covered + 1) if var in vl else (missing if vl_dir else waiting).append((r, 'S4' if svc == 'sds' else 'D4', f'VL_MAIN variable {var}'))
            continue
        if r['v2t'] == 'Catalog view':
            (covered := covered + 1) if view_file else waiting.append((r, 'S1', 'catalog view not built'))
            continue
        if r['v1t'] == 'Trigger':
            m_ = ITEM_RX.search(v2)
            (covered := covered + 1) if m_ and m_.group(1) in items else waiting.append((r, 'S4' if svc == 'sds' else 'D4', f'schedule on {m_.group(1) if m_ else v2}'))
            continue
        m_ = ITEM_RX.search(v2)
        if m_:
            name = m_.group(1)
            stage = next((sid for k, sid in STAGE_OF.items() if v2.startswith(k)), None)
            if name in items:
                covered += 1
            else:
                (missing if stage and done(stage) else waiting).append((r, stage or '-', f'item {name}'))
            continue
        obj = re.fullmatch(r'([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)', r['v1']) if r['v1t'].startswith('SQL') else re.search(r'([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)\s*$', v2)
        if obj and sql_text:
            hit = any(re.search(rf'CREATE\s+(?:OR\s+ALTER\s+)?\w+\s+\[?{obj.group(1)}\]?\.\[?{obj.group(2)}\]?\b', t, re.I) for t in sql_text.values())
            (covered := covered + 1) if hit else (missing if done('D3') else waiting).append((r, 'D2', f'SQL object {obj.group(0)}'))
        else:
            waiting.append((r, 'D2' if svc == 'dp' else '-', v2[:60]))
    total = covered + len(missing) + len(waiting)
    R.add('Coverage', f'DPV1 objects to migrate: {total}', OK if not missing and not waiting else FAIL if missing else TODO,
          f'{covered} built, {len(waiting)} waiting for their stage, {len(missing)} missing after their stage completed',
          'Build the missing items (see "Missing elements"), then re-run the review.' if missing or waiting else '')
    for r, stage, what in missing:
        R.add('Coverage', f"{r['v1t']} `{r['v1']}`", FAIL, f'Stage {stage} is completed but {what} is missing', f"Re-run stage {stage} for this object (target `{r['v2']}`).", auto=True)
    drops = [r for r in S['rows'] if r['a'] == 'drop']
    R.add('Coverage', f'Objects not migrated by rule: {len(drops)}', OK, ', '.join(sorted({r['v1t'] for r in drops})) + ' (ADLS linked services, datasets, Synapse pools, wrappers)' if drops else 'none')
    for r in S['rows']:
        if r['a'] == 'review':
            R.add('Coverage', f"{r['v1t']} `{r['v1']}`", WARN, f"Needs a manual decision: {r['n']}", 'Decide migrate or drop, record it in 1-framing/03-target-design-and-plan.md (Analyst notes) and in the change log.')

    # 2 name check
    miss = [c for c in S.get('candidates', []) if c['status'] == 'not included']
    R.add('Name check', f"Other DPV1 objects named like {scope}: {len(S.get('candidates', []))}", FAIL if miss else OK,
          f"{len(miss)} not included: {', '.join(c['name'] for c in miss[:8])}" if miss else 'all are in this scope or in another scope',
          'Confirm each one is out of scope (track.py log --type decision) or add it to the scope rules.' if miss else '')

    # 3 catalog (source dataset)
    if svc == 'sds':
        if not view_file:
            R.add('Catalog', f'View [CATALOG].[{view}]', FAIL if done('S1') else TODO, 'not generated', f'python -I 0-shared/scripts/create_catalog_view.py --id {scope}', auto=True)
        else:
            from common import work_path
            prof_p = work_path('sds', scope, 'catalog-profile.json')
            prof = read_json(prof_p) if exists(prof_p) else {}
            if prof.get('origin') == 'none':
                R.add('Catalog', f'Catalog rows for [CATALOG].[{view}]', FAIL, f'no catalog script for {scope}: not in the DPV1 export (the table list lives only in the metabase table CATALOG.{scope})',
                      f'Add 2-config/migration/catalog-scripts/{scope}.sql (CREATE TABLE [CATALOG].[{scope}] + one INSERT per table), then run create_catalog_view.py --id {scope}.', rel(pd, view_file))
            if prof.get('incremental'):
                wm_ok = any(p.replace('\\', '/').endswith(f"/Tables/{prof['watermark_table'].split('.')[-1]}.sql") for p in sql_text)
                R.add('Catalog', f"Watermark table {prof['watermark_table']}", OK if wm_ok else FAIL, 'incremental source: watermark per table in the warehouse' if wm_ok else 'missing',
                      '' if wm_ok else f'python -I 0-shared/scripts/create_catalog_view.py --id {scope}', '', not wm_ok)
            rows = len(re.findall(r"^\s*\(", sql_text[view_file].split('FROM (VALUES', 1)[-1], re.M)) if 'FROM (VALUES' in sql_text[view_file] else -1
            rows = prof.get('rows', rows) if prof else rows
            want = prof.get('expected_rows') if prof.get('origin') in ('dpv1', 'repo') else len(S['catalog'])
            if prof.get('origin') != 'none':
              R.add('Catalog', f'View [CATALOG].[{view}] rows = catalog script', OK if rows == want or rows == -1 else FAIL,
                  f'{rows} rows in the view, {want} in the script' if rows >= 0 else f"reads {sp['catalog_database']}", '' if rows in (want, -1) else f'Re-run create_catalog_view.py --id {scope} and compare with the catalog script.', rel(pd, view_file), rows != want)
            stale = [p for p in sql_text if '/Views/' in p.replace('\\', '/') and not p.replace('\\', '/').endswith(f'/{view}.sql')]
            if stale:
                R.add('Catalog', 'Old catalog view files', FAIL, ', '.join(os.path.basename(p) for p in stale), 'Delete the old view files: only <source>_catalog is deployed.', rel(pd, stale[0]), True)

    # 4 variable library
    if not vl_dir:
        R.add('Variable library', 'VL_MAIN generated', FAIL if done('S4' if svc == 'sds' else 'D4') else TODO, 'not generated yet',
              f'python -I 0-shared/scripts/create_variable_library.py --service {svc} --id {scope}', auto=True)
    else:
        f = rel(pd, vl_dir)
        sets = {os.path.basename(p)[:-5]: read_json(p) for p in glob.glob(os.path.join(vl_dir, 'valueSets', '*.json'))}
        R.add('Variable library', 'Value sets DEV, UAT, PRD', OK if set(sets) >= {'DEV', 'UAT', 'PRD'} else FAIL, ', '.join(sorted(sets)), '' if set(sets) >= {'DEV', 'UAT', 'PRD'} else 'Re-generate VL_MAIN.', f, True)
        bad_sets = [e for e, j in sets.items() if {o['name'] for o in j['variableOverrides']} != set(vl)]
        R.add('Variable library', 'Every value set overrides every variable', FAIL if bad_sets else OK, f"mismatch in {', '.join(bad_sets)}" if bad_sets else f'{len(vl)} variables in each set',
              'Re-generate VL_MAIN.' if bad_sets else '', f, bool(bad_sets))
        forb = [(n, why) for n in vl for rx, why in FORBIDDEN_VL if re.search(rx, n)]
        own = [n for n in vl if scope.upper() in n.upper().split('_')]
        other = len(vl) - len(own)
        R.add('Variable library', 'Only locating values (no ADLS, DPV1, batch size or catalog details)', FAIL if forb else OK,
              '; '.join(f'{n}: {why}' for n, why in forb) if forb else f"{', '.join(own)} (+ {other} variables of other sources or shared, kept from the shared VL_MAIN and not checked here)",
              'Remove these variables and re-generate VL_MAIN.' if forb else '', f, bool(forb))
        badtype = [n for n, v in vl.items() if v.get('type') not in ('String', 'Boolean', 'Integer', 'Number', 'DateTime', 'Guid', 'ItemReference')]
        if badtype:
            R.add('Variable library', 'Variable types', FAIL, ', '.join(badtype), 'Use String, Boolean or Integer.', f, True)
        todo = [n for n, v in vl.items() if v.get('value') == '<to set>' and (scope.upper() in n.upper().split('_') or n.startswith('COMMON_'))]
        R.add('Deployment', 'VL_MAIN DEV values set', WARN if todo else OK, f"{len(todo)} still `<to set>`: {', '.join(todo)}" if todo else 'all set',
              'Fill the IDs once the items and connections exist in DEV (environment-values.json), then re-generate.' if todo else '', f)
        vn = vl_name(S['folder'], 'CATALOG_VIEW_NAME') if svc == 'sds' else ''
        if svc == 'sds' and vn in vl and vl[vn]['value'] != f"{sp['catalog_schema']}.{view}":
            R.add('Variable library', f'{vn} matches the view', FAIL, f"{vl[vn]['value']} vs {sp['catalog_schema']}.{view}", 'Re-generate VL_MAIN.', f, True)

    # 5 fabric items
    bad = []
    for name, (typ, folder) in items.items():
        try:
            j = read_json(os.path.join(folder, '.platform'))
            if not j.get('config', {}).get('logicalId'):
                bad.append((name, 'no logicalId'))
        except ValueError:
            bad.append((name, '.platform is not valid JSON'))
        if not re.fullmatch(r'[A-Za-z0-9_]+', name):
            bad.append((name, 'name has characters not allowed (A-Z, 0-9, _)'))
        if not os.path.basename(folder).startswith(name + '.'):
            bad.append((name, f'folder {os.path.basename(folder)} does not match displayName'))
    R.add('Fabric items', f'{len(items)} items in Fabric Git format', FAIL if bad else OK if items else TODO,
          '; '.join(f'{n}: {w}' for n, w in bad) if bad else ', '.join(sorted(items)) or 'none built yet', 'Fix the .platform files or folder names.' if bad else '', '', bool(bad))

    # 6 hardcoding
    vl_values = {str(v) for j in [read_json(p) for p in glob.glob(os.path.join(vl_dir or '-', 'valueSets', '*.json'))] for v in [o['value'] for o in j['variableOverrides']]}
    code = files(pd, ('.json', '.py', '.sql', '.ipynb'))
    # same-workspace references use the item's logicalId (KI-030), the zero GUID stands for "this workspace"
    by_id = {read_json(os.path.join(f, '.platform')).get('config', {}).get('logicalId'): n for n, (_, f) in items.items()}
    allowed = set(by_id) | {'00000000-0000-0000-0000-000000000000'}
    hits = []
    for p in code:
        if '.VariableLibrary' in p or p.endswith('.platform') or os.path.basename(p).endswith(('review.json',)):
            continue
        t = read_text(p, 'replace')
        for g in set(GUID.findall(t)) - vl_values - allowed:
            hits.append((p, f'GUID {g}', 'Replace with @pipeline().libraryVariables.<NAME>, vl.<NAME> or a __VL_MAIN.<NAME>__ deploy token'))
        code_only = '\n'.join(l for l in t.splitlines() if not l.lstrip().startswith(('#', '--')))
        for rx, why in SMELLS:
            if re.search(rx, code_only if 'cleansed' in why else t):
                hits.append((p, why, why.split(': ', 1)[-1]))
    R.add('Hardcoding', f'{len(code)} built files scanned', FAIL if hits else OK if code else TODO, f'{len(hits)} findings' if hits else 'no GUID, ADLS path, secret or if-chain' if code else 'nothing built yet')
    for p, what, fix in hits[:30]:
        R.add('Hardcoding', what, FAIL, 'found in built item', fix, rel(pd, p), True)

    # 7 lineage
    refs = set()
    for p in code:
        t = read_text(p, 'replace')
        refs |= set(re.findall(r'libraryVariables\.([A-Za-z0-9_]+)', t)) | set(re.findall(r'\bvl\.([A-Z][A-Za-z0-9_]+)', t)) | set(re.findall(r'__VL_MAIN\.([A-Z0-9_]+)__', t))
        if '__VL_MAIN.' in t and vl_dir and not exists(os.path.join(os.path.dirname(vl_dir), 'parameter.yml')):
            R.add('Lineage', 'Deploy tokens resolved by parameter.yml', FAIL, 'item uses __VL_MAIN.<NAME>__ tokens but parameter.yml is missing',
                  f'python -I 0-shared/scripts/create_variable_library.py --service {svc} --id {scope}', rel(pd, p), True)
    unknown = sorted(r for r in refs if vl_dir and r not in vl)
    if refs:
        R.add('Lineage', f'{len(refs)} VL_MAIN variables referenced by pipelines / notebooks', FAIL if unknown else OK,
              f"not in VL_MAIN: {', '.join(unknown)}" if unknown else 'all exist', 'Add the variables to create_variable_library.py or fix the reference.' if unknown else '', '', bool(unknown))
    # Fabric resolves @pipeline().libraryVariables.X against the pipeline's own libraryVariables block, not VL_MAIN directly:
    # X must be declared there, under the VL_MAIN name ("Parameter X was not found under PL_..." otherwise).
    undeclared = []
    for p in code:
        if p.endswith('pipeline-content.json'):
            try:
                decl = (json.loads(read_text(p, 'replace').lstrip('﻿')).get('properties') or {}).get('libraryVariables') or {}
            except ValueError:
                continue
            used = set(re.findall(r'libraryVariables\.([A-Za-z0-9_]+)', read_text(p, 'replace')))
            name = os.path.basename(os.path.dirname(p)).split('.')[0]
            undeclared += [f'{name}: {u} not declared' for u in sorted(used - set(decl))]
            undeclared += [f'{name}: {k} declared as {d.get("variableName")}' for k, d in sorted(decl.items()) if d.get('variableName') != k]
            undeclared += [f'{name}: {k} not in VL_MAIN' for k in sorted(decl) if vl_dir and k not in vl]
    if any(p.endswith('pipeline-content.json') for p in code):
        R.add('Lineage', 'Every library variable used is declared in its pipeline under its VL_MAIN name', FAIL if undeclared else OK,
              '; '.join(undeclared[:6]) + (f' (+{len(undeclared) - 6})' if len(undeclared) > 6 else '') if undeclared else 'expressions, declarations and VL_MAIN agree',
              'Regenerate the pipelines (build_source_dataset.py), which declare each variable under the name the expressions use.' if undeclared else '', '', bool(undeclared))
    called = set()
    for p in code:
        if p.endswith('pipeline-content.json'):
            t = read_text(p, 'replace')
            called |= set(re.findall(r'"(?:referenceName|pipelineName|notebookName)"\s*:\s*"((?:PL|NB)_[A-Z0-9_]+)"', t))
            called |= {by_id.get(ref, f'unknown logicalId {ref}') for ref in re.findall(r'"(?:referenceName|notebookId)"\s*:\s*"([0-9a-f-]{36})"', t) if ref != '00000000-0000-0000-0000-000000000000'}
    broken = sorted(c for c in called if c not in items)
    if called:
        R.add('Lineage', f'{len(called)} pipelines / notebooks called', FAIL if broken else OK, f"called but not built: {', '.join(broken)}" if broken else 'all built',
              'Build the called items or fix the activity reference.' if broken else '', '', False)
    import source_contract
    if svc == 'sds':
        cons = S.get('consumers', [])
        R.add('Lineage', 'Data products that read this source (DPV1)', OK if S['downstream'] else WARN,
              ('; '.join(f"{x['dp']} ({len(x['evidence'])} DPV1 objects)" for x in cons) or ', '.join(S['downstream'])) + f'. They will read it through LH_INP_SDS_{src}; nothing of a data product is built here.'
              if S['downstream'] else 'no consumer found in DPV1', '' if S['downstream'] else 'Confirm the source is still used before migrating it.')
        if done('S4'):
            c = source_contract.publish(scope)
            R.add('Lineage', 'Source dataset contract for data products', OK if c['readiness']['ready'] else WARN,
                  f"{len(c['tables'])} tables with their DPV1 access paths; consumers: {', '.join(x['data_product'] for x in c['consumers']) or 'none'}",
                  '' if c['readiness']['ready'] else 'Not ready for data products: ' + '; '.join(c['readiness'].get('blockers', ['S1-S4 not completed'])), '3-build/build-notes/build-notes.md (hand-over)')
        else:
            R.add('Lineage', 'Source dataset contract for data products', TODO, 'published at the end of S4', 'Run build_source_dataset.py --stage S4 (or source_contract.py publish).')
    else:
        _, inputs = source_contract.show(scope)
        for o in inputs:
            u = o['source']
            if not o['contract']:
                R.add('Lineage', f'Input source dataset {u}', WARN, 'no source dataset contract yet: the input Lakehouse would point to nothing',
                      f'Run Source Dataset Migration for {u} (wf-1 + wf-2) first.')
            else:
                R.add('Lineage', f'Input source dataset {u}', OK if o['ready'] else WARN,
                      f"contract {'ready' if o['ready'] else 'published, source not finished'}: {len(o['tables_used'])}/{o['tables_total']} tables used by the DPV1 code",
                      '' if o['ready'] else f'Finish S1-S4 of {u}.')

    # 7b one-sync deployment: no item id written in a pipeline (Git sync cannot resolve deploy tokens or ids of other items)
    pls = list(walk_files(os.path.join(pd, '3-build'), names={'pipeline-content.json'}))
    bad = []
    for p in pls:
        bad += [(p, w) for w in one_sync_findings(read_text(p, 'replace'))]
    if pls:
        R.add('Deployment', 'Pipelines deploy in one Git sync (no item ids or deploy tokens in the files)', FAIL if bad else OK,
              f'{len(bad)} findings: ' + '; '.join(f'{os.path.basename(os.path.dirname(p))}: {w}' for p, w in bad[:3]) if bad else f'{len(pls)} pipelines: connections resolved at run time from VL_MAIN',
              'Regenerate the pipelines (build_source_dataset.py), then publish again (deploy_publish.py).' if bad else '', rel(pd, bad[0][0]) if bad else '', bool(bad))

    # 7c key reference questions (framing): a data product needs them answered, a source dataset is warned
    import reference_questions
    left = reference_questions.open_required(svc, scope)
    if left is not None:
        R.add('Framing', 'Key reference questions answered', (FAIL if svc == 'dp' else WARN) if left else OK,
              f"{len(left)} required open: {', '.join(left)}" if left else 'every required question has an answer (1-framing/04-key-reference-questions.md)',
              f'python -I 0-shared/scripts/reference_questions.py show --service {svc} --id {scope}, then answer them with the developer.' if left else '', '1-framing/04-key-reference-questions.md' if left else '')

    # 8 service rules
    shortcuts = list(walk_files(os.path.join(pd, '3-build'), names={'shortcuts.metadata.json'}))
    if svc == 'sds':
        R.add('Service rules', 'No shortcut in a source dataset', FAIL if shortcuts else OK, ', '.join(rel(pd, s) for s in shortcuts) if shortcuts else 'data is ingested from the source',
              'Delete the shortcut definitions: the source dataset ingests directly from the source.' if shortcuts else '', rel(pd, shortcuts[0]) if shortcuts else '', bool(shortcuts))
        R.add('Service rules', 'ADLS linked services and datasets not migrated', OK, 'dropped by rule: OneLake is built into the Lakehouse; datasets do not exist in Fabric')
        # ingestion method (ingestion-design.md): notebook only where DPV1 had one, one write per table, no notebook per table
        import ingestion
        _, conn_type, method, _, _ = ingestion.source_kind(S, m['objects'])
        # DPV1 per-table queries (Switch on the table name): every one must reach the Fabric Lookup, or the table silently runs SELECT *
        sw = ingestion.dpv1_switch_queries(S, pd) if method == 'structured' else {}
        if sw:
            s2 = next((p for p in walk_files(os.path.join(pd, '3-build'), names={'pipeline-content.json'}) if '_SOURCE_TO_RAW.DataPipeline' in p), None)
            lkp = ''
            if s2:
                acts = read_json(s2)['properties']['activities']
                lkp = next((a['typeProperties']['source']['sqlReaderQuery']['value'] for a in acts if a['name'] == ingestion.LKP), '')
            qp = ingestion.queries_path(S['folder'])
            over = read_json(qp).get('overrides', {}) if exists(qp) else {}
            on, used = sw['on'], {**sw['queries'], **over}
            lost = [t for t, q in used.items() if f"WHEN c.[{on}] = '{t}'" not in lkp or ingestion.query_expr(q) not in lkp]
            manual = [t for t in sw['manual'] if t not in over]
            bad = lost + manual
            R.add('Ingestion', 'DPV1 per-table queries carried into the catalog Lookup', (FAIL if bad else OK) if s2 else TODO,
                  (f"{len(bad)} of {len(used) + len(manual)} tables would run SELECT *: " + ', '.join(bad[:6]) if bad else
                   f"{len(used)} queries from `{sw['pipeline']}` ({sw['switch']} on {on}) in ExtractQuery") if s2 else 'S2 not built yet',
                  ('Write the dynamic ones in "overrides" of 2-config/migration/extract-queries/' + S['folder'].upper() + '.json, then rebuild S2.' if manual
                   else 'Rebuild S2 (build_source_dataset.py --stage S2).') if bad else '', rel(pd, s2) if bad and s2 else '', bool(lost) and not manual)
            prof_p = os.path.join(pd, '3-build', '_work', 'catalog-profile.json')
            if exists(prof_p) and read_json(prof_p).get('incremental'):
                ordered = [t for t, q in used.items() if re.search(r'(?i)\border\s+by\b', q)]
                R.add('Ingestion', 'Per-table queries work for incremental rows', WARN,
                      'incremental rows run SELECT * FROM (<query>) q WHERE <watermark> > <since>: each query must return its watermark column'
                      + (f"; ORDER BY not allowed in a derived table: {', '.join(ordered)}" if ordered else ''),
                      'Check the watermark column is in the select list of each query (catalog WatermarkColumn).')
        prof_p = os.path.join(pd, '3-build', '_work', 'catalog-profile.json')
        if conn_type == 'RestService' and exists(prof_p) and read_json(prof_p).get('incremental'):  # the watermark must be inside the API request, or every run re-reads everything
            s2p = next((p for p in walk_files(os.path.join(pd, '3-build'), names={'pipeline-content.json'}) if '_SOURCE_TO_RAW.DataPipeline' in p), None)
            used = bool(s2p) and any('WatermarkNow' in part[:600] for part in read_text(s2p, 'replace').split('"relativeUrl"')[1:])  # any request (a Web activity for a list comes first)
            rp = ingestion.requests_path(S['folder'])
            rj = read_json(rp) if exists(rp) else {}
            why = '' if used else (rj.get('manual') or 'the request does not use the live watermark')
            R.add('Ingestion', 'Incremental REST: the request carries the watermark', (OK if used else FAIL) if s2p else TODO,
                  'relativeUrl uses item().WatermarkNow (DPV1 request: ' + str(rj.get('pipeline', '')) + ')' if used else (why if s2p else 'S2 not built yet'),
                  '' if used else 'Write the request in "override" of 2-config/migration/request-urls/' + S['folder'].upper() + '.json (item().WatermarkNow is the live watermark), then rebuild S2.',
                  rel(pd, s2p) if (s2p and not used) else '')
        nbs = [p for p in walk_files(os.path.join(pd, '3-build'), names={'notebook-content.py'}) if '_LIST_ITEMS.Notebook' not in p]  # the list notebook only reads a landed list (build_list_notebook)
        flat = [p for p in nbs if '_FLATTEN.Notebook' in p]
        if nbs or S['notebooks']:
            ok = bool(S['notebooks']) and len(nbs) - len(flat) <= 1
            R.add('Ingestion', 'Notebook only where DPV1 had one, one loader per source', OK if ok else FAIL,
                  f"{len(nbs)} notebook(s) ({len(flat)} FLATTEN); DPV1 had {len(S['notebooks'])}", '' if ok else 'Remove the extra notebook: use the Copy raw => table path (skill-raw-to-lakehouse).',
                  rel(pd, nbs[0]) if nbs else '')
            mixed = bool(ingestion.file_inputs(S['folder']).get('tables')) and method == 'structured'  # database plus files in one source
            semi = method != 'structured' or mixed
            ok = (len(flat) == 1) == semi
            R.add('Ingestion', 'NB_<SRC>_FLATTEN only for semi-structured sources', OK if ok else FAIL,
                  f"{method}{' + files' if mixed else ''}: {len(flat)} FLATTEN notebook(s)", '' if ok else 'Regenerate S3 (build_source_dataset.py --stage S3).', rel(pd, flat[0]) if flat else '', not ok)
        fi = ingestion.file_inputs(S['folder']) if method == 'structured' else {}
        if fi.get('tables'):  # database plus files: every file is a catalog row of its own Lookup, copied, flattened, and in the contract
            s2f = next((p for p in walk_files(os.path.join(pd, '3-build'), names={'pipeline-content.json'}) if '_SOURCE_TO_RAW.DataPipeline' in p), None)
            tx = read_text(s2f, 'replace') if s2f else ''
            have = bool(s2f) and 'GET FILES FROM CATALOG VIEW' in tx and "ConnectionKey = 'files'" in tx and fi['conn_var'] in tx if fi.get('conn_var') else bool(s2f) and 'GET FILES FROM CATALOG VIEW' in tx
            conf = [t['name'] for t in fi['tables'] if t.get('confirm')]
            R.add('Ingestion', 'Files ingested next to the database (second input group)', (OK if have else FAIL) if s2f else TODO,
                  (f"{len(fi['tables'])} file tables: own Lookup, Copy and FLATTEN; connection {fi['connection']}" + (f"; {len(conf)} inferred from the product code, confirm file or sheet (Q13)" if conf else '')) if have else ('S2 not built yet' if not s2f else 'the S2 pipeline has no files branch'),
                  '' if have else 'Regenerate S2 (build_source_dataset.py --stage S2).', rel(pd, s2f) if (s2f and not have) else '', bool(s2f) and not have)
        loaders = [p for p in nbs if p not in flat]
        bad = [p for p in loaders if re.search(r'catalog_json|Files/\{landing_root\}', read_text(p, 'replace'))]
        if loaders:
            R.add('Ingestion', 'Loader reads only the tables that copied, from Files/raw', FAIL if bad else OK,
                  'reads the catalog or Files/landing' if bad else 'tables_json from LoadedTables, raw parquet only',
                  'Regenerate S3 (build_source_dataset.py --stage S3).' if bad else '', rel(pd, bad[0]) if bad else '', bool(bad))
        pls_txt = {p: read_text(p, 'replace') for p in walk_files(os.path.join(pd, '3-build'), names={'pipeline-content.json'})}
        s2t = next((t for p, t in pls_txt.items() if 'SOURCE_TO_RAW' in p), '')
        s3t = next((t for p, t in pls_txt.items() if 'RAW_TO_DELTA' in p), '')
        mt = next((t for p, t in pls_txt.items() if 'MASTER_ORCHESTRATOR' in p), '')
        if s2t:
            ok = 'Add to loaded tables' in s2t and 'Add to failed tables' in s2t and 'pipelineReturnValue' in s2t
            R.add('Ingestion', 'S2 lists copied and failed tables and returns them', OK if ok else FAIL, 'LoadedTables / FailedTables returned' if ok else 'success / failure lists missing',
                  '' if ok else 'Regenerate S2 (build_source_dataset.py --stage S2).', '', not ok)
        if s3t:
            ok = 'GET TABLES FROM CATALOG VIEW' not in s3t and 'LoadedTables' in s3t and 'pipelineReturnValue' in s3t
            R.add('Ingestion', 'S3 loads only LoadedTables (no catalog Lookup) and returns loaded / failed', OK if ok else FAIL,
                  'parameter LoadedTables, return value set' if ok else 'S3 still reads the catalog', '' if ok else 'Regenerate S3 (build_source_dataset.py --stage S3).', '', not ok)
        if mt:
            ok = 'Fail with failed tables' in mt and "pipelineReturnValue.LoadedTables" in mt
            wm_ok = 'Update watermarks' not in mt or 'OPENJSON' in mt
            R.add('Ingestion', 'Master passes LoadedTables and fails with the failed tables', OK if ok else FAIL, 'final Fail lists every failed table' if ok else 'missing',
                  '' if ok else 'Regenerate S4 (build_source_dataset.py --stage S4).', '', not ok)
            R.add('Ingestion', 'Watermark updated only for the tables loaded in this run', OK if wm_ok else FAIL, 'loaded list only' if wm_ok else 'all active incremental tables',
                  '' if wm_ok else 'Regenerate S4 (build_source_dataset.py --stage S4).', '', not wm_ok)
        per_table = [p for p in nbs if re.search(r'notebook(utils)?\.run\(|mssparkutils\.notebook\.run', read_text(p, 'replace'))]
        if nbs:
            R.add('Ingestion', 'No notebook started per table', FAIL if per_table else OK, 'notebook.run found' if per_table else 'all tables in one session',
                  'Load the tables in the thread pool of the one notebook.' if per_table else '', rel(pd, per_table[0]) if per_table else '')
        s2 = [p for p in walk_files(os.path.join(pd, '3-build'), names={'pipeline-content.json'}) if 'SOURCE_TO_RAW' in p]
        if s2 and method == 'structured':
            twice = 'LandingRoot' in read_text(s2[0], 'replace') and not ingestion.file_inputs(S['folder']).get('tables')  # a mixed source lands its files, not the database tables
            R.add('Ingestion', 'Database extract written once (straight to Files/raw)', FAIL if twice else OK,
                  'the pipeline writes to Files/landing too' if twice else 'one parquet write per table',
                  'Regenerate S2 (build_source_dataset.py --stage S2).' if twice else '', rel(pd, s2[0]), twice)
        loop = ingestion.dpv1_rest_loop(S, pd) if s2 and method != 'structured' else {}  # DPV1 calls some APIs once per item of a list: a single call per API gets a 404
        if loop:
            child = any('_SOURCE_TO_RAW_CHILD_API.DataPipeline' in p for p in walk_files(os.path.join(pd, '3-build'), names={'pipeline-content.json'}))
            R.add('Ingestion', 'APIs called once per item of a list (DPV1 child pipeline) run once per item', OK if child else FAIL,
                  f"child pipeline built for the rows with a {loop['param_column']}" if child else f"DPV1 {loop['parent']} runs {loop['child']} per {loop['item_key']}: the build calls each API once",
                  '' if child else 'Regenerate S2 (build_source_dataset.py --stage S2); if it says what could not be derived, fill rest-loops/<SRC>.json "override".',
                  rel(pd, s2[0]) if not child else '', not child)
    else:
        inp = [n for n in items if n.startswith('LH_INP_SDS_')]
        need = [f"LH_INP_SDS_{u.replace('-', '_')}" for u in S['upstream']]
        lack = [n for n in need if n not in inp]
        R.add('Service rules', 'Input Lakehouse with shortcuts per source', OK if not lack else FAIL if done('D3') else TODO,
              f"missing: {', '.join(lack)}" if lack else ', '.join(need) or 'no input source', 'Generate the input Lakehouses and their shortcuts.metadata.json (wf-3 D3).' if lack else '')

    # 8b data product: the DPV1 serverless modeling and loaders are carried over, the transport is gone
    if svc == 'dp':
        dbp = os.path.join(pd, '3-build', 'fabric-deployment', 'database-projects')
        sqls = list(walk_files(dbp, exts=('.sql',))) if exists(dbp) else []
        emb = os.path.join(pd, '2-legacy-code', 'embedded-sql')
        want = len([f for f in os.listdir(emb) if re.match(r'(?i)(ldw|out\w*)\.', f)]) if exists(emb) else 0
        views = [p for p in sqls if re.search(r'(?i)^\s*CREATE\s+(?:OR\s+ALTER\s+)?VIEW\s+\[?(?:ldw|out\w*)\]?\.', re.sub(r'(?m)^--.*$', '', read_text(p, 'replace')))]
        if want or sqls:
            R.add('Modeling', 'DPV1 LDW and OUT objects carried over as views', (OK if len(views) >= want else FAIL) if sqls else TODO,
                  f'{len(views)} views in the database project for {want} DPV1 LDW / OUT objects' if sqls else 'D2/D3 not built yet',
                  'Run convert_serverless_sql.py, then dacpac_retarget.py (D2, K2).' if len(views) < want else '', rel(pd, dbp) if sqls and len(views) < want else '', bool(sqls) and len(views) < want)
        if sqls:
            left = [p for p in sqls if re.search(r'(?is)(?<![A-Za-z0-9_])STG_\w+\]?\.\[?\w|(?<![A-Za-z0-9_])spot_\w+\.dbo\b|\bOPENROWSET\b|\bCREATE\s+EXTERNAL\s+TABLE\b', re.sub(r'(?m)^--.*$', '', read_text(p, 'replace')))]
            R.add('Modeling', 'No DPV1 transport left (STG, INP views, SPOT, external tables)', FAIL if left else OK,
                  f'{len(left)} file(s) still read STG / INP / SPOT or an external table: {", ".join(os.path.basename(p) for p in left[:3])}' if left else f'{len(sqls)} SQL files read LH_INP_SDS tables or the Warehouse only',
                  'Run convert_serverless_sql.py again (a read with no source dataset table stops it and lists the names).' if left else '', rel(pd, left[0]) if left else '', bool(left))

    # 8c deployability: what Fabric refuses at import or deployment, known at build time (deploy_gate.py)
    import deploy_gate
    bd = os.path.join(pd, '3-build', 'fabric-deployment')
    if exists(bd):
        sc_vars = deploy_gate.shortcut_variables(bd)
        if sc_vars:  # a shortcut target needs real ids when the workspace is synced
            unres = deploy_gate.unresolved_imports(bd, 'DEV')
            R.add('Deployment', 'Import-time ids of the shortcuts are real GUIDs in DEV', FAIL if unres else OK,
                  ('not deployable: ' + '; '.join(f'{v} = {x}' for v, x, _ in unres[:4]) + ' (Fabric: "target workspace ID or artifact ID is not a valid GUID")') if unres else
                  f'{len(sc_vars)} VL_MAIN variables used by shortcuts hold real ids',
                  'python -I 0-shared/scripts/resolve_upstream.py --id ' + scope + ' (Fabric, or the source VL_MAIN of the deployment repo), or give --source <SRC> --workspace-id <GUID> --lakehouse-id <GUID>; then create_variable_library.py' if unres else '',
                  rel(pd, bd) if unres else '', False)
        if svc == 'dp' and deploy_gate.database_projects(bd):
            cl = deploy_gate.closure(bd)
            closed = [m for k in deploy_gate.CLOSURE_FAILS for m in cl.get(k, [])]
            R.add('Deployment', 'Database project closure (schemas, references, pipeline procedures)', FAIL if closed else OK,
                  '; '.join(closed[:3]) if closed else 'every schema, object and procedure a pipeline calls is created in the project',
                  'Fix the T-SQL (convert_serverless_sql.py, d2_assemble_flat.py) so the project references only what it creates.' if closed else '', rel(pd, bd) if closed else '', False)
            ci = deploy_gate.cicd(bd)
            R.add('Deployment', 'Promotable to UAT and PRD: environment-agnostic folder, Lakehouse as SQLCMD variable with EXT-LH project, DACPAC pipeline, one profile per environment', FAIL if ci['fail'] else OK,
                  '; '.join(ci['fail'][:3]) if ci['fail'] else 'same folder and DACPAC for every environment' + (f"; to fill per environment: {len(ci['warn'])} value(s)" if ci['warn'] else ''),
                  f'Run dacpac_retarget.py, then build_cicd.py --id {scope}.' if ci['fail'] else '', rel(pd, bd) if ci['fail'] else '', False)
            R.add('Modeling', 'Lakehouse read only in the 1-input views',FAIL if cl.get('input_layer') else OK,
                  '; '.join(cl['input_layer'][:2]) if cl.get('input_layer') else 'LH_INP_SDS_<SRC> is read in [INP_<SRC>] views only: one place to re-point',
                  'Run build_input_layer (convert_serverless_sql.py / d2_assemble_flat.py), then dacpac_retarget.py.' if cl.get('input_layer') else '', rel(pd, bd) if cl.get('input_layer') else '', False)

    # 9 deployment
    lint_block = []
    for p, t in sql_text.items():
        for ln, rid, sev, fix, line in lint_text(t):
            if sev == 'block':
                lint_block.append((p, ln, rid, fix))
    if sql_text:
        R.add('Deployment', f'T-SQL lint on {len(sql_text)} files', FAIL if lint_block else OK, f'{len(lint_block)} blocking findings' if lint_block else '0 blocking findings',
              'Fix in T-SQL (wf-4 K3), then re-run tsql_fabric_lint.py.' if lint_block else '')
        for p, ln, rid, fix in lint_block[:20]:
            R.add('Deployment', f'{rid} line {ln}', FAIL, fix, fix, rel(pd, p), True)
    for proj in walk_files(pd, exts=('.sqlproj',)):
        ok = 'SqlDwUnifiedDatabaseSchemaProvider' in read_text(proj)
        R.add('Deployment', f'{os.path.basename(proj)} targets Fabric Warehouse', OK if ok else FAIL, 'DSP SqlDwUnifiedDatabaseSchemaProvider' if ok else 'wrong DSP',
              '' if ok else 'Set <DSP>Microsoft.Data.Tools.Schema.Sql.SqlDwUnifiedDatabaseSchemaProvider</DSP>.', rel(pd, proj), not ok)

    # 10 tracking
    incons = [sid for sid, s in st['stages'].items() if s.get('status') == 'completed' and any(x['status'] == FAIL and x['area'] == 'Coverage' and f'Stage {sid}' in x['remark'] for x in R.items)]
    if incons:
        R.add('Tracking', 'Completed stages with missing outputs', FAIL, ', '.join(incons), 'Set these stages back to in_progress (track.py set) until the outputs exist.', '', True)
    if st['stages'].get('F2', {}).get('status') != 'completed':
        R.add('Tracking', 'Framing F2 completed', WARN, 'F2 is not completed yet', 'Resolve the name check and the review rows, then mark F2 completed.')
    if st.get('gates', {}).get('framing_approved', {}).get('status') != 'completed':
        R.add('Tracking', 'Gate framing_approved', WARN, 'not approved yet', 'Ask the owner to approve the framing (track.py gate --gate framing_approved).')

    # 11 framing inputs and the deployment repo
    import project_inputs, deploy_publish
    gap = project_inputs.missing(svc, scope)
    R.add('Deployment', 'Framing inputs (workspace, deployment repo path)', OK if not gap else FAIL,
          'saved in 0_progress_tracking/progress.json' if not gap else f"missing: {', '.join(gap)}",
          '' if not gap else f'Ask the developer and run project_inputs.py set --service {svc} --id {scope} --workspace <NAME> --deployment-repo <PATH>.', '', False)
    if not gap:
        try:
            _, _, repo, rows = deploy_publish.plan(svc, scope)
            diff = [r for r, x in rows if x != 'same']
            R.add('Deployment', 'Deployment repo holds the build', OK if not diff else WARN,
                  f'{len(rows)} files identical in {repo}' if not diff else f'{len(diff)} of {len(rows)} files new, changed or in conflict',
                  '' if not diff else f'python -I 0-shared/scripts/deploy_publish.py publish --service {svc} --id {scope}')
        except SystemExit as e:
            R.add('Deployment', 'Deployment repo holds the build', WARN, str(e)[:160], 'Check the deployment repo path.')

    # write
    fails, warns, todos = (sum(1 for x in R.items if x['status'] == s) for s in (FAIL, WARN, TODO))
    goods = [x for x in R.items if x['status'] == OK]
    verdict = f'{FAIL} not ready' if fails else f'{WARN} ready with warnings' if warns else f'{TODO} build not finished' if todos else f'{OK} ready'
    day = f'{datetime.date.today():%Y-%m-%d}'
    out = project_dir(svc, scope, 'review')
    tbl = lambda rows: ['| ID | Area | Check | Status | Remark | Fix | File |', '| --- | --- | --- | --- | --- | --- | --- |'] + \
        [f"| {x['id']} | {x['area']} | {x['check']} | {x['status']} | {x['remark'].replace('|', '/')} | {x['fix'].replace('|', '/')} | {('`' + x['file'] + '`') if x['file'] else ''} |" for x in rows]
    L = [f"# Gap Review: {scope} ({track.SVC_LABEL[svc]})", '', f'Last update: {day}', '',
         f'- **Verdict**: {verdict}', f'- **Findings**: {len(R.items)} checks · {OK} {len(goods)} good · {WARN} {warns} warnings · {FAIL} {fails} failures · {TODO} {todos} waiting for a stage',
         f'- **Coverage**: {covered} / {total} DPV1 objects built' if total else '- **Coverage**: nothing to migrate', '',
         'Status: ✅ good · ⚠️ warning (does not block) · ❌ failure (blocks deployment, the m-bug-fixer acts on it) · ⚪ waiting for its stage', '',
         '## What has been validated', ''] + tbl(R.items) + ['', '## What is good', ''] + ([f"- ✅ {x['check']}: {x['remark']}" for x in goods] or ['- Nothing yet']) + \
        ['', '## What is not good', ''] + ([f"- {x['status']} **{x['check']}**: {x['remark']}" for x in R.items if x['status'] in (FAIL, WARN)] or ['- Nothing']) + \
        ['', '## Missing elements', ''] + ([f"- {FAIL} {r['v1t']} `{r['v1']}` => `{r['v2']}` ({what}, stage {stage})" for r, stage, what in missing] +
                                         [f"- {TODO} {r['v1t']} `{r['v1']}` => `{r['v2']}` (stage {stage})" for r, stage, what in waiting] or ['- None']) + \
        ['', '## How to fix', ''] + ([f"- **{x['id']}** {x['check']}: {x['fix']}" + (' _(m-bug-fixer can apply it)_' if x['auto_fix'] else '') for x in R.items if x['fix'] and x['status'] in (FAIL, WARN)] or ['- Nothing to fix']) + \
        ['', 'Next: run the **m-bug-fixer** on this review, then run the gap review again.', '']
    for old in glob.glob(os.path.join(out, '????-??-??-review.*')):  # former one-file-per-day layout
        os.remove(old)
    write(os.path.join(out, 'gap-review.md'), '\n'.join(L))
    write(os.path.join(out, 'gap-review.json'), json.dumps({'project': scope, 'service': svc, 'date': day, 'verdict': verdict, 'coverage': [covered, total],
                                                                'findings': R.items}, indent=1, ensure_ascii=False) + '\n')
    track_event(scope, svc, 'S5' if svc == 'sds' else 'D6', f'Gap review: {verdict} ({fails} ❌, {warns} ⚠️, {todos} ⚪), review/gap-review.md',
                typ='issue' if fails else 'note', gate='gap_review_passed', gate_ok=not fails and not todos, evidence=f'review/gap-review.md ({day})')
    print(f'{scope}: {verdict} · {len(R.items)} checks ({fails} fail, {warns} warn, {todos} waiting) · coverage {covered}/{total} => {os.path.relpath(os.path.join(out, "gap-review.md"), ROOT)}')


if __name__ == '__main__':
    main()
