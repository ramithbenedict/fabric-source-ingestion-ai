"""Store the built artifacts of a project in the deployment repository, inside its workspace folder.

The project folder keeps the working copy:
  4-migration-project-deliverables/<Service>/<NAME>/3-build/fabric-deployment/<WORKSPACE_FOLDER>/...  (+ database-projects/)
The deployment repo gets the same tree, so it can be synced to Fabric unchanged:
  <DEPLOYMENT_REPO_PATH>/<WORKSPACE_FOLDER>/...                                                       (+ database-projects/)

Usage (from the repository root):
  python -I 0-shared/scripts/deploy_publish.py publish --service sds --id EASYTENDER [--dry-run] [--force]
  python -I 0-shared/scripts/deploy_publish.py status  --service sds --id EASYTENDER      # exit 2 when the repo differs from the build

Rules:
- Items already in the repo with another logicalId (same .platform path) are not overwritten: Git sync would see a different item. They are listed; --force replaces them.
- A shared item (VL_MAIN) that already exists with other content is listed and kept: merge it by hand, because other sources use the same workspace.
- Files in the repo that the build does not have are never deleted.
- A pipeline that Fabric's Git import cannot resolve (common.one_sync_findings) blocks the publish: nothing is copied.
"""
import argparse, json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import project_dir, deploy_dir, lp, unlp, read_text, walk_files, exists, track_event, one_sync_findings
import project_inputs

SHARED = ()


def vl_superset(built, deployed):
    """A built VL_MAIN file may replace the deployed one when it is the same item (logicalId) and keeps every deployed variable
    (create_variable_library.workspace_library merges the workspace). Other files of the library follow variables.json."""
    from create_variable_library import read_library, RETIRED
    b, d = os.path.dirname(built), os.path.dirname(deployed)
    if os.path.basename(b) == 'valueSets':
        b, d = os.path.dirname(b), os.path.dirname(d)
    (bid, bv), (did, dv) = read_library(b), read_library(d)
    return bool(bid) and bid == did and {v['name'] for v in bv} >= {v['name'] for v in dv} - set(RETIRED)


def same_json(a, b):
    """True when two JSON files hold the same content: a commit from the workspace rewrites them with CRLF and no final newline."""
    if not a.endswith(('.json', '.platform')):
        return False
    try:
        return json.loads(read_text(a)) == json.loads(read_text(b))
    except ValueError:
        return False


def same_item(a, b):
    """Two .platform files that describe the same Fabric item: same type, display name and logicalId."""
    try:
        x, y = json.loads(read_text(a)), json.loads(read_text(b))
        key = lambda d: (d['metadata']['type'], d['metadata']['displayName'], d['config']['logicalId'])
        return key(x) == key(y)
    except (ValueError, KeyError):
        return False


def register_profiles(repo, src):
    """Add the profiles of the build (ci-cd/profiles/*.yaml) to the `values:` list of ci-cd/deployment-pipeline.yaml. Returns the names added."""
    import re
    path = os.path.join(repo, 'ci-cd', 'deployment-pipeline.yaml')
    names = [os.path.splitext(f)[0] for f in sorted(os.listdir(os.path.join(src, 'ci-cd', 'profiles')))] if os.path.isdir(os.path.join(src, 'ci-cd', 'profiles')) else []
    if not names or not exists(path):
        return []
    text = read_text(path, 'replace')
    new = [n for n in names if not re.search(rf'^\s*-\s*{re.escape(n)}\s*$', text, re.M)]
    if not new:
        return []
    last = list(re.finditer(r'^(\s*)-\s*(dp_\w+)\s*$', text, re.M))
    if not last:
        return []
    m = last[-1]
    nl = '\r\n' if '\r\n' in text else '\n'
    text = text[:m.end()] + ''.join(f'{nl}{m.group(1)}- {n}' for n in new) + text[m.end():]
    with open(lp(path), 'w', encoding='utf-8', newline='') as fh:
        fh.write(text)
    return new


def plan(service, name):
    d = project_inputs.load(service, name)
    if not d.get('deployment_repo') or not d.get('workspace_folder'):
        raise SystemExit(f'{name}: deployment repo path or workspace missing. Run framing (F1) or: project_inputs.py set --service {service} --id {name} --workspace <NAME> --deployment-repo <PATH>')
    src = deploy_dir(service, name)
    if not os.path.isdir(lp(src)):
        raise SystemExit(f'{name}: nothing built yet under {src}')
    repo = d['deployment_repo']
    if not os.path.isdir(repo):
        raise SystemExit(f'Deployment repo path not found: {repo}')
    rows = []  # (relative path, status)
    for f in walk_files(src):
        rel = os.path.relpath(f, src)
        dest = os.path.join(repo, rel)
        if not exists(dest):
            st = 'new'
        elif read_text(f, 'replace') == read_text(dest, 'replace') or same_json(f, dest):
            st = 'same'
        elif any(p.endswith('.VariableLibrary') for p in rel.split(os.sep)):
            st = 'update' if vl_superset(f, dest) else 'conflict'  # VL_MAIN is shared by the workspace: never drop another source's variable
        elif os.path.basename(rel) == '.platform' or os.path.basename(rel) in SHARED:
            st = 'update' if same_item(f, dest) else 'conflict'  # the same item (type, name, logicalId) with another description is an update
        else:
            st = 'update'
        rows.append((rel, st))
    return d, src, repo, rows


