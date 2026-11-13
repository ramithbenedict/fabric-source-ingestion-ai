"""As-is (DPV1) and to-be (Fabric) trees of a migration scope, built from the migration map.

Used by frame_scope.py (markdown, ```text blocks in 01-scope-analysis.md and 03-target-design-and-plan.md) and by
refresh_hub.py (the hub mapper renders the same lines as a dark tree). One source, two renderings.

A tree is a list of lines: (prefix, name, kind, comment)
  kind: 'root' | 'dir' | 'item' | 'gone' (not migrated) | 'more' (truncated)
"""
import os, re

MAX_LEAVES = 6
ICON = {'translate': '🟢', 'rebuild': '🟢', 'reuse': '🟢', 'rewrite': '🟢', 'merge': '🔵', 'collapse': '🔵', 'inline': '🔵', 'replace': '🟣',
        'upstream': '⚪', 'product': '⚪', 'shared': '⚪', 'drop': '🔴', 'review': '🟠'}
GONE = {'drop', 'upstream', 'product', 'shared', 'review'}


def _insert(tree, path, comment, kind):
    node = tree
    for part in path[:-1]:
        node = node.setdefault(part + '/', {})
    leaf = node.setdefault(path[-1], {'__leaf__': [kind, []]})
    if '__leaf__' in leaf and comment and comment not in leaf['__leaf__'][1]:
        leaf['__leaf__'][1].append(comment)


def _lines(node, prefix=''):
    keys = sorted(node, key=lambda k: (not k.endswith('/'), k.lower()))
    dirs = [k for k in keys if k.endswith('/')]
    leaves = [k for k in keys if not k.endswith('/')]
    shown = dirs + leaves[:MAX_LEAVES]
    hidden = len(leaves) - len(leaves[:MAX_LEAVES])
    out = []
    for i, k in enumerate(shown):
        last = i == len(shown) - 1 and not hidden
        branch, cont = ('└── ', '    ') if last else ('├── ', '│   ')
        if k.endswith('/'):
            child = node[k]
            n = _count(child)
            out.append((prefix + branch, k, 'dir', f'{n} object{"s" if n != 1 else ""}' if n > 1 else ''))
            out += _lines(child, prefix + cont)
        else:
            kind, comments = node[k]['__leaf__']
            text = ' · '.join(comments[:3]) + (f' · +{len(comments) - 3} more' if len(comments) > 3 else '')
            out.append((prefix + branch, k, kind, text.replace(' · ← ', ', ')))
    if hidden:
        out.append((prefix + '└── ', f'… +{hidden} more', 'more', ''))
    return out


def _count(node):
    return sum(_count(v) if k.endswith('/') else 1 for k, v in node.items())


def _short(v2):
    v2 = re.sub(r'\s*\(.*?\)\s*$', '', v2 or '')
    if '=> ' in v2:
        return v2.split('=> ')[-1].strip()
    return v2.split('/')[-1].split(': ')[-1].strip() or '-'


def as_is(S, O, kind):
    """DPV1 tree: where each object lives in the Synapse export, with what happens to it."""
    tree = {}
    for r in S['rows']:
        t, n = r['v1t'], r['v1']
        if t == 'Pipeline':
            path = ['pipeline'] + [p for p in (O['pipeline'].get(n, {}).get('folder') or '').split('/') if p] + [n]
        elif t == 'Notebook':
            path = ['notebook'] + [p for p in (O['notebook'].get(n, {}).get('folder') or '').split('/') if p] + [n]
        elif t == 'Source table':
            path = ['ADLS data (catalog tables)', n.split('.')[0], n.split('.')[-1]]
        elif t.startswith('SQL ') and t != 'SQL script':
            schema, obj = (n.split('.', 1) + [''])[:2] if '.' in n else ('dbo', n)
            path = ['dedicated pool', schema, t[4:] + 's', obj]
        else:
            path = [{'Linked service': 'linkedService', 'Dataset': 'dataset', 'Trigger': 'trigger', 'SQL script': 'sqlscript', 'Data flow': 'dataflow'}.get(t, t), n]
        a = r['a']
        _insert(tree, path, f"{ICON.get(a, '⚫')} {a}" + ('' if a in ('drop',) or r['v2'] in ('-', '') else f" → {_short(r['v2'])}"), 'gone' if a == 'drop' else 'item')
    root = f"DPV1 · {S['scope']} ({'source dataset' if kind == 'sds' else 'data product'})"
    return [('', root + '/', 'root', f'{len(S["rows"])} objects')] + _lines(tree)


