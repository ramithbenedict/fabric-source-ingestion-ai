"""D4/K4: the CI/CD files that promote a data product from DEV to UAT and PRD, in the DPV2 shape (REPO-FABRIC-DEPLOYMENT):

  ci-cd-dacpac/pipeline-dpg-<group>.yml          builds the DACPAC (.NET 8) and publishes it to the warehouse of the branch's environment (dev / uat / prd)
  ci-cd/profiles/<workspace>_{dev,uat,prd}.yaml  one profile per environment for ci-cd/deployment-pipeline.yaml (fabric-cicd: the same workspace folder to each workspace)

Written into 3-build/fabric-deployment/ next to the workspace folder, so deploy_publish.py copies them to the deployment repo. The workspace folder has no
environment suffix. Values that exist only after the first sync of an environment (workspace id, warehouse SQL endpoint) stay `<to set>` and are listed by
deploy_preflight.py; give them with:

  python -I 0-shared/scripts/build_cicd.py --id RMA [--workspace-id DEV=<GUID> --workspace-id UAT=<GUID> ...] [--endpoint UAT=<host> ...]

The DEV endpoint is read from VL_MAIN (WH_DPG_<G>_SQL_ENDPOINT); the Lakehouse names the DACPAC reads are passed as /v:<LH>=<LH> (SQLCMD variables of the sqlproj).
"""
import argparse, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project_inputs, deploy_gate
from common import load_map, resolve_scope, write, deploy_dir, read_json, read_text, walk_files, track_event