def conflict_note(rel):
    return 'other logicalId or content: item already in the repo' if rel.endswith('.platform') else 'shared file differs: merge by hand'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['publish', 'status'])
    ap.add_argument('--service', choices=['sds', 'dp'], required=True)
    ap.add_argument('--id', required=True)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--force', action='store_true', help='also replace items that conflict')
    ap.add_argument('--allow-placeholders', action='store_true', help='publish although a shortcut target id is still a placeholder (the sync will fail on it)')
    a = ap.parse_args()
    from common import load_map, resolve_scope
    name, _ = resolve_scope(load_map(), a.service, a.id)
    d, src, repo, rows = plan(a.service, name)
    count = lambda s: sum(1 for _, x in rows if x == s)
    head = f"{name}: build => {repo} ({d['workspace_folder']}/): {count('new')} new, {count('update')} changed, {count('same')} identical, {count('conflict')} conflicts"
    if a.cmd == 'status':
        print(head)
        sys.exit(0 if not (count('new') or count('update') or count('conflict')) else 2)
    # a pipeline that Fabric's Git import cannot resolve blocks the whole sync of the workspace: never publish one (B48, B59)
    blocked = [(rel, w) for rel, _ in rows if rel.endswith('pipeline-content.json') for w in one_sync_findings(read_text(os.path.join(src, rel), 'replace'))]
    if blocked:
        for rel, w in blocked:
            print(f'  BLOCKED {rel}: {w}')
        raise SystemExit(f'{name}: nothing published, {len(blocked)} findings would fail the Fabric import. Regenerate (build_source_dataset.py), then publish again.')
    # what Fabric refuses at import is known now: a shortcut target id that is not a real GUID, a project that references what it does not create (deploy_gate.py)
    import deploy_gate
    unres = deploy_gate.unresolved_imports(src, 'DEV')
    closed = [m for k, v in deploy_gate.closure(src).items() if k in deploy_gate.CLOSURE_FAILS for m in v]
    if (unres or closed) and not a.allow_placeholders and not a.dry_run:
        for v, x, f in unres:
            print(f'  NOT DEPLOYABLE {f}: {v} = {x} (DEV): Fabric rejects the shortcut ("target workspace ID or artifact ID is not a valid GUID")')
        for m in closed:
            print(f'  NOT DEPLOYABLE {m}')
        raise SystemExit(f"{name}: nothing published. " + (f"Resolve the ids: python -I 0-shared/scripts/resolve_upstream.py --id {name}, then create_variable_library.py --service {a.service} --id {name}. " if unres else '') + 'Or --allow-placeholders to publish anyway.')
    promo = deploy_gate.cicd(src) if a.service == 'dp' else {'fail': []}
    if promo['fail'] and not a.allow_placeholders and not a.dry_run:
        for m in promo['fail']:
            print(f'  NOT PROMOTABLE {m}')
        raise SystemExit(f'{name}: nothing published. The build would not deploy to UAT and PRD unchanged: dacpac_retarget.py, then build_cicd.py --id {name}. Or --allow-placeholders.')
    done = 0
    for rel, st in rows:
        if st in ('new', 'update') or (st == 'conflict' and a.force):
            if not a.dry_run:
                dest = os.path.join(repo, rel)
                os.makedirs(lp(os.path.dirname(dest)), exist_ok=True)
                shutil.copyfile(lp(os.path.join(src, rel)), lp(dest))
            done += 1
    for rel, st in rows:
        if st == 'conflict' and not a.force:
            print(f'  CONFLICT {rel}: {conflict_note(rel)}')
    if a.service == 'dp' and not a.dry_run:  # ci-cd/deployment-pipeline.yaml lists the profiles a run can pick: add ours (a shared file, only appended)
        listed = register_profiles(repo, src)
        if listed:
            print(f"  deployment-pipeline.yaml: profile(s) added: {', '.join(listed)}")
    print(head + f"\n{'Would copy' if a.dry_run else 'Copied'} {done} files." + (' Conflicts kept; review them, then --force or merge by hand.' if count('conflict') and not a.force else ''))
    if not a.dry_run:
        track_event(name, a.service, None, f"Artifacts stored in the deployment repo `{repo}` under `{d['workspace_folder']}/`: {done} files, {count('conflict') if not a.force else 0} conflicts kept", 'change')


if __name__ == '__main__':
    main()
