"""Generate VL_MAIN (Fabric Variable Library, Git format) for one scope with DEV, UAT and PRD value sets.

Usage (from the repository root):
  python -I 0-shared/scripts/create_variable_library.py --service sds --id GAIA
  python -I 0-shared/scripts/create_variable_library.py --service dp  --id GAIA

Writes VL_MAIN.VariableLibrary/ (.platform, settings.json, variables.json, valueSets/DEV|UAT|PRD.json) to
  4-migration-project-deliverables/<source-dataset|data-product>/<PROJECT>/3-build/fabric-deployment/<WORKSPACE>/ (workspace root)
Pipelines read it at run time (@pipeline().libraryVariables.<NAME>): no id is written into a pipeline file.
Values come from 2-config/migration/environment-values.json, shared-platform.json and the DPV1 environment
if-chains; unknown values are '<to set>'. Variable rules: 2-config/conventions/03-fabric-items/variable-library-convention.md
"""
import argparse, json, os, re, sys, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, catalog_warehouse, paths, load_map, resolve_scope, write, track_event, project_dir, deploy_dir, read_json, exists, vl_name, walk_files

ENVS = ['DEV', 'UAT', 'PRD']
TODO = '<to set>'
RETIRED = ('WORKSPACE_ID', 'IS_PROD')  # not VL_MAIN variables: pipelines use @pipeline().DataFactory, the value sets carry the environment
ZERO = '00000000-0000-0000-0000-000000000000'  # file placeholder of an id variable: Fabric's Git import resolves item / connection ids and fails on '<to set>'
SCHEMA = 'https://developer.microsoft.com/json-schemas/fabric/item/variableLibrary/definition/'


def cfg(name):
    return read_json(os.path.join(ROOT, '2-config', 'migration', name))


def catalog_view(shared, src):
    """Catalog view name of a source, e.g. geos_catalog."""
    return shared['catalog_view_pattern'].format(source=src.lower(), SOURCE=src)


