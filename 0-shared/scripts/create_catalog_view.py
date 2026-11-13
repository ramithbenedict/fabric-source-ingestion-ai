"""wf-2 S1: build the catalog view of one source dataset from its DPV1 catalog script, in the catalog warehouse.

DPV1 keeps one catalog script per source (sqlscript Catalog_<SOURCE>: CREATE TABLE [CATALOG].[<SOURCE>] + INSERT rows:
table list, full/incremental, active flag, watermark). This script reads it and writes:
  - the catalog warehouse item (Fabric Git format, SDK database project inside, as in skill-fabric-create-warehouse)
  - [CATALOG].[<source>_catalog] (e.g. geos_catalog): all the catalog details; columns from the DPV1 DDL (Fabric types), rows from the DPV1 INSERTs (VALUES)
    or, when catalog_database is configured, a read of [catalog_database].[CATALOG].[<SOURCE>]
  - the S1-catalog-view section of build-notes.md and catalog-profile.json: rows, load profile (full / incremental), watermark table, VL_MAIN variables
Catalog source, in order: the DPV1 catalog script; else 2-config/migration/catalog-scripts/<SOURCE>.sql (owner supplied); else the
columns the DPV1 pipelines read (item().X), with no rows and the gate catalog_rows_match open.
Incremental sources (watermark loads in DPV1) also get [CATALOG].[catalog_<source>_watermark].
Location: catalog_warehouse_location = same_workspace (DP_SDS_<DOMAIN>) for now, or shared (DP_COMMON_<ENV>).

Usage: python -I 0-shared/scripts/create_catalog_view.py --id GEOS
Output: 4-migration-project-deliverables/source-dataset/<SOURCE>/3-build/fabric-deployment/<WORKSPACE>/<WH>.Warehouse/ (workspace root;
        DP_COMMON/ once the warehouse is shared) and the S1-catalog-view section of 3-build/build-notes/build-notes.md
"""
import argparse, json, os, re, sys, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, catalog_warehouse, write_note, paths, load_map, resolve_scope, write, track_event, project_dir, deploy_dir, notes_path, work_path, read_json, read_text, exists, vl_name, project_catalog_warehouse
from create_variable_library import catalog_view

TYPE_MAP = [(r'^n?varchar\((\w+)\)', lambda m: f"varchar({'8000' if m.group(1).lower() == 'max' else m.group(1)})"),
            (r'^n?char\((\d+)\)', lambda m: f'char({m.group(1)})'),
            (r'^datetimeoffset.*|^datetime$|^smalldatetime$|^datetime2.*', lambda m: 'datetime2(6)'),
            (r'^bit$', lambda m: 'bit'), (r'^tinyint$', lambda m: 'smallint'),
            (r'^(int|bigint|smallint|date|float|real)$', lambda m: m.group(1)),
            (r'^decimal\((\d+),\s*(\d+)\)|^numeric\((\d+),\s*(\d+)\)', lambda m: f"decimal({m.group(1) or m.group(3)},{m.group(2) or m.group(4)})")]
DEFAULT = [('schemaName', 'varchar(50)'), ('tableName', 'varchar(200)'), ('isIncLoad', 'bit'), ('DeltaMode', 'varchar(10)'),
           ('isActive', 'bit'), ('watermark', 'datetime2(6)'), ('TableProvenance', 'varchar(20)'), ('Comment', 'varchar(500)')]


def fabric_type(t):
    t = re.sub(r'[\[\]\s]', '', t).lower()
    for rx, fn in TYPE_MAP:
        m = re.match(rx, t)
        if m:
            return fn(m)
    return 'varchar(4000)'


def split_values(v):
    """Split a VALUES(...) row on commas outside quotes."""
    out, cur, q = [], '', False
    for ch in v:
        if ch == "'":
            q = not q
        if ch == ',' and not q:
            out.append(cur.strip()); cur = ''
        else:
            cur += ch
    out.append(cur.strip())
    return out


