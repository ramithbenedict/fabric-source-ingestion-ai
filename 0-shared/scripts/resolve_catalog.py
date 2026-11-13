"""Resolve the IDs of the common catalog warehouse from Fabric (read-only) and cache them in progress.json (project_inputs.catalog_ids).

Reads: workspace id (by workspace name), warehouse id and SQL endpoint (by warehouse name). The cached IDs fill the VL_MAIN value of the
environment of the workspace name (suffix _DEV, _UAT, _PRD; none = DEV) the next time create_variable_library.py runs.
Cached values are used first; --refresh asks Fabric again. Sign-in: browser window (azure-identity), no Azure CLI.

  python -I 0-shared/scripts/resolve_catalog.py --id RMA                       # workspace and warehouse from the saved project inputs
  python -I 0-shared/scripts/resolve_catalog.py --id RMA --workspace Platform-Hub_DEV --refresh
"""
import argparse, json, os, re, subprocess, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project_inputs
from common import resolve_scope, load_map, catalog_warehouse, read_json, ROOT, write
from project_inputs import ENV_SUFFIX

API = 'https://api.fabric.microsoft.com/v1'


_TOKEN = []


def token():
    """Fabric token through the browser sign-in (azure-identity), no Azure CLI; one sign-in per run."""
    if not _TOKEN:
        try:
            from azure.identity import InteractiveBrowserCredential
            _TOKEN.append(InteractiveBrowserCredential(login_hint='gbadhani_azr@technip.onmicrosoft.com')
                          .get_token('https://api.fabric.microsoft.com/.default').token)
        except Exception as e:
            raise SystemExit('No Fabric token: browser sign-in failed (pip install azure-identity?).\n' + str(e)[:300])
    return _TOKEN[0]


def get(path, tok):
    req = urllib.request.Request(API + path, headers={'Authorization': f'Bearer {tok}'})
    with urllib.request.urlopen(req, timeout=60) as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--id', required=True, help='source dataset')
    ap.add_argument('--workspace', help='catalog workspace name (default: the saved catalog_workspace, else the target workspace)')
    ap.add_argument('--warehouse', help='catalog warehouse name (default: the saved one)')
    ap.add_argument('--refresh', action='store_true', help='ask Fabric even when the IDs are cached')
    a = ap.parse_args()
    m = load_map()
    scope, _ = resolve_scope(m, 'sds', a.id)
    d = project_inputs.load('sds', scope)
    ws = a.workspace or d.get('catalog_workspace') or d.get('workspace')
    wh = a.warehouse or d.get('catalog_warehouse') or catalog_warehouse(read_json(os.path.join(ROOT, '2-config', 'migration', 'shared-platform.json')), scope)
    if not ws:
        raise SystemExit('No workspace: pass --workspace or save the framing inputs first.')
    env = (ENV_SUFFIX.search(ws).group(1).upper() if ENV_SUFFIX.search(ws) else 'DEV')
    ids = d.get('catalog_ids', {})
    if ids.get(env, {}).get('warehouse_name') == wh and ids[env].get('workspace_name') == ws and not a.refresh:
        print(f'{env}: cached {ids[env]}')
        return
    tok = token()
    hit = [w for w in get('/workspaces', tok).get('value', []) if w['displayName'].lower() == ws.lower()]
    if len(hit) != 1:
        raise SystemExit(f'Workspace "{ws}": {len(hit)} match(es) in Fabric. Check the name (with its environment suffix) and your access.')
    wid = hit[0]['id']
    whs = [w for w in get(f'/workspaces/{wid}/warehouses', tok).get('value', []) if w['displayName'].lower() == wh.lower()]
    if len(whs) != 1:
        raise SystemExit(f'Warehouse "{wh}" not found in workspace "{ws}" (create it by syncing the deployment repo first, or give --warehouse).')
    ids[env] = {'workspace_name': ws, 'workspace_id': wid, 'warehouse_name': wh, 'warehouse_id': whs[0]['id'],
                'sql_endpoint': (whs[0].get('properties') or {}).get('connectionString', '')}
    st = project_inputs.path('sds', scope)
    doc = read_json(st)
    doc.setdefault('project_inputs', {})['catalog_ids'] = ids
    write(st, json.dumps(doc, indent=1, ensure_ascii=False) + '\n')
    print(f'{env}: {json.dumps(ids[env])}\nRe-run create_variable_library.py to fill VL_MAIN.')


if __name__ == '__main__':
    main()