def build_variables(m, service, scope):
    """Return [{name, type, note, values: {DEV, UAT, PRD}}] for a scope."""
    S = (m['sds'] if service == 'sds' else m['dp'])[scope]
    env, shared = cfg('environment-values.json')['values'], cfg('shared-platform.json')
    out, seen = [], set()
    import project_inputs
    given = project_inputs.load(service, scope).get('vl_values', {})  # ids typed by the owner after a sync: {ENV: {NAME: value}}, they win over placeholders

    def add(name, note, values=None, typ='String', const=None):
        if name in seen:
            return
        seen.add(name)
        vals = {e: const for e in ENVS} if const is not None else {e: (values or {}).get(e) or TODO for e in ENVS}
        vals = {e: given.get(e, {}).get(name) or vals[e] for e in ENVS}
        out.append({'name': name, 'type': typ, 'note': note, 'values': vals})

    if service == 'sds':
        # Only what pipelines and notebooks need to locate things. The catalog content (tables, load mode,
        # watermark…) lives in the catalog view, not in VL_MAIN. OneLake needs no ADLS connection.
        src = S['folder']
        from common import project_catalog_warehouse, project_catalog_workspace, catalog_remote
        shared_loc = catalog_remote(shared, src)
        cws = project_catalog_workspace(src)
        import project_inputs
        ids = project_inputs.load('sds', scope).get('catalog_ids', {}) if cws or project_catalog_warehouse(src) else {}  # resolved from Fabric (resolve_catalog.py)
        got = lambda key: {e: ids[e][key] for e in ids if ids[e].get(key)}
        wh = catalog_warehouse(shared, src)
        n = lambda base: vl_name(src, base)  # names that differ per source carry it: several sources can share one workspace
        add(f'LH_SDS_{src}_ID', f"Item ID of {S['lakehouse']}.")
        add(n('LH_NAME'), f"Name of {S['lakehouse']}: the notebooks look the lakehouse up by this name in the workspace they run in (no attached lakehouse needed).", const=S['lakehouse'])
        who = f'the sources that keep their catalog view in {wh}' if project_catalog_warehouse(src) else f'the {src} pipelines'
        add(n('CATALOG_WAREHOUSE_NAME'), (f'Common warehouse holding the catalog views of {who}.' if project_catalog_warehouse(src) else f"Warehouse holding the catalog view of {src} ({'shared workspace' if shared_loc else 'same workspace for now'})."), const=wh)
        add(n('CATALOG_WAREHOUSE_ID'), f"Item ID of {wh}.", got('warehouse_id'))
        add(n('CATALOG_WAREHOUSE_CONN_ID'), f"Fabric connection ID used by {who} to read and update {wh} (catalog Lookup and watermark Script).")
        add(n('CATALOG_WAREHOUSE_SQL_ENDPOINT'), f"SQL endpoint of {wh} (needed by the catalog Lookup connection).", got('sql_endpoint'))
        if shared_loc:
            add(n('CATALOG_WAREHOUSE_WORKSPACE_ID'), f"Workspace ID of {wh}'s workspace{' (' + cws + ')' if cws else ' (shared workspace)'}.", got('workspace_id'))
        add(n('LH_CONN_ID'), f"Fabric connection ID used by the {src} pipelines to read and write Lakehouse files (Copy activities).")
        add(n('CATALOG_VIEW_NAME'), f'Catalog view of {src}: tables to ingest, load mode, active flag, watermark.',
            const=f"{shared['catalog_schema']}.{catalog_view(shared, src)}")
        from common import work_path
        prof_p = work_path('sds', scope, 'catalog-profile.json')
        wm = read_json(prof_p).get('watermark_table') if exists(prof_p) else None
        if wm:  # incremental source: the watermark per table lives in a warehouse table (a view is read-only)
            add(n('CATALOG_WATERMARK_TABLE_NAME'), f'Watermark table of {src} in {wh}, updated after each successful run.', const=wm)
    else:
        g = S['group']
        add(f'WH_DPG_{g}_ID', f"Item ID of {S['warehouse']}.")
        add(f'WH_DPG_{g}_SQL_ENDPOINT', f"SQL endpoint of {S['warehouse']}.")
        add(f'WH_DPG_{g}_CONN_ID', f"Fabric connection ID used by the process pipeline to call the stored procedures of {S['warehouse']}.")
        import project_inputs
        up = project_inputs.load('dp', scope).get('upstream_ids', {})  # resolved from Fabric (resolve_upstream.py)
        for u in S['upstream']:
            t = u.replace('-', '_')
            pick = lambda key: {e: up[e][t][key] for e in up if (up[e].get(t) or {}).get(key)}
            add(f'LH_INP_SDS_{t}_ID', f'Item ID of the input Lakehouse LH_INP_SDS_{t}.')
            add(f'LH_SDS_{t}_ID', f'Item ID of the source Lakehouse LH_SDS_{t} (shortcut target).', pick('lakehouse_id'))
            add(f'LH_SDS_{t}_WORKSPACE_ID', f'Workspace ID of LH_SDS_{t}.', pick('workspace_id'))
    for r in S['rows']:  # one connection per source system
        if r['v1t'] == 'Linked service' and r['v2t'] == 'Connection':
            conn = r['v2'].split(' (')[0]
            base = re.sub(r'^CONN_|_<ENV>$', '', conn)
            add(f'{base}_CONN_ID', f"Fabric connection ID replacing linked service {r['v1']}.")
            add(f'{base}_CONN_NAME', f"Fabric connection name replacing linked service {r['v1']}.", {e: conn.replace('<ENV>', e) for e in ENVS})
            import ingestion
            ls_type = m['objects']['linkedService'].get(r['v1'], {}).get('type')
            if service == 'sds' and ingestion.dpv1_auth_headers(S, project_dir('sds', scope), r['v1'], ls_type):  # a header read from Key Vault: its own Web v2 connection
                add(ingestion.keyvault_var(S['folder']), f"Fabric connection ID (Web v2 to the Key Vault) used to read the API key header of {r['v1']}.")
    # DPV1 environment if-chains point to ADLS zones, Synapse and Key Vault secrets: they are not carried over.
    # frame_scope.py lists them in 03-target-design-and-plan.md (variable library section) for reference.
    return out


