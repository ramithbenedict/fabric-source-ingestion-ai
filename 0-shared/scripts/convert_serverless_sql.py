"""wf-3 D2: turn the serverless modeling code of DPV1 (INP, LDW and OUT) and the dedicated-pool loaders into Fabric Warehouse T-SQL files.

Usage (from the repository root, after extract_scope_code.py --service dp):
  python -I 0-shared/scripts/convert_serverless_sql.py --id GAIA

Reads 2-legacy-code/embedded-sql/ and the source dataset contracts. Writes 3-build/_work/d2-converted-sql/ (one .sql per object, input of
dacpac_retarget.py --flat) and the D2 section of build-notes.md. What it does:
  - LDW and OUT procedures SP_CREATE_[<n>_]<NAME> whose body is the view's SELECT  =>  CREATE VIEW [ldw|out].[<NAME>]   (the DPV1 pipelines did this at run time)
  - CREATE VIEW [LDW|OUT].[x] written as views already                             =>  kept
  - every INP_<x>.<TABLE>_VW or INP_<x>.<TABLE> read                              =>  [LH_INP_SDS_<SRC>].[dbo].[<table>] from the contracts (a read with no contract table is reported and stops the stage)
  - SP_TRAN_<table> loaders (TRUNCATE + INSERT ... SELECT FROM [STG_x].[<table>])  =>  the same procedure reading [out].[<table>_VW]: column lists, fact key lookups
    and -1 defaults stay as DPV1 had them; the STG tables, the curated parquet copy and SP_EXEC_SP_ALIM_DW_TABLES are dropped
  - DW and DM tables                                                              =>  kept (K3 removes DISTRIBUTION, indexes and fixes types)
Nothing is invented: a view with ORDER BY, a construct Fabric lacks or a name that maps to nothing is listed for the developer.
"""
import argparse, collections, glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, load_map, resolve_scope, write, write_note, track_event, project_dir, read_text, exists

PROC_VIEW = re.compile(r'^\s*CREATE\s+PROC(?:EDURE)?\s+\[?(LDW|OUT)\]?\.\[?SP_CREATE_(?:(\d+)_)?(\w+?)\]?\s*(?:AS)?\s*$', re.I | re.M)
INP_REF = re.compile(r'(?<![A-Za-z0-9_])\[?(INP_\w+)\]?\.\[?(\w+?)(?:_VW)?\]?(?![\w\]])', re.I)
DROPPED = (('sp_exec_sp_alim_dw_tables', 'dynamic EXEC of a loader by name: the pipeline calls each loader'), ('sp_create_spot_view', 'creates INP views over SPOT: replaced by LH_INP_SDS shortcuts'),
           ('sp_meta_create_inp_view', 'creates INP views over SPOT: replaced by LH_INP_SDS shortcuts'))


TABLE_OPTIONS = re.compile(r'\)\s*WITH\s*\((?:\s|,|DISTRIBUTION\s*=\s*\w+(?:\s*\([^)]*\))?|HEAP|CLUSTERED\s+COLUMNSTORE\s+INDEX|CLUSTERED\s+INDEX\s*\([^)]*\)|PARTITION\s*\([^)]*\))+\)', re.I)
ROWVERSION_COL = re.compile(r'(\[?RowVersion\]?\s+)\[?datetime2?\]?(?:\s*\(\s*\d\s*\))?(?=\s*(?:NOT\s+NULL|NULL|,|\)|$))', re.I | re.M)
ROWVERSION_CAST = re.compile(r'CAST\(\s*(\[?RowVersion\]?)\s+AS\s+\[?datetime2?\]?(?:\s*\(\s*\d\s*\))?\s*\)', re.I)
K3_RULES = (('DISTRIBUTION / HEAP / indexes removed', None), ('RowVersion datetime => varbinary(8) (column)', ROWVERSION_COL), ('RowVersion datetime => varbinary(8) (CAST)', ROWVERSION_CAST),
            ('NVARCHAR => VARCHAR, NCHAR => CHAR', re.compile(r'\bN(VARCHAR|CHAR)\b', re.I)),
            ('DATETIME => DATETIME2(6)', re.compile(r'\bDATETIME\b(?!\s*2)', re.I)), ('MONEY => DECIMAL(19,4)', re.compile(r'\bMONEY\b', re.I)),
            ('IDENTITY removed (the values come from the source)', re.compile(r'\s+IDENTITY\s*\(\s*\d+\s*,[ ]*\d+\s*\)', re.I)),
            ('DATETIME2 / TIME / DATETIMEOFFSET (7) => (6)', re.compile(r'\b(datetime2|datetimeoffset|time)(\s*\(\s*)7(\s*\))', re.I)))