def parse_catalog(q, source):
    """Columns (Fabric types) and rows of a catalog script: CREATE TABLE [CATALOG].[<SOURCE>] (...) + INSERT INTO ... VALUES (...)."""
    if re.search(r"VALUES\s*\(\s*''\w", q):  # script wrapped in sp_executesql: quotes are doubled
        q = q.replace("''", "'")
    end = r'\s*\((.*?)\)\s*(?:ON\b|WITH\b|;|GO\b|INSERT\b|$)'
    m = (re.search(rf'CREATE\s+TABLE\s+\[?CATALOG\]?\.\[?{re.escape(source)}\]?' + end, q, re.I | re.S)
         or re.search(r'CREATE\s+TABLE\s+\[?CATALOG\]?\.\[?\w+\]?' + end, q, re.I | re.S))  # the table may not carry the source name (Catalog_Dwh creates [CATALOG].[DWH])
    cols =[(c, fabric_type(t + (s or ''))) for c, t, s in re.findall(r'^\s*,?\s*\[?(\w+)\]?\s+\[?(\w+)\]?\s*(\([\w\s,]+\))?', m.group(1), re.M)  # a column list may start each line with a comma
            if c.upper() not in ('INSERT', 'VALUES', 'CONSTRAINT', 'PRIMARY')] if m else []
    raw = re.findall(r'^\s*INSERT\s+INTO\s+\[?CATALOG\]?\.\[?\w+\]?\s*VALUES\s*\((.*)\)\s*;?\s*(?:--.*)?$', q, re.I | re.M)
    rows = [split_values(r) for r in raw]
    nc = re.sub(r'^[ \t]*--[^\n]*$', '', re.sub(r'/\*.*?\*/', '', q, flags=re.S), flags=re.M)  # comments out
    if len(raw) < len(re.findall(r'(?i)insert\s+into\s+\[?catalog\]?', nc)):  # other styles: values over several lines, a column list, several tuples per INSERT
        stm = insert_statements(nc)
        if len(stm) > len(raw):
            names = [c.lower() for c, _ in cols]
            rows = []
            for cl, body in stm:
                v = split_values(body)
                if cl:
                    d = dict(zip([x.lower() for x in cl], v))
                    v = [d.get(n, 'NULL') for n in names]
                rows.append(v)
            raw = rows
    return cols, [r for r in rows if cols and len(r) == len(cols)], len(raw)


def insert_statements(q):
    """[(column names or None, text of one VALUES tuple)] for every INSERT INTO [CATALOG].[x] [(cols)] VALUES (...)[, (...)]: quote-aware, any layout."""
    out = []
    for m in re.finditer(r'INSERT\s+INTO\s+\[?CATALOG\]?\.\[?\w+\]?\s*(\([^)]*\))?\s*VALUES\s*', q, re.I):
        names = [x.strip(' []\t\r\n') for x in m.group(1)[1:-1].split(',')] if m.group(1) else None
        i = m.end()
        while i < len(q) and q[i] == '(':
            depth, j, inq = 0, i, False
            while j < len(q):
                ch = q[j]
                if ch == "'":
                    inq = not inq
                elif not inq:
                    depth += ch == '('
                    if ch == ')':
                        depth -= 1
                        if depth == 0:
                            break
                j += 1
            out.append((names, q[i + 1:j]))
            k = j + 1
            while k < len(q) and q[k] in ' \t\r\n':
                k += 1
            if k < len(q) and q[k] == ',':
                k += 1
                while k < len(q) and q[k] in ' \t\r\n':
                    k += 1
                i = k
            else:
                break
    return out


def read_dpv1_catalog(script, source):
    p = os.path.join(paths()['dpv1_export_root'], 'sqlscript', script + '.json')
    if not exists(p):
        return [], [], 0
    return parse_catalog((read_json(p)['properties'].get('content') or {}).get('query', ''), source)


