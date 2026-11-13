"""The five inputs every framing asks for, saved once per project in
4-migration-project-deliverables/<service>/<name>/0_progress_tracking/progress.json, key "project_inputs"

  service           Source Dataset | Data Product
  domain / group    domain code (source dataset) or data product group (data product)
  name              source or project name (also the project folder name)
  workspace         target Fabric workspace name, e.g. DP_SDS_CONST_DEV (an environment suffix is allowed)
  workspace_folder  the same without environment suffix = the folder in the deployment repo
  deployment_repo   local path of the deployment repository (REPO-FABRIC-DEPLOYMENT); artifacts are stored in <deployment_repo>/<workspace_folder>/
  catalog_warehouse optional (source dataset): common warehouse in the workspace that holds the catalog views of several sources, e.g. WH_CATALOG_COMMON.
                    VL_MAIN then has one CATALOG_WAREHOUSE_* set instead of one per source. Empty = own WH_CATALOG_<SOURCE>.
  catalog_workspace optional: workspace that holds that warehouse when it is not the target workspace (e.g. Platform-Hub_DEV). Empty = the target
                    workspace. A different workspace makes the pipelines use CATALOG_WAREHOUSE_WORKSPACE_ID. catalog_ids caches the IDs
                    resolved from Fabric by resolve_catalog.py (per environment).

Usage (from the repository root):
  python -I 0-shared/scripts/project_inputs.py show --service sds --id EASYTENDER
  python -I 0-shared/scripts/project_inputs.py set  --service sds --id EASYTENDER --workspace DP_SDS_CONST_DEV --deployment-repo C:/repos/REPO-FABRIC-DEPLOYMENT
frame_scope.py saves the inputs when it is given --workspace and --deployment-repo; common.load_map() applies the workspace to the scope.
"""
import argparse, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import project_dir, write, read_json, exists, SERVICE_DIR

ENV_SUFFIX = re.compile(r'[_-](DEV|UAT|PRD|PROD|TST|TEST|<ENV>)$', re.I)
KEYS = ('service', 'domain', 'group', 'name', 'workspace', 'workspace_folder', 'deployment_repo', 'catalog_warehouse', 'catalog_workspace', 'catalog_ids')


def folder_of(workspace):
    """Workspace folder in the deployment repo: the workspace name without environment suffix."""
    return ENV_SUFFIX.sub('', workspace.strip())


def path(service, name):
    return project_dir(service, name, '0_progress_tracking', 'progress.json')


def load(service, name):
    p = path(service, name)
    if exists(p):
        return read_json(p).get('project_inputs', {})
    old = project_dir(service, name, '0_progress_tracking', 'project-inputs.json')  # former separate file
    return read_json(old) if exists(old) else {}


def save(service, name, **kw):
    d = load(service, name)
    d.update({k: v for k, v in kw.items() if v})
    d['service'], d['name'] = {'sds': 'Source Dataset', 'dp': 'Data Product'}[service], name
    if d.get('workspace') and not kw.get('workspace_folder'):
        d['workspace_folder'] = folder_of(d['workspace'])
    if d.get('workspace_folder'):
        d['workspace_folder'] = folder_of(d['workspace_folder'])  # environment-agnostic: the same folder is promoted DEV => UAT => PRD (fabric-git-repo-structure.md, section 3)
    if d.get('deployment_repo'):
        d['deployment_repo'] = os.path.abspath(d['deployment_repo'])
    if d.get('catalog_workspace') and folder_of(d['catalog_workspace']) == d.get('workspace_folder'):
        d['catalog_workspace'] = ''  # same workspace as the target: nothing remote
    st = read_json(path(service, name)) if exists(path(service, name)) else {}
    st['project_inputs'] = d
    write(path(service, name), json.dumps(st, indent=1, ensure_ascii=False) + '\n')
    return d


def missing(service, name):
    d = load(service, name)
    return [k for k in ('workspace', 'deployment_repo') if not d.get(k)]


def apply_to_map(m):
    """Give each scope with saved inputs its chosen workspace (used by every script through common.load_map)."""
    for svc in ('sds', 'dp'):
        for scope, S in m[svc].items():
            ws = load(svc, scope).get('workspace_folder')
            if ws:
                S['ws'] = ws + '_<ENV>'
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['show', 'set'])
    ap.add_argument('--service', choices=['sds', 'dp'], required=True)
    ap.add_argument('--id', required=True)
    ap.add_argument('--workspace')
    ap.add_argument('--deployment-repo')
    ap.add_argument('--workspace-folder', help='repo folder when it differs from the workspace name; an environment suffix is removed (DP_DPG_RMA_DEV => DP_DPG_RMA)')
    ap.add_argument('--catalog-warehouse', help='common catalog warehouse of the workspace, e.g. WH_CATALOG_COMMON (source dataset)')
    ap.add_argument('--catalog-workspace', help='workspace that holds the catalog warehouse when it is not the target workspace, e.g. Platform-Hub_DEV')
    a = ap.parse_args()
    if a.cmd == 'set':
        d = save(a.service, a.id, workspace=a.workspace, deployment_repo=a.deployment_repo, catalog_warehouse=a.catalog_warehouse,
                 catalog_workspace=a.catalog_workspace, workspace_folder=a.workspace_folder)
    else:
        d = load(a.service, a.id)
    print(json.dumps(d, indent=1, ensure_ascii=False) if d else f'No inputs saved for {a.id}: framing asks for them (F1).')
    gap = missing(a.service, a.id)
    if gap:
        print('Missing: ' + ', '.join(gap))


if __name__ == '__main__':
    main()