def k3_fix(sql, counts):
    """The deterministic fixes of wf-4 K3 (the lint rules DISTRIBUTION, HEAP_CCI, NVARCHAR, DATETIME, MONEY): same text otherwise."""
    sql, n = TABLE_OPTIONS.subn(')', sql)
    counts[K3_RULES[0][0]] += n
    for label, rx in K3_RULES[1:]:
        repl = {'NVARCHAR => VARCHAR, NCHAR => CHAR': lambda m: m.group(1).upper() if m.group(1).isupper() else m.group(1).lower(), 'DATETIME => DATETIME2(6)': lambda m: 'DATETIME2(6)' if m.group(0).isupper() else 'datetime2(6)',
                'MONEY => DECIMAL(19,4)': lambda m: 'DECIMAL(19,4)', 'IDENTITY removed (the values come from the source)': lambda m: '',
                'RowVersion datetime => varbinary(8) (column)': lambda m: m.group(1) + 'varbinary(8)',  # a SQL Server rowversion is binary: the Lakehouse holds varbinary and Fabric cannot read it as a date (error 241)
                'RowVersion datetime => varbinary(8) (CAST)': lambda m: f'CAST({m.group(1)} AS varbinary(8))',
                'DATETIME2 / TIME / DATETIMEOFFSET (7) => (6)': lambda m: f'{m.group(1)}{m.group(2)}6{m.group(3)}'}[label]  # Fabric Warehouse: precision 0 to 6 (Msg 24597)
        sql, n = rx.subn(repl, sql)
        counts[label] += n
    return sql


LH_READ = re.compile(r'(?<![A-Za-z0-9_])\[?(LH_INP_SDS_(\w+?))\]?\.\[?dbo\]?\.\[?(\w+)\]?', re.I)


def build_input_layer(files, write_view):
    """The input layer of a database project (convention database-project-structure.md, as DPG-ECV): the Lakehouse is read in one place, the views
    [INP_<SRC>].[<table>] over [LH_INP_SDS_<SRC>].[dbo].[<table>]. Every other file reads [INP_<SRC>].[<table>]: renaming or moving a Lakehouse touches
    these views only, and the DPV1 INP_<SRC> names stay. files: the .sql files to rewrite; write_view(src, table, lakehouse, text): writes one input view.
    Returns the number of input views."""
    pairs = collections.OrderedDict()
    for f in files:
        t = open(f, encoding='utf-8').read()

        def one(m):
            pairs[(m.group(1), m.group(2).upper(), m.group(3).lower())] = 1
            return f'[INP_{m.group(2).upper()}].[{m.group(3).lower()}]'
        new = LH_READ.sub(one, t)
        if new != t:
            write(f, new)
    for lh, src, tbl in pairs:
        write_view(src, tbl, lh, f'-- Input layer [INP_{src}]: the only place that reads {lh}; the other objects read [INP_{src}].[{tbl}]\n'
                                f'CREATE VIEW [INP_{src}].[{tbl}]\nAS\nSELECT *\nFROM [$({lh})].[dbo].[{tbl}];\n')  # SQLCMD variable: the Lakehouse name is set per environment by the DACPAC pipeline
    return len(pairs)


def table_columns(sql):
    """Column names of a CREATE TABLE (first parenthesis, top-level commas)."""
    i = sql.find('(')
    if i < 0:
        return []
    depth, j, parts, cur = 0, i, [], ''
    for ch in sql[i:]:
        if ch == '(':
            depth += 1
            if depth == 1:
                continue
        elif ch == ')':
            depth -= 1
            if depth == 0:
                break
        if ch == ',' and depth == 1:
            parts.append(cur)
            cur = ''
        else:
            cur += ch
    parts.append(cur)
    cols = []
    for p in parts:
        m = re.match(r'\s*\[?(\w+)\]?\s+\[?\w+', p)
        if m and m.group(1).upper() not in ('CONSTRAINT', 'PRIMARY', 'UNIQUE', 'INDEX', 'FOREIGN', 'CHECK'):
            cols.append(m.group(1))
    return cols


