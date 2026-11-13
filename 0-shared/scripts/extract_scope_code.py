"""Extract the full legacy code of one scope from the DPV1 export (read-only) into the project deliverables.

Usage (from the repository root):
  python -I 0-shared/scripts/extract_scope_code.py --service dp  --id GAIA
  python -I 0-shared/scripts/extract_scope_code.py --service sds --id GAIA

Writes 4-migration-project-deliverables/<source-dataset|data-product>/<PROJECT>/2-legacy-code/:
  pipelines/<name>.json      pipeline definitions as exported
  notebooks/<name>.py        code cells of Synapse notebooks
  dataflows/<name>.dfs       Mapping Data Flow scripts
  sqlscripts/<name>.sql      Synapse SQL scripts
  embedded-sql/<schema>.<object>.sql   T-SQL objects created inside pipeline Script activities, one per file
  legacy-code-index.md       what was extracted and from where
"""
import argparse, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, paths, load_map, resolve_scope, write, track_event, project_dir

CREATE = re.compile(r'CREATE\s+(?:OR\s+ALTER\s+)?(PROC(?:EDURE)?|VIEW|TABLE|FUNCTION|EXTERNAL\s+TABLE)\s+\[?(\w+)\]?\.\[?(\w+)\]?', re.I)


def load(kind, name):
    p = os.path.join(paths()['dpv1_export_root'], kind, name + '.json')
    return json.load(open(p, encoding='utf-8-sig')) if os.path.exists(p) else None


def walk(acts):
    for a in acts or []:
        yield a
        tp = a.get('typeProperties', {})
        for k in ('activities', 'ifTrueActivities', 'ifFalseActivities', 'defaultActivities'):
            yield from walk(tp.get(k))
        for c in tp.get('cases', []) or []:
            yield from walk(c.get('activities'))


def script_texts(pipeline):
    for a in walk(pipeline.get('properties', {}).get('activities')):
        for s in (a.get('typeProperties', {}).get('scripts') or []):
            t = s.get('text')
            t = t.get('value', '') if isinstance(t, dict) else (t or '')
            if t:
                yield a['name'], t


def split_objects(text):
    """Split a script into one statement per CREATE; unwrap EXEC sp_executesql N'...' quoting."""
    marks = [m for m in CREATE.finditer(text)]
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[m.start():end]
        body = re.split(r"\n\s*'\s*\n|\n\s*GO\s*\n|\n\s*EXEC\s+sp_executesql\s+N'", body, maxsplit=1, flags=re.I)[0]
        yield m.group(2).lower(), m.group(3).lower(), m.group(1).upper(), body.replace("''", "'").strip().rstrip("'").rstrip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--service', choices=['sds', 'dp'], required=True)
    ap.add_argument('--id', required=True)
    ap.add_argument('--parallel', action='store_true', help='allow a second project in progress (owner agreed)')
    a = ap.parse_args()
    m = load_map()
    scope, _ = resolve_scope(m, a.service, a.id)
    import track
    track.ensure_single_active(scope, a.service, a.parallel)
    if a.service == 'dp':  # a data product starts only when its source datasets are migrated
        import source_contract
        source_contract.require_sources(scope)
    S = (m['sds'] if a.service == 'sds' else m['dp'])[scope]
    out = project_dir(a.service, scope, '2-legacy-code')
    idx = {'pipelines': [], 'notebooks': [], 'dataflows': [], 'sqlscripts': [], 'embedded-sql': []}
    # only this service's objects: rows handled by the other service (product / upstream) stay with it
    other = {r['v1'] for r in S['rows'] if r['a'] in ('product', 'upstream')}
    pipes = [p for p in S['pipelines'] if p not in S['shared'] and p not in other]
    for n in pipes:
        j = load('pipeline', n)
        if not j:
            continue
        write(os.path.join(out, 'pipelines', n + '.json'), json.dumps(j, indent=1))
        idx['pipelines'].append(n)
        for act, text in script_texts(j):
            for s, o, k, body in split_objects(text):
                f = f'{s}.{o}.sql'
                write(os.path.join(out, 'embedded-sql', f), f'-- {k} {s}.{o}\n-- extracted from pipeline {n}, activity "{act}"\n\n{body}\n')
                idx['embedded-sql'].append((f, n, act))
    for n in [x for x in S['notebooks'] if x not in other]:
        j = load('notebook', n)
        if j:
            cells = j.get('properties', {}).get('cells', [])
            code = '\n\n# %% ----\n'.join(''.join(c.get('source', [])) for c in cells if c.get('cell_type') == 'code')
            write(os.path.join(out, 'notebooks', n + '.py'), f'# Synapse notebook {n} (code cells only)\n\n{code}\n')
            idx['notebooks'].append(n)
    for n in S['dataflows']:
        j = load('dataflow', n)
        if j:
            lines = j.get('properties', {}).get('typeProperties', {}).get('scriptLines', [])
            write(os.path.join(out, 'dataflows', n + '.dfs'), '\n'.join(lines) + '\n')
            idx['dataflows'].append(n)
    for n in [x for x in S['sqlscripts'] if x not in other]:
        j = load('sqlscript', n)
        if j:
            q = ((j.get('properties') or {}).get('content') or {}).get('query', '') or ''
            write(os.path.join(out, 'sqlscripts', n + '.sql'), q.replace('\r\n', '\n') + '\n')
            idx['sqlscripts'].append(n)
    L = [f'# {scope} · legacy code extracted from DPV1', '', f"Source: `{m['meta'].get('source_root', '')}`. Read-only copy; do not edit, translate into the stage folders instead.", '',
         f"- Pipelines: {len(idx['pipelines'])}", f"- Notebooks: {len(idx['notebooks'])}", f"- Data flows: {len(idx['dataflows'])}",
         f"- SQL scripts: {len(idx['sqlscripts'])}", f"- T-SQL objects embedded in pipelines: {len(idx['embedded-sql'])}",
         f"- Left to the other service (not copied): {', '.join('`' + x + '`' for x in sorted(other)) or 'none'}", '']
    if idx['embedded-sql']:
        L += ['## Embedded T-SQL objects', '', '| File | Pipeline | Activity |', '|---|---|---|'] + [f'| `embedded-sql/{f}` | `{p}` | {act} |' for f, p, act in idx['embedded-sql']]
    write(os.path.join(out, 'legacy-code-index.md'), '\n'.join(L) + '\n')
    track_event(scope, a.service, 'D1' if a.service == 'dp' else 'S2',
                f"Legacy code extracted: {len(idx['pipelines'])} pipelines, {len(idx['notebooks'])} notebooks, {len(idx['sqlscripts'])} SQL scripts, {len(idx['embedded-sql'])} embedded T-SQL objects")
    print(f"{scope}: {len(idx['pipelines'])} pipelines, {len(idx['notebooks'])} notebooks, {len(idx['sqlscripts'])} SQL scripts, "
          f"{len(idx['embedded-sql'])} embedded T-SQL objects → {os.path.relpath(out, ROOT)}")


if __name__ == '__main__':
    main()