INFER_TYPES = {'schemaname': 'varchar(50)', 'tablename': 'varchar(200)', 'targettable': 'varchar(200)', 'apiname': 'varchar(200)',
               'watermarkparam': 'varchar(200)', 'watermarkval': 'datetime2(6)', 'watermark': 'datetime2(6)', 'unicitykeys': 'varchar(500)',
               'deltamode': 'varchar(10)', 'comment': 'varchar(500)'}


def legacy_profile(S):
    """What the DPV1 ingestion pipelines of the source read from their catalog (item().X), whether they load incrementally,
    and source table names they rename on the fly (equals(item().TableName, 'A') => 'B')."""
    own = [r['v1'] for r in S['rows'] if r['v1t'] == 'Pipeline' and r['a'] not in ('product', 'upstream', 'shared', 'drop')]
    text = ''.join(read_text(f) for f in (os.path.join(paths()['dpv1_export_root'], 'pipeline', n + '.json') for n in own) if exists(f))
    used = sorted(set(re.findall(r'item\(\)\.(\w+)', text)))
    nb_keys = set()
    for n in S['notebooks']:
        f = os.path.join(paths()['dpv1_export_root'], 'notebook', n + '.json')
        if exists(f):
            nb_keys |= set(re.findall(r'metadata_dict\.get\(\\?"(\w+)', read_text(f)))
    incremental = bool(re.search(r'item\(\)\.(WatermarkParam|WatermarkVal|WatermarkField|isFullLoad|isIncLoad)', text, re.I)) and 'WATERMARK' in text.upper()
    sp = r'(?:\s|\\n)*'  # JSON text: line breaks are the two characters \n
    renames = dict(re.findall(rf"equals\({sp}item\(\)\.TableName{sp},{sp}'([^']+)'{sp}\){sp},{sp}'([^']+)'", text))
    return {'columns_used': used + sorted(k for k in nb_keys if k not in used), 'incremental': incremental, 'renames': renames, 'pipelines': own}


NAMES = {'schema': ('schemaname',), 'table': ('tablename', 'name', 'objectname'), 'active': ('isactive',),
         'keys': ('unicitykeys', 'merge_keys', 'pks', 'primarykey', 'keycolumns'), 'wcol': ('watermarkparam', 'watermarkfield', 'deltacolumn', 'watermarkcolumn'),
         'wval': ('watermarkval', 'watermark', 'watermarkvalue'), 'isinc': ('isincload',), 'isfull': ('isfullload', 'fullload'), 'isdel': ('isdeletelog',),
         'target': ('targettable',), 'path': ('sourcepath', 'apiname', 'relativeurl', 'relativepath', 'apipath', 'filepath', 'servicename'),
         'opts': ('fileoptions',), 'root': ('rootpath',), 'fmt': ('sourceformat',)}