ENVS = ('DEV', 'UAT', 'PRD')
TODO = '<to set>'
PIPELINE = """trigger:
  branches:
    include:
      - dev
      - uat
      - prd
  paths:
    include:
      - database-projects/{name}

pool:
  vmImage: 'windows-latest'

extends:
  template: templates/dacpac-pipeline.yml
  parameters:
    projectName: '{name}'
    # one /v:NAME=VALUE per SQLCMD variable declared in {name}.sqlproj (the Lakehouses the input views read), repeated in each environment
    environments:
{envs}"""
ENV_BLOCK = """      {env}:
        targetServer: '{server}'
        targetDatabase: '{wh}'
        sqlCmdVariables: {cmd}
"""
PROFILE = """# Profile of workspace {ws}_{env} (name in lower case). Used by ci-cd/deployment-pipeline.yaml.
variables:

  # target workspace id, can be found in the URL (.../groups/<id>/)
  workspaceId: '{wsid}'

  # environment name: DEV, UAT, PRD
  environmentName: '{env}'

  # Git branch name used as source
  branchName: '{branch}'

  # Folder name in the REPO-FABRIC-DEPLOYMENT repository that stores all the workspace artifacts (no environment suffix)
  repositoryDirectory: '{ws}'

  # 'all' means full deployment
  foldersToInclude: 'all'
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--id', required=True, help='data product')
    ap.add_argument('--workspace-id', action='append', default=[], metavar='ENV=GUID', help='id of the DP workspace of an environment (URL .../groups/<id>/)')
    ap.add_argument('--endpoint', action='append', default=[], metavar='ENV=HOST', help='SQL endpoint of the warehouse in an environment (DEV comes from VL_MAIN)')
    ap.add_argument('--var', action='append', default=[], metavar='ENV:NAME=VALUE', help='value of a SQLCMD variable of the database project in an environment (a DPV1 project variable)')
    a = ap.parse_args()
    m = load_map()
    scope, _ = resolve_scope(m, 'dp', a.id)
    S = m['dp'][scope]
    g, ws = S['group'], project_inputs.load('dp', scope).get('workspace_folder')
    if not ws or deploy_gate.ENV_SUFFIX.search(ws):
        raise SystemExit(f'{scope}: the workspace folder must have no environment suffix (got {ws!r}). Run: project_inputs.py set --service dp --id {scope} --workspace <NAME_DEV>')
    pin = project_inputs.load('dp', scope)
    pdoc = read_json(project_inputs.path('dp', scope))
    inputs = pdoc.setdefault('project_inputs', {})
    for key, given in (('workspace_ids', a.workspace_id), ('endpoints', a.endpoint)):
        for kv in given:
            e, _, v = kv.partition('=')
            if e.upper() not in ENVS or not v.strip():
                raise SystemExit(f'--{key[:-1].replace("_", "-")} {kv!r}: use ENV=VALUE with ENV in {", ".join(ENVS)}')
            inputs.setdefault(key, {})[e.upper()] = v.strip()
    for kv in a.var:
        env_name, _, v = kv.partition('=')
        e, _, n = env_name.partition(':')
        if e.upper() not in ENVS or not n or not v.strip():
            raise SystemExit(f'--var {kv!r}: use ENV:NAME=VALUE')
        inputs.setdefault('sqlcmd_values', {}).setdefault(e.upper(), {})[n.strip()] = v.strip()
    if a.workspace_id or a.endpoint or a.var:
        write(project_inputs.path('dp', scope), json.dumps(pdoc, indent=1, ensure_ascii=False) + '\n')
    pin = project_inputs.load('dp', scope)
    name, wh = f'DPG-{g}', f'WH_DPG_{g}'
    bd = deploy_dir('dp', scope)
    dbp = os.path.join(bd, 'database-projects', name)
    if not os.path.isdir(dbp):
        raise SystemExit(f'{scope}: no database project {name} under {bd}. Run dacpac_retarget.py first.')
    proj = read_text(os.path.join(dbp, f'{name}.sqlproj'), 'replace')
    declared = {n: dv.strip() for n, dv in re.findall(r'<SqlCmdVariable Include="(\w+)">\s*<DefaultValue>(.*?)</DefaultValue>', proj, re.S)}  # every SQLCMD variable of the project
    lakes = sorted(declared)
    vl = os.path.join(bd, ws, 'VL_MAIN.VariableLibrary')
    blocks = []
    for env in ENVS:
        ep = (pin.get('endpoints') or {}).get(env) or (deploy_gate.vl_values(vl, env).get(f'{wh}_SQL_ENDPOINT') if env == 'DEV' else None)
        ep = ep if ep and TODO not in ep and '<' not in ep else f'{TODO}.datawarehouse.fabric.microsoft.com'
        given = (pin.get('sqlcmd_values') or {}).get(env, {})
        val = lambda n: given.get(n) or (n if n.startswith('LH_') else None) or (declared.get(n) if env == 'DEV' else None) or TODO  # a Lakehouse keeps its name in every environment; any other value is the owner's per environment
        cmd = ('>\n          ' + '\n          '.join(f'/v:{n}={val(n)}' for n in lakes)) if lakes else "''"
        blocks.append(ENV_BLOCK.format(env=env, server=ep, wh=wh, cmd=cmd))
    write(os.path.join(bd, 'ci-cd-dacpac', f'pipeline-{name.lower()}.yml'), PIPELINE.format(name=name, envs=''.join(blocks)).rstrip('\n') + '\n')
    for env in ENVS:
        wsid = (pin.get('workspace_ids') or {}).get(env) or TODO
        write(os.path.join(bd, 'ci-cd', 'profiles', f'{ws.lower()}_{env.lower()}.yaml'), PROFILE.format(ws=ws, env=env, wsid=wsid, branch=env.lower()))
    left = [f'{e} value of {n}' for e in ENVS for n in lakes if not n.startswith('LH_') and not ((pin.get('sqlcmd_values') or {}).get(e, {}).get(n) or (declared.get(n) if e == 'DEV' else None))] + [f'{e} workspace id' for e in ENVS if not (pin.get('workspace_ids') or {}).get(e)] + [f'{e} SQL endpoint' for e in ENVS if e != 'DEV' and not (pin.get('endpoints') or {}).get(e)]
    track_event(scope, 'dp', 'D4', f'CI/CD files written: ci-cd-dacpac/pipeline-{name.lower()}.yml and 3 profiles for {ws}; to fill: {", ".join(left) or "none"}', 'change')
    print(f'{scope}: pipeline-{name.lower()}.yml (SQLCMD: {", ".join(lakes) or "none"}) and ci-cd/profiles/{ws.lower()}_{{dev,uat,prd}}.yaml written under {os.path.relpath(bd)}.')
    print('Still to give: ' + (', '.join(left) or 'nothing'))


if __name__ == '__main__':
    main()
