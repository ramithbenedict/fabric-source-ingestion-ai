"""wf-1-framing, stage F2: write the deterministic framing pack for one migration scope.

Usage (from the repository root):
  python -I 0-shared/scripts/frame_scope.py --service sds --id GAIA [--domain ENG]
  python -I 0-shared/scripts/frame_scope.py --service dp  --id DW_GAIA          # project, master pipeline or DW/DM schema

Writes 4-migration-project-deliverables/<source-dataset|data-product>/<project>/1-framing/, four files:
  01-scope-analysis.md            scope card, identification and name check (what to decide), as-is tree
  02-object-mapping.md            every DPV1 object, its evidence, action and Fabric target
  03-target-design-and-plan.md    to-be tree, decisions, VL_MAIN, migration plan (pre-filled)
  04-key-reference-questions.md   what the developer must confirm, with the evidence (reference_questions.py)
  analysis/dpv1-inventory.md      reference only: DPV1 pipelines, linked services, notebooks, datasets, SQL, full name check,
                                  DPV1 environment values, Fabric items and what they replace
and creates or updates the progress tracking (0_progress_tracking/, via track.py). Generated sections are overwritten; text below the
"Analyst notes" heading of 03 is kept when the file already exists.
"""
import argparse, datetime, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, paths, load_map, resolve_scope, write, project_dir, SERVICE_DIR
from create_variable_library import build_variables, dpv1_env_values
import track
import scope_tree

KEEP = '## Analyst notes'
# colour-coded actions and Fabric-AI-DEV-REPO item icons (2-config/conventions/00-ai-repo/markdown-formatting-convention.md)
ACTIONS = {'translate': '🟢', 'rebuild': '🟢', 'reuse': '🟢', 'rewrite': '🟢', 'merge': '🔵', 'collapse': '🔵', 'inline': '🔵',
           'replace': '🟣', 'upstream': '⚪', 'product': '⚪', 'shared': '⚪', 'drop': '🔴', 'review': '🟠'}
ACTION_MEANING = {'translate': 'converted to the Fabric equivalent', 'rebuild': 'orchestration rebuilt', 'reuse': 'existing Fabric item reused',
                  'rewrite': 'rewritten (no Fabric equivalent)', 'merge': 'several objects become one',
                  'collapse': 'hop absorbed into silver procedures', 'inline': 'absorbed into an activity', 'replace': 'replaced by DACPAC, catalog view or OneLake',
                  'upstream': 'handled by Source Dataset Migration', 'product': 'handled by Data Product Migration', 'shared': 'shared framework, migrated once',
                  'drop': 'not migrated', 'review': 'needs a manual decision'}
action_icon = lambda a: f"{ACTIONS.get(a, '⚫')} {a}"


def type_icon(t):
    t = (t or '').lower()
    return '🔗' if 'pipeline' in t or t == 'schedule' else '📓' if 'notebook' in t else '♒' if any(x in t for x in ('lakehouse', 'warehouse', 'table', 'view', 'dacpac', 'procedure', 'catalog')) \
        else '🔌' if 'connection' in t else '🏢' if 'workspace' in t else 'ℹ️' if t in ('-', 'source dataset', 'data product') else '📂'


def md(head, rows):
    esc = lambda c: str('' if c is None else c).replace('|', '\\|').replace('\n', ' ')
    return '\n'.join(['| ' + ' | '.join(head) + ' |', '|' + '|'.join('---' for _ in head) + '|'] + ['| ' + ' | '.join(esc(c) for c in r) + ' |' for r in rows])


def keep_notes(path, text):
    """Preserve the analyst-written part of a pre-filled file."""
    if os.path.exists(path):
        old = open(path, encoding='utf-8').read()
        if KEEP in old:
            text = text.split(KEEP)[0] + KEEP + old.split(KEEP, 1)[1]
    write(path, text)


OLD_FILES = ('01-scope-card.md', '02-identification.md', '03-as-is-inventory.md', '04-object-mapping.md', '04-object-mapping.csv',
             '05-variable-library.md', '06-target-design.md', '07-migration-plan.md')  # layout before the three-file framing pack