def normalised(cols, kind, incremental, layout, src, renames, schema_prefix=False):
    """The standard columns every pipeline and notebook reads (ingestion.py), as SQL over the DPV1 columns (CTE c).
    Returns (renamed DPV1 columns, derived columns)."""
    have = {c.lower(): c for c, _ in cols}
    pick = lambda k: next((have[n] for n in NAMES[k] if n in have), None)
    q = lambda c: f'c.[{c}]'
    sch, tbl = pick('schema'), pick('table')
    schema = q(sch) if sch else f"CAST('{src.lower()}' AS varchar(50))"
    table = q(tbl) if tbl else q(pick('path')) if pick('path') else "CAST(NULL AS varchar(200))"  # API catalog: the API name is the table
    keep = [f'{q(c)} AS [SchemaName]' if c == sch else f'{q(c)} AS [TableName]' if c == tbl else q(c) for c, _ in cols]
    if not sch:
        keep.append(f'{schema} AS [SchemaName]')  # the pipelines join the watermark on SchemaName, TableName
    if not tbl:
        keep.append(f'CAST({table} AS varchar(200)) AS [TableName]')
    first = lambda c: f"NULLIF(LEFT({q(c)}, CHARINDEX('|', {q(c)} + '|') - 1), '')"
    if not incremental:  # DPV1 extracts every table in full, whatever the catalog flags say: keep that
        load = "CAST('full' AS varchar(12))"
    elif pick('isfull'):
        load = f"CASE WHEN CAST({q(pick('isfull'))} AS int) = 1 THEN 'full' ELSE 'incremental' END"
    elif pick('isinc'):
        load = f"CASE WHEN CAST({q(pick('isinc'))} AS int) = 1 THEN 'incremental' ELSE 'full' END"
    else:
        load = "CAST('incremental' AS varchar(12))"
    isdel = f"CAST(COALESCE({q(pick('isdel'))}, 0) AS int)" if pick('isdel') else 'CAST(0 AS int)'
    target = q(pick('target')) if pick('target') else 'CAST(NULL AS varchar(200))'
    hist = f"{table} LIKE '%[_]History'" if layout.get('history') else '1 = 0'
    base = f"LEFT({table}, LEN({table}) - 8)"
    pre = (lambda x: f"CONCAT({schema}, '_', {x})") if schema_prefix else (lambda x: x)  # folder = table name; schema only when two schemas share a name
    entity = (f"LOWER(CASE WHEN {isdel} = 1 THEN {pre(target)} WHEN {hist} THEN {pre(base)} ELSE {pre(table)} END)" if kind == 'structured'
              else f"LOWER(REPLACE({table}, ' ', '_'))")
    tail = (f"CASE WHEN {isdel} = 1 THEN '/DELETE_LOGS' WHEN {hist} THEN '/HISTORY' ELSE '' END" if (layout.get('delete_logs') or layout.get('history'))
            else "CAST('' AS varchar(20))")
    case = ' '.join(f"WHEN '{k}' THEN '{v}'" for k, v in renames.items())
    source_name = f"CASE {table} {case} ELSE {table} END" if case and tbl else table
    derived = [
        f"CAST({q(pick('active')) if pick('active') else 1} AS int) AS [Active]",
        f"{load} AS [LoadMethod]",
        f"CAST({q(pick('keys')) if pick('keys') else 'NULL'} AS varchar(500)) AS [KeyColumns]",
        f"CAST({first(pick('wcol')) if pick('wcol') else 'NULL'} AS varchar(128)) AS [WatermarkColumn]",
        f"CAST({q(pick('wval')) if pick('wval') else 'NULL'} AS varchar(40)) AS [WatermarkValue]",
        f"{isdel} AS [IsDeleteLog]", f"CAST({target} AS varchar(200)) AS [DeleteTarget]",
        f"CAST({source_name} AS varchar(200)) AS [SourceName]",
        f"CAST({entity} AS varchar(300)) AS [EntityName]", f"CAST({tail} AS varchar(20)) AS [FolderTail]",
        f"CAST(LOWER(REPLACE({table}, ' ', '_')) AS varchar(200)) AS [TargetName]",
        f"CAST({q(pick('fmt')) if pick('fmt') else repr(layout.get('format', 'table')).replace(chr(34), chr(39))} AS varchar(20)) AS [SourceFormat]",
        f"CAST({q(pick('path')) if pick('path') else table} AS varchar(1000)) AS [SourcePath]",
        f"CAST({q(pick('opts')) if pick('opts') else 'NULL'} AS varchar(1000)) AS [FileOptions]",
        f"CAST({q(pick('root')) if pick('root') else 'NULL'} AS varchar(200)) AS [RootPath]"]
    return keep, derived


