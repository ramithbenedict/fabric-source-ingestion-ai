"""Answer lists for the five framing questions (F1), so the developer selects instead of typing.

Each command prints a lettered list, the recommended option first, then "Z) Other". Agents show it as the question.

  python -I 0-shared/scripts/framing_menu.py service
  python -I 0-shared/scripts/framing_menu.py domain    [--source EASYTENDER]      # from 2-config/conventions/01-general/domains.md
  python -I 0-shared/scripts/framing_menu.py source    --domain CONST             # sources of that domain in the hub, not started first
  python -I 0-shared/scripts/framing_menu.py workspace --service sds --domain CONST
  python -I 0-shared/scripts/framing_menu.py repo                                 # deployment repositories found next to this repository
  python -I 0-shared/scripts/framing_menu.py catalog   --workspace Platform-Hub    # sixth question (source dataset): common catalog warehouse

Domain codes keep only A-Z, 0-9 and _ (P&C => PC, S&M => SM, T&I => TI): the list shows both.
"""
import argparse, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, paths, read_json, exists, read_text

LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXY'


def clean(code):
    return re.sub(r'[^A-Z0-9_]', '', code.upper())


def domains():
    """[(name, code, owner)] from the domain directory of the conventions."""
    rows = []
    for line in read_text(os.path.join(ROOT, '2-config', 'conventions', '01-general', 'domains.md')).splitlines():
        c = [x.strip() for x in line.strip().strip('|').split('|')]
        if len(c) >= 3 and line.startswith('|') and c[1] and not set(c[1]) <= {'-'} and c[0] != 'Domain Name':
            rows.append((c[0], c[1], c[2]))
    return rows


def hub_scope(kind, name):
    p = os.path.join(paths()['hub_root'], 'knowledge', kind, f'{name.lower()}.json')
    return read_json(p)['scope'] if exists(p) else None


