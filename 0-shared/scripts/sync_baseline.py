"""Copy the conventions and skills listed in 2-config/migration/baseline-sync.json from Fabric-AI-DEV-REPO (one-way).

Usage: python -I 0-shared/scripts/sync_baseline.py
"""
import datetime, json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, paths

SKIP = {'__pycache__', '_old', 'old', '_archive', '.git'}


def main():
    base = paths()['baseline_repo']
    cfg = json.load(open(os.path.join(ROOT, '2-config', 'migration', 'baseline-sync.json'), encoding='utf-8'))
    done, missing = [], []
    for rel in cfg['paths']:
        src, dst = os.path.join(base, rel), os.path.join(ROOT, rel)
        if not os.path.exists(src):
            missing.append(rel); continue
        if os.path.isdir(src):
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst, ignore=lambda d, names: [n for n in names if n in SKIP])
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy2(src, dst)
        done.append(rel)
    with open(os.path.join(ROOT, '2-config', 'migration', 'baseline-sync.lock'), 'w', encoding='utf-8') as f:
        f.write(f'synced_at: {datetime.datetime.now():%Y-%m-%d %H:%M}\nbaseline: {base}\npaths: {len(done)}\nmissing: {missing}\n')
    print(f'synced {len(done)} paths' + (f', missing in baseline: {missing}' if missing else ''))


if __name__ == '__main__':
    main()
