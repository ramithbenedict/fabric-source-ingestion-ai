"""Resolve the IDs a data product needs from its source datasets and cache them in progress.json.

For each upstream source: workspace id and item id of LH_SDS_<SRC>. They fill LH_SDS_<SRC>_ID and LH_SDS_<SRC>_WORKSPACE_ID of VL_MAIN the next time
create_variable_library.py runs, so the shortcuts of LH_INP_SDS_<SRC> import with real GUIDs (a placeholder fails the import: deploy_gate.py).

Order, first hit wins (cached values are used first; --refresh looks again):
  1. by hand:           --source <SRC> --workspace-id <GUID> [--lakehouse-id <GUID>]  (the workspace URL has .../groups/<id>/)
  2. deployment repo:   LH_SDS_<SRC>_ID in the VL_MAIN of the source workspace folder (the item id the source dataset was deployed with), the workspace id from
                        its WORKSPACE_ID variable or its ci-cd profile. No sign-in.
  3. Fabric (read-only): workspace and lakehouse by name through the REST API, with the browser sign-in (azure-identity).
Anything still missing stops the script and says what to give.

  python -I 0-shared/scripts/resolve_upstream.py --id RMA [--refresh]
  python -I 0-shared/scripts/resolve_upstream.py --id RMA --source RMA --workspace-id <GUID>
"""
import argparse, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project_inputs
from common import resolve_scope, load_map, read_json, write
from project_inputs import ENV_SUFFIX
import deploy_gate


def upstream_ids(scope):
    return project_inputs.load('dp', scope).get('upstream_ids', {})


def complete(rec):
    return bool(rec) and deploy_gate.is_real_guid(rec.get('lakehouse_id')) and deploy_gate.is_real_guid(rec.get('workspace_id'))


def missing(scope, upstream):
    """Sources whose DEV ids are not both resolved (the builders stop before writing zero GUIDs)."""
    ids = upstream_ids(scope).get('DEV', {})
    return [u for u in upstream if not complete(ids.get(u.replace('-', '_')))]


