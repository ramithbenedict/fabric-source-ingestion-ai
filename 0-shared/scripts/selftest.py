"""Regression test of the data product builders: rebuild RMA in a scratch copy of this repo and compare with what is committed.

  python -I 0-shared/scripts/selftest.py [--keep]

1. copies the repo (without .git) to a temporary folder: nothing in this repo or in the deployment repo is written;
2. deletes the built items of RMA there (3-build/fabric-deployment) and rebuilds them from the saved inputs (3-build/_work/d2-flat, progress.json):
   create_variable_library, build_input_lakehouse, build_warehouse, build_process_pipeline, dacpac_retarget, build_cicd;
3. the rebuilt tree must be identical to the committed one (line endings ignored);
4. review_scope and deploy_preflight must report no failure.
Exit 0 = the builders still produce the reviewed RMA build. Run it after changing any script in 0-shared/scripts.
"""
import argparse, filecmp, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PROJECT, GROUP = 'RMA', 'RMA'
BUILD = os.path.join('4-migration-project-deliverables', 'data-product', PROJECT.lower(), '3-build', 'fabric-deployment')


def tree(base):
    out = {}
    for d, _, fs in os.walk(base):
        for f in fs:
            p = os.path.join(d, f)
            out[os.path.relpath(p, base)] = open(p, 'rb').read().replace(b'\r\n', b'\n')
    return out


def run(root, script, *args):
    r = subprocess.run([sys.executable, '-I', os.path.join(root, '0-shared', 'scripts', script), *args], cwd=root, capture_output=True, text=True, encoding='utf-8')
    return r.returncode, (r.stdout + r.stderr).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--keep', action='store_true', help='keep the scratch copy and print its path')
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # the review prints status symbols; a cp1252 console would fail on them
    tmp =tempfile.mkdtemp(prefix='fabric-selftest-')
    root = os.path.join(tmp, 'repo')
    shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns('.git', '__pycache__'))
    problems = []
    try:
        built = os.path.join(root, BUILD)
        before = tree(built)
        shutil.rmtree(built)
        steps = [('create_variable_library.py', '--service', 'dp', '--id', PROJECT), ('build_input_lakehouse.py', '--id', PROJECT),
                 ('build_warehouse.py', '--id', PROJECT, '--group', GROUP),
                 ('dacpac_retarget.py', '--flat', os.path.join(root, os.path.dirname(BUILD), '_work', 'd2-flat'), '--group', GROUP, '--product', PROJECT.lower(), '--project', PROJECT,
                  '--schema-map', f'dw_{PROJECT.lower()}=OUT_SILV_{GROUP},dm_{PROJECT.lower()}=OUT_GOLD_{GROUP}', '--gold-views'),
                 ('build_process_pipeline.py', '--id', PROJECT, '--group', GROUP),
                 ('build_cicd.py', '--id', PROJECT)]
        for step in steps:
            code, out = run(root, *step)
            print(('ok   ' if code == 0 else 'FAIL ') + ' '.join(step[:3]))
            if code:
                problems.append(f'{step[0]} exited {code}: {out[-300:]}')
        after = tree(built)
        for rel in sorted(set(before) | set(after)):
            if rel not in after:
                problems.append(f'not rebuilt: {rel}')
            elif rel not in before:
                problems.append(f'new file: {rel}')
            elif before[rel] != after[rel]:
                problems.append(f'differs: {rel}')
        code, out = run(root, 'review_scope.py', '--service', 'dp', '--id', PROJECT)
        m = re.search(r'\((\d+) fail', out)
        print(f'review: {out.splitlines()[-1][:120] if out else "no output"}')
        if code or not m or m.group(1) != '0':
            problems.append('the review reports failures')
        code, out = run(root, 'deploy_preflight.py', 'check', '--service', 'dp', '--id', PROJECT)
        print(f'preflight: {out.splitlines()[-1] if out else "no output"}')
        if code or '0 step(s) would fail' not in out:
            problems.append('the preflight reports a failing step')
    finally:
        if a.keep:
            print(f'scratch copy kept: {root}')
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    if problems:
        print(f'\nSELFTEST FAILED ({len(problems)}):')
        for p in problems[:25]:
            print(' -', p)
        sys.exit(1)
    print(f'\nSELFTEST OK: {len(after)} files rebuilt identical, review and preflight clean.')


if __name__ == '__main__':
    main()
