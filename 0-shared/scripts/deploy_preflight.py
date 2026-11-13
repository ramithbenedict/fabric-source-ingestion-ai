"""Preflight and runbook of a deployment: what Fabric will refuse, found before you sync, and the exact order of the steps.

Usage (from the repository root):
  python -I 0-shared/scripts/deploy_preflight.py check   --service dp --id RMA     # ✅ / ❌ / ⚪ per step, exit 2 when a step would fail
  python -I 0-shared/scripts/deploy_preflight.py runbook --service dp --id RMA     # writes 3-build/deployment-runbook.md

check reads the build, the deployment repo and (when the browser sign-in works) Fabric. It never writes. runbook writes the ordered steps with this product's names, the
values to fill and where each comes from. Rules: 3-workflows/wf-2-migration-source-dataset/deployment-design.md ("Standard rule", "Deployment order").
"""
import argparse, glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, load_map, resolve_scope, write, project_dir, deploy_dir, read_json, read_text, exists, walk_files
import deploy_gate, project_inputs

OK, BAD, WAIT = '✅', '❌', '⚪'


def checks(service, scope, m):
    S = m[service][scope]
    pin = project_inputs.load(service, scope)
    repo, ws = pin.get('deployment_repo'), pin.get('workspace_folder')
    bd = deploy_dir(service, scope)
    out = []
    add = lambda st, name, detail, fix='': out.append((st, name, detail, fix))
    items = [os.path.basename(os.path.dirname(p)) for p in walk_files(bd, names={'.platform'})]
    need = (['VL_MAIN.VariableLibrary'] + [f'WH_DPG_{S["group"]}.Warehouse'] + [f'LH_INP_SDS_{u.replace("-", "_")}.Lakehouse' for u in S['upstream']]
            + [f'PL_{S["group"]}_PROCESS_DATA_PRODUCT.DataPipeline', f'PL_{S["group"]}_MASTER_ORCHESTRATOR.DataPipeline']) if service == 'dp' else []
    gone = [n for n in need if n not in items]
    add(BAD if gone else OK, 'Every item of the product is built', f"missing: {', '.join(gone)}" if gone else f'{len(items)} items in Fabric Git format',
        'build_input_lakehouse.py, build_warehouse.py, create_variable_library.py, build_process_pipeline.py' if gone else '')
    unres = deploy_gate.unresolved_imports(bd, 'DEV')
    add(BAD if unres else OK, 'Shortcut target ids are real GUIDs (import fails otherwise)', '; '.join(f'{v} = {x}' for v, x, _ in unres) if unres else 'LH_SDS_<SRC>_ID and _WORKSPACE_ID resolved',
        f'resolve_upstream.py --id {scope} [--source <SRC> --workspace-id <GUID>], then create_variable_library.py --service {service} --id {scope}' if unres else '')
    cl = deploy_gate.closure(bd)
    flat = [x for v in cl.values() for x in v]
    add(BAD if flat else OK, 'Database project closure and input layer', '; '.join(flat[:2]) if flat else 'every schema, reference and pipeline procedure resolves; the Lakehouse is read in [INP_<SRC>] views only',
        'convert_serverless_sql.py / d2_assemble_flat.py, dacpac_retarget.py' if flat else '')
    if service == 'dp':
        ci = deploy_gate.cicd(bd)
        add(BAD if ci['fail'] else OK, 'Promotable to UAT and PRD (folder, EXT-LH project, DACPAC pipeline, profiles)', '; '.join(ci['fail'][:2]) if ci['fail'] else 'one folder, one DACPAC, one profile per environment',
            f'dacpac_retarget.py, then build_cicd.py --id {scope}' if ci['fail'] else '')
        add(WAIT, 'Per environment (UAT, PRD): fill after the workspace and warehouse exist', '; '.join(ci['warn']) if ci['warn'] else 'all set',
            f'build_cicd.py --id {scope} --workspace-id ENV=<GUID> --endpoint ENV=<host>; create_variable_library.py --service dp --id {scope} --env ENV --set NAME=VALUE' if ci['warn'] else '')
    lint = project_dir(service, scope, '4-dacpac', 'lint-report.md')
    blocking = int(re.search(r'blocking: (\d+)', read_text(lint, 'replace')).group(1)) if exists(lint) and re.search(r'blocking: (\d+)', read_text(lint, 'replace')) else None
    add(WAIT if blocking is None else (BAD if blocking else OK), 'T-SQL lint: 0 blocking', 'no lint report' if blocking is None else f'{blocking} blocking', 'tsql_fabric_lint.py' if blocking else '')
    srcs = []
    for u in (S['upstream'] if service == 'dp' else []):
        sp = project_inputs.load('sds', u)
        folder = sp.get('workspace_folder')
        import resolve_upstream
        rec = resolve_upstream.from_repo(u, 'DEV', repo)
        mine = (project_inputs.load('dp', scope).get('upstream_ids', {}).get('DEV', {}).get(u.replace('-', '_')) or {}).get('lakehouse_id')
        have = bool(rec.get('lakehouse_id') or mine) and not rec.get('conflict')
        if rec.get('conflict') and mine:
            have = True  # decided by hand: resolve_upstream.py --source (the value is kept in progress.json)
        srcs.append((u, folder, have, rec.get('conflict', '') if not mine else ''))
    if service == 'dp':
        add(OK if all(s[2] for s in srcs) and srcs else BAD, 'Source datasets are deployed and their lakehouse id is certain', ', '.join(f'{u} in {f}: {"yes" if h else "NO"}' + (f' ({c})' if c else '') for u, f, h, c in srcs),
            'Deploy and run the source dataset first (wf-2); settle a conflict with resolve_upstream.py --source <SRC> --lakehouse-id <GUID>' if not all(s[2] for s in srcs) else '')
    try:
        import subprocess
        st = subprocess.run([sys.executable, '-I', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'deploy_publish.py'), 'status', '--service', service, '--id', scope], capture_output=True, text=True, encoding='utf-8')
        add(OK if st.returncode == 0 else WAIT, 'The deployment repo holds the build', st.stdout.strip().splitlines()[0][:160] if st.stdout.strip() else st.stderr.strip()[:160],
            f'deploy_publish.py publish --service {service} --id {scope} (then commit and push the deployment repo)' if st.returncode else '')
    except Exception as exc:  # noqa
        add(WAIT, 'The deployment repo holds the build', str(exc)[:120])
    vals = deploy_gate.vl_values(os.path.join(bd, ws or '', 'VL_MAIN.VariableLibrary'), 'DEV') if service == 'dp' else {}
    after = [n for n in (f'WH_DPG_{S["group"]}_ID', f'WH_DPG_{S["group"]}_SQL_ENDPOINT', f'WH_DPG_{S["group"]}_CONN_ID', f'LH_INP_SDS_{S["upstream"][0].replace("-", "_")}_ID' if S['upstream'] else '') if n and not deploy_gate.is_real_guid(vals.get(n)) and not (n.endswith('ENDPOINT') and vals.get(n) not in (None, '<to set>'))] if service == 'dp' else []
    if service == 'dp':
        add(WAIT, 'After the first sync: fill VL_MAIN DEV with the ids Fabric gives', ', '.join(after) if after else 'all set',
            'Step 5 of the runbook: they exist only once the warehouse and the lakehouse are in the workspace' if after else '')
    return out