def from_repo(u, env, repo):
    """What the deployment repo already knows about the source dataset: {'lakehouse_id', 'workspace_id'} (only real GUIDs)."""
    t = u.replace('-', '_')
    sds = project_inputs.load('sds', u)
    folder = sds.get('workspace_folder') or ENV_SUFFIX.sub('', sds.get('workspace', '')).strip()
    out = {}
    if not (repo and folder and os.path.isdir(os.path.join(repo, folder))):
        return out
    vl = os.path.join(repo, folder, 'VL_MAIN.VariableLibrary')
    vals = deploy_gate.vl_values(vl, env)
    default = {v['name']: v.get('value') for v in read_json(os.path.join(vl, 'variables.json')).get('variables', [])} if os.path.exists(os.path.join(vl, 'variables.json')) else {}
    key = f'LH_SDS_{t}_ID'
    a, b = default.get(key), vals.get(key)  # the default value and the value of this environment
    conn = vals.get(f'{t}_LH_CONN_ID')
    if deploy_gate.is_real_guid(b) and deploy_gate.is_real_guid(a) and a.lower() != b.lower():
        out['conflict'] = f'the source VL_MAIN holds {a} (default value) and {b} ({env} value set) for {key}: which one is the item id of LH_SDS_{t}?'
    elif deploy_gate.is_real_guid(b) and conn and str(conn).lower() == b.lower():
        out['conflict'] = f'{key} is the same GUID as {t}_LH_CONN_ID ({b}) in the source VL_MAIN: an item id and a connection id cannot be equal, check which is right'
    elif deploy_gate.is_real_guid(b):
        out['lakehouse_id'] = b.lower()
    ws = vals.get('WORKSPACE_ID')
    if not deploy_gate.is_real_guid(ws):
        prof = os.path.join(repo, 'ci-cd', 'profiles', f"{re.sub(r'[^a-z0-9]+', '_', folder.lower())}_{env.lower()}.yaml")
        m = re.search(r"workspaceId:\s*'?([0-9a-f-]{36})'?", open(prof, encoding='utf-8').read(), re.I) if os.path.exists(prof) else None
        ws = m.group(1) if m else None
    if not deploy_gate.is_real_guid(ws):  # Fabric names the workspace in every commit it makes: "Committing N items from workspace <id>"
        try:
            import subprocess
            log = subprocess.run(['git', '-C', repo, 'log', '--format=%s', '--', folder], capture_output=True, text=True, encoding='utf-8').stdout
            seen = re.findall(r'from workspace ([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', log, re.I)
            if len(seen) >= 2 and len({x.lower() for x in seen}) == 1:
                ws = seen[0]
                out['workspace_from_commits'] = len(seen)
        except OSError:
            pass
    if deploy_gate.is_real_guid(ws):
        out['workspace_id'] = ws.lower()
    out['workspace_name'] = folder
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--id', required=True, help='data product')
    ap.add_argument('--refresh', action='store_true')
    ap.add_argument('--source', help='set the ids of one source by hand (no Fabric access): its name, with --workspace-id (and --lakehouse-id when the deployment repo does not hold it)')
    ap.add_argument('--workspace-id', help='workspace id of the source dataset (the groups/<id> part of the workspace URL)')
    ap.add_argument('--lakehouse-id', help='item id of LH_SDS_<SOURCE> (the id after lakehouses/ in its URL)')
    a = ap.parse_args()
    m = load_map()
    scope, _ = resolve_scope(m, 'dp', a.id)
    S = m['dp'][scope]
    d = project_inputs.load('dp', scope)
    env = ENV_SUFFIX.search(d.get('workspace', '')).group(1).upper() if ENV_SUFFIX.search(d.get('workspace', '')) else 'DEV'
    repo = d.get('deployment_repo')
    ids = d.get('upstream_ids', {})
    ids.setdefault(env, {})
    only = a.source.upper().replace('-', '_') if a.source else None
    todo = [u for u in S['upstream'] if (only and u.replace('-', '_') == only) or (not only and (a.refresh or not complete(ids[env].get(u.replace('-', '_')))))]
    if only and not todo:
        raise SystemExit(f'{only} is not an input source of {scope}: {", ".join(S["upstream"])}')
    need_fabric, notes = [], []
    for u in todo:
        t = u.replace('-', '_')
        rec = from_repo(u, env, repo)
        prev = ids[env].get(t) or {}
        for k in ('lakehouse_id', 'workspace_id'):  # a value given by hand earlier stays (it settles a conflict)
            if prev.get(k) and prev.get('source', 'by hand') == 'by hand' and deploy_gate.is_real_guid(prev[k]):
                rec[k] = prev[k]
                if k == 'lakehouse_id':
                    rec.pop('conflict', None)
        if only:  # by hand wins
            for key, arg in (('workspace_id', a.workspace_id), ('lakehouse_id', a.lakehouse_id)):
                if arg:
                    if not deploy_gate.is_real_guid(arg.lower()):
                        raise SystemExit(f'--{key.replace("_", "-")} must be a valid, non-zero GUID.')
                    rec[key] = arg.lower()
        if complete(rec):
            how = 'by hand' if only or prev.get('source', 'by hand') == 'by hand' and prev.get('lakehouse_id') else 'deployment repo'
            ids[env][t] = {'workspace_name': rec.get('workspace_name', 'manual'), 'workspace_id': rec['workspace_id'], 'lakehouse_name': f'LH_SDS_{t}', 'lakehouse_id': rec['lakehouse_id'],
                           'source': how}
            notes.append(f"{u}: lakehouse id {how}" + (f"; workspace id from the {rec['workspace_from_commits']} commits Fabric made for {rec.get('workspace_name')} (confirm it once in the workspace URL)" if rec.get('workspace_from_commits') else ''))
        else:
            ids[env][t] = {**{k: v for k, v in rec.items() if k != 'conflict'}, 'lakehouse_name': f'LH_SDS_{t}', 'workspace_name': rec.get('workspace_name', '')} if rec else {}
            if rec.get('conflict'):
                notes.append(f"{u}: CONFLICT: {rec['conflict']}")
            need_fabric.append(u)
    stp = project_inputs.path('dp', scope)  # keep what is known now (a value given by hand survives while the other id is still missing)
    pdoc = read_json(stp)
    pdoc.setdefault('project_inputs', {})['upstream_ids'] = ids
    write(stp, json.dumps(pdoc, indent=1, ensure_ascii=False) + '\n')
    for u in need_fabric:  # still incomplete: ask Fabric (read-only)
        t = u.replace('-', '_')
        have = ids[env].get(t, {})
        try:
            from resolve_catalog import token, get
            tok = token()
        except SystemExit as exc:
            raise SystemExit(''.join(n + '\n' for n in notes if 'CONFLICT' in n) +
                             f"{u}: the deployment repo gives {'the lakehouse id ' + have['lakehouse_id'] if have.get('lakehouse_id') else 'no lakehouse id'} and "
                             f"{'the workspace id' if have.get('workspace_id') else 'no workspace id'}, and Fabric is not reachable ({str(exc).splitlines()[0][:120]}).\n"
                             f"Give what is missing: python -I 0-shared/scripts/resolve_upstream.py --id {scope} --source {u} --workspace-id <GUID of the {u} source workspace>"
                             f"{'' if have.get('lakehouse_id') else ' --lakehouse-id <GUID of LH_SDS_' + t + '>'}\n(the workspace URL has .../groups/<workspace id>/, the lakehouse URL .../lakehouses/<item id>), or re-run this command and sign in in the browser window.")
        sds = project_inputs.load('sds', u)
        base = ENV_SUFFIX.sub('', sds.get('workspace', '')).strip()
        if not base:
            raise SystemExit(f'Source {u}: no workspace saved at its framing. Run: project_inputs.py set --service sds --id {u} --workspace <NAME>')
        workspaces = get('/workspaces', tok).get('value', [])
        names = [f'{base}_{env}', base]  # the workspace may or may not carry the environment suffix
        hit = [w for n in names for w in workspaces if w['displayName'].lower() == n.lower()]
        if len(hit) < 1:
            raise SystemExit(f'Source {u}: workspace {names} not found in Fabric (check name and access).')
        wid, lh = hit[0]['id'], f'LH_SDS_{t}'
        found = [x for x in get(f'/workspaces/{wid}/lakehouses', tok).get('value', []) if x['displayName'].lower() == lh.lower()]
        if len(found) != 1:
            raise SystemExit(f'Source {u}: Lakehouse {lh} not found in workspace {hit[0]["displayName"]}: deploy the source dataset first (Data Product Migration starts after it).')
        ids[env][t] = {'workspace_name': hit[0]['displayName'], 'workspace_id': wid, 'lakehouse_name': lh, 'lakehouse_id': found[0]['id'], 'source': 'Fabric'}
        if have.get('lakehouse_id') and have['lakehouse_id'] != found[0]['id'].lower():
            print(f"WARNING {u}: the deployment repo holds lakehouse id {have['lakehouse_id']} but Fabric has {found[0]['id']}: the source VL_MAIN is out of date.")
        notes.append(f'{u}: Fabric')
    st = project_inputs.path('dp', scope)
    doc = read_json(st)
    doc.setdefault('project_inputs', {})['upstream_ids'] = ids
    write(st, json.dumps(doc, indent=1, ensure_ascii=False) + '\n')
    print(f'{env}: ' + '; '.join(notes or ['cached']) + f'\n{json.dumps(ids[env])}\nRe-run create_variable_library.py to fill VL_MAIN.')


if __name__ == '__main__':
    main()