def layout(kind, scope, S=None):
    """Folder organisation DPV1 uses for raw (parquet) and delta, read from the legacy code of the scope: the extracted copy in
    2-legacy-code/, else the DPV1 export files of its pipelines and notebooks (S given). Fabric follows it: date tree
    (<yyyy>/<mm>/<dd>) and HISTORY / DELETE_LOGS subfolders only where DPV1 has them; otherwise one folder per table."""
    import json
    from common import project_dir, walk_files, read_text, read_json, exists, paths
    code = project_dir(kind, scope, '2-legacy-code')
    L = {'raw_dates': False, 'history': False, 'delete_logs': False, 'delta_dates': False, 'found': False}
    if kind != 'sds':
        return L
    if exists(code):
        text = ''.join(read_text(p, 'replace') for p in walk_files(code, exts=('.py', '.json', '.sql')))
    elif S:
        root, parts = paths()['dpv1_export_root'], []
        for n in S.get('pipelines', []):
            f = os.path.join(root, 'pipeline', n + '.json')
            if exists(f):
                parts.append(json.dumps(read_json(f), indent=1))
        for n in S.get('notebooks', []):
            f = os.path.join(root, 'notebook', n + '.json')
            if exists(f):
                parts.append('\n'.join(''.join(c.get('source', [])) for c in read_json(f)['properties'].get('cells', []) if c.get('cell_type') == 'code'))
        text = '\n'.join(parts)
    else:
        return L
    if not text:
        return L
    L['found'] = True
    raw = re.search(r'(PARQUET|RAW)[^\n]{0,200}(year|yyyy|DeltaPath|%Y)', text) is not None
    L['raw_dates'] = raw
    L['history'] = "'HISTORY'" in text or '/HISTORY' in text or 'HISTORY/' in text
    L['delete_logs'] = 'DELETE_LOGS' in text
    L['delta_dates'] = re.search(r'(CLEANSED|DELTA)[^\n]{0,200}(DeltaPath|year|yyyy)', text) is not None
    return L