def file_rows_select(cols, keep, derived, fi, src):
    """SELECT of the file inputs of a mixed source, in the column order of the main SELECT (UNION ALL): the DPV1 columns are NULL, the standard
    columns are set from the file list (ingestion.file_inputs). Returns (VALUES CTE text, SELECT text)."""
    esc = lambda x: str(x).replace("'", "''")
    sch = fi.get('schema') or src.upper()
    vals = ',\n        '.join(f"('{esc(sch)}', '{esc(t['name'])}', '{esc(t.get('format') or fi.get('format', 'csv'))}', '{esc(t['path'])}')" for t in fi['tables'])
    types = {c: t for c, t in cols}
    name_of = lambda e: re.search(r'AS \[(\w+)\]$', e).group(1) if re.search(r'AS \[(\w+)\]$', e) else re.search(r'c\.\[(\w+)\]$', e).group(1)
    out = []
    for e in keep:
        n = name_of(e)
        orig = re.search(r'c\.\[(\w+)\]', e).group(1) if re.search(r'c\.\[(\w+)\]', e) else n
        if n == 'SchemaName':
            out.append(f'CAST(f.[SchemaName] AS varchar(50)) AS [SchemaName]')
        elif n == 'TableName':
            out.append(f'CAST(f.[TableName] AS varchar(200)) AS [TableName]')
        else:
            out.append(f'CAST(NULL AS {types.get(orig, "varchar(200)")}) AS [{n}]')
    fixed = {'Active': 'CAST(1 AS int)', 'LoadMethod': "CAST('full' AS varchar(12))", 'IsDeleteLog': 'CAST(0 AS int)',
             'SourceName': 'CAST(f.[TableName] AS varchar(200))', 'EntityName': "CAST(LOWER(REPLACE(f.[TableName], ' ', '_')) AS varchar(300))",
             'FolderTail': "CAST('' AS varchar(20))", 'TargetName': "CAST(LOWER(REPLACE(f.[TableName], ' ', '_')) AS varchar(200))",
             'SourceFormat': 'CAST(f.[SourceFormat] AS varchar(20))', 'SourcePath': 'CAST(f.[SourcePath] AS varchar(1000))'}
    for e in derived:
        n = name_of(e)
        typ = re.search(r'AS (varchar\(\d+\)|int)\) AS \[' + n + r'\]$', e)
        out.append(f"{fixed[n]} AS [{n}]" if n in fixed else f"CAST(NULL AS {typ.group(1) if typ else 'varchar(200)'}) AS [{n}]")
    out.append("CAST('files' AS varchar(20)) AS [ConnectionKey]")
    cte = f"f AS (\n    SELECT * FROM (VALUES\n        {vals}\n    ) AS v ([SchemaName], [TableName], [SourceFormat], [SourcePath])\n)"
    return cte, 'SELECT\n    ' + ',\n    '.join(out) + '\nFROM f'