def show(question, options, recommended=None, note=''):
    """options: [(label, detail)]; recommended: index or None (moved first)."""
    opts = list(options)
    if recommended is not None:
        opts.insert(0, opts.pop(recommended))
    lines = [question] + ([note] if note else [])
    for i, (lab, det) in enumerate(opts):
        lines.append(f"  {LETTERS[i]}) {lab}" + (f' - {det}' if det else '') + (' (recommended)' if recommended is not None and i == 0 else ''))
    lines.append('  Z) Other (please specify)')
    print('\n'.join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['service', 'domain', 'source', 'workspace', 'repo', 'catalog', 'catalog-workspace'])
    ap.add_argument('--source')
    ap.add_argument('--workspace', help='workspace folder (catalog): warehouses already in the deployment repo are offered')
    ap.add_argument('--repo', help='deployment repository path (catalog)')
    ap.add_argument('--domain')
    ap.add_argument('--service', choices=['sds', 'dp'], default='sds')
    a = ap.parse_args()
    if a.cmd == 'service':
        show('Which service offering?', [('Source Dataset', 'build a source dataset and its lineage'), ('Data Product', 'build a data product (needs its source datasets migrated first)')])
    elif a.cmd == 'domain':
        rows = domains()
        rec, why = None, ''
        if a.source:
            S = hub_scope('sds', a.source)
            if S and S.get('domain'):
                rec = next((i for i, r in enumerate(rows) if clean(r[1]) == S['domain']), None)
                why = f"The hub suggests {S['domain']} for {a.source.upper()}" + ('' if S.get('domain_confirmed') else ' (not confirmed by an owner yet)')
        show('Which domain?', [(f"{n} ({c}{' => ' + clean(c) if clean(c) != c else ''})", f'owner {o}') for n, c, o in rows], rec, why)
    elif a.cmd == 'source':
        p = os.path.join(paths()['hub_root'], 'knowledge', 'index.json')
        idx = read_json(p)['sds'] if exists(p) else {}
        dom = clean(a.domain or '')
        mine = sorted(s for s, v in idx.items() if v.get('domain') == dom)
        opts = [(s, f"{idx[s]['objects']} objects, {idx[s]['catalog_tables']} catalog tables" + (', read by ' + ', '.join(x for x in idx[s]['read_by'] if x != s) if [x for x in idx[s]['read_by'] if x != s] else '')) for s in mine[:20]]
        show(f'Which source of {dom or "the domain"}?', opts, 0 if opts else None,
             f'Sources the hub places in {dom}. The hub domain is only a guess: a source not listed is typed under Other.' if opts else 'No source is placed in this domain by the hub: type the name.')
    elif a.cmd == 'catalog':
        have = []
        if a.repo and a.workspace and os.path.isdir(os.path.join(a.repo, a.workspace)):
            have = sorted(d[:-len('.Warehouse')] for d in os.listdir(os.path.join(a.repo, a.workspace)) if d.startswith('WH_CATALOG') and d.endswith('.Warehouse'))
        opts = [(w, 'already in the workspace: reuse it (same VL_MAIN CATALOG_WAREHOUSE_* values)') for w in have if w == 'WH_CATALOG_COMMON']
        opts += [('WH_CATALOG_COMMON', 'new common warehouse: the catalog views of every source of the workspace, one set of VL_MAIN parameters')] if not opts else []
        opts += [(w, 'already in the workspace') for w in have if w != 'WH_CATALOG_COMMON']
        opts.append(('None', 'own warehouse WH_CATALOG_<SOURCE> for this source (its own VL_MAIN parameters)'))
        show('Is there a common warehouse that can store the catalog views / tables of this source?', opts, 0,
             'Reusing one warehouse for catalog views, logs and references avoids recreating the same VL_MAIN parameters for every source.')
    elif a.cmd == 'catalog-workspace':
        ws = a.workspace or 'the target workspace'
        opts = [(a.workspace or 'Target workspace', 'same workspace as the source dataset: no extra workspace id in VL_MAIN')]
        if a.repo and os.path.isdir(a.repo):
            opts += [(d, 'workspace folder in the deployment repo that already holds a catalog warehouse') for d in sorted(os.listdir(a.repo))
                     if d != a.workspace and os.path.isdir(os.path.join(a.repo, d)) and any(x.startswith('WH_CATALOG') and x.endswith('.Warehouse') for x in os.listdir(os.path.join(a.repo, d)))]
        show(f'In which workspace is the catalog warehouse (other than {ws})?', opts, 0,
             'Give the real workspace name (with its environment, e.g. Platform-Hub_DEV): resolve_catalog.py reads the workspace, warehouse and SQL endpoint IDs from Fabric.')
    elif a.cmd == 'workspace':
        d = clean(a.domain or 'DOMAIN')
        base = f'DP_SDS_{d}' if a.service == 'sds' else f'DP_DPG_{d}'
        show('Which target workspace?', [(f'{base}_{e}', 'workspace folder in the deployment repo: ' + base) for e in ('DEV', 'UAT', 'PRD')], 0,
             'Convention: 2-config/conventions/02-fabric-workspace. The folder name is the workspace name without the environment suffix.')
    else:
        found = []
        for up in (os.path.abspath(os.path.join(ROOT, '..')), os.path.abspath(os.path.join(ROOT, '..', '..'))):
            for root, dirs, _ in os.walk(up):
                if root.count(os.sep) - up.count(os.sep) > 2:
                    dirs[:] = []
                    continue
                for d in list(dirs):
                    if d.upper() == 'REPO-FABRIC-DEPLOYMENT':
                        found.append(os.path.join(root, d))
                        dirs.remove(d)
        found = sorted(set(found))
        show('Where is the deployment repository?', [(f, 'found on this machine') for f in found], 0 if found else None,
             '' if found else 'None found next to this repository: type the full path.')


if __name__ == '__main__':
    main()