def to_be(S, kind, catalog=None, O=None):
    """Fabric tree: workspace, folders and items, each with the DPV1 objects it replaces."""
    tree, gone = {}, {}
    ws = S['ws']
    for r in S['rows']:
        a, v2, v1 = r['a'], r['v2'] or '', r['v1']
        if a in GONE:
            gone.setdefault(a, []).append(v1)
            continue
        if r['v2t'] == 'Connection':
            path = ['Fabric connections (tenant)', v2.split(' (')[0]]
        elif r['v2t'] == 'Catalog view':
            cw = (catalog or {}).get('warehouse', 'WH_CATALOG_<SOURCE>').replace('<SOURCE>', S.get('folder', S['scope']).upper())
            path = [ws, cw, (catalog or {}).get('schema', 'CATALOG'), f"{S.get('folder', S['scope']).lower()}_catalog (view)"]
        elif kind == 'sds' and r['v1t'] == 'Source table':
            tbl = v2.split('=> ')[-1]
            path = [ws, S['folder'], S['lakehouse'], 'Tables', tbl]
        elif r['v1t'] == 'Trigger':
            path = [ws, S.get('folder', ''), '0-ORCHESTRATION', f"{_short(v2.replace('Schedule on ', ''))} (schedule)"] if kind == 'sds' else [ws, 'ORCHESTRATION', f"{_short(v2.replace('Schedule on ', ''))} (schedule)"]
        elif re.match(r'^(0-ORCHESTRATION|1-SOURCE_TO_RAW|2-RAW_TO_DELTA)/', v2):
            path = [ws, S.get('folder', '')] + v2.split('/')
        elif v2.startswith('ORCHESTRATION/'):
            path = [ws] + re.sub(r'\s*\(.*\)$', '', v2).split('/')
        elif kind == 'dp' and v2.startswith(S.get('dbproject', '~') + '/'):
            parts = [p for p in v2.split('/') if p]
            path = ['database-projects'] + parts
        elif r['v2t'] in ('OneLake', 'Pipeline activity', '-', 'Warehouse'):
            continue
        else:
            path = ['other targets', _short(v2)]
        path = [p for p in path if p]
        _insert(tree, path, f'← {v1}', 'item')
    if kind == 'sds':
        lh = tree.setdefault(ws + '/', {}).setdefault(S['folder'] + '/', {}).setdefault(S['lakehouse'] + '/', {})
        files = lh.setdefault('Files/', {})
        L = layout(kind, S['scope'], S)
        src = S['folder'].lower()
        part = '/<yyyy>/<mm>/<dd>/<HHhMM>'
        sub = [x for x, on in (('HISTORY', L['history']), ('DELETE_LOGS', L['delete_logs'])) if on]
        method = 'structured'
        if O is not None:
            import ingestion
            method = ingestion.source_kind(S, O)[2]
        if method == 'structured':  # database: parquet written once by the Copy, no landing
            raw = f"raw/{src}/<table>" + (part if L['raw_dates'] else '')
            files.setdefault(raw, {'__leaf__': ['item', ['parquet' + (', a folder per run as in DPV1' if L['raw_dates'] else ', overwritten at each run')]]})
            for x in sub:
                files.setdefault(f"{raw}/{x}", {'__leaf__': ['item', ['parquet, as DPV1' + (' (delete log of the target table)' if x == 'DELETE_LOGS' else ' (history table)')]]})
        else:  # API or files: the run folder holds every table as delivered, then parquet per table
            files.setdefault(f"landing/{src}{part}", {'__leaf__': ['item', ['all tables of the run, as delivered (json, csv, xml, xlsx)']]})
            files.setdefault(f"raw/{src}{part}/<table>", {'__leaf__': ['item', ['parquet, written by the notebook']]})
        if L['delta_dates']:
            lh.setdefault('Tables/', {}).setdefault('dbo/', {}).setdefault('<table>/<yyyy>/<mm>/<dd>', {'__leaf__': ['item', ['delta, date tree as DPV1']]})
    else:
        for u in S.get('upstream', []):
            _insert(tree, [ws, f"LH_INP_SDS_{u.replace('-', '_')}", 'shortcuts'], f"→ LH_SDS_{u.replace('-', '_')} tables (no copy)", 'item')
        _insert(tree, [ws, S.get('warehouse', 'WH_DPG')], f"database project {S.get('dbproject', '')}", 'item')
    _insert(tree, [ws, 'VL_MAIN'], 'DEV · UAT · PRD', 'item')
    lines = [('', 'Fabric · DPV2/', 'root', '')] + _lines(tree)
    if gone:
        lines.append(('', 'Not migrated here/', 'root', ''))
        labels = {'drop': 'not migrated (rule or owner decision)', 'upstream': 'Source Dataset Migration', 'product': 'Data Product Migration', 'shared': 'shared framework', 'review': 'waiting for a decision'}
        keys = list(gone)
        for i, a in enumerate(keys):
            names = gone[a]
            lines.append(('└── ' if i == len(keys) - 1 else '├── ', f"{ICON.get(a, '')} {labels[a]}", 'gone', f"{len(names)}: {', '.join(names[:4])}{' …' if len(names) > 4 else ''}"))
    return lines


def to_text(lines, width=None):
    width = width or min(64, max(len(p) + len(n) for p, n, _, _ in lines) + 2)
    return '\n'.join((p + n).ljust(width) + (f'  # {c}' if c else '') if c else p + n for p, n, _, c in lines)
