"""m-bug-fixer, deterministic part: apply the fixes a gap review marks as auto-fixable and that a script can do.

Usage (from the repository root):
  python -I 0-shared/scripts/fix_from_review.py --service sds --id GEOS [--review <date>] [--dry-run]

Reads <project>/review/gap-review.json (the latest review) and, per ❌ finding:
  catalog view missing or wrong rows   => re-run create_catalog_view.py
  VL_MAIN missing, wrong or with forbidden variables   => re-run create_variable_library.py
  old catalog view files               => delete them (only <source>_catalog is deployed)
  shortcut definitions in a source dataset   => delete them (the source dataset ingests from the source)
Everything else (code changes in pipelines, notebooks, T-SQL) is left to the agent, listed in the fix log as "manual".
Adds a dated section at the top of <project>/review/fix-log.md and logs each fix in the change log. Run review_scope.py again afterwards.
"""
import argparse, datetime, glob, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, load_map, resolve_scope, write, track_event, project_dir, read_json, exists, walk_files, lp, read_text

HERE = os.path.dirname(os.path.abspath(__file__))


def run(script, *args):
    r = subprocess.run([sys.executable, '-I', os.path.join(HERE, script), *args], capture_output=True, text=True, encoding='utf-8', cwd=ROOT)
    return (r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr).strip() else f'{script}: no output'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--service', choices=['sds', 'dp'], required=True)
    ap.add_argument('--id', required=True)
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    scope, _ = resolve_scope(load_map(), a.service, a.id)
    rdir = project_dir(a.service, scope, 'review')
    reviews = [p for p in [os.path.join(rdir, 'gap-review.json')] if os.path.exists(p)] or sorted(glob.glob(os.path.join(rdir, '????-??-??-review.json')))
    if not reviews:
        sys.exit(f'No review for {scope}: run  python -I 0-shared/scripts/review_scope.py --service {a.service} --id {scope}  first.')
    rv = read_json(reviews[-1])
    pd = project_dir(a.service, scope)
    todo = [f for f in rv['findings'] if f['status'] == '❌']
    actions, done, manual = {}, [], []
    for f in todo:
        area, chk, path = f['area'], f['check'], os.path.join(pd, f['file']) if f['file'] else ''
        if area == 'Catalog' and chk.startswith('Old catalog view'):
            actions.setdefault(('delete', path), []).append(f['id'])
        elif area == 'Catalog':
            actions.setdefault(('script', 'create_catalog_view.py', '--id', scope), []).append(f['id'])
        elif area in ('Variable library',) or (area == 'Coverage' and 'VL_MAIN variable' in f['remark']):
            actions.setdefault(('script', 'create_variable_library.py', '--service', a.service, '--id', scope), []).append(f['id'])
        elif area == 'Service rules' and 'shortcut' in chk.lower() and a.service == 'sds':
            for p in walk_files(os.path.join(pd, '3-build'), names={'shortcuts.metadata.json'}):
                actions.setdefault(('delete', p), []).append(f['id'])
        else:
            manual.append(f)
    for act, ids in actions.items():
        if act[0] == 'delete':
            what = f"delete `{os.path.relpath(act[1], pd).replace(os.sep, '/')}`"
            if not a.dry_run and exists(act[1]):
                os.remove(lp(act[1]))
        else:
            what = f"run `{' '.join(act[1:])}`" + ('' if a.dry_run else f' => {run(*act[1:])}')
        done.append((ids, what))
        if not a.dry_run:
            track_event(scope, a.service, 'S5' if a.service == 'sds' else 'D6', f"Bug fix {', '.join(ids)}: {what}", typ='change')
    day = f'{datetime.date.today():%Y-%m-%d}'
    L = [f'## {day}', '', f"- **Review**: `{os.path.basename(reviews[-1])[:-5]}.md` of {rv.get('date', '?')} ({rv['verdict']})",
         f'- **Failures in the review**: {len(todo)} · applied by script: {sum(len(i) for i, _ in done)} · left to the agent: {len(manual)}', f"- **Mode**: {'dry run' if a.dry_run else 'applied'}", '',
         '## Applied by script', '', '| Findings | Fix |', '| --- | --- |'] + [f"| {', '.join(i)} | {w} |" for i, w in done] + ([] if done else ['| - | - |']) + \
        ['', '## Left to the agent (manual)', '', '| ID | Area | Check | Fix | File |', '| --- | --- | --- | --- | --- |'] + \
        [f"| {f['id']} | {f['area']} | {f['check']} | {f['fix']} | {f['file']} |" for f in manual] + ([] if manual else ['| - | - | - | - | - |']) + \
        ['', f'Next: python -I 0-shared/scripts/review_scope.py --service {a.service} --id {scope}', '']
    if not a.dry_run:  # one file, newest run first; former per-day files are folded in once
        log = os.path.join(rdir, 'fix-log.md')
        olds = sorted(glob.glob(os.path.join(rdir, '????-??-??-fix-log.md')), reverse=True)
        body = read_text(log).split('\n', 2)[2] if exists(log) and read_text(log).count('\n') >= 2 else ''
        body += ''.join('\n## ' + os.path.basename(o)[:10] + ' (former file)\n' + read_text(o).split('\n', 1)[1] for o in olds)
        write(log, '\n'.join([f'# Fix Log: {scope}', ''] + L) + '\n' + body)
        for o in olds:
            os.remove(o)
    print(f"{scope}: {len(todo)} failures · {sum(len(i) for i, _ in done)} fixed by script · {len(manual)} manual" + (' (dry run)' if a.dry_run else f" => {os.path.relpath(os.path.join(rdir, 'fix-log.md'), ROOT)}"))


if __name__ == '__main__':
    main()