def runbook(service, scope, m):
    S = m[service][scope]
    pin = project_inputs.load(service, scope)
    g, ws = S['group'], pin.get('workspace_folder') or S['ws'].replace('_<ENV>', '')
    wh, srcs = f'WH_DPG_{g}', S['upstream']
    L = [f'# Deployment runbook: {scope} (data product)', '',
         f'Generated by `deploy_preflight.py runbook`. Workspace `{ws}`, warehouse `{wh}`, database project `DPG-{g}`, master `PL_{g}_MASTER_ORCHESTRATOR`. Before every step: `python -I 0-shared/scripts/deploy_preflight.py check --service dp --id {scope}`.', '',
         '| # | Step | Where | What must be true / what to do | Why it fails otherwise |', '| --- | --- | --- | --- | --- |']
    rows = [
        ('0', 'Source datasets deployed and run', 'Fabric, source workspace', f"{', '.join('LH_SDS_' + u.replace('-', '_') for u in srcs)} exist and hold the `dbo` tables the shortcuts point to (run the source master once)", 'A shortcut to a table that does not exist fails'),
        ('1', 'Resolve the source ids', 'migration repo', f'`resolve_upstream.py --id {scope}` (deployment repo, then Fabric). If it cannot: `--source <SRC> --workspace-id <GUID>` (URL `.../groups/<id>/`). Then `create_variable_library.py --service dp --id {scope}`', '"Either target workspace ID or artifact ID is not a valid GUID"'),
        ('2', 'Review and preflight', 'migration repo', f'`review_scope.py --service dp --id {scope}`: no ❌. `deploy_preflight.py check`: no ❌', 'Everything below assumes this'),
        ('3', 'Publish to the deployment repo', 'migration repo', f'`deploy_publish.py publish --service dp --id {scope}` (refuses unresolved ids). Commit and push the deployment repo branch of the workspace', 'The sync reads Git'),
        ('4', 'Sync the workspace', f'Fabric, {ws}', 'Git integration: connect the workspace to branch `dev`, folder `{ws}` (no environment suffix; the folder field cannot be edited, so disconnect and reconnect to change it); if asked which side wins, choose Git into the workspace. Then Source control => **Updates** => **Update all**. Do not Commit from the workspace first. Check: the input Lakehouse shows the shortcuts under Tables/dbo, the warehouse, VL_MAIN and the two pipelines exist', 'A commit from the workspace deletes what the workspace does not have yet; a folder that does not exist on the branch gives "Invalid folder path"'),
        ('5', 'Fill VL_MAIN (DEV value set)', f'Fabric, {ws}', f'`{wh}_ID` = item id of the warehouse, `{wh}_SQL_ENDPOINT` = its SQL connection string, `{wh}_CONN_ID` = the **Connection ID** (not the warehouse item id) of a Fabric connection of type Warehouse, **Cloud** (not an on-premises gateway), OAuth 2.0 (Settings => Manage connections), `LH_INP_SDS_*_ID` = item id of the input Lakehouse. Then commit the workspace change', 'The pipelines read them at run time'),
        ('6', 'Deploy the database project (DACPAC)', 'Azure DevOps', f'Create the pipeline from `ci-cd-dacpac/pipeline-dpg-{scope.lower()}.yml` once. The branch picks the environment (dev => DEV, uat => UAT, prd => PRD): `targetServer` = the SQL endpoint of {wh} in that environment, `targetDatabase` = {wh}; the Lakehouse the input views read is passed as a SQLCMD variable (`/v:LH_...=LH_...`, `EXT-LH-*` project). .NET 8 SDK. Before the first run the service principal behind the service connection named in `ci-cd-dacpac/templates/dacpac-pipeline.yml` is **Contributor** on the workspace (Manage access). Use Run pipeline on the branch, never Rerun failed jobs (it reuses the old commit). A table whose column type changed is dropped in the warehouse first (Fabric has no ALTER COLUMN)', 'Views, tables and procedures do not exist before it: the pipeline fails on a missing procedure; no access gives "authentication failed"'),
        ('7', 'Run', f'Fabric, {ws}', f'Run `PL_{g}_MASTER_ORCHESTRATOR` once (after the source master). It sets a run id and date and runs `PL_{g}_PROCESS_DATA_PRODUCT`. Before: `SELECT TOP 5 * FROM [INP_<SRC>].[<table>]` returns rows (the source Lakehouse is loaded). Every loader must succeed', 'Error 241 = a column a view casts has another type in the Lakehouse: compare with `INFORMATION_SCHEMA.COLUMNS` of the Lakehouse'),
        ('8', 'Verify', 'Fabric + DPV1 pool', 'Row counts and checksums per table against DPV1 (`skill-equivalence-tests`, `pool_read.py`); save the queries and results in `3-build/equivalence-tests/`', 'Equivalence is the acceptance'),
        ('9', 'UAT and PRD', 'migration repo, Fabric, Azure DevOps', f'Same folder `{ws}`, same DACPAC: only values change. Create the UAT and PRD workspaces (Git: branch uat / prd, folder `{ws}`), then `build_cicd.py --id {scope} --workspace-id ENV=<GUID> --endpoint ENV=<host>` and `create_variable_library.py --service dp --id {scope} --env ENV --set NAME=VALUE` (item, connection and endpoint ids; `resolve_upstream.py` for the source Lakehouse of that environment). Run profile `{ws.lower()}_<env>` in `ci-cd/deployment-pipeline.yaml` (its `environmentName` makes the value set of that environment the active one of `VL_MAIN`; a plain Git sync does not), then the DACPAC pipeline on the branch. Check in the workspace: `VL_MAIN` shows UAT (or PRD) as the active value set and the `LH_INP_SDS_*` shortcuts point at the Lakehouse of that environment. Repeat 3 to 8', 'The same gates apply per environment; a value of DEV in UAT points UAT at DEV (the gate refuses a UAT or PRD value equal to the DEV one)')]
    L += [f'| {a} | {b} | {c} | {d} | {e} |' for a, b, c, d, e in rows]
    write(project_dir(service, scope, '3-build', 'deployment-runbook.md'), '\n'.join(L) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=['check', 'runbook'])
    ap.add_argument('--service', choices=['sds', 'dp'], required=True)
    ap.add_argument('--id', required=True)
    a = ap.parse_args()
    m = load_map()
    scope, _ = resolve_scope(m, a.service, a.id)
    if a.action == 'runbook':
        runbook(a.service, scope, m)
        print(f'{scope}: 3-build/deployment-runbook.md written')
        return
    res = checks(a.service, scope, m)
    for st, name, detail, fix in res:
        print(f'{st} {name}: {detail}' + (f'\n     => {fix}' if fix else ''))
    bad = sum(1 for r in res if r[0] == BAD)
    print(f'\n{scope}: {bad} step(s) would fail')
    sys.exit(2 if bad else 0)


if __name__ == '__main__':
    main()