def section(text):
    """A former stand-alone page as a section: headings one level down, its own 'Last update' line dropped."""
    out = []
    for line in text.split('\n'):
        if line.startswith('Last update:'):
            continue
        out.append('#' + line if line.startswith('#') else line)
    return '\n'.join(out).strip('\n') + '\n'


def save_choices(scope, a):
    """Persist names confirmed during framing so every later script and the hub use them."""
    cfgdir = os.path.join(ROOT, '2-config', 'migration')
    tm_path, sp_path = os.path.join(cfgdir, 'scope-target-map.json'), os.path.join(cfgdir, 'shared-platform.json')
    tm, sp = json.load(open(tm_path, encoding='utf-8')), json.load(open(sp_path, encoding='utf-8'))
    if a.domain:
        clean = re.sub(r'[^A-Z0-9_]', '', a.domain.upper())
        if clean != a.domain.upper():
            print(f'NOTE: domain code "{a.domain}" has characters not allowed in Fabric item names; using "{clean}". Confirm with the domain owner.')
        a.domain = clean
    if a.domain and a.service == 'sds':
        tm['domains'][scope] = a.domain
    if a.group and a.service == 'dp':
        tm['groups'][scope] = a.group.upper()
    if (a.domain or a.group) and scope not in tm['confirmed']:
        tm['confirmed'].append(scope)
    if a.catalog_warehouse:
        sp['catalog_warehouse'] = a.catalog_warehouse
    if a.catalog_location:
        sp['catalog_warehouse_location'] = a.catalog_location
    for p, d in ((tm_path, tm), (sp_path, sp)):
        write(p, json.dumps(d, indent=2, ensure_ascii=False) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--service', choices=['sds', 'dp'], required=True)
    ap.add_argument('--id', required=True, help='source name (sds) or project / master pipeline / DW schema (dp)')
    ap.add_argument('--domain', help='domain code of a source dataset (saved in scope-target-map.json)')
    ap.add_argument('--group', help='data product group name (saved in scope-target-map.json)')
    ap.add_argument('--catalog-warehouse', help='catalog warehouse name, e.g. the shared warehouse once it exists (saved in shared-platform.json)')
    ap.add_argument('--catalog-location', choices=['same_workspace', 'shared'], help='where the catalog warehouse lives (saved in shared-platform.json)')
    ap.add_argument('--common-catalog-warehouse', help='common warehouse of the workspace that holds the catalog views of several sources, e.g. WH_CATALOG_COMMON (saved in 0_progress_tracking/progress.json)')
    ap.add_argument('--catalog-workspace', help='workspace that holds the common catalog warehouse when it is not the target workspace, e.g. Platform-Hub_DEV (saved in progress.json)')
    ap.add_argument('--workspace', help='target Fabric workspace name, e.g. DP_SDS_CONST_DEV (saved in 0_progress_tracking/progress.json)')
    ap.add_argument('--deployment-repo', help='path of the deployment repository; artifacts are also stored in <path>/<workspace folder>/')
    ap.add_argument('--parallel', action='store_true', help='allow a second project in progress (owner agreed)')
    a = ap.parse_args()
    m = load_map()
    scope, how = resolve_scope(m, a.service, a.id)
    track.ensure_single_active(scope, a.service, a.parallel)
    if a.service == 'dp':  # a data product starts only when its source datasets are migrated
        import source_contract
        source_contract.require_sources(scope)
    save_choices(scope, a)
    import project_inputs
    pin = project_inputs.save(a.service, scope, domain=a.domain, group=a.group, workspace=a.workspace, deployment_repo=a.deployment_repo,
                              catalog_warehouse=a.common_catalog_warehouse if a.service == 'sds' else None,
                              catalog_workspace=a.catalog_workspace if a.service == 'sds' else None)
    if pin.get('workspace_folder'):
        m['sds' if a.service == 'sds' else 'dp'][scope]['ws'] = pin['workspace_folder'] + '_<ENV>'
    gap = project_inputs.missing(a.service, scope)
    if gap:
        print('NOTE: framing needs ' + ' and '.join(gap) + ': ask the developer, then re-run with --workspace / --deployment-repo.')
    if a.group and a.service == 'dp':
        S0 = m['dp'][scope]
        S0['warehouse'], S0['dbproject'] = f'WH_DPG_{a.group.upper()}', f'DPG-{a.group.upper()}'
        if not pin.get('workspace_folder'):
            S0['ws'] = f'DP_DPG_{a.group.upper()}_<ENV>'
        S0['group'], S0['group_confirmed'] = a.group.upper(), True
    S = (m['sds'] if a.service == 'sds' else m['dp'])[scope]
    O = m['objects']
    isS = a.service == 'sds'
    proj = next((p for p in m['projects'] if p['scope'] == scope), {})
    det = proj.get('detected') or {}
    if isS and a.domain:
        if not pin.get('workspace_folder'):
            S['ws'] = S['ws'].replace(f"DP_SDS_{S['domain']}_", f'DP_SDS_{a.domain.upper()}_')
        S['domain'], S['domain_confirmed'] = a.domain.upper(), True
    kind = 'source-dataset' if isS else 'data-product'
    out = project_dir(a.service, scope, '1-framing')
    today = f'{datetime.date.today():%Y-%m-%d}'
    src_rel = m['meta'].get('source_root', '')

    # 01 scope card
    target = ([f"- Workspace: `{S['ws']}`", f"- Folder: `{S['folder']}`", f"- Lakehouse: `{S['lakehouse']}` (ingested directly from the source: databases → Files/raw (parquet), APIs and files → Files/landing → Files/raw; then tables; no shortcut)"]
              if isS else [f"- Workspace: `{S['ws']}`", f"- Warehouse: `{S['warehouse']}` · database project (DACPAC): `{S['dbproject']}`",
                           f"- Input Lakehouses: {', '.join('`LH_INP_SDS_' + u.replace('-', '_') + '`' for u in S['upstream']) or 'none'}"])
    card = '\n'.join([
        f"# Scope Card: {scope} ({'Source Dataset' if isS else 'Data Product'} Migration)", '', f'Last update: {today}', '',
        f"Framed on {today} from `{src_rel}` (hub generated {m['meta'].get('generated_at', '')}). Resolved from {how} `{a.id}`.", '',
        '## Service', '', f"- {'wf-2-migration-source-dataset: Synapse source ingestion up to SPOT_DB source' if isS else 'wf-3-migration-data-product: SPOT_DB source → DW / DM (dedicated-pool code via wf-4-migration-dacpac)'}",
        f"- {'Domain' if isS else 'Data product group'}: **{S['domain'] if isS else S['group']}**{'' if (S['domain_confirmed'] if isS else S['group_confirmed']) else ' (to confirm)'}", '',
        '## Target in Fabric', '', *target, '',
        '## Size', '', f"- DPV1 objects mapped: {len(S['rows'])} · pipelines {len(S['pipelines'])} · notebooks {len(S['notebooks'])} · linked services {len(S['linked_services'])}",
        f"- Complexity (repo-measured): {det.get('complexity', 'n/a')} ({det.get('objects', 0)} objects)" + (f"; register: {', '.join(r['project'] + ' ' + r['complexity'] for r in proj.get('register', []))}" if proj.get('register') else '; not in the project register'),
        f"- Actions: {', '.join(f'{k} {v}' for k, v in sorted(S['counts'].items(), key=lambda x: -x[1]))}", '',
        '## Lineage with the other service offering', '',
        *(([f"- Data products that read {scope} in DPV1 (analysis only: they are migrated by Data Product Migration, never by this workflow):"] +
           [f"  - **{x['dp']}**: {len(x['evidence'])} DPV1 objects, e.g. {x['evidence'][0]}" for x in S.get('consumers', [])] +
           [f"  - **{g}**: calls a pipeline of this source" for g in S['downstream'] if g not in {x['dp'] for x in S.get('consumers', [])}] +
           [f"- What they will need is published at the end of S4 in `source-dataset-contract.json` (tables, DPV1 access paths, VL_MAIN names)."])
          if isS and S['downstream'] else [f"- Data products that read {scope} in DPV1: none found"] if isS else
          [f"- Input source datasets: {', '.join(S['upstream']) or 'none detected'}" + (f" (found from the data it reads: {', '.join(S.get('upstream_data', []))})" if S.get('upstream_data') else ''),
           '- Each one is read through `LH_INP_SDS_<SOURCE>` built from its source dataset contract (`build_input_lakehouse.py`, D3).',
           f"- Reads other data products: {', '.join(x['dp'] + ' (' + x['evidence'][0] + ')' for x in S.get('reads_products', [])) or 'none found'}",
           f"- Read by other data products: {', '.join(x['dp'] for x in S.get('read_by_products', [])) or 'none found'}"]),
        f"- Entry points: {', '.join('`' + e + '`' for e in S['entry']) or 'none'}",
        f"- Triggers: {', '.join(t + ' (' + O['trigger'].get(t, {}).get('state', '') + ')' for t in S['triggers']) or 'none in the repository'}", ''])

    # 02 identification
    cand = S.get('candidates', [])
    miss = [c for c in cand if c['status'] == 'not included']
    ident = '\n'.join([
        f'# Scope Identification: {scope}', '', f'Last update: {today}', '',
        'Rules applied to the DPV1 export (see skill `skill-scope-resolution`). Every object in `02-object-mapping.md` carries its evidence in "Found by".', '',
        md(['Rule', 'Objects'], sorted(S.get('identified', {}).items(), key=lambda x: -x[1])), '',
        f'## Name check: {len(cand)} other DPV1 objects match "{scope}"', '',
        f"- In the other service for this project: {sum(c['status'] == 'other service' for c in cand)}",
        f"- In other scopes: {sum(c['status'].startswith('in ') for c in cand)}",
        f"- **Not included: {len(miss)}** — confirm each one is out of scope or add it before building.", '',
        (md(['Kind', 'Object', 'Folder'], [[c['kind'], c['name'], c['folder']] for c in miss]) if miss else '_Nothing to decide._'), '',
        '_The full list of matching objects is in `analysis/dpv1-inventory.md`._', ''])
    name_check = md(['Kind', 'Object', 'Folder', 'Status'], [[c['kind'], c['name'], c['folder'], c['status']] for c in cand]) if cand else '_No other object matches the scope name._'

    # 03 as-is inventory
    P = O['pipeline']
    inv = [f'# As-is Inventory (DPV1): {scope}', '', f'Last update: {today}', '',
           '## As-is tree', '', 'Where each object lives in the Synapse export, and what happens to it (🟢 converted, 🔵 merged, 🟣 replaced, ⚪ elsewhere, 🟠 decision, 🔴 not migrated).', '',
           '```text', scope_tree.to_text(scope_tree.as_is(S, O, a.service)), '```', '', '_Pipelines, linked services, notebooks, datasets and SQL of the scope: `analysis/dpv1-inventory.md`._', '']
    tables = ['## Pipelines', '',
           md(['Pipeline', 'Folder', 'Activities', 'Children', 'Triggers'], [[n, P.get(n, {}).get('folder', ''), P.get(n, {}).get('acts', ''), len(P.get(n, {}).get('children', [])), ', '.join(P.get(n, {}).get('triggers', []))] for n in S['pipelines']]), '',
           '## Linked services', '', md(['Linked service', 'Type', 'Runtime', 'Details'], [[n, O['linkedService'].get(n, {}).get('type'), O['linkedService'].get(n, {}).get('runtime'),
                                                                                         '; '.join(f'{k}={v}' for k, v in O['linkedService'].get(n, {}).get('details', {}).items())] for n in S['linked_services']]), '',
           '## Notebooks', '', md(['Notebook', 'Lines', 'mssparkutils', 'Called by'], [[n, O['notebook'].get(n, {}).get('lines'), O['notebook'].get(n, {}).get('mssparkutils'), ', '.join(O['notebook'].get(n, {}).get('called_by', [])[:3])] for n in S['notebooks']]) if S['notebooks'] else '_None._', '',
           '## Data flows', '', ', '.join(f'`{n}`' for n in S['dataflows']) or '_None._', '',
           '## Datasets', '', md(['Dataset', 'Type', 'Linked service'], [[n, O['dataset'].get(n, {}).get('type'), O['dataset'].get(n, {}).get('ls')] for n in S['datasets']]) if S['datasets'] else '_None._', '',
           '## SQL scripts', '', ', '.join(f'`{n}`' for n in S['sqlscripts']) or '_None._', '']
    if isS:
        tables += ['## Source tables (CATALOG)', '', md(['Schema', 'Table', 'Load'], [[c['schema'], c['table'], 'incremental' if c['incremental'] else 'full'] for c in S['catalog']]) if S['catalog'] else '_No CATALOG table list in the repository: take it from the metabase._', '']
    else:
        tables += [f"## SQL objects ({', '.join(S['schemas'])})", '', md(['Object', 'Kind', 'Defined in'], [[k, O['sql'][k]['kind'], 'referenced only: extract from the Synapse database' if O['sql'][k].get('ref_only') else (O['sql'][k]['defined_in'] or [''])[0]] for k in S['sqlobjects']]) if S['sqlobjects'] else '_No SQL definitions in the repository: extract the DDL from the Synapse database (wf-4)._', '']
    carried = []  # analyst notes of the former 06 / 07 pages move to the Analyst notes of 03
    for old in ('06-target-design.md', '07-migration-plan.md'):
        f = os.path.join(out, old)
        if os.path.exists(f) and KEEP in open(f, encoding='utf-8').read():
            notes = open(f, encoding='utf-8').read().split(KEEP, 1)[1].strip()
            if notes and not notes.startswith('_'):
                carried += [f"### From the former {old}", '', notes, '']
    for old in OLD_FILES:  # former eight-file layout of a project framed before
        if os.path.exists(os.path.join(out, old)):
            os.remove(os.path.join(out, old))
    write(os.path.join(out, '01-scope-analysis.md'), '\n'.join([
        f"# Scope Analysis: {scope} ({'Source Dataset' if isS else 'Data Product'} Migration)", '', f'Last update: {today}', '',
        'Sections: 1. scope card · 2. identification and name check · 3. as-is (DPV1). Mapping: `02-object-mapping.md`; target and plan: `03-target-design-and-plan.md`.', '',
        section(card), section(ident), section('\n'.join(inv))]))

    # 04 object mapping
    head = ['DPV1 type', 'DPV1 object', 'Found by', 'Action', 'Fabric type', 'Fabric target', 'Workspace', 'Note']
    rows = [[r['v1t'], r['v1'], r.get('by', ''), r['a'], r['v2t'], r['v2'], r['ws'], r['n']] for r in S['rows']]
    counts = {}
    for r in S['rows']:
        counts[r['a']] = counts.get(r['a'], 0) + 1
    pretty = [[r['v1t'], f"`{r['v1']}`", r.get('by', ''), action_icon(r['a']), f"{type_icon(r['v2t'])} {r['v2t']}", f"`{r['v2']}`" if r['v2'] not in ('-', '') else '-', r['ws'], r['n']] for r in S['rows']]
    write(os.path.join(out, '02-object-mapping.md'), '\n'.join([
        f'# Object Mapping: {scope}', '', f"Last update: {today}", '', '## Summary', '',
        md(['Action', 'Objects', 'Meaning'], [[action_icon(k), v, ACTION_MEANING.get(k, '')] for k, v in sorted(counts.items(), key=lambda x: -x[1])]), '',
        '## Objects', '', md(head, pretty), '']) + '\n')

    # 05 variable library
    variables = build_variables(m, a.service, scope)
    legacy = dpv1_env_values(S)
    vl_text = '\n'.join([
        f"# Variable Library VL_MAIN: {scope} ({S['ws']})", '', f'Last update: {today}', '',
        f"Generated by `create_variable_library.py --service {a.service} --id {scope}` in stage {'S4' if isS else 'D4'}. Value sets DEV, UAT, PRD; `<to set>` values are filled once the items and connections exist.", '',
        md(['Variable', 'Type', 'DEV', 'UAT', 'PRD', 'Note'], [[v['name'], v['type'], v['values']['DEV'], v['values']['UAT'], v['values']['PRD'], v['note']] for v in variables]), '',
        '_DPV1 environment values (not carried to VL_MAIN) are in `analysis/dpv1-inventory.md`._', ''])
    env_values = md(['DPV1 parameter', 'DEV', 'UAT', 'PRD', 'Used by'], [[v['var'], v['values'].get('DEV'), v['values'].get('UAT'), v['values'].get('PRD'), ', '.join(v['used_by'][:3])] for v in legacy]) if legacy else '_None._'

    # 06 target design (pre-filled) and 07 plan (pre-filled)
    inputs = []
    if not isS:  # what the product reuses from each source dataset contract
        import source_contract
        _, shown = source_contract.show(scope)
        inputs = ['## Input source datasets (from their contracts)', '', '| Source dataset | Contract | Input Lakehouse | Tables used by the DPV1 code |', '| --- | --- | --- | --- |']
        inputs += [f"| {o['source']} | {'✅ ready' if o.get('ready') else '🟡 published, source not finished' if o['contract'] else '⚪ not migrated yet'} | "
                   f"`LH_INP_SDS_{o['source'].replace('-', '_')}` | {(str(len(o['tables_used'])) + '/' + str(o['tables_total'])) if o['contract'] else '-'} |" for o in shown]
        inputs += ['', 'D3 builds the input Lakehouses with `build_input_lakehouse.py`; D2 re-points the DPV1 reads to the `[INP_<SRC>]` views (source contract).', '']
    by_target = {}
    for r in S['rows']:
        if r['a'] not in ('drop', 'upstream', 'product', 'shared') and r['v2'] not in ('-', ''):
            by_target.setdefault(r['v2'], []).append(r['v1'])
    sp = json.load(open(os.path.join(ROOT, '2-config', 'migration', 'shared-platform.json'), encoding='utf-8'))
    from common import catalog_warehouse
    catalog = {'warehouse': catalog_warehouse(sp, S.get('folder', scope)), 'schema': sp['catalog_schema']}
    write_design = '\n'.join([f'# Target Design: {scope}', '', f'Last update: {today}', '', '> Generated from the object mapping. Complete or correct it under "Analyst notes"; generated sections are rewritten on re-run.', '',
                              '## To-be tree', '', 'Fabric workspace, folders and items, each with the DPV1 objects it replaces (←). The as-is tree is in 01-scope-analysis.md.', '',
                              '```text', scope_tree.to_text(scope_tree.to_be(S, a.service, catalog, O)), '```', '',
                              *inputs,
                              '## Decisions to confirm', '', f"- {'Domain' if isS else 'Group'} name: `{S['domain'] if isS else S['group']}`",
                              '- Every row with action `review` in 02-object-mapping.md', '- Every "not included" object in 01-scope-analysis.md (name check)', ''])
    stages = (['S1 Catalog view and Lakehouse', 'S2 Source to RAW', 'S3 RAW to Lakehouse tables', 'S4 Orchestration and VL_MAIN', 'S5 Gap review and readiness'] if isS else
              ['D1 Extract legacy T-SQL', 'D2 Translate to Fabric Warehouse T-SQL (wf-4 when a DACPAC exists)', 'D3 Database project and Warehouse', 'D4 Pipelines and VL_MAIN', 'D5 Equivalence tests', 'D6 Gap review and readiness'])
    plan = '\n'.join([f'# Migration Plan: {scope}', '', f'Last update: {today}', '', f"Workflow: `{'wf-2-migration-source-dataset' if isS else 'wf-3-migration-data-product'}`. Outputs go to `4-migration-project-deliverables/{SERVICE_DIR[a.service]}/{scope}/` (2-legacy-code, 3-build, {'review' if isS else '4-dacpac, review'}).", '',
                                                                     md(['Stage', 'Status', 'Output'], [[s, '⚪ not started', ''] for s in stages]), '',
                                                                     f"Live status: [`0_progress_tracking/{scope.lower()}_tracking.md`](../0_progress_tracking/{scope.lower()}_tracking.md)", '',
                                                                     '## Prerequisites', '', *([f'- Source dataset `{u}` is migrated to Fabric (LH_SDS_{u.replace("-", "_")}); exposed here through LH_INP_SDS_{u.replace("-", "_")} shortcuts' for u in S['upstream']] if not isS else ['- Gateway and connections available for: ' + (', '.join(sorted({O['linkedService'].get(n, {}).get('type', '?') for n in S['linked_services']})) or 'none')]),
                                                                     '', '## Open points', '', *([f"- Review `{r['v1']}`: {r['n']}" for r in S['rows'] if r['a'] == 'review'] or ['- None flagged by the rules.']),
                                                                     *([f'- {len(miss)} name-check objects not included (see 01-scope-analysis.md)'] if miss else []), ''])
    write(os.path.join(out, 'analysis', 'dpv1-inventory.md'), '\n'.join([
        f'# DPV1 Inventory: {scope}', '', f'Last update: {today}', '',
        'Reference detail behind `01-scope-analysis.md` and `03-target-design-and-plan.md`: what the scope holds in the Synapse export. Generated by `frame_scope.py`; do not edit.', '',
        section('\n'.join(['# DPV1 objects of the scope', ''] + tables)),
        section('\n'.join(['# Name check: every DPV1 object named like the scope', '', name_check, ''])),
        section('\n'.join(['# DPV1 environment values (reference only, not carried to VL_MAIN)', '', env_values, ''])),
        section('\n'.join(['# Fabric items and what they replace', '', md(['Fabric target', 'Replaces (DPV1)'], [[k, ', '.join(v)] for k, v in sorted(by_target.items())]), '']))]))
    keep_notes(os.path.join(out, '03-target-design-and-plan.md'), '\n'.join([
        f'# Target Design and Plan: {scope}', '', f'Last update: {today}', '',
        'Sections: 1. target design (to-be tree, Fabric items) · 2. variable library VL_MAIN · 3. migration plan. Complete or correct them under "Analyst notes" at the end.', '',
        section(write_design), section(vl_text), section(plan), KEEP, '', *(carried or ['_Design decisions, effort, risks and owner decisions._', ''])]))

    # progress tracking (0_progress_tracking/, Fabric-AI-DEV-REPO format)
    svc = a.service
    st = track.init(scope, svc, quiet=True)
    for item in [f"{track.SVC_LABEL[svc]} identifier: `{a.id}` (resolved from {how})",
                 f"{'Domain' if isS else 'Data product group'}: `{S['domain'] if isS else S['group']}`" + ('' if (S['domain_confirmed'] if isS else S['group_confirmed']) else ' (to confirm)'),
                 *( [f"Catalog warehouse: `{catalog['warehouse']}`"] if isS else [])]:
        if item not in st['inputs']:
            st['inputs'].append(item)
    track.add_log(st, 'change', f"Framing pack generated in `1-framing/` ({len(S['rows'])} objects)", 'F2')
    track.save(st)
    done = lambda sid: st['stages'].get(sid, {}).get('status') == 'completed'
    if not done('F1'):
        track.set_status(scope, svc, 'F1', 'completed')
    if not done('F2'):  # a re-run never reopens a stage the developer has closed
        track.set_status(scope, svc, 'F2', 'in_progress', f'{len(miss)} name-check objects to confirm' if miss else 'resolve review rows, then mark completed')
    if not miss:
        st = track.load(scope, svc)
        st['gates']['name_check_resolved'] = {'status': 'completed', 'evidence': '0 objects not included (01-scope-analysis.md)'}
        track.save(st)
    import reference_questions  # the key reference questions, with evidence from DPV1 and the deployment repo; data product gate
    reference_questions.write_page(a.service, scope, S, m, pin)
    reference_questions.sync_gate(a.service, scope)
    left = reference_questions.open_required(a.service, scope) or []
    print(f"{scope} ({kind}) framed => {os.path.relpath(out, ROOT)} · {len(S['rows'])} objects · {len(miss)} name-check items to confirm · {len(left)} required reference questions open (04-key-reference-questions.md)")


if __name__ == '__main__':
    main()