def literal(v, typ):
    v = v.strip()
    if v.upper() == 'NULL' or v in ("''",) and typ.startswith(('datetime', 'int', 'bit', 'decimal')):
        return 'NULL'
    if typ == 'bit':
        return v.strip("'")
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--id', required=True, help='source name')
    a = ap.parse_args()
    sp = read_json(os.path.join(ROOT, '2-config', 'migration', 'shared-platform.json'))
    m = load_map()
    scope, _ = resolve_scope(m, 'sds', a.id)
    S = m['sds'][scope]
    src, sch = S['folder'], sp['catalog_schema']
    wh = catalog_warehouse(sp, src)
    view = catalog_view(sp, src)
    from common import project_catalog_workspace
    import project_inputs as _pi
    cws = project_catalog_workspace(src)  # workspace chosen in framing for the catalog warehouse (another than the target one)
    ws = (_pi.folder_of(cws) + '_<ENV>') if cws else sp['shared_workspace'] if sp['catalog_warehouse_location'] == 'shared' else S['ws']
    # where the catalog comes from: the DPV1 catalog script, else a script the owner adds to the repo, else the DPV1 pipeline code (columns only)
    scripts = sorted({c['from'] for c in S['catalog']})
    repo_script = os.path.join(ROOT, '2-config', 'migration', 'catalog-scripts', f'{scope}.sql')
    prof = legacy_profile(S)
    if scripts:
        origin, where = 'dpv1', f"DPV1 sqlscript `{scripts[0]}`"
        cols, rows, expected = read_dpv1_catalog(scripts[0], scope)
    elif exists(repo_script):
        origin, where = 'repo', f"`2-config/migration/catalog-scripts/{scope}.sql` (supplied by the owner: no catalog script in the DPV1 export)"
        cols, rows, expected = parse_catalog(read_text(repo_script), scope)
    else:
        origin, where = 'none', ('no catalog script: not in the DPV1 export and not in `2-config/migration/catalog-scripts/`; '
                                 f'columns inferred from the DPV1 pipelines ({", ".join(prof["pipelines"]) or "none"}), no rows')
        cols, rows, expected = [], [], None
    if not cols:
        cols = [(c, INFER_TYPES.get(c.lower(), 'bit' if c.lower().startswith('is') else 'varchar(200)')) for c in prof['columns_used']] or DEFAULT
    tcol = next((c for c, _ in cols if c.lower() == 'tablename'), None)
    incremental = prof['incremental']
    wm_table = f"catalog_{src.lower()}_watermark" if incremental else None
    base = deploy_dir('sds', scope, ws.replace('_<ENV>', ''), f'{wh}.Warehouse')

    # warehouse item (keep logicalId when re-run), as in skill-fabric-create-warehouse
    plat = os.path.join(base, '.platform')
    common = project_catalog_warehouse(src)
    cands = []
    if common:  # one item for several sources: the id is the one already deployed, else the one another source's build holds
        import project_inputs
        repo = project_inputs.load('sds', scope).get('deployment_repo')
        wsf = ws.replace('_<ENV>', '')
        if repo:
            cands.append(os.path.join(repo, wsf, f'{wh}.Warehouse', '.platform'))
        cands.append(plat)
        root = os.path.dirname(project_dir('sds', scope))
        cands += [deploy_dir('sds', o, wsf, f'{wh}.Warehouse', '.platform') for o in sorted(os.listdir(root)) if o.lower() != scope.lower()]
    else:
        cands.append(plat)
    found = next((c for c in cands if exists(c)), None)
    logical = read_json(found)['config']['logicalId'] if found else str(uuid.uuid4())
    desc = ('Common catalog warehouse: the catalog views of the source datasets of this workspace.' if common
            else f'Catalog warehouse of {src}: the view listing the tables to ingest' + (' (watermark table too).' if incremental else '.'))
    write(plat, json.dumps({'$schema': 'https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json',
                            'metadata': {'type': 'Warehouse', 'displayName': wh, 'description': desc},
                            'config': {'version': '2.0', 'logicalId': logical}}, indent=2) + '\n')
    write(os.path.join(base, f'{wh}.sqlproj'), f"""<Project DefaultTargets="Build">
  <Sdk Name="Microsoft.Build.Sql" Version="0.1.19-preview" />
  <PropertyGroup>
    <Name>{wh}</Name>
    <DSP>Microsoft.Data.Tools.Schema.Sql.SqlDwUnifiedDatabaseSchemaProvider</DSP>
    <ModelCollation>1033, CI</ModelCollation>
    <DefaultCollation>Latin1_General_100_CI_AS_KS_WS_SC_UTF8</DefaultCollation>
  </PropertyGroup>
  <Target Name="BeforeBuild">
    <Delete Files="$(BaseIntermediateOutputPath)\\project.assets.json" />
  </Target>
</Project>
""")
    write(os.path.join(base, sch, f'{sch}.sql'), f'CREATE SCHEMA [{sch}];\n')
    import ingestion, scope_tree
    _, _, kind, fmt, _ = ingestion.source_kind(S, m['objects'])
    layout = dict(scope_tree.layout('sds', scope, S), format=fmt)
    ti = next((i for i, (c, _) in enumerate(cols) if c.lower() in NAMES['table']), None)
    si = next((i for i, (c, _) in enumerate(cols) if c.lower() in NAMES['schema']), None)
    names = [(r[si] if si is not None else '', r[ti].lower()) for r in rows] if ti is not None else []
    clash = len({t for _, t in names}) < len(set(names))
    keep, derived = normalised(cols, kind, incremental, layout, src, prof['renames'], clash)
    if sp.get('catalog_database'):
        cte = f"SELECT {', '.join(f'[{c}]' for c, _ in cols)} FROM [{sp['catalog_database']}].[{sch}].[{src}]"
    else:
        vals = ',\n        '.join('(' + ', '.join(literal(v, t) for v, (_, t) in zip(r, cols)) + ')' for r in rows) or '(' + ', '.join('NULL' for _ in cols) + ')'
        cte = ("SELECT " + ', '.join(f'CAST([{c}] AS {t}) AS [{c}]' for c, t in cols) +
               f"\n    FROM (VALUES\n        {vals}\n    ) AS v ({', '.join(f'[{c}]' for c, _ in cols)})" + ('' if rows else '\n    WHERE 1 = 0'))
    fi = ingestion.save_file_inputs(S, m['objects'], m, project_dir('sds', scope), src) if kind == 'structured' else {}  # files ingested next to the database
    if fi.get('tables'):  # mixed source: the file inputs are catalog rows too (ConnectionKey 'files'), the database rows are 'main'
        fcte, fsel = file_rows_select(cols, keep, derived, fi, src)
        body = (f"WITH c AS (\n    {cte}\n),\n{fcte}\nSELECT\n    " + ',\n    '.join(keep) + ',\n    -- standard columns read by the pipelines and the notebook (ingestion.py)\n    '
                + ',\n    '.join(derived) + ",\n    CAST('main' AS varchar(20)) AS [ConnectionKey]\nFROM c\nUNION ALL\n" + fsel + ';')
    else:
        body = (f"WITH c AS (\n    {cte}\n)\nSELECT\n    " + ',\n    '.join(keep) + ',\n    -- standard columns read by the pipelines and the notebook (ingestion.py)\n    '
                + ',\n    '.join(derived) + '\nFROM c;')
    write(os.path.join(base, sch, 'Views', f'{view}.sql'),
          f"-- Catalog of source dataset {src}: tables to ingest, load mode, active flag, watermark.\n"
          f"-- Built from {where} by create_catalog_view.py. Read by PL_{src}_SOURCE_TO_RAW and PL_{src}_RAW_TO_DELTA through VL_MAIN.\n"
          f"-- DPV1 columns are kept (schema and table renamed SchemaName, TableName); the standard columns follow.\n"
          f"CREATE VIEW [{sch}].[{view}]\nAS\n{body}\n")
    if wm_table:  # DPV1 updated CATALOG.<SOURCE>.WatermarkVal with SP_COMMON_UpdateWatermark; a view is read-only, so the watermark lives here
        # same text as Fabric writes back on commit (no comments, tab-indented, no final newline): a different text makes the Git sync drop and recreate the table
        write(os.path.join(base, sch, 'Tables', f'{wm_table}.sql'),
              f"CREATE TABLE [{sch}].[{wm_table}] (\n\n\t[SchemaName] varchar(50) NOT NULL, \n\t[TableName] varchar(200) NOT NULL, \n"
              f"\t[WatermarkVal] datetime2(6) NULL, \n\t[UpdatedAt] datetime2(6) NULL\n);")
    idx = {c.lower(): i for i, (c, _) in enumerate(cols)}
    flag = lambda r, k: k in idx and r[idx[k]].strip("' ") == '1'
    active = sum(1 for r in rows if flag(r, 'isactive'))
    inc = sum(1 for r in rows if flag(r, 'isincload') or ('isfullload' in idx and not flag(r, 'isfullload')))
    profile = {'source': src, 'origin': origin, 'where': where, 'view': f'{sch}.{view}', 'columns': cols, 'rows': len(rows), 'expected_rows': expected,
               'incremental': incremental, 'watermark_table': f'{sch}.{wm_table}' if wm_table else None, 'renames': prof['renames'],
               'columns_used_by_dpv1': prof['columns_used']}
    write(work_path('sds', scope, 'catalog-profile.json'), json.dumps(profile, indent=1) + '\n')
    L = [f'# Catalog view: {src}', '', f'- **Warehouse**: `{wh}` in `{ws}` ({"remote" if cws else sp["catalog_warehouse_location"]})', f'- **View**: `[{sch}].[{view}]`',
         f"- **Built from**: {where}" + (f" (reads `{sp['catalog_database']}`)" if sp.get('catalog_database') else ''),
         f'- **Rows**: {len(rows)} tables, {active} active, {inc} incremental, {len(rows) - inc} full' + (f' (script has {expected} INSERT rows)' if expected is not None else ''),
         f"- **Load profile (from the DPV1 pipelines)**: {'incremental, watermark per table' if incremental else 'full load'}"]
    if wm_table:
        L.append(f'- **Watermark table**: `[{sch}].[{wm_table}]` (read with the view, updated after each successful run; replaces `SP_COMMON_UpdateWatermark`)')
    if prof['renames']:
        L.append('- **Source table names**: column `SourceTableName` keeps the DPV1 renames: ' + ', '.join(f'`{k}` => `{v}`' for k, v in prof['renames'].items()))
    if origin == 'none':
        L += ['', '## ❌ Catalog rows missing', '', f'The DPV1 export has no catalog script for {scope}: the table list lives only in the metabase table `CATALOG.{scope}`.',
              f'Add the script as `2-config/migration/catalog-scripts/{scope}.sql` (same format as a DPV1 catalog script: `CREATE TABLE [CATALOG].[{scope}]` + one `INSERT` per table), then re-run this script.']
    L += ['', '## VL_MAIN variables used by the pipelines', '', 'Only the location of the view is in VL_MAIN. Tables, load mode, active flag and watermark stay in the view.', '',
          '| Variable | Value |', '| --- | --- |', f'| `{vl_name(src, "CATALOG_VIEW_NAME")}` | `{sch}.{view}` |']
    if wm_table:
        L.append(f'| `{vl_name(src, "CATALOG_WATERMARK_TABLE_NAME")}` | `{sch}.{wm_table}` |')
    L += [f'| `{vl_name(src, "CATALOG_WAREHOUSE_NAME")}` | `{wh}` |', f'| `{vl_name(src, "CATALOG_WAREHOUSE_ID")}` | item ID per environment (DEV / UAT / PRD) |', '',
          f'Columns: {len(cols)} DPV1 columns plus the standard columns (list: `../analysis/build-details.md`).']
    D = [f'# Catalog view columns: {src}', '', '| Column | Fabric type |', '| --- | --- |'] + [f'| `{c}` | `{t}` |' for c, t in cols]
    L += ['', '## Standard columns (read by the pipelines and the notebook)', '',
          '`Active`, `LoadMethod` (full / incremental), `KeyColumns`, `WatermarkColumn`, `WatermarkValue`, `IsDeleteLog`, `DeleteTarget`, `SourceName`, '
          '`EntityName` and `FolderTail` (DPV1 folder tree), `TargetName`, `SourceFormat`, `SourcePath`, `FileOptions`, `RootPath`.',
          f"Load method: {'from the DPV1 catalog flags' if incremental else 'full for every table, as the DPV1 pipelines extract them'}."]
    write_note('sds', scope, 'S1-catalog-view', '\n'.join(L) + '\n', '\n'.join(D) + '\n')
    ok = origin != 'none' and len(rows) == expected
    track_event(scope, 'sds', 'S1', f'Catalog view `[{sch}].[{view}]` generated in `{wh}`: {len(rows)} rows ({active} active), from {origin}' + (f'; watermark table `{wm_table}`' if wm_table else ''),
                typ='change' if origin != 'none' else 'issue', gate='catalog_rows_match', gate_ok=ok,
                evidence=f'{len(rows)} view rows / {expected} catalog script rows' if expected is not None else f'no catalog script: add 2-config/migration/catalog-scripts/{scope}.sql')
    print(f'{scope}: [{sch}].[{view}] in {wh} ({ws}) · {len(cols)} columns · {len(rows)} rows ({active} active) · from {origin}'
          + (f' · watermark table {wm_table}' if wm_table else '') + f' → {os.path.relpath(base, ROOT)}')


if __name__ == '__main__':
    main()