def add_loaders(out, notes, stats, keep_dw):
    """Copy-through products (DPV1 loaded the pool with Copy activities, no SP_TRAN procedure): one set-based load per table, TRUNCATE + INSERT ... SELECT
    from the OUT view of the same name. When a product has the same table in a DW and a DM schema, only the DM table is loaded (the DW copy is dropped) unless keep_dw."""
    files = {os.path.basename(f)[:-4]: f for f in glob.glob(os.path.join(out, '*.sql'))}
    has_loader = set()  # tables a DPV1 loader already fills: read from its INSERT INTO (the procedure name does not always match: SP_TRAN_ITEM_DIM_DIM fills ITEM_DIM)
    for n, f in files.items():
        if '.sp_tran_' in n:
            t = re.search(r'INSERT\s+INTO\s+\[?\w+\]?\.\[?(\w+)\]?', open(f, encoding='utf-8').read(), re.I)
            has_loader.add(t.group(1).lower() if t else re.sub(r'^sp_tran_', '', n.split('.', 1)[1]))
    views = {}
    for n in files:
        sch, _, name = n.partition('.')
        if sch.startswith('out'):
            views[re.sub(r'_vw$', '', name)] = (sch, name)
    tables = {}
    for n, f in files.items():
        sch, _, name = n.partition('.')
        if re.match(r'^(dw|dm)', sch) and '.sp_' not in n and name not in has_loader and not name.startswith('sp_'):
            tables.setdefault(name, []).append((sch, n, f))
    for name, hits in sorted(tables.items()):
        if name not in views:
            continue
        layers = sorted(hits)
        dm = [h for h in layers if h[0].startswith('dm')]
        if len(layers) > 1 and dm and not keep_dw:
            for h in layers:
                if h not in dm:
                    os.remove(h[2])
                    notes['dw_dropped'].append(h[1])
            layers = dm
        for sch, n, f in layers:
            cols = table_columns(re.sub(r'(?is)^(?:--[^\n]*\n)+', '', open(f, encoding='utf-8').read()).split('CREATE TABLE', 1)[-1])
            if not cols:
                notes['no_columns'].append(n)
                continue
            vs, vn = views[name]
            col = ',\n        '.join(f'[{c}]' for c in cols)
            body = (f"-- loader: DPV1 copied the OUT view to STG, then to the table with Copy activities; one set-based load from the OUT view here\n"
                    f"CREATE PROCEDURE [{sch}].[SP_LOAD_{name.upper()}]\nAS\nBEGIN\n    TRUNCATE TABLE [{sch}].[{name.upper()}];\n    INSERT INTO [{sch}].[{name.upper()}]\n    (\n        {col}\n    )\n"
                    f"    SELECT\n        {col}\n    FROM [{vs}].[{vn}];\nEND\n")
            write(os.path.join(out, f'{sch}.sp_load_{name}.sql'), body)
            stats['copy_loaders'] += 1


def contract_tables(upstream):
    """{lower table name: (source, 'dbo.<name>')} of every upstream source dataset contract."""
    import source_contract
    out = {}
    for u in upstream:
        c = source_contract.load(u)
        for t in (c or {}).get('tables', []):
            n = t['fabric'].split('.', 1)[1]
            out.setdefault(n, (u, c['input_lakehouse']))
    return out


NOT_ALIAS = {'WHERE', 'ON', 'LEFT', 'RIGHT', 'INNER', 'FULL', 'CROSS', 'OUTER', 'JOIN', 'GROUP', 'ORDER', 'UNION', 'HAVING', 'WITH', 'EXCEPT', 'INTERSECT', 'OPTION', 'FOR', 'SELECT', 'AS'}
FROM_REF = re.compile(r'(\b(?:FROM|JOIN)\s+)\[?(INP_\w+)\]?\.\[?(\w+?)(?:_VW)?\]?(?![\w\]\.])(\s+(?:AS\s+)?\[?(\w+)\]?)?', re.I)
QUALIFIER = re.compile(r'(?<![A-Za-z0-9_])\[?(INP_\w+)\]?\.\[?(\w+?)(?:_VW)?\]?\.(?=\[?\w)', re.I)


def rewrite_inputs(body, tables, unmapped):
    """INP_<x>.<TABLE>[_VW] => [LH_INP_SDS_<SRC>].[dbo].[<table>]. A table read without alias gets its DPV1 name as alias, and a column qualified by that
    name (INP_<x>.<TABLE>.<col>) keeps working: [<TABLE>].<col>."""
    def hit(sch, name):
        n = name.lower()
        h = tables.get(n) or tables.get(n + '_vw')
        if not h:
            unmapped[f'{sch}.{name}'] += 1
        return n, h

    def from_ref(m):
        n, h = hit(m.group(2), m.group(3))
        if not h:
            return m.group(0)
        target = f'{m.group(1)}[{h[1]}].[dbo].[{n}]'
        if m.group(5) and m.group(5).upper() not in NOT_ALIAS:  # the table already has an alias: keep it
            return target + m.group(4)
        return f'{target} AS [{m.group(3)}]' + (m.group(4) or '')  # no alias: the DPV1 name becomes the alias (the text after it, a keyword, stays)
    body = FROM_REF.sub(from_ref, body)
    body = QUALIFIER.sub(lambda m: f'[{m.group(2)}].', body)  # INP_x.TABLE.col => [TABLE].col (the alias given above)
    return INP_REF.sub(lambda m: (lambda n_h: f'[{n_h[1][1]}].[dbo].[{n_h[0]}]' if n_h[1] else m.group(0))(hit(m.group(1), m.group(2))), body)  # any other read