def dpv1_env_values(S):
    """DPV1 values chosen per environment in pipeline code (reference only)."""
    return [v for v in S['vl'] if not re.search(r'_ID$', v['var']) and any(v['values'].get(e) for e in ENVS)]


def read_library(lib):
    """(logicalId, [{name, type, note, values}]) of a VL_MAIN.VariableLibrary folder, or (None, []) when there is none."""
    plat, var = os.path.join(lib, '.platform'), os.path.join(lib, 'variables.json')
    if not exists(var):
        return (read_json(plat)['config']['logicalId'] if exists(plat) else None), []
    sets = {e: {o['name']: o['value'] for o in read_json(os.path.join(lib, 'valueSets', f'{e}.json')).get('variableOverrides', [])}
            for e in ENVS if exists(os.path.join(lib, 'valueSets', f'{e}.json'))}
    out = [{'name': v['name'], 'type': v.get('type', 'String'), 'note': v.get('note', ''),
            'values': {e: (lambda x: TODO if x == ZERO else x)(sets.get(e, {}).get(v['name'], v.get('value'))) for e in ENVS}} for v in read_json(var)['variables']]
    return (read_json(plat)['config']['logicalId'] if exists(plat) else None), out


def is_placeholder(x):
    """A value that carries no information: it may be replaced by a real one."""
    return x is None or str(x).strip().lower() in ('', TODO.lower(), ZERO, 'null', 'none', 'tbd', 'todo')


def workspace_library(service, scope, ws, variables):
    """VL_MAIN is one item per workspace, shared by every source (or product) of that workspace. Merge, in this order:
    the VL_MAIN of the deployment repo's workspace folder, the VL_MAIN built by the other projects of the same workspace,
    then this build. An existing real value is NEVER overridden (one VL_MAIN serves every project of the workspace: changing a value
    would break the pipelines of the others); only placeholders ('<to set>', zero GUID, empty, null) take the value of the new build.
    The logicalId of the deployment repo wins, so a publish updates the same item. Returns (logicalId, variables, kept_names)."""
    import project_inputs
    folders = []
    repo = project_inputs.load(service, scope).get('deployment_repo')
    if repo:
        folders.append(os.path.join(repo, ws, 'VL_MAIN.VariableLibrary'))
    base = os.path.dirname(project_dir(service, scope))
    for other in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        if other != scope.lower() and os.path.isdir(os.path.join(base, other, '3-build')):
            folders.append(deploy_dir(service, other, ws, 'VL_MAIN.VariableLibrary'))
    own = deploy_dir(service, scope, ws, 'VL_MAIN.VariableLibrary')
    merged, logical = {}, None
    projects = {d.upper().replace('-', '_') for d in (os.listdir(base) if os.path.isdir(base) else [])} | {scope.upper().replace('-', '_')}
    current = {v['name'] for v in variables}  # shared names (CATALOG_WAREHOUSE_*) carry no source name: this build still needs them
    live = lambda n: n not in RETIRED and (n in current or bool(projects & set(n.split('_'))))  # names of sources not built here, and retired names, are stale
    for f in folders + [own]:
        lid, vs = read_library(f)
        logical = logical or lid
        for v in vs if f != own else []:  # the previous build of this project is replaced, not merged (no stale names kept)
            if live(v['name']):
                cur = merged.get(v['name'])
                if cur:  # the first real value found wins (the deployment repo comes first)
                    v = dict(cur, values={e: cur['values'][e] if not is_placeholder(cur['values'][e]) else v['values'][e] for e in ENVS})
                merged[v['name']] = v
    mine = {v['name'] for v in variables}
    for v in variables:
        old = merged.get(v['name'], {}).get('values', {})
        merged[v['name']] = dict(v, values={e: old[e] if e in old and not is_placeholder(old[e]) else (v['values'][e] if not is_placeholder(v['values'][e]) else old.get(e, TODO)) for e in ENVS})
    order = lambda v: v['name']  # by name: stable files
    return logical, sorted(merged.values(), key=order), sorted(set(merged) - mine)