def view_from_proc(kind, name, text):
    """CREATE VIEW from the body of a SP_CREATE_* procedure: everything after the header line (AS)."""
    m = PROC_VIEW.search(text)
    body = text[m.end():].strip() if m else text
    body = re.sub(r"\n\s*'\s*$", '', body).rstrip().rstrip(';')
    return f'CREATE VIEW [{kind.lower()}].[{name}]\nAS\n{body}\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--id', required=True)
    ap.add_argument('--parallel', action='store_true')
    ap.add_argument('--keep-dw', action='store_true', help='copy-through product with the same table in a DW and a DM schema: load both (default: DM only, the DW copy is dropped)')
    ap.add_argument('--no-k3', action='store_true', help='keep DISTRIBUTION, HEAP, NVARCHAR, DATETIME as they are (K3 then fixes them)')
    a = ap.parse_args()
    m = load_map()
    scope, _ = resolve_scope(m, 'dp', a.id)
    D = m['dp'][scope]
    import track
    track.ensure_single_active(scope, 'dp', a.parallel)
    import source_contract
    source_contract.require_sources(scope)
    src = os.path.join(project_dir('dp', scope), '2-legacy-code', 'embedded-sql')
    if not os.path.isdir(src):
        sys.exit(f'{scope}: no 2-legacy-code/embedded-sql: run extract_scope_code.py --service dp --id {scope} first')
    out = os.path.join(project_dir('dp', scope), '3-build', '_work', 'd2-converted-sql')
    for f in glob.glob(os.path.join(out, '*.sql')):
        os.remove(f)
    tables, unmapped = contract_tables(D['upstream']), collections.Counter()
    stats, notes, k3 = collections.Counter(), collections.defaultdict(list), collections.Counter()
    for f in sorted(glob.glob(os.path.join(src, '*.sql'))):
        base = os.path.basename(f)
        text = read_text(f, 'replace')
        stem = base[:-4].lower()
        if any(d in stem for d, _ in DROPPED):
            notes['dropped'].append(f"{stem}: {next(w for d, w in DROPPED if d in stem)}")
            stats['dropped'] += 1
            continue
        head = text.split('\n', 3)
        comment = '\n'.join(l for l in head[:2] if l.startswith('--'))
        pm = PROC_VIEW.search(text)
        if pm:  # SP_CREATE_<n>_<NAME>: the body is the view
            kind, idx, name = pm.group(1).lower(), pm.group(2), pm.group(3)
            sql = view_from_proc(kind, name, text)
            stats[f'{kind}_views'] += 1
            if re.search(r'\bORDER\s+BY\b(?![^()]*\))', sql, re.I):
                notes['order_by'].append(f'{kind}.{name}')
            out_name, tag = f'{kind}.{name.lower()}.sql', f'-- view {kind}.{name} (was procedure SP_CREATE_{(idx + "_") if idx else ""}{name}' + (f', batch {idx}' if idx else '') + ')'
        elif re.match(r'^\s*(?:--.*\n|\s)*CREATE\s+PROC(?:EDURE)?\s+\[?dw_\w+\]?\.\[?SP_TRAN_', text, re.I):  # loader: staging table => OUT view
            sql = re.sub(r'\[?STG_\w+\]?\.\[?(\w+)\]?', lambda x: f'[out].[{x.group(1)}_VW]', re.sub(r'(?i)CREATE\s+PROC\b', 'CREATE PROCEDURE', text.split('\n', 3)[-1] if text.startswith('--') else text))
            stats['loaders'] += 1
            out_name, tag = base.lower(), '-- loader: STG table replaced by the OUT view (DPV1 SP_TRAN_*)'
            stats['fact_loaders' if re.search(r'_fact\b', stem) else 'dim_loaders'] += 1
        else:  # tables and anything else: kept
            sql = text.split('\n', 3)[-1] if text.startswith('--') else text
            out_name, tag = base.lower(), comment.split('\n')[0] if comment else ''
            stats['kept'] += 1
        sql = rewrite_inputs(sql, tables, unmapped)
        if not a.no_k3:
            sql = k3_fix(sql, k3)
        write(os.path.join(out, out_name), (tag + '\n' if tag else '') + sql.strip() + '\n')
    add_loaders(out, notes, stats, a.keep_dw)
    stats['input_views'] = build_input_layer(sorted(glob.glob(os.path.join(out, '*.sql'))), lambda s, t, lh, text: write(os.path.join(out, f'inp_{s.lower()}.{t}.sql'), text))
    procs = [m.group(1) for f in sorted(glob.glob(os.path.join(out, '*.sql'))) for m in [re.search(r'CREATE\s+PROCEDURE\s+(\[?\w+\]?\.\[?\w+\]?)', open(f, encoding='utf-8').read(), re.I)] if m]
    order = {'batches': [{'name': 'dimensions', 'run': 'parallel', 'procedures': [p for p in procs if not re.search(r'_fact\]?$', p, re.I)]},
                         {'name': 'facts', 'run': 'parallel, after the dimensions (fact loaders look up the dimension keys)', 'procedures': [p for p in procs if re.search(r'_fact\]?$', p, re.I)]}]}
    write(os.path.join(project_dir('dp', scope), '3-build', '_work', 'd2-load-order.json'), json.dumps(order, indent=1) + '\n')
    for k, v in sorted(unmapped.items()):
        notes['unmapped'].append(f'{k} ({v} reads)')
    L = [f'# D2 Serverless modeling to Warehouse T-SQL: {scope}', '', f"- **Input**: `2-legacy-code/embedded-sql/` ({sum(stats.values())} objects), contracts of {', '.join(D['upstream']) or 'none'} ({len(tables)} tables)",
         f"- **Output**: `3-build/_work/d2-converted-sql/`: {stats['ldw_views']} LDW views, {stats['out_views']} OUT views written as procedures, {stats['loaders']} DPV1 loaders rewritten ({stats['dim_loaders']} dimensions, {stats['fact_loaders']} facts), {stats['copy_loaders']} copy-through loads generated, {stats['input_views']} input views [INP_<SRC>] over the Lakehouse tables, {stats['kept']} objects kept (tables, views), {stats['dropped']} dropped",
         '- **Next**: `dacpac_retarget.py --flat 3-build/_work/d2-converted-sql ...` places them in the database project; `tsql_fabric_lint.py` finds what Fabric does not support (K3).', '']
    if k3:
        L += ['## Fabric fixes applied (wf-4 K3, mechanical)', ''] + [f'- {k}: {v}' for k, v in k3.items() if v] + ['']
    if notes['dropped']:
        L += ['## Dropped (replaced, not migrated)', ''] + [f'- {x}' for x in notes['dropped'][:6]] + ([f"- ... {len(notes['dropped'])} in all"] if len(notes['dropped']) > 6 else []) + ['']
    if notes['dw_dropped']:
        L += ['## DW copy dropped (copy-through)', '', f"{len(notes['dw_dropped'])} DW tables are identical copies of the DM tables in DPV1 (OUT => STG => DW => DM): only the DM tables are loaded, from the OUT views. Run with `--keep-dw` to keep both (framing question Q06: does anything read the DW tables?).", '']
    if notes['no_columns']:
        L += ['## Tables without a readable column list (no loader generated)', ''] + [f'- `{x}`' for x in notes['no_columns']] + ['']
    if notes['order_by']:
        L += ['## Views with ORDER BY (not allowed in a view without TOP)', ''] + [f'- `{x}`' for x in notes['order_by']] + ['']
    if notes['unmapped']:
        L += ['## ❌ Reads with no source dataset table', '', 'The source dataset contract has no table for these reads: add them to the source dataset (framing question Q21) or write the mapping, then run this step again.', ''] + [f'- `{x}`' for x in notes['unmapped']] + ['']
    write_note('dp', scope, 'D2-translation', '\n'.join(L) + '\n')
    track_event(scope, 'dp', 'D2', f"Serverless modeling converted: {stats['ldw_views'] + stats['out_views']} views, {stats['loaders']} loaders, {len(notes['unmapped'])} unmapped reads", 'change')
    print(f"{scope}: {stats['ldw_views']} LDW + {stats['out_views']} OUT views from procedures, {stats['loaders']} loaders rewritten ({stats['dim_loaders']} dim, {stats['fact_loaders']} fact), {stats['copy_loaders']} copy-through loads, {stats['kept']} kept, {stats['dropped']} dropped, "
          f"{len(notes['unmapped'])} unmapped reads, {len(notes['order_by'])} views with ORDER BY => {os.path.relpath(out, ROOT)}")
    sys.exit(2 if notes['unmapped'] else 0)


if __name__ == '__main__':
    main()