def save_workspace_library(service, scope, ws, variables):
    """Write VL_MAIN of the workspace: this build merged with the other sources of the workspace. Returns (folder, names kept from others)."""
    logical, merged, kept = workspace_library(service, scope, ws, variables)
    return write_library(deploy_dir(service, scope, ws), merged, logical), kept


def write_library(folder, variables, logical=None):
    lib = os.path.join(folder, 'VL_MAIN.VariableLibrary')
    plat = os.path.join(lib, '.platform')
    logical = logical or (read_json(plat)['config']['logicalId'] if exists(plat) else str(uuid.uuid4()))
    dump = lambda o: json.dumps(o, indent=2, ensure_ascii=False) + '\n'
    variables = [dict(v, values={e: ZERO if x == TODO and v['name'].endswith('_ID') else x for e, x in v['values'].items()}) for v in variables]
    write(plat, dump({'$schema': 'https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json',
                      'metadata': {'type': 'VariableLibrary', 'displayName': 'VL_MAIN'}, 'config': {'version': '2.0', 'logicalId': logical}}))
    write(os.path.join(lib, 'settings.json'), dump({'$schema': SCHEMA + 'settings/1.0.0/schema.json', 'valueSetsOrder': ENVS}))
    write(os.path.join(lib, 'variables.json'), dump({'$schema': SCHEMA + 'variables/1.0.0/schema.json',
                                                     'variables': [{'name': v['name'], 'note': v['note'], 'type': v['type'], 'value': v['values']['DEV']} for v in variables]}))
    for e in ENVS:
        write(os.path.join(lib, 'valueSets', f'{e}.json'), dump({'$schema': SCHEMA + 'valueSet/1.0.0/schema.json', 'name': e,
                                                                 'variableOverrides': [{'name': v['name'], 'value': v['values'][e]} for v in variables]}))
    return lib


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--service', choices=['sds', 'dp'], required=True)
    ap.add_argument('--id', required=True)
    ap.add_argument('--env', default='DEV', choices=ENVS, help='environment of --set')
    ap.add_argument('--set', action='append', default=[], metavar='NAME=VALUE', help='value of a variable that exists only after the first sync (item, connection or endpoint id); kept in progress.json and applied on every build')
    a = ap.parse_args()
    if a.set:
        import project_inputs
        pdoc = read_json(project_inputs.path(a.service, a.id))
        vals = pdoc.setdefault('project_inputs', {}).setdefault('vl_values', {}).setdefault(a.env, {})
        for kv in a.set:
            k, _, v = kv.partition('=')
            if not k or not v.strip():
                raise SystemExit(f'--set {kv!r}: use NAME=VALUE')
            vals[k.strip()] = v.strip()
        write(project_inputs.path(a.service, a.id), json.dumps(pdoc, indent=1, ensure_ascii=False) + '\n')
    m = load_map()
    scope, _ = resolve_scope(m, a.service, a.id)
    if a.service == 'dp':  # a data product starts only when its source datasets are migrated
        import source_contract
        source_contract.require_sources(scope)
    S = (m['sds'] if a.service == 'sds' else m['dp'])[scope]
    variables = build_variables(m, a.service, scope)
    ws = S['ws'].replace('_<ENV>', '')
    lib, _ = save_workspace_library(a.service, scope, ws, variables)  # VL_MAIN at the workspace root, merged with the workspace
    todo = sum(1 for v in variables for e in ENVS if v['values'][e] == TODO)
    dev_todo = [v['name'] for v in variables if v['values']['DEV'] == TODO]
    track_event(scope, a.service, 'S4' if a.service == 'sds' else 'D4', f'VL_MAIN generated: {len(variables)} variables, DEV / UAT / PRD, {todo} values `<to set>`',
                gate='vl_main_complete', gate_ok=not dev_todo, evidence=f"DEV still to set: {', '.join(dev_todo)}" if dev_todo else 'all DEV values set')
    print(f'{scope}: VL_MAIN with {len(variables)} variables × {len(ENVS)} value sets → {os.path.relpath(lib, ROOT)} ({todo} values still <to set>)')


if __name__ == '__main__':
    main()
