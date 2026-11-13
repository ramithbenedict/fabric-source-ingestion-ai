"""Ingestion methods of a source dataset (wf-2 S2-S4), built from how DPV1 ingests the source.

Design: 3-workflows/wf-2-migration-source-dataset/ingestion-design.md. One method per source, chosen from the DPV1 code:

  structured       database or list source (Oracle, SQL Server, Azure SQL, PostgreSQL, SharePoint list…)
                   Copy writes parquet straight to Files/raw/<src>/<inst>/<entity>/<yyyy>/<mm>/<dd>/<HHhMM>/   (no landing copy)
  semi-structured  REST API or files (SFTP, HTTP, file share, blob, S3, FTP)
                   Copy lands the files as delivered in Files/landing/…/<run>/; the notebook writes parquet to Files/raw/…/<run>/
  load mode        per catalog row: full (overwrite) or incremental (watermark extract, MERGE on keys, delete logs, history)

The catalog view gives every row the same columns (normalised by create_catalog_view.py from the DPV1 catalog):
  SchemaName, TableName, Active, LoadMethod, KeyColumns, WatermarkColumn, WatermarkValue, EntityName, FolderTail, TargetName,
  IsDeleteLog, DeleteTarget, SourceFormat, SourcePath, FileOptions, RootPath
The Lookup adds ExtractQuery (structured: the SELECT to run, watermark minus 1 day as DPV1) and Since (semi-structured: changes since).

S3 is one notebook per source, generated only when DPV1 cleansed the source in a notebook. It loads all tables in one Spark
session (thread pool), with only the handlers and DPV1 cleansing rules the source needs (rules read from the legacy notebooks).
A source that DPV1 cleansed without a notebook gets a Copy from raw parquet to Lakehouse tables instead.
"""
import json, os, re, glob
from common import paths, write, write_note, notes_path, read_json, read_text, exists, vl_name

LKP = 'GET TABLES FROM CATALOG VIEW'
DB = {'Oracle': ('OracleSource', 'OracleTable', 'oracle'), 'SqlServer': ('SqlServerSource', 'SqlServerTable', 'tsql'),
      'AzureSqlDatabase': ('AzureSqlSource', 'AzureSqlTable', 'tsql'), 'AzureSqlDW': ('SqlDWSource', 'AzureSqlDWTable', 'tsql'),
      'MySql': ('MySqlSource', 'MySqlTable', 'ansi'), 'PostgreSql': ('PostgreSqlSource', 'PostgreSqlTable', 'ansi'),
      'AzurePostgreSql': ('AzurePostgreSqlSource', 'AzurePostgreSqlTable', 'ansi'), 'AmazonRedshift': ('AmazonRedshiftSource', 'AmazonRedshiftTable', 'ansi'),
      'SharePointOnlineList': ('SharePointOnlineListSource', 'SharePointOnlineListResource', 'list')}
FILES = {'Sftp': 'SftpReadSettings', 'FileServer': 'FileServerReadSettings', 'HttpServer': 'HttpReadSettings', 'AzureBlobStorage': 'AzureBlobStorageReadSettings',
         'AmazonS3': 'AmazonS3ReadSettings', 'AzureFileStorage': 'AzureFileStorageReadSettings', 'FtpServer': 'FtpReadSettings',
         'OracleCloudStorage': 'OracleCloudStorageReadSettings'}
LOCATION = {'Sftp': 'SftpLocation', 'FileServer': 'FileServerLocation', 'HttpServer': 'HttpServerLocation', 'AzureBlobStorage': 'AzureBlobStorageLocation',
            'AmazonS3': 'AmazonS3Location', 'AzureFileStorage': 'AzureFileStorageLocation', 'FtpServer': 'FtpServerLocation',
            'OracleCloudStorage': 'OracleCloudStorageLocation'}
INTERNAL = {'AzureBlobFS', 'AzureKeyVault', 'AzureTableStorage'}  # DPV1 zones and secrets, never a source
FORMAT_OF_DATASET = {'Json': 'json', 'DelimitedText': 'csv', 'Excel': 'excel', 'Xml': 'xml', 'Parquet': 'parquet', 'RestResource': 'json'}


# ---------------------------------------------------------------- source classification (also used by create_catalog_view.py)
def source_kind(S, O):
    """(linked service, connector type, method, default format, dialect) of a source, from its DPV1 linked services and datasets."""
    conns = [r['v1'] for r in S['rows'] if r['v1t'] == 'Linked service' and r['v2t'] == 'Connection']
    types = {n: O['linkedService'].get(n, {}).get('type', '') for n in conns}
    pick = next((n for n in conns if types[n] in DB), None) or next((n for n in conns if types[n] not in INTERNAL), conns[0] if conns else '')
    typ = types.get(pick, '')
    if typ in DB:
        return pick, typ, 'structured', 'table', DB[typ][2]
    fmts = [FORMAT_OF_DATASET.get(O['dataset'].get(d, {}).get('type')) for d in S['datasets']]
    fmts = [f for f in fmts if f and f != 'parquet'] or ['json' if typ == 'RestService' else 'csv']
    return pick, typ, 'semi-structured', max(set(fmts), key=fmts.count), None


# ---------------------------------------------------------------- DPV1 cleansing rules, read from the legacy notebooks
RULES = [  # (rule, regex on the legacy code, value extractor, meaning)
    ('clamp_1900', r"1900-01-01", None, 'timestamps before 1900-01-01 set to 1900-01-01'),
    ('empty_to_null', r"""==\s*(?:""|'')""", None, 'empty strings become NULL'),
    ('upper_columns', r"\.upper\(\)\s*\)\s*for\s+\w+\s+in\s+\w+\.columns|alias\(\w+\.upper\(\)\)", None, 'column names in upper case'),
    ('tz_offset_fix', r"\\\+\\d\{2\}\$", None, "'+hh' offsets completed to '+hh:00'"),
    ('string_null_over', r"length\(col\(\w+\)\)\s*>\s*(\d+)", int, 'strings longer than N characters become NULL'),
    ('string_cut', r"substring\(cast\(.{0,40}?,\s*1,\s*\{?(\d+)", int, 'strings cut to N characters (per column when DPV1 had exceptions)'),
    ('dedupe', r"dropDuplicates\(", None, 'duplicate rows removed (on the keys when there are keys)'),
    ('latest_per_key', r"row_number\(\)\.over|Window\.partitionBy", None, 'latest row per key kept (window on the watermark column)'),
    ('flatten', r"def\s+flatten\w*\(", None, 'nested JSON structs flattened (a.b => a_b)'),
    ('json_root', r"explode\(col\([\"'](\w+)[\"']\)\)", str, 'records are the array in this JSON attribute'),
    ('parquet_vectorized_off', r"enableVectorizedReader[\"']?\s*:\s*[\"']false", None, 'parquet vectorised reader off (DPV1 decimal workaround)'),
]


def legacy_rules(S, pd):
    """DPV1 cleansing rules found in the scope's notebooks: {rule: value or True}, with the notebook that has it."""
    texts = {}
    for p in glob.glob(os.path.join(pd, '2-legacy-code', 'notebooks', '*.py')):
        texts[os.path.basename(p)[:-3]] = read_text(p, 'replace')
    if not texts:  # legacy code not extracted yet: read the export directly
        for n in S['notebooks']:
            f = os.path.join(paths()['dpv1_export_root'], 'notebook', n + '.json')
            if exists(f):
                cells = read_json(f)['properties'].get('cells', [])
                texts[n] = '\n'.join(''.join(c.get('source', [])) for c in cells if c.get('cell_type') == 'code')
    found, where = {}, {}
    for rule, rx, conv, _ in RULES:
        for n, t in texts.items():
            code = '\n'.join(l for l in t.splitlines() if not l.lstrip().startswith(('#', '//')))  # comments name rules, they do not apply them
            m = re.search(rx, code, re.S)
            if m:
                found[rule] = conv(m.group(1)) if conv else True
                cut = re.search(r"\{(\d+)\s+if\s+\w+\s+in\s+(\w+)\s+else\s+(\d+)\}", code) if rule == 'string_cut' else None
                if cut:  # DPV1: {4000 if c in columns_to_exclude else 255}
                    names = re.search(rf"{cut.group(2)}\s*=\s*\{{([^}}]*)\}}", code)
                    cols = re.findall(r"[\"']([^\"']+)[\"']", names.group(1)) if names else []
                    found[rule] = {'default': int(cut.group(3)), 'columns': {c: int(cut.group(1)) for c in cols}}
                where.setdefault(rule, n)
                break
    return found, where, sorted(texts)


# ---------------------------------------------------------------- pipeline building blocks
VL = lambda n: f'@pipeline().libraryVariables.{n}'
V = lambda c, base: vl_name(c.src, base)  # source-specific names carry the source (common.SOURCE_VARS)


def libs(c, lakehouse=False, warehouse=False, source=False, catalog=True):
    """libraryVariables a pipeline must declare for the connections it uses (every VL expression needs its declaration,
    under the same name as in VL_MAIN)."""
    out = ([V(c, 'CATALOG_VIEW_NAME')] + ([V(c, 'CATALOG_WATERMARK_TABLE_NAME')] if c.incremental else [])) if catalog else []
    if lakehouse:
        out += [f'LH_SDS_{c.src}_ID', V(c, 'LH_CONN_ID'), V(c, 'LH_NAME')]
    if warehouse:
        out += [V(c, 'CATALOG_WAREHOUSE_ID'), V(c, 'CATALOG_WAREHOUSE_SQL_ENDPOINT'), V(c, 'CATALOG_WAREHOUSE_CONN_ID')]
        from common import catalog_remote
        if catalog_remote(c.sp, c.src):
            out.append(V(c, 'CATALOG_WAREHOUSE_WORKSPACE_ID'))
    if source and c.conn_var:
        out.append(c.conn_var)
    return list(dict.fromkeys(out))


def warehouse(b, c):
    """connectionSettings of the catalog warehouse. Every id is resolved at run time from VL_MAIN (workspace: the pipeline's own,
    or the shared one), so the pipeline has no sync-time dependency on the warehouse item: items deploy together in one sync."""
    from common import catalog_warehouse, catalog_remote
    shared = catalog_remote(c.sp, c.src)
    return {'name': catalog_warehouse(c.sp, c.src).lower(), 'properties': {
        'annotations': [], 'type': 'DataWarehouse',
        'typeProperties': {'artifactId': VL(V(c, 'CATALOG_WAREHOUSE_ID')), 'endpoint': VL(V(c, 'CATALOG_WAREHOUSE_SQL_ENDPOINT')),
                           'workspaceId': VL(V(c, 'CATALOG_WAREHOUSE_WORKSPACE_ID')) if shared else '@pipeline().DataFactory'},
        # Fabric's Git import resolves this connection when it discovers dependencies: without it, "Object reference not set" (B48, B59)
        'externalReferences': {'connection': VL(V(c, 'CATALOG_WAREHOUSE_CONN_ID'))}}}


# ---------------------------------------------------------------- DPV1 per-table queries (Switch on the table name)
ITEM_REF = re.compile(r'@\{\s*item\(\)\.(\w+)\s*\}')
# DPV1's own incremental filter at the end of a query: Fabric adds its watermark filter itself (lookup_sql), so it is dropped
WM_TAIL = re.compile(r'\s*@\{\s*if\((?:(?!@\{).)*?watermark(?:(?!@\{).)*\}\s*;?\s*$', re.I | re.S)
PER_TABLE = re.compile(r'(?i)table|source|entity|object')  # a Switch on these picks a table; others (platform, mode) pick a source type
CATALOG_COL = {'schemaname': 'SchemaName', 'tablename': 'TableName'}  # create_catalog_view.py renames only these; other DPV1 columns keep their name


def queries_path(src):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '2-config', 'migration', 'extract-queries', f'{src.upper()}.json')


def legacy_pipelines(S, pd):
    """{name: pipeline json} of the scope: 2-legacy-code/pipelines/, or the DPV1 export when the legacy code is not extracted yet."""
    files = glob.glob(os.path.join(pd, '2-legacy-code', 'pipelines', '*.json'))
    if not files:
        files = [f for f in (os.path.join(paths()['dpv1_export_root'], 'pipeline', r['v1'] + '.json') for r in S['rows'] if r['v1t'] == 'Pipeline') if exists(f)]
    out = {}
    for f in files:
        try:
            out[os.path.basename(f)[:-5]] = read_json(f)
        except ValueError:
            pass
    return out


def _walk(acts):
    for a in acts or []:
        yield a
        tp = a.get('typeProperties', {})
        for k in ('activities', 'ifTrueActivities', 'ifFalseActivities', 'defaultActivities'):
            yield from _walk(tp.get(k))
        for case in tp.get('cases') or []:
            yield from _walk(case.get('activities'))


def _copy_query(acts):
    for a in _walk(acts):
        if a['type'] == 'Copy':
            src = a['typeProperties'].get('source', {})
            q = src.get('sqlReaderQuery') or src.get('query')
            return q.get('value') if isinstance(q, dict) else q
    return None


def _is_select_star(q):
    """True for DPV1's default extract: select * from @{item().SchemaName}.@{item().tableName} (same as the Fabric default)."""
    s = re.sub(r'[\s\[\]"]+', '', ITEM_REF.sub(lambda m: m.group(1).lower(), WM_TAIL.sub('', q or ''))).lower().rstrip(';')
    return s in ('select*fromschemaname.tablename', 'select*fromtablename')


def dpv1_switch_queries(S, pd):
    """Per-table extract queries of DPV1: a Switch on @item().<column> whose branches each run a Copy with their own query.
    Returns {'on': catalog column, 'pipeline', 'queries': {value: DPV1 text}, 'manual': {value: reason}}; empty when DPV1 has none.
    A branch that runs DPV1's default SELECT * is left out (Fabric's default); DPV1's trailing watermark filter is dropped (Fabric adds its own). A query that uses @{item().X} is kept: lookup_sql turns
    it into a CONCAT over the catalog row. Any other expression (pipeline parameters, functions) cannot be carried over: 'manual'."""
    for name, p in sorted(legacy_pipelines(S, pd).items()):
        for sw in _walk(p['properties'].get('activities')):
            on = sw.get('typeProperties', {}).get('on') if sw['type'] == 'Switch' else None
            m = re.fullmatch(r'@item\(\)\.(\w+)', ((on or {}).get('value') if isinstance(on, dict) else on or '').strip())
            if not m or not PER_TABLE.search(m.group(1)):
                continue
            queries, manual = {}, {}
            for case in sw['typeProperties'].get('cases') or []:
                q = _copy_query(case.get('activities'))
                if not q or _is_select_star(q):
                    continue
                q = WM_TAIL.sub('', q)
                rest = ITEM_REF.sub('', q)
                if q.lstrip().startswith('@') or '@{' in rest:
                    manual[case['value']] = 'dynamic query (pipeline expression): rewrite it over the catalog row in the overrides of extract-queries/<SRC>.json'
                else:
                    queries[case['value']] = q
            if queries or manual:
                return {'on': CATALOG_COL.get(m.group(1).lower(), m.group(1)), 'pipeline': name, 'switch': sw['name'], 'queries': queries, 'manual': manual}
    return {}


def save_switch_queries(c):
    """Write 2-config/migration/extract-queries/<SRC>.json from the DPV1 Switch (S2). 'overrides' is kept: hand-written queries win,
    and fill the 'manual' ones. Returns the content (empty dict when the source has no per-table query)."""
    p = queries_path(c.src)
    old = read_json(p) if exists(p) else {}
    sw = dpv1_switch_queries(c.S, c.pd)
    if not sw and not old.get('overrides'):
        return {}
    doc = {'_doc': f'Per-table extract queries of {c.src}, generated from the DPV1 Switch by ingestion.save_switch_queries (S2). '
                   'Every other table runs SELECT *. Write hand-made queries in "overrides" (kept by every build; they also replace the "manual" ones).',
           'pipeline': sw.get('pipeline', old.get('pipeline', '')), 'switch': sw.get('switch', old.get('switch', '')),
           'on': sw.get('on') or old.get('on') or 'TableName', 'queries': sw.get('queries', {}), 'manual': sw.get('manual', {}),
           'overrides': old.get('overrides', {})}
    write(p, json.dumps(doc, indent=2, ensure_ascii=False) + '\n')
    return doc


def extract_queries(c):
    """(catalog column, {value: DPV1 text}) used by the Lookup: the generated queries, then the overrides."""
    p = queries_path(c.src)
    d = read_json(p) if exists(p) else {}
    return d.get('on') or 'TableName', {**d.get('queries', {}), **d.get('overrides', {})}


def query_expr(q):
    """T-SQL string expression of a DPV1 query: a literal, or a CONCAT when it reads @{item().X} (=> the catalog column c.[X]).
    A trailing ';' is dropped so the query can be wrapped for an incremental load."""
    q = q.rstrip().rstrip(';').rstrip()
    lit = lambda s: "'" + s.replace("'", "''") + "'"
    parts, pos = [], 0
    for m in ITEM_REF.finditer(q):
        parts += [lit(q[pos:m.start()]), f"c.[{CATALOG_COL.get(m.group(1).lower(), m.group(1))}]"]
        pos = m.end()
    parts.append(lit(q[pos:]))
    parts = [x for x in parts if x != "''"]
    return parts[0] if len(parts) == 1 else 'CONCAT(' + ', '.join(parts) + ')'


# ---------------------------------------------------------------- REST request of an incremental API (the watermark is inside the request)
WM_VAL = re.compile(r'item\(\)\.WatermarkVal(?![A-Za-z_])', re.I)
URL_PARAM = re.compile(r'^(?:query|relativeurl|prelativeurl|url|path|relative_url)$', re.I)


def requests_path(src):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '2-config', 'migration', 'request-urls', f'{src.upper()}.json')


def dpv1_rest_request(S, pd):
    """The request a DPV1 REST Copy builds from the catalog row: dataset parameter (Query, relativeUrl...) whose expression reads item().X only.
    Returns {'pipeline', 'param', 'source', 'expression', 'manual'}; 'expression' has item().WatermarkVal replaced by item().WatermarkNow (the
    live watermark the Lookup returns). 'manual' says why none could be derived (pipeline parameters, variables). {} when DPV1 has no REST Copy."""
    best = {}
    for name, p in sorted(legacy_pipelines(S, pd).items()):
        for a in _walk(p['properties'].get('activities')):
            if a['type'] != 'Copy' or a['typeProperties'].get('source', {}).get('type') != 'RestSource':
                continue
            for inp in a.get('inputs') or []:
                for k, v in (inp.get('parameters') or {}).items():
                    v = v.get('value') if isinstance(v, dict) else v
                    if not (URL_PARAM.match(k) and isinstance(v, str) and v.startswith('@')):
                        continue
                    cand = {'pipeline': name, 'param': k, 'source': re.sub(r'\s+', ' ', v).strip()}
                    dyn = re.findall(r'(?:pipeline\(\)\.parameters|variables\(|activity\()[^,)]*', v)
                    if 'item()' not in v:
                        cand['manual'] = 'the request does not come from the catalog row'
                    elif dyn:
                        cand['manual'] = 'the request uses ' + ', '.join(sorted(set(dyn))[:3]) + ' (parent pipeline or variables): write it in "override"'
                    else:
                        cand['expression'] = WM_VAL.sub('item().WatermarkNow', cand['source'])
                    rank = (bool(cand.get('expression')), bool(WM_VAL.search(v)))
                    if not best or rank > best['_rank']:
                        best = dict(cand, _rank=rank)
    best.pop('_rank', None)
    return best


def save_rest_request(c):
    """Write 2-config/migration/request-urls/<SRC>.json from the DPV1 REST Copy (S2). 'override' is kept: a hand-written expression wins."""
    p = requests_path(c.src)
    old = read_json(p) if exists(p) else {}
    r = dpv1_rest_request(c.S, c.pd) or {'manual': 'no REST Copy with a request expression was found in DPV1 (the request is built elsewhere): write it in "override"'}
    doc = {'_doc': f'Request (relativeUrl) of the REST Copy of {c.src}, generated from the DPV1 Copy by ingestion.save_rest_request (S2). item().WatermarkVal became item().WatermarkNow '
                   '(the live watermark, ISO 8601 with Z as a Synapse Lookup returned it). Write a hand-made expression in "override" (kept by every build).',
           'pipeline': r.get('pipeline', ''), 'param': r.get('param', ''), 'source': r.get('source', ''), 'expression': r.get('expression', ''), 'manual': r.get('manual', ''),
           'override': old.get('override', '')}
    write(p, json.dumps(doc, indent=2, ensure_ascii=False) + '\n')
    return doc


def rest_request_expr(c):
    """Expression for the relativeUrl of an incremental REST Copy: override, else the translated DPV1 request, else None (SourcePath is used)."""
    p = requests_path(c.src)
    d = read_json(p) if exists(p) else {}
    e = d.get('override') or d.get('expression') or ''
    return e if e.startswith('@') else None


# ---------------------------------------------------------------- REST header taken from Key Vault (DPV1 linked service authHeaders)
def dpv1_auth_headers(S, pd, conn_ls, conn_type):
    """Headers the DPV1 REST linked service sends with every call, read from a Key Vault secret (authHeaders: {'ocp-apim-subscription-key': {secretName}}).
    A Fabric REST connection cannot carry a header: each REST Copy sends it as an additional header, the secret read by a Web activity.
    Returns {} when there is none, else {'headers': {name: {'secret'}}, 'vaults': [vault url], 'api_version'}."""
    f = os.path.join(paths()['dpv1_export_root'], 'linkedService', f'{conn_ls}.json')
    if conn_type != 'RestService' or not conn_ls or not exists(f):
        return {}
    tp = (read_json(f).get('properties') or {}).get('typeProperties') or {}
    hdrs = {h: {'secret': v['secretName']} for h, v in (tp.get('authHeaders') or {}).items() if isinstance(v, dict) and v.get('secretName')}
    if not hdrs:
        return {}
    vaults, ver = set(), '7.0'
    for p in legacy_pipelines(S, pd).values():  # the Web activity of DPV1 that reads the secret: vault urls per environment, api-version
        for a in _walk(p['properties'].get('activities')):
            u = _text((a.get('typeProperties') or {}).get('url')) if a['type'] == 'WebActivity' else ''
            if any(f"secrets/{v['secret']}" in u for v in hdrs.values()):
                vaults.update(re.findall(r'https://[\w.-]+\.vault\.azure\.net/', u))
                m = re.search(r'api-version=([\w.\-]+)', u)
                ver = m.group(1) if m else ver
    return {'headers': hdrs, 'vaults': sorted(vaults), 'api_version': ver}


def keyvault_var(src):
    return f'{src.upper()}_KEYVAULT_CONN_ID'


def auth_activities(b, c, hdrs, depends=None):
    """Web activities that read the header secrets (Key Vault through a Web v2 connection), and the expression of the additionalHeaders object."""
    acts, parts = [], []
    for h, v in hdrs['headers'].items():
        name = f"Get secret {v['secret']}"
        out = f"activity('{name}').output"
        acts.append({'name': name, 'type': 'WebActivity', 'dependsOn': depends or [],
                     'policy': {'timeout': '0.00:10:00', 'retry': 2, 'retryIntervalInSeconds': 30, 'secureInput': True, 'secureOutput': True},
                     'description': f"DPV1 `Get APIM SubKey`: reads the Key Vault secret `{v['secret']}` (header `{h}` of the DPV1 linked service {c.conn_ls}). The output is secure.",
                     'typeProperties': {'method': 'GET', 'relativeUrl': f"secrets/{v['secret']}?api-version={hdrs['api_version']}"},
                     'externalReferences': {'connection': f'@pipeline().libraryVariables.{keyvault_var(c.src)}'}})
        parts.append(f"'\"{h}\":\"', if(contains({out}, 'value'), {out}.value, {out}.data.value), '\"'")
    expr = "@json(concat('{', " + ", ',', ".join(parts) + ", '}'))"
    return acts, expr


def add_auth_headers(b, c, acts, hdrs, wait_on):
    """Parent/child pipeline: the secret activities, additionalHeaders on every REST Copy, and the activities in `wait_on` wait for the secret."""
    kv, expr = auth_activities(b, c, hdrs)
    names = [a['name'] for a in kv]
    cond = lambda: [{'activity': n, 'dependencyConditions': ['Succeeded']} for n in names]

    def walk(items):
        for a in items:
            tp = a.get('typeProperties', {})
            if a['type'] == 'Copy' and tp.get('source', {}).get('type') == 'RestSource':
                tp['source']['additionalHeaders'] = b.expr(expr)
            for k in ('activities', 'ifTrueActivities', 'ifFalseActivities'):
                walk(tp.get(k) or [])
    walk(acts)
    for a in acts:
        if a['name'] in wait_on:
            a['dependsOn'] = a.get('dependsOn', []) + cond()
    fail = {'name': 'Fail Key Vault', 'type': 'Fail', 'dependsOn': [{'activity': n, 'dependencyConditions': ['Failed']} for n in names],
            'typeProperties': {'errorCode': 'KEYVAULT_SECRET_FAILED', 'message': f"The pipeline could not read the Key Vault secret(s) {', '.join(v['secret'] for v in hdrs['headers'].values())}: check the connection {keyvault_var(c.src)} and its access."}}
    return kv + acts + [fail]


# ---------------------------------------------------------------- REST API called once per item of a parent API (DPV1: child pipeline with a ForEach)
def loops_path(src):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '2-config', 'migration', 'rest-loops', f'{src.upper()}.json')


def _text(v):
    return str(v.get('value') if isinstance(v, dict) else v)


def dpv1_rest_loop(S, pd):
    """The DPV1 pattern "parent API, then one call per item": the parent pipeline fetches a list (Web activity + Filter), a Switch on the catalog column
    ParamName sends the rows that have one to a child pipeline (ExecutePipeline), and the child runs a ForEach over the list with one REST Copy per item
    (URL: <api>/?<ParamName>=<item key>&LastSyncDate=...). Returns {} when DPV1 has no such pattern (every other source), else
    {'parent', 'child', 'param_column', 'list_url', 'list_filter', 'item_key', 'batch', 'url', 'manual', ...}; 'manual' says what could not be derived."""
    pls = legacy_pipelines(S, pd)
    for pname, p in sorted(pls.items()):
        acts = list(_walk(p['properties'].get('activities')))
        for ex in (a for a in acts if a['type'] == 'ExecutePipeline'):
            child = pls.get((ex['typeProperties'].get('pipeline') or {}).get('referenceName'))
            if not child:
                continue
            cparams = child['properties'].get('parameters') or {}
            given = ex['typeProperties'].get('parameters') or {}
            arr = next((k for k, v in given.items() if (cparams.get(k) or {}).get('type', '').lower() == 'array' and re.search(r"activity\('[^']+'\)\.output\.value", _text(v))), None)
            obj = next((k for k, v in given.items() if (cparams.get(k) or {}).get('type', '').lower() == 'object' and _text(v).strip() == '@item()'), None)
            if not (arr and obj):
                continue
            flt_name = re.search(r"activity\('([^']+)'\)", _text(given[arr])).group(1)
            flt = next((a for a in acts if a['type'] == 'Filter' and a['name'] == flt_name), None)
            cacts = list(_walk(child['properties'].get('activities')))
            fe = next((a for a in cacts if a['type'] == 'ForEach' and f'parameters.{arr}' in _text(a['typeProperties'].get('items'))), None)
            cp = next((a for a in _walk((fe or {}).get('typeProperties', {}).get('activities')) if a['type'] == 'Copy' and a['typeProperties'].get('source', {}).get('type') == 'RestSource'), None)
            if not (flt and fe and cp):
                continue
            r = {'parent': pname, 'child': ex['typeProperties']['pipeline']['referenceName'], 'list_activity': '', 'list_url': '', 'list_filter': '', 'item_key': '',
                 'param_column': '', 'batch': fe['typeProperties'].get('batchCount') or 20, 'url': '', 'object_param': obj, 'array_param': arr, 'manual': ''}
            sw = next((a for a in acts if a['type'] == 'Switch'), None)
            m = re.search(r'item\(\)\.(\w+)', _text(sw['typeProperties']['on'])) if sw else None
            r['param_column'] = m.group(1) if m else ''
            fm = re.search(r"activity\('([^']+)'\)", _text(flt['typeProperties']['items']))
            web = next((a for a in acts if a['type'] == 'WebActivity' and fm and a['name'] == fm.group(1)), None)
            r['list_activity'] = web['name'] if web else ''
            r['list_filter'] = re.sub(r'\s+', ' ', _text(flt['typeProperties']['condition'])).strip()
            km = re.search(r'item\(\)\.(\w+)', r['list_filter'])
            r['item_key'] = km.group(1) if km else ''
            um = re.search(r'@\{pipeline\(\)\.parameters\.(\w+)\}([^@{}\s]*)\s*$', _text(web['typeProperties'].get('url'))) if web else None
            if um:
                r['list_url'] = ((p['properties'].get('parameters') or {}).get(um.group(1)) or {}).get('defaultValue', '') + um.group(2)
            sets = {a['typeProperties'].get('variableName'): _text(a['typeProperties'].get('value')) for a in cacts if a['type'] == 'SetVariable'}
            for inp in cp.get('inputs') or []:
                for k, v in (inp.get('parameters') or {}).items():
                    if URL_PARAM.match(k) and _text(v).startswith('@'):
                        u = re.sub(r'\s+', ' ', _text(v)).strip()
                        u = re.sub(r"variables\('(\w+)'\)", lambda mm: (sets.get(mm.group(1)) or mm.group(0)).lstrip('@'), u)
                        r['url'] = re.sub(r'(?<![A-Za-z_])WatermarkVal(?![A-Za-z_])', 'WatermarkNow', u)
            miss = [n for n, v in (('the list URL (Web activity)', r['list_url']), ('the list filter', r['list_filter']), ('the item key', r['item_key']),
                                   ('the catalog column that selects these rows', r['param_column']), ('the request of the child Copy', r['url'])) if not v]
            if r['list_filter'] and not re.fullmatch(r'@greater\(length\(item\(\)\.\w+\), ?0\)', r['list_filter']):
                miss.append('the list filter (only "the item has a key" is built)')
            if 'variables(' in r['url']:
                miss.append('the request of the child Copy (variables left)')
            r['manual'] = ('could not derive ' + ', '.join(miss) + ': write the values in "override"') if miss else ''
            return r
    return {}


def save_rest_loop(c):
    """Write 2-config/migration/rest-loops/<SRC>.json from the DPV1 pattern (S2) and return it with the overrides applied; {} when DPV1 has none.
    'override' (kept): any key of the detected pattern, replaced by hand."""
    r = dpv1_rest_loop(c.S, c.pd)
    if not r:
        return {}
    p = loops_path(c.src)
    old = read_json(p) if exists(p) else {}
    doc = {'_doc': f'REST API of {c.src} called once per item of a parent API (DPV1: child pipeline with a ForEach), generated from the DPV1 pipelines by '
                   'ingestion.save_rest_loop (S2). Write replacements in "override" (any key below; kept by every build).', **r, 'override': old.get('override') or {}}
    write(p, json.dumps(doc, indent=2, ensure_ascii=False) + '\n')
    got = dict(r, **doc['override'])
    need = ('list_url', 'list_filter', 'item_key', 'param_column', 'url')
    got['manual'] = '' if all(got.get(k) for k in need) and 'variables(' not in got['url'] else (r['manual'] or 'incomplete override')
    return got


# ---------------------------------------------------------------- one source, two kinds of input (database + files)
def files_path(src):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '2-config', 'migration', 'file-inputs', f'{src.upper()}.json')


def detect_file_inputs(S, O, m, pd):
    """Files (SharePoint, Excel, CSV, SFTP...) that a source ingests next to its database, from the DPV1 code: the second connection, where the files
    are (pipeline parameters, Graph folder) and the tables the data products read from them (INP_<X>.<NAME> where INP_<X> is not the database input).
    {} when the source has no second input."""
    main_ls = source_kind(S, O)[0]
    ls = [(r['v1'], O['linkedService'].get(r['v1'], {}).get('type', '')) for r in S['rows'] if r['v1t'] == 'Linked service' and r['v2t'] == 'Connection' and r['v1'] != main_ls]
    ls = [(n, t) for n, t in ls if (t in FILES or 'SharePoint' in t) and t not in INTERNAL]
    if not ls or source_kind(S, O)[2] != 'structured':
        return {}
    import classify_scenarios as cs
    folder_hits, kinds = set(), set()
    for n in S['pipelines']:
        for a in _walk((cs.dpv1('pipeline', n) or {}).get('properties', {}).get('activities')):
            j = json.dumps(a.get('typeProperties', {}))
            if a['type'] == 'WebActivity' and re.search(r'(?i)graph\.microsoft|sharepoint', j):
                kinds.add('sharepoint')
                folder_hits |= {x.replace('%20', ' ') for x in re.findall(r'root:/([^:"\\]+)', j)}
    tables = set()
    cat = {c['table'].lower() for c in S['catalog']}
    for D in m['dp'].values():
        if D['upstream'] == [S['folder']]:  # a product with several sources reads other schemas too: its names are not attributed to this source
            for n in set(D['pipelines']) | set(D['sqlscripts']):
                txt = '\n'.join(cs.scripts_of(cs.dpv1('pipeline', n))) if n in D['pipelines'] else (((cs.dpv1('sqlscript', n) or {}).get('properties', {}).get('content') or {}).get('query', ''))
                for sch, t in re.findall(r'\binp_([a-z0-9_]+)\]?\.\[?([a-z0-9_]+?)(?:_vw)?\]?(?![a-z0-9_])', txt.replace("''", "'").lower()):
                    if sch != S['folder'].lower().replace('-', '_') and not t.startswith('sp_') and t not in cat:
                        tables.add((sch, t))
    sch_names = sorted({s for s, _ in tables})
    return {'connection': ls[0][0], 'conn_type': ls[0][1], 'kind': 'sharepoint' if 'sharepoint' in kinds else 'files', 'folder': sorted(folder_hits)[0] if folder_hits else '',
            'schema': sch_names[0].upper() if len(sch_names) == 1 else '', 'format': 'csv',
            'tables': [{'name': t.upper(), 'format': 'csv', 'path': f'{t.upper()}.csv', 'confirm': True} for _, t in sorted(tables)]}


def save_file_inputs(S, O, m, pd, src):
    """Write 2-config/migration/file-inputs/<SRC>.json (S1). 'overrides' (kept): {'tables': [...]} replaces the detected list, {'folder': ...}, {'format': ...}."""
    p = files_path(src)
    old = read_json(p) if exists(p) else {}
    d = detect_file_inputs(S, O, m, pd)
    if not d and not old.get('overrides'):
        return {}
    ov = old.get('overrides', {})
    doc = {'_doc': f'Files that {src} ingests next to its database (generated from the DPV1 code by ingestion.save_file_inputs). Each table becomes a catalog row with ConnectionKey "files". '
                   '"confirm": true = inferred from the tables the data products read: confirm the file or sheet with the owner (framing question Q13). '
                   'Write corrections in "overrides" (kept by every build): {"tables": [{"name", "format", "path"}], "folder", "format"}.',
           **d, 'overrides': ov}
    write(p, json.dumps(doc, indent=2, ensure_ascii=False) + '\n')
    return effective_file_inputs(doc)


def effective_file_inputs(d):
    """The detected file inputs with the overrides applied."""
    if not d:
        return {}
    ov = d.get('overrides') or {}
    out = dict(d, folder=ov.get('folder', d.get('folder', '')), format=ov.get('format', d.get('format', 'csv')))
    out['tables'] = ov.get('tables') or d.get('tables', [])
    return out


def file_inputs(src):
    p = files_path(src)
    return effective_file_inputs(read_json(p)) if exists(p) else {}


def files_ctx(c):
    """A copy of the build context for the file group of a mixed source: semi-structured, its own connection, landing then flatten."""
    import copy
    f = copy.copy(c)
    fi = c.files
    f.method, f.conn_type, f.conn_var, f.fmt, f.dialect, f.raw_dates, f.incremental, f.conn_key = 'semi-structured', fi['conn_type'], fi['conn_var'], fi.get('format', 'csv'), None, True, False, 'files'
    return f


def lookup_sql(c):
    """Active catalog rows, plus ExtractQuery (structured) and Since (changes since the watermark minus 1 day, as DPV1)."""
    wm = "@{pipeline().libraryVariables." + V(c, 'CATALOG_WATERMARK_TABLE_NAME') + "}" if c.incremental else None
    since = ("DATEADD(day, -1, COALESCE(w.WatermarkVal, TRY_CAST(c.WatermarkValue AS datetime2(6)), CAST('2000-01-01' AS datetime2(6))))" if wm
             else "CAST('2000-01-01' AS datetime2(6))")
    d = c.dialect
    q = {'tsql': ("CONCAT('[', c.SchemaName, '].[', c.SourceName, ']')", "CONCAT('COALESCE([', c.WatermarkColumn, '], ''2000-01-01'')')",
                  "CONCAT('''', CONVERT(varchar(23), {s}, 121), '''')"),
         'oracle': ("CONCAT('\"', c.SchemaName, '\".\"', c.SourceName, '\"')", "CONCAT('NVL(\"', c.WatermarkColumn, '\", DATE ''2000-01-01'')')",
                    "CONCAT('TO_TIMESTAMP(''', CONVERT(varchar(19), {s}, 120), ''', ''YYYY-MM-DD HH24:MI:SS'')')"),
         'ansi': ("CONCAT('\"', c.SchemaName, '\".\"', c.SourceName, '\"')", "CONCAT('COALESCE(\"', c.WatermarkColumn, '\", ''2000-01-01'')')",
                  "CONCAT('TIMESTAMP ''', CONVERT(varchar(19), {s}, 120), '''')")}.get(d)
    cols = ["c.*", f"CONVERT(varchar(33), {since}, 126) AS Since"]
    if wm:  # the live watermark as DPV1 expressions read it (item().WatermarkVal): ISO 8601 with Z, null when the table never loaded
        cols.append("CONCAT(CONVERT(varchar(19), COALESCE(w.WatermarkVal, TRY_CAST(c.WatermarkValue AS datetime2(6))), 126), 'Z') AS WatermarkNow")
    if q:
        tbl, col, lit = q
        lit = lit.format(s=since)
        # DPV1 per-table queries (Switch on the table name => extract-queries/<SRC>.json): the other tables run SELECT *.
        # An incremental table keeps its query, wrapped: SELECT * FROM (<query>) q WHERE <watermark> > <since>.
        on, custom = extract_queries(c)
        full = f"CONCAT('SELECT * FROM ', {tbl})"
        inc = f"CONCAT('SELECT * FROM ', {tbl}, ' WHERE ', {col}, ' > ', {lit})"
        if custom:
            def when(wrap):
                return ' '.join(f"WHEN c.[{on}] = '{t.replace(chr(39), chr(39) * 2)}' THEN {wrap(query_expr(q))}" for t, q in custom.items())

            def since_filter(e):
                return f"CONCAT('SELECT * FROM (', {e}, ') q WHERE ', {col}, ' > ', {lit})"
            full = f'CASE {when(lambda e: e)} ELSE {full} END'
            if c.incremental:  # a full-load source never takes this branch: keep the Lookup short
                inc = f'CASE {when(since_filter)} ELSE {inc} END'
        cols.append(f"CASE WHEN c.LoadMethod = 'incremental' AND c.WatermarkColumn IS NOT NULL\n"
                    f"     THEN {inc}\n"
                    f"     ELSE {full} END AS ExtractQuery")
    sql = "SELECT " + ",\n       ".join(cols) + "\nFROM @{pipeline().libraryVariables." + V(c, 'CATALOG_VIEW_NAME') + "} AS c\n"
    if wm:
        sql += f"LEFT JOIN {wm} AS w ON w.SchemaName = c.SchemaName AND w.TableName = c.TableName\n"
    key = getattr(c, 'conn_key', None)  # mixed source: this Lookup reads the rows of its own input group only
    return sql + "WHERE c.Active = 1" + (f" AND c.ConnectionKey = '{key}'" if key else '')


def catalog_lookup(b, c, depends, name=LKP):
    return {'name': name, 'type': 'Lookup', 'dependsOn': depends,
            'description': f'Active tables of {c.src} from the catalog view (with the extract query and the watermark), names from VL_MAIN.' + (' Files group of a mixed source.' if name != LKP else ''),
            'policy': {'timeout': '0.00:10:00', 'retry': 2, 'retryIntervalInSeconds': 30},
            'typeProperties': {'source': {'type': 'DataWarehouseSource', 'partitionOption': 'None', 'queryTimeout': '02:00:00', 'sqlReaderQuery': b.expr(lookup_sql(c))},
                               'firstRowOnly': False,
                               'datasetSettings': {'type': 'DataWarehouseTable', 'schema': [], 'annotations': [], 'typeProperties': {},
                                                   'connectionSettings': warehouse(b, c)}}}


def append_on(b, name, after, condition, variable, value, desc):
    """AppendVariable that runs after one activity of a ForEach iteration (DPV1 "Append Success Files"). A failed Copy followed by
    its Failed path counts as a handled iteration, so the other tables carry on."""
    return {'name': name, 'type': 'AppendVariable', 'dependsOn': [{'activity': after, 'dependencyConditions': [condition]}], 'description': desc,
            'typeProperties': {'variableName': variable, 'value': b.expr(value)}}


def return_value(b, depends, pairs):
    """Pipeline return value (Fabric Set Variable 'pipelineReturnValue'): read by the caller as
    @activity('<Execute ...>').output.pipelineReturnValue.<key>."""
    return {'name': 'Return loaded and failed tables', 'type': 'SetVariable', 'dependsOn': depends, 'policy': {'secureInput': False, 'secureOutput': False},
            'description': 'Gives the master the tables that went through this step and the ones that failed, with their error.',
            'typeProperties': {'variableName': 'pipelineReturnValue', 'setSystemVariable': True,
                               'value': [{'key': k, 'value': {'type': 'Expression', 'content': v}} for k, v in pairs]}}


RUN = "@{pipeline().parameters.RunPartition}"
RUN_DEFAULT = ("@concat(formatDateTime(pipeline().TriggerTime, 'yyyy/MM/dd'), '/', formatDateTime(pipeline().TriggerTime, 'HH'), 'h', "
               "formatDateTime(pipeline().TriggerTime, 'mm'))")


def folder(b, c, root, run="@{variables('Run')}"):
    """Folder of one catalog row:
    structured        raw/<src>/<entity>[/<yyyy>/<mm>/<dd>/<HHhMM>][/HISTORY|/DELETE_LOGS]   date tree only when DPV1 raw had one
    semi-structured   landing/<src>/<yyyy>/<mm>/<dd>/<HHhMM>/                                  every table of the run, as delivered"""
    if root == 'LandingRoot':
        return b.expr(f"@{{pipeline().parameters.LandingRoot}}/{run}")
    dated = f"/{run}" if c.raw_dates else ''
    return b.expr(f"@{{pipeline().parameters.RawRoot}}/@{{item().EntityName}}{dated}@{{item().FolderTail}}")


def lake_location(b, c, root, file_name=None):
    loc = {'type': 'LakehouseLocation', 'folderPath': folder(b, c, root)}
    if file_name:
        loc['fileName'] = b.expr(file_name)
    return loc


def parquet_sink(b, c, root):
    return {'type': 'ParquetSink', 'formatSettings': {'type': 'ParquetWriteSettings', 'enableVertiParquet': True},
            'storeSettings': {'type': 'LakehouseWriteSettings', 'copyBehavior': 'PreserveHierarchy'},
            'datasetSettings': {'type': 'Parquet', 'typeProperties': {'location': lake_location(b, c, root, None if c.raw_dates else '@{item().EntityName}.parquet'),
                                                                      'compressionCodec': 'snappy'}, 'schema': [],
                                'connectionSettings': c.lakehouse_settings(), 'annotations': []}}


def copy_activity(b, c):
    """One Copy per catalog row. Structured: the ExtractQuery of the row => parquet in raw. Semi-structured: the files or API pages => landing."""
    policy = {'timeout': '7.00:00:00', 'retry': 3, 'retryIntervalInSeconds': 60}
    conn = {'connection': f'@pipeline().libraryVariables.{c.conn_var}'}
    if c.method == 'structured':
        src_type, ds_type, _ = DB[c.conn_type]
        if c.dialect == 'list':
            source = {'type': src_type, 'httpRequestTimeout': '00:05:00'}
            ds = {'type': ds_type, 'annotations': [], 'typeProperties': {'listName': b.expr('@item().SourcePath')}, 'externalReferences': conn}
        else:
            source = {'type': src_type, 'partitionOption': 'None', 'queryTimeout': '02:00:00', 'sqlReaderQuery': b.expr('@item().ExtractQuery')}
            if c.conn_type == 'Oracle':  # NUMBER without precision is Decimal(256,130) by default: Spark reads at most 38
                source.update(numberPrecision=38, numberScale=10)
            ds = {'type': ds_type, 'annotations': [], 'externalReferences': conn,  # the query wins; schema / table name the source object
                  'typeProperties': {'schema': b.expr('@item().SchemaName'), 'table': b.expr('@item().SourceName')}}
        return {'name': 'Extract to RAW parquet', 'type': 'Copy', 'dependsOn': [], 'policy': policy,
                'description': 'Runs the ExtractQuery of the catalog row (full table, or changes since the watermark minus 1 day) and writes parquet once, '
                               'straight to Files/raw (DPV1: Copy into RAW/DATASOURCE=…).',
                'typeProperties': {'source': dict(source, datasetSettings=ds), 'sink': parquet_sink(b, c, 'RawRoot'), 'enableStaging': False,
                                   'translator': {'type': 'TabularTranslator', 'typeConversion': True,
                                                  'typeConversionSettings': {'allowDataTruncation': True, 'treatBooleanAsNumber': False}}}}
    land = lake_location(b, c, 'LandingRoot')
    if c.conn_type == 'RestService':
        land = lake_location(b, c, 'LandingRoot', '@{item().EntityName}.json')  # one file per table in the run folder
        source = {'type': 'RestSource', 'httpRequestTimeout': '00:05:00', 'requestInterval': '00.00:00:00.010', 'requestMethod': 'GET'}
        if c.pagination:
            source['paginationRules'] = c.pagination
        req = rest_request_expr(c) if c.incremental else None  # incremental API: the watermark is inside the request (DPV1 expression)
        ds = {'type': 'RestResource', 'annotations': [], 'typeProperties': {'relativeUrl': b.expr(req or '@item().SourcePath')}, 'externalReferences': conn}
        sink = {'type': 'JsonSink', 'storeSettings': {'type': 'LakehouseWriteSettings'}, 'formatSettings': {'type': 'JsonWriteSettings'},
                'datasetSettings': {'type': 'Json', 'typeProperties': {'location': land}, 'schema': {}, 'connectionSettings': c.lakehouse_settings(), 'annotations': []}}
        desc = 'Reads the API path of the catalog row page by page (DPV1 pagination) and lands the JSON as delivered.'
    else:
        store = {'type': FILES.get(c.conn_type, 'SftpReadSettings'), 'recursive': False, 'wildcardFileName': b.expr('@item().SourcePath')}
        if c.incremental:
            store['modifiedDatetimeStart'] = b.expr("@if(equals(item().LoadMethod, 'incremental'), item().Since, '1900-01-01T00:00:00Z')")
        loc = {'type': LOCATION.get(c.conn_type, 'SftpLocation')}
        if c.conn_type == 'HttpServer':  # HTTP has no wildcard: the file is a relative URL of the connection (SharePoint through Graph: root:/<folder>/<file>:/content)
            fold = (getattr(c, 'files', None) or {}).get('folder', '').replace(' ', '%20')
            store = {'type': 'HttpReadSettings', 'requestMethod': 'GET'}
            loc['relativeUrl'] = b.expr(f"@concat('root:/{fold}/', item().SourcePath, ':/content')" if fold else '@item().SourcePath')
        source = {'type': 'BinarySource', 'storeSettings': store, 'formatSettings': {'type': 'BinaryReadSettings'}}
        ds = {'type': 'Binary', 'annotations': [], 'typeProperties': {'location': loc}, 'externalReferences': conn}
        if c.conn_type == 'HttpServer':  # the URL does not name the file: the sink does (SourcePath), so the FLATTEN notebook finds it by that name
            land = lake_location(b, c, 'LandingRoot', '@{item().SourcePath}')
        sink = {'type': 'BinarySink', 'storeSettings': {'type': 'LakehouseWriteSettings', 'copyBehavior': 'PreserveHierarchy'},
                'datasetSettings': {'type': 'Binary', 'typeProperties': {'location': land}, 'connectionSettings': c.lakehouse_settings(), 'annotations': []}}
        desc = 'Copies the files that match the catalog row (only files changed since the watermark for incremental rows) and lands them as delivered.'
    return {'name': 'Land as delivered', 'type': 'Copy', 'dependsOn': [], 'policy': policy, 'description': desc,
            'typeProperties': {'source': dict(source, datasetSettings=ds), 'sink': sink, 'enableStaging': False}}


def loop_file_name(loop):
    """Landing file of one item of the list: <EntityName>~<item key>.json (the FLATTEN notebook reads <EntityName>.json and <EntityName>~*.json)."""
    return f"@{{pipeline().parameters.{loop['object_param']}.EntityName}}~@{{item().{loop['item_key']}}}.json"


def active_loop(c):
    """The REST loop (save_rest_loop) when this source has one that could be built, else {} (every source without the DPV1 pattern)."""
    if c.conn_type != 'RestService' or not c.incremental:
        return {}
    r = dpv1_rest_loop(c.S, c.pd)
    if not r:
        return {}
    p = loops_path(c.src)
    got = dict(r, **((read_json(p).get('override') if exists(p) else None) or {}))
    return got if all(got.get(k) for k in ('list_url', 'list_filter', 'item_key', 'param_column', 'url')) and 'variables(' not in got['url'] else {}


def build_loop_child(b, c, loop):
    """PL_<SRC>_SOURCE_TO_RAW_CHILD_API (DPV1 PL_RAWDATA_*_CHILD_API): one REST Copy per item of the list, 50 in parallel as DPV1, landing
    <EntityName>~<item key>.json in the run folder. A failed item fails the child, as DPV1 (the parent lists the API in FailedTables). Returns its logicalId."""
    conn = {'connection': f'@pipeline().libraryVariables.{c.conn_var}'}
    apim, items = loop['object_param'], loop['array_param']
    source = {'type': 'RestSource', 'httpRequestTimeout': '00:05:00', 'requestInterval': '00.00:00:00.010', 'requestMethod': 'GET'}
    if c.pagination:
        source['paginationRules'] = c.pagination
    ds = {'type': 'RestResource', 'annotations': [], 'typeProperties': {'relativeUrl': b.expr(loop['url'])}, 'externalReferences': conn}
    location = {'type': 'LakehouseLocation', 'folderPath': b.expr('@{pipeline().parameters.LandingRoot}/@{pipeline().parameters.Run}'), 'fileName': b.expr(loop_file_name(loop))}
    sink = {'type': 'JsonSink', 'storeSettings': {'type': 'LakehouseWriteSettings'}, 'formatSettings': {'type': 'JsonWriteSettings'},
            'datasetSettings': {'type': 'Json', 'typeProperties': {'location': location}, 'schema': {}, 'connectionSettings': c.lakehouse_settings(), 'annotations': []}}
    cp = {'name': 'Land item', 'type': 'Copy', 'dependsOn': [], 'policy': {'timeout': '7.00:00:00', 'retry': 3, 'retryIntervalInSeconds': 60},
          'description': f"One call of the API for this {loop['item_key']}: `{loop['url']}`. The JSON lands as delivered, one file per item.",
          'typeProperties': {'source': dict(source, datasetSettings=ds), 'sink': sink, 'enableStaging': False}}
    err = {'name': 'Add to errors', 'type': 'AppendVariable', 'dependsOn': [{'activity': 'Land item', 'dependencyConditions': ['Failed']}],
           'description': 'The failed item and the Copy error; the other items carry on, then the child fails (DPV1 INGESTION FAILURE).',
           'typeProperties': {'variableName': 'errors', 'value': b.expr(f"@concat(item().{loop['item_key']}, ': ', activity('Land item').error.message)")}}
    acts = [{'name': 'ForEach item', 'type': 'ForEach', 'dependsOn': [],
             'description': f"One Copy per item of the list ({loop['batch']} in parallel, as DPV1).",
             'typeProperties': {'isSequential': False, 'batchCount': loop['batch'], 'items': b.expr(f'@pipeline().parameters.{items}'), 'activities': [cp, err]}},
            {'name': 'Any item failed', 'type': 'IfCondition', 'dependsOn': [{'activity': 'ForEach item', 'dependencyConditions': ['Succeeded']}],
             'typeProperties': {'expression': b.expr("@greater(length(variables('errors')), 0)"), 'ifFalseActivities': [], 'ifTrueActivities': [
                 {'name': 'Fail on failed items', 'type': 'Fail', 'dependsOn': [],
                  'typeProperties': {'errorCode': 'API_ITEM_FAILED', 'message': b.expr(
                      f"@concat(pipeline().parameters.{apim}.ApiName, ': ', string(length(variables('errors'))), ' call(s) failed, first: ', string(first(variables('errors'))))")}}]}},
            {'name': 'Fail Item Loop', 'type': 'Fail', 'dependsOn': [{'activity': 'ForEach item', 'dependencyConditions': ['Failed']}],
             'typeProperties': {'errorCode': 'API_LOOP_FAILED', 'message': f'PL_{c.src}_SOURCE_TO_RAW_CHILD_API could not run the loop over the list.'}}]
    hdrs = dpv1_auth_headers(c.S, c.pd, c.conn_ls, c.conn_type)
    if hdrs:
        acts = add_auth_headers(b, c, acts, hdrs, {'ForEach item'})
    lv = lambda n: {'type': 'String', 'variableName': n, 'libraryName': 'VL_MAIN'}
    content = {'properties': {'activities': acts,
                              'parameters': {apim: {'type': 'Object'}, items: {'type': 'Array'}, 'Run': {'type': 'String'}, 'LandingRoot': {'type': 'String', 'defaultValue': c.landing}},
                              'variables': {'errors': {'type': 'Array', 'defaultValue': []}},
                              'libraryVariables': {n: lv(n) for n in libs(c, lakehouse=True, source=True, catalog=False) + ([keyvault_var(c.src)] if hdrs else [])}}}
    name = f'PL_{c.src}_SOURCE_TO_RAW_CHILD_API'
    out = c.out('1-SOURCE_TO_RAW', f'{name}.DataPipeline')
    lid = b.platform(out, 'DataPipeline', name, f"{c.src}: one REST call per {loop['item_key']} of the list, for the catalog rows that have a {loop['param_column']} (DPV1 {loop['child']}).")
    write(os.path.join(out, 'pipeline-content.json'), b.dump(content))
    return lid


LIST_FILE = 'list_of_items.json'

LIST_NB_PARAMS = """# Parameters: PL_<SRC>_SOURCE_TO_RAW overrides them; the values below let the notebook run on its own.
lakehouse_name = globals().get("lakehouse_name", "<LAKEHOUSE>")   # looked up in the workspace this notebook runs in: no default lakehouse needed
landing_root = globals().get("landing_root", "<LANDING_ROOT>").strip("/")
run_partition = globals().get("run_partition", "")      # yyyy/MM/dd/HHhmm of this run (the run folder of the landed list)"""

LIST_NB_CODE = """import json
import notebookutils

<LH_RESOLVE>

ITEM_KEY = "<ITEM_KEY>"      # DPV1 filter: the item has a <ITEM_KEY> (length > 0)
LIST_FILE = "<LIST_FILE>"    # landed by the Copy 'Land list of items' of PL_<SRC>_SOURCE_TO_RAW

path = f"{LH_ROOT}/Files/{landing_root}/{run_partition}/{LIST_FILE}"
text = notebookutils.fs.head(path, 100 * 1024 * 1024)
try:                                   # one JSON document (an array, or one object)
    data = json.loads(text)
except ValueError:                     # JSON lines: one item per line (what a Copy writes for a list)
    data = [json.loads(line) for line in text.splitlines() if line.strip()]
items = data if isinstance(data, list) else [data]
valid = [{ITEM_KEY: i[ITEM_KEY]} for i in items if isinstance(i, dict) and len(str(i.get(ITEM_KEY) or "")) > 0]
print(f"{len(items)} items in the list, {len(valid)} with a {ITEM_KEY}")
notebookutils.notebook.exit(json.dumps(valid))   # the pipeline loops over this array"""


def build_list_notebook(b, c, loop):
    """NB_<SRC>_LIST_ITEMS: reads the list of items that the Copy landed and returns the valid ones (DPV1 Filter 'Valid Projects') to the pipeline.
    The list is read from the lake, so the REST connection of the Copy (with the API key) is the only connection the source needs."""
    name = f'NB_{c.src}_LIST_ITEMS'
    folder = c.out('1-SOURCE_TO_RAW', f'{name}.Notebook')
    lid = b.platform(folder, 'Notebook', name, f"{c.src}: the valid items of the list that the REST API returns ({loop['list_url']}), for the per-item calls.")
    intro = '\n'.join([f'# # {name}', f"# Reads `{LIST_FILE}` (the answer of `{loop['list_url']}`, landed by `PL_{c.src}_SOURCE_TO_RAW`) and returns the items that have a `{loop['item_key']}`.",
                       '# ', f"# **Replaces (DPV1):** the Web activities `Get APIM SubKey` and `{loop['list_activity']}` and the Filter `{loop['list_filter']}` of `{loop['parent']}`."])
    code = LIST_NB_CODE.replace('<LH_RESOLVE>', LH_RESOLVE)
    text = NOTEBOOK_HEAD + MARKDOWN.format(text=intro) + ''.join(CELL.format(code=x) for x in (LIST_NB_PARAMS, code))
    for k, v in {'<LAKEHOUSE>': c.lh, '<LANDING_ROOT>': c.landing, '<ITEM_KEY>': loop['item_key'], '<LIST_FILE>': LIST_FILE, '<SRC>': c.src}.items():
        text = text.replace(k, v)
    write(os.path.join(folder, 'notebook-content.py'), text)
    return lid


def apply_rest_loop(b, c, acts, loop, child_id, copy):
    """Parent changes for the parameterised APIs (DPV1 PL_RAWDATA_*: Get projects, Valid projects, Switch ExtractMode): the list of items is landed once
    (Copy through the same REST connection) and read by a notebook; each catalog row that has a ParamName runs the child pipeline instead of the single Copy.
    Returns the new activity list."""
    conn = {'connection': f'@pipeline().libraryVariables.{c.conn_var}'}
    source = {'type': 'RestSource', 'httpRequestTimeout': '00:05:00', 'requestInterval': '00.00:00:00.010', 'requestMethod': 'GET'}
    if c.pagination:
        source['paginationRules'] = c.pagination
    ds = {'type': 'RestResource', 'annotations': [], 'typeProperties': {'relativeUrl': loop['list_url']}, 'externalReferences': conn}
    location = {'type': 'LakehouseLocation', 'folderPath': b.expr("@{pipeline().parameters.LandingRoot}/@{variables('Run')}"), 'fileName': LIST_FILE}
    sink = {'type': 'JsonSink', 'storeSettings': {'type': 'LakehouseWriteSettings'}, 'formatSettings': {'type': 'JsonWriteSettings'},
            'datasetSettings': {'type': 'Json', 'typeProperties': {'location': location}, 'schema': {}, 'connectionSettings': c.lakehouse_settings(), 'annotations': []}}
    land = {'name': 'Land list of items', 'type': 'Copy', 'dependsOn': [{'activity': 'Set run partition', 'dependencyConditions': ['Succeeded']}],
            'policy': {'timeout': '0.01:00:00', 'retry': 3, 'retryIntervalInSeconds': 60},
            'description': f"DPV1 `{loop['list_activity']}`: calls `{loop['list_url']}` once and lands the answer; the parameterised APIs run for every item of it. "
                           'The API key is in the connection (DPV1 read it from Key Vault).',
            'typeProperties': {'source': dict(source, datasetSettings=ds), 'sink': sink, 'enableStaging': False}}
    param = lambda n, v: (n, {'value': b.expr(v), 'type': 'String'})
    nb_id = build_list_notebook(b, c, loop)
    valid = {'name': 'Valid items', 'type': 'TridentNotebook', 'dependsOn': [{'activity': 'Land list of items', 'dependencyConditions': ['Succeeded']}],
             'policy': {'timeout': '0.00:30:00', 'retry': 1, 'retryIntervalInSeconds': 60},
             'description': f"DPV1 filter: `{loop['list_filter']}`. Runs NB_{c.src}_LIST_ITEMS: reads the landed list and returns the items that have a {loop['item_key']}.",
             'typeProperties': {'notebookId': nb_id, 'workspaceId': b.ZERO, 'sessionTag': f'{c.src.lower()}-list-items', 'parameters': dict([
                 param('lakehouse_name', VL(V(c, 'LH_NAME'))), param('landing_root', '@pipeline().parameters.LandingRoot'), param('run_partition', "@variables('Run')")])}}
    each = next(a for a in acts if a['name'] == f'ForEach table in {c.src}')
    each['dependsOn'].append({'activity': 'Valid items', 'dependencyConditions': ['Succeeded']})
    inner = each['typeProperties']['activities']
    single, ok1, ko1 = inner
    ex_name = 'Run per item'
    ex = {'name': ex_name, 'type': 'ExecutePipeline', 'policy': {'secureInput': False}, 'dependsOn': [],
          'description': f"DPV1 `{loop['child']}`: one call per item of the list for this API, then waits for it.",
          'typeProperties': {'pipeline': {'referenceName': child_id, 'type': 'PipelineReference'}, 'waitOnCompletion': True,
                             'parameters': {loop['object_param']: b.expr('@item()'), loop['array_param']: b.expr("@json(activity('Valid items').output.result.exitValue)"),
                                            'Run': b.expr("@variables('Run')"), 'LandingRoot': b.expr('@pipeline().parameters.LandingRoot')}}}
    ok2 = append_on(b, 'Add API to loaded tables', ex_name, 'Succeeded', 'LoadedTables', '@string(item())', 'The catalog row of an API that landed for every item.')
    ko2 = append_on(b, 'Add API to failed tables', ex_name, 'Failed', 'FailedTables',
                    f"@concat(item().SchemaName, '.', item().TableName, ' (copy): ', activity('{ex_name}').error.message)", 'The API and the error of the child.')
    cond = {'name': 'Has a parameter', 'type': 'IfCondition', 'dependsOn': [],
            'description': f"DPV1 Switch ExtractMode: rows with a {loop['param_column']} run once per item (child pipeline), the others run one call.",
            'typeProperties': {'expression': b.expr(f"@not(empty(coalesce(item()?['{loop['param_column']}'], '')))"),
                               'ifTrueActivities': [ex, ok2, ko2], 'ifFalseActivities': [single, ok1, ko1]}}
    each['typeProperties']['activities'] = [cond]
    i = acts.index(each)
    fails = [{'name': 'Fail List of Items', 'type': 'Fail', 'dependsOn': [{'activity': 'Land list of items', 'dependencyConditions': ['Failed']}, {'activity': 'Valid items', 'dependencyConditions': ['Failed']}],
              'typeProperties': {'errorCode': 'LIST_OF_ITEMS_FAILED', 'message': f"PL_{c.src}_SOURCE_TO_RAW could not get the list `{loop['list_url']}` (connection, URL, answer) or read it."}}]
    return acts[:i] + [land, valid] + acts[i:] + fails


def build_s2(b, c):
    sw = save_switch_queries(c) if c.method == 'structured' else {}  # before the Lookup: lookup_sql reads it
    rq = save_rest_request(c) if (c.conn_type == 'RestService' and c.incremental) else {}  # before the Copy: copy_activity reads it
    loop = save_rest_loop(c) if (c.conn_type == 'RestService' and c.incremental) else {}  # DPV1 calls some APIs once per item of a list (child pipeline)
    copy = copy_activity(b, c)
    cf = files_ctx(c) if c.mixed else None  # files ingested next to the database: their own Lookup, ForEach and Copy in this pipeline
    fcopy = copy_activity(b, cf) if cf else None
    acts = [
        {'name': 'Set run partition', 'type': 'SetVariable', 'dependsOn': [],
         'description': 'Run folder yyyy/MM/dd/HHhmm: given by the master orchestrator (same folder for both children), or from the trigger time.',
         'typeProperties': {'variableName': 'Run', 'value': b.expr(f"@if(empty(pipeline().parameters.RunPartition), {RUN_DEFAULT[1:]}, pipeline().parameters.RunPartition)")}},
        catalog_lookup(b, c, [{'activity': 'Set run partition', 'dependencyConditions': ['Succeeded']}]),
        {'name': f'ForEach table in {c.src}', 'type': 'ForEach', 'dependsOn': [{'activity': LKP, 'dependencyConditions': ['Succeeded']}],
         'description': 'One Copy per catalog row, 20 in parallel. A table that copied is added to LoadedTables (only those go to the lakehouse); '
                        'a table that failed is added to FailedTables with its error, and the others carry on.',
         'typeProperties': {'isSequential': False, 'batchCount': 20, 'items': b.expr(f"@activity('{LKP}').output.value"), 'activities': [
             copy, append_on(b, 'Add to loaded tables', copy['name'], 'Succeeded', 'LoadedTables', '@string(item())',
                             'The catalog row of a table that copied: the notebook loads it with its keys and load method.'),
             append_on(b, 'Add to failed tables', copy['name'], 'Failed', 'FailedTables',
                       f"@concat(item().SchemaName, '.', item().TableName, ' (copy): ', activity('{copy['name']}').error.message)",
                       'The table and the Copy error: listed in the failure message of the master.')]}},
        return_value(b, [{'activity': f'ForEach table in {c.src}', 'dependencyConditions': ['Succeeded']}] + ([{'activity': 'ForEach file in ' + c.src, 'dependencyConditions': ['Succeeded']}] if cf else []),
                     [('LoadedTables', "@variables('LoadedTables')"), ('FailedTables', "@variables('FailedTables')")]),
        {'name': 'Fail Catalog Lookup', 'type': 'Fail', 'dependsOn': [{'activity': LKP, 'dependencyConditions': ['Failed']}],
         'typeProperties': {'errorCode': 'CATALOG_LOOKUP_FAILED', 'message': f'PL_{c.src}_SOURCE_TO_RAW could not read the catalog view (VL_MAIN names, warehouse).'}},
        {'name': 'Fail Copy Loop', 'type': 'Fail', 'dependsOn': [{'activity': f'ForEach table in {c.src}', 'dependencyConditions': ['Failed']}],
         'typeProperties': {'errorCode': 'SOURCE_TO_RAW_LOOP_FAILED', 'message': f'PL_{c.src}_SOURCE_TO_RAW failed for at least one table: open the failed Copy run.'}}]
    if cf:
        FL = 'GET FILES FROM CATALOG VIEW'
        acts += [catalog_lookup(b, cf, [{'activity': 'Set run partition', 'dependencyConditions': ['Succeeded']}], FL),
                 {'name': 'ForEach file in ' + c.src, 'type': 'ForEach', 'dependsOn': [{'activity': FL, 'dependencyConditions': ['Succeeded']}],
                  'description': 'One Copy per file of the catalog (ConnectionKey files): lands the file as delivered in Files/landing; the FLATTEN notebook converts it to parquet in Files/raw.',
                  'typeProperties': {'isSequential': False, 'batchCount': 10, 'items': b.expr(f"@activity('{FL}').output.value"), 'activities': [
                      fcopy, append_on(b, 'Add file to loaded tables', fcopy['name'], 'Succeeded', 'LoadedTables', '@string(item())', 'The catalog row of a file that landed: the FLATTEN notebook converts it, the loader writes the table.'),
                      append_on(b, 'Add file to failed tables', fcopy['name'], 'Failed', 'FailedTables',
                                f"@concat(item().SchemaName, '.', item().TableName, ' (file): ', activity('{fcopy['name']}').error.message)", 'The file and the Copy error.')]}},
                 {'name': 'Fail File Lookup', 'type': 'Fail', 'dependsOn': [{'activity': FL, 'dependencyConditions': ['Failed']}],
                  'typeProperties': {'errorCode': 'FILE_CATALOG_LOOKUP_FAILED', 'message': f'PL_{c.src}_SOURCE_TO_RAW could not read the file rows of the catalog view.'}},
                 {'name': 'Fail File Loop', 'type': 'Fail', 'dependsOn': [{'activity': 'ForEach file in ' + c.src, 'dependencyConditions': ['Failed']}],
                  'typeProperties': {'errorCode': 'FILES_LOOP_FAILED', 'message': f'PL_{c.src}_SOURCE_TO_RAW failed for at least one file: open the failed Copy run.'}}]
    extra = []
    if loop and not loop['manual']:
        acts = apply_rest_loop(b, c, acts, loop, build_loop_child(b, c, loop), copy)
        extra = [f"PL_{c.src}_SOURCE_TO_RAW_CHILD_API"]
    hdrs = dpv1_auth_headers(c.S, c.pd, c.conn_ls, c.conn_type)  # the DPV1 REST linked service sends a Key Vault secret as a header
    if hdrs:
        acts = add_auth_headers(b, c, acts, hdrs, {'Land list of items', f'ForEach table in {c.src}'})
    lv = lambda n: {'type': 'String', 'variableName': n, 'libraryName': 'VL_MAIN'}
    p = lambda v: {'type': 'String', 'defaultValue': v}
    params = {'RawRoot': p(c.raw), 'RunPartition': p('')}
    if c.method == 'semi-structured' or cf:
        params['LandingRoot'] = p(c.landing)
    content = {'properties': {'activities': acts, 'parameters': params,
                              'variables': {'Run': {'type': 'String'}, 'LoadedTables': {'type': 'Array', 'defaultValue': []}, 'FailedTables': {'type': 'Array', 'defaultValue': []}},
                              'libraryVariables': {n: lv(n) for n in dict.fromkeys(libs(c, lakehouse=True, warehouse=True, source=True) + ([cf.conn_var] if cf and cf.conn_var else []) + ([keyvault_var(c.src)] if hdrs else []))}}}
    name = f'PL_{c.src}_SOURCE_TO_RAW'
    out = c.out('1-SOURCE_TO_RAW', f'{name}.DataPipeline')
    zone = 'Files/raw (parquet, written once)' if c.method == 'structured' else 'Files/landing (as delivered)'
    b.platform(out, 'DataPipeline', name, f'{c.src} ({c.method}) => {zone}, one Copy per catalog row.')
    write(os.path.join(out, 'pipeline-content.json'), b.dump(content))
    L = [f'# S2 Source to RAW: {c.src} ({c.method}{", incremental" if c.incremental else ", full"})', '',
         f'- **Item**: `{c.ws}/{c.src}/1-SOURCE_TO_RAW/{name}`',
         f"- **Replaces (DPV1)**: {', '.join('`' + x + '`' for x in c.legacy['SOURCE_TO_RAW']) or 'none'}",
         f'- **Source**: {c.conn_type} through `{c.conn_ls}` => Fabric connection `{c.conn_var}`', '',
         '## Activities', '', '1. Set run partition (from the master, so both children use the same folder)',
         '2. Lookup on the catalog view: active rows' + (', watermark per table, `ExtractQuery`' if c.method == 'structured' else ', `Since`'),
         f"3. ForEach (20 in parallel): one Copy per row => `{c.tree_text()}`; a table that copied goes to `LoadedTables`, one that failed to `FailedTables` (with its error)",
         '4. Return both lists to the master: only `LoadedTables` goes on to the lakehouse; `FailedTables` ends the run with a failure message', '',
         '## Kept from DPV1', '', '- Table list and load mode from the catalog; watermark minus 1 day for incremental rows; the DPV1 folder tree',
         '## Removed (no effect on the data)', '',
         '- Copy landing => raw for databases (the extract is written once, as parquet)',
         '- "is there data?" calls and "clear landing" deletes: run folders make them unnecessary (DPV1 success list kept: `LoadedTables`)']
    if sw:
        on, used = extract_queries(c)
        L += ['', '## Per-table queries (DPV1 Switch)', '',
              f"DPV1 `{sw['pipeline']}` switches on `{sw['on']}` (`{sw['switch']}`): {len(used)} tables have their own query, the others run `SELECT *`. "
              'The Lookup returns the query of each row as `ExtractQuery`, so one Copy replaces the branches. File: `2-config/migration/extract-queries/' + c.src.upper() + '.json`.', '',
              *[f"- `{t}`" + (' (override)' if t in sw.get('overrides', {}) else '') for t in used]]
        if c.incremental:
            L.append('- Incremental rows keep their query: `SELECT * FROM (<query>) q WHERE <watermark> > <since>` (the query must return the watermark column)')
        L += [f"- ❌ `{t}`: {why}" for t, why in sw['manual'].items() if t not in sw.get('overrides', {})]
    if rq:
        L += ['', '## REST request with the watermark', '',
              f"DPV1 `{rq['pipeline']}` builds the request in the dataset parameter `{rq['param']}`. The Copy uses it as `relativeUrl`, with `item().WatermarkVal` replaced by `item().WatermarkNow` (the live watermark from the watermark table). File: `2-config/migration/request-urls/{c.src.upper()}.json`."]
        L += [f"- ❌ {rq['manual']}"] if rq.get('manual') and not rq.get('override') else []
    if c.method == 'semi-structured':
        L += ['', '## Check against DPV1', '',
              f"- API pagination: {'copied from DPV1 `' + c.pagination_from + '`' if c.pagination else 'none found in DPV1: add the pagination rules of the API'}",
              '- `SourcePath` of each catalog row: the API path or the file wildcard (from the DPV1 catalog or the DPV1 dataset)']
    if hdrs:
        L += ['', '## API key header from Key Vault (DPV1 linked service)', '',
              f"The DPV1 linked service `{c.conn_ls}` sends " + ', '.join(f"`{h}` (Key Vault secret `{v['secret']}`)" for h, v in hdrs['headers'].items()) + '. A Fabric REST connection cannot carry a header, so: '
              f"a Web activity reads the secret through the Web v2 connection `{keyvault_var(c.src)}` (vault {', '.join(hdrs['vaults']) or 'see DPV1'}, per environment), and every REST Copy sends it as an additional header. "
              'The secret activity has secure input and output: the key is not in the run log or the repository.']
    if loop:
        L += ['', '## APIs called once per item of a list (DPV1 child pipeline)', '',
              f"DPV1 `{loop['parent']}` gets `{loop['list_url']}` (filter `{loop['list_filter']}`), then runs `{loop['child']}` for every catalog row that has a `{loop['param_column']}`: "
              f"one REST Copy per `{loop['item_key']}` ({loop['batch']} in parallel). File: `2-config/migration/rest-loops/{c.src.upper()}.json`.", '']
        if loop['manual']:
            L += [f"- ❌ {loop['manual']} (until then the pipeline calls every API once, without the parameter)"]
        else:
            L += [f"- `Land list of items` (Copy through the same REST connection, so the API key is in the connection) and `Valid items` (`NB_{c.src}_LIST_ITEMS` reads the landed list, same filter) once per run",
                  f"- `Has a parameter` in the ForEach: rows without a {loop['param_column']} run the single Copy; rows with one run `PL_{c.src}_SOURCE_TO_RAW_CHILD_API`, one Copy per `{loop['item_key']}`: `{loop['url']}`",
                  f"- The child lands `<EntityName>~<{loop['item_key']}>.json` in the run folder; `NB_{c.src}_FLATTEN` reads `<EntityName>.json` and `<EntityName>~*.json`",
                  '- A failed item fails the API (DPV1 INGESTION FAILURE): the API goes to `FailedTables` with the error',
                  f"- The notebook returns `[{{{loop['item_key']}: …}}]`; the child gets it as `projectMetadata`"]
    write_note('sds', c.scope, 'S2-source-to-raw', '\n'.join(L) + '\n')
    return [name] + extra


NOTEBOOK_HEAD = '''# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   }
# META }
'''
CELL = '''
# CELL ********************

{code}

# METADATA ********************

# META {{
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }}
'''

MARKDOWN = """
# MARKDOWN ********************

{text}
"""

SNIPPETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates', 'raw-to-delta-snippets.py')


def snippets():
    """{name: code} from 0-shared/templates/raw-to-delta-snippets.py (the reusable functions, maintained once)."""
    text = read_text(SNIPPETS)
    parts = re.split(r'^# --- snippet: (\w+)\s*$', text, flags=re.M)
    return {parts[i]: parts[i + 1].strip('\n') for i in range(1, len(parts), 2)}


NB_PARAMS = """# Parameters: PL_<SRC>_RAW_TO_DELTA overrides them; the values below let the notebook run on its own.
lakehouse_name = globals().get("lakehouse_name", "<LAKEHOUSE>")   # looked up in the workspace this notebook runs in: no default lakehouse needed
tables_json = globals().get("tables_json", "[]")        # catalog rows of the tables that copied (or flattened) in this run
run_partition = globals().get("run_partition", "")      # yyyy/MM/dd/HHhmm of this run; empty = newest folder
raw_root = globals().get("raw_root", "<RAW_ROOT>").strip("/")
target_schema = globals().get("target_schema", "dbo")
max_parallel = int(globals().get("max_parallel", "8"))
pipeline_name = globals().get("pipeline_name", "NB_<SRC>_RAW_TO_DELTA")"""

FLATTEN_PARAMS = """# Parameters: PL_<SRC>_RAW_TO_DELTA overrides them; the values below let the notebook run on its own.
lakehouse_name = globals().get("lakehouse_name", "<LAKEHOUSE>")   # looked up in the workspace this notebook runs in: no default lakehouse needed
tables_json = globals().get("tables_json", "[]")        # catalog rows of the tables that copied in this run
run_partition = globals().get("run_partition", "")      # yyyy/MM/dd/HHhmm of this run; empty = newest folder
landing_root = globals().get("landing_root", "<LANDING_ROOT>").strip("/")
raw_root = globals().get("raw_root", "<RAW_ROOT>").strip("/")
max_parallel = int(globals().get("max_parallel", "8"))"""

LH_RESOLVE = """# Source lakehouse: found by name in the workspace this notebook runs in (same name in DEV, UAT and PRD), so nothing has to be attached
_lh = notebookutils.lakehouse.get(lakehouse_name, notebookutils.runtime.context["currentWorkspaceId"])
LH_ROOT = _lh["properties"]["abfsPath"].rstrip("/")   # OneLake root of this lakehouse"""

NB_SETUP = """# Settings, catalog rows, small helpers
import fnmatch, json, re, time
from concurrent.futures import ThreadPoolExecutor
import notebookutils
from delta.tables import DeltaTable
from pyspark.sql import functions as F, Window

<LH_RESOLVE>

# Spark settings of DPV1 NTBK_COMMON_MASTER_RAW_TO_CLEAN (%%configure)
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "CORRECTED")   # dates before 1582
spark.conf.set("spark.sql.parquet.int96RebaseModeInRead", "CORRECTED")
<VECTORIZED>spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", "true")     # new source columns are added by MERGE

<CONSTANTS>

rows = [json.loads(r) if isinstance(r, str) else r for r in json.loads(tables_json or "[]")]  # only the tables that copied
truthy = lambda v: str(v).strip().lower() in ("1", "true")
data_rows = [r for r in rows if not truthy(r.get("IsDeleteLog"))]
DELETE_LOGS = {}
for r in rows:
    if truthy(r.get("IsDeleteLog")):
        DELETE_LOGS.setdefault(((r.get("SchemaName") or "") + "." + (r.get("DeleteTarget") or "")).lower(), []).append(r)


def col(name):
    \"\"\"A column name as it is after cleaning.\"\"\"
    return (name.upper() if UPPER_COLUMNS else name) if name else name


def keys_of(row):
    \"\"\"KeyColumns of a catalog row ('A|B', 'A,B' or 'A.B').\"\"\"
    return [col(k.strip()) for k in re.split(r"[|,.]", row.get("KeyColumns") or "") if k.strip()]"""

NB_RUN = """# Run the tables in parallel, 3 attempts each (DPV1 NTBK_COMMON_MASTER_RAW_TO_CLEAN: ThreadPoolExecutor, retries, 30 s wait).
# A table that fails is reported, not raised: the others still load, and the master lists the failures at the end.
# One Spark session for every table: max_parallel tables at a time, the others wait in the queue. The largest tables start first,
# and each table thread has its own scheduler pool, so with FAIR scheduling a large table never holds all the cores.
start = time.time()
FAIR = spark.sparkContext.getConf().get("spark.scheduler.mode", "FIFO").upper() == "FAIR"
print(f"{len(data_rows)} tables, {max_parallel} at a time, scheduler {'FAIR' if FAIR else 'FIFO (set spark.scheduler.mode=FAIR in the workspace Spark settings)'}")
with ThreadPoolExecutor(max_parallel) as pool:
    sizes = list(pool.map(lambda r: folder_size(table_path(r) or ""), data_rows))
data_rows = [r for _, r in sorted(zip(sizes, data_rows), key=lambda x: -x[0])]


def run_with_retry(row):
    spark.sparkContext.setLocalProperty("spark.scheduler.pool", (row.get("TableName") or "table")[:80])
    for attempt in range(1, 4):
        try:
            return dict(load_table(row), SchemaName=row.get("SchemaName"), TableName=row.get("TableName"), error=None)
        except Exception as exc:
            error = str(exc)[:600]
            print(f"LOAD {row.get('TableName')} attempt {attempt} failed: {error}")
            time.sleep(30)
    return {"SchemaName": row.get("SchemaName"), "TableName": row.get("TableName"), "error": error}


with ThreadPoolExecutor(max_parallel) as pool:
    results = list(pool.map(run_with_retry, data_rows))

loaded = [r for r in results if not r["error"]]
done = {(r["SchemaName"], (r["TableName"] or "").lower()) for r in loaded}  # a delete log counts as loaded when its target loaded
loaded += [{"SchemaName": r.get("SchemaName"), "TableName": r.get("TableName"), "mode": "delete log applied"}
           for r in rows if truthy(r.get("IsDeleteLog")) and (r.get("SchemaName"), (r.get("DeleteTarget") or "").lower()) in done]
failed = [f"{r['SchemaName']}.{r['TableName']} (load): {r['error']}" for r in results if r["error"]]
summary = {"pipeline_name": pipeline_name, "run_partition": run_partition, "tables": len(data_rows), "loaded": loaded, "failed": failed,
           "execution_time_sec": round(time.time() - start, 1)}
print(json.dumps(summary, indent=2, default=str))
notebookutils.notebook.exit(json.dumps(summary, default=str))"""

FLATTEN_SETUP = """# Settings, rows of the tables that copied
import fnmatch, json, time
from concurrent.futures import ThreadPoolExecutor
import notebookutils
from pyspark.sql import functions as F

<LH_RESOLVE>
<MOUNT>
<CONSTANTS>

rows = [json.loads(r) if isinstance(r, str) else r for r in json.loads(tables_json or "[]")]"""

FLATTEN_RUN = """passthrough = globals().get("passthrough", [])   # rows that are already raw parquet (mixed source): handed on to the loader as they are
# Run the tables in parallel in this one session, 3 attempts each, the largest delivery first. A table that fails is reported, not raised.
with ThreadPoolExecutor(max_parallel) as pool:
    sizes = list(pool.map(lambda r: sum(s for _, s in landing_files(r)[1]), rows))
rows = [r for _, r in sorted(zip(sizes, rows), key=lambda x: -x[0])]


def flatten_with_retry(row):
    spark.sparkContext.setLocalProperty("spark.scheduler.pool", (row.get("TableName") or "table")[:80])
    for attempt in range(1, 4):
        try:
            return row, flatten_to_raw(row), None
        except Exception as exc:
            error = str(exc)[:600]
            print(f"FLATTEN {row.get('TableName')} attempt {attempt} failed: {error}")
            time.sleep(30)
    return row, None, error


with ThreadPoolExecutor(max_parallel) as pool:
    results = list(pool.map(flatten_with_retry, rows))

flattened = passthrough + [json.dumps(row) for row, raw, error in results if not error]   # no file in landing = nothing new: still passed on
failed = [f"{row.get('SchemaName')}.{row.get('TableName')} (flatten): {error}" for row, raw, error in results if error]
print(json.dumps({"flattened": len(flattened), "failed": failed}, indent=2))
notebookutils.notebook.exit(json.dumps({"flattened": flattened, "failed": failed}))"""


# Incremental source without delete logs: same loader, minus what only the big full-load sources need (size ordering, FAIR pools, delete logs).
# The loaded entries carry LoadMethod: the Update watermarks step reads it from there.
NB_RUN_LEAN = """# Run the tables in parallel in this one session (max_parallel at a time), 3 attempts each.
# A table that fails is reported, not raised: the others still load, and the master lists the failures at the end.
start = time.time()


def run_with_retry(row):
    for attempt in range(1, 4):
        try:
            return dict(load_table(row), SchemaName=row.get("SchemaName"), TableName=row.get("TableName"), LoadMethod=row.get("LoadMethod"), error=None)
        except Exception as exc:
            error = str(exc)[:600]
            print(f"LOAD {row.get('TableName')} attempt {attempt} failed: {error}")
            time.sleep(30)
    return {"SchemaName": row.get("SchemaName"), "TableName": row.get("TableName"), "error": error}


with ThreadPoolExecutor(max_parallel) as pool:
    results = list(pool.map(run_with_retry, data_rows))

loaded = [r for r in results if not r["error"]]
failed = [f"{r['SchemaName']}.{r['TableName']} (load): {r['error']}" for r in results if r["error"]]
summary = {"pipeline_name": pipeline_name, "run_partition": run_partition, "tables": len(data_rows), "loaded": loaded, "failed": failed,
           "execution_time_sec": round(time.time() - start, 1)}
print(json.dumps(summary, indent=2, default=str))
notebookutils.notebook.exit(json.dumps(summary, default=str))"""

SETUP_DELETE_BLOCK = NB_SETUP[NB_SETUP.index('truthy = lambda'):NB_SETUP.index('def col(name)')]


STEPS = ('upper_columns', 'empty_to_null', 'tz_offset_fix', 'string_null_over', 'string_cut', 'clamp_1900', 'latest_per_key', 'dedupe')
STEP_CALL = {  # rule => (snippet, line in clean())
    'upper_columns': ('upper_columns', 'df = upper_case_columns(df)'),
    'empty_to_null': ('empty_to_null', 'df = empty_strings_to_null(df)'),
    'tz_offset_fix': ('tz_offset_fix', 'df = fix_timezone_offsets(df)'),
    'string_null_over': ('string_null_over', 'df = null_long_strings(df, {v})'),
    'string_cut': ('string_cut', 'df = cut_strings(df, {v})'),
    'clamp_1900': ('clamp_1900', 'df = clamp_dates_1900(df)'),
}


def notebook_text(c, lh_id, rules, where, legacy_nb):
    """NB_<SRC>_RAW_TO_DELTA: only the functions this source needs, each taken from the DPV1 notebook it replaces."""
    lib = snippets()
    incremental, deletes = c.incremental, bool(c.layout.get('delete_logs'))
    origin = lambda r: where.get(r, ', '.join(legacy_nb) or 'DPV1 child notebook')
    used, lines = ['folders'], []
    if getattr(c, 'mixed', False):  # database rows read their own raw folder; file rows read what NB_<SRC>_FLATTEN wrote: one reader per row kind
        db, fl = lib['read_raw_dated' if c.raw_dates else 'read_raw_flat'], lib['read_raw_run']
        lib['read_raw_mixed'] = (re.sub(r'\b(table_path|read_table)\b', r'\1_db', db) + '\n\n\n' + re.sub(r'\b(table_path|read_table)\b', r'\1_files', fl) +
                                 '\n\n\ndef read_table(row):\n    """Database rows (SourceFormat table): raw parquet of the table. File rows: parquet written by NB_<SRC>_FLATTEN."""\n'
                                 '    return read_table_db(row) if (row.get("SourceFormat") or "table") == "table" else read_table_files(row)\n\n\n'
                                 'def table_path(row):\n    return table_path_db(row) if (row.get("SourceFormat") or "table") == "table" else table_path_files(row)').replace('<SRC>', c.src)
        used.append('read_raw_mixed')
    elif c.method == 'structured':
        used.append('read_raw_dated' if c.raw_dates else 'read_raw_flat')
    else:  # NB_<SRC>_FLATTEN wrote Files/raw/<src>/<run>/<table>/
        used.append('read_raw_run')
    for rule in ('upper_columns', 'empty_to_null', 'tz_offset_fix', 'string_null_over', 'string_cut', 'clamp_1900'):
        if rule in rules:
            snip, call = STEP_CALL[rule]
            v = rules[rule]
            if rule == 'string_cut':
                v = f"{v['default']}, {json.dumps(v['columns'])}" if isinstance(v, dict) else v
            used.append(snip)
            lines.append(f"    {call.format(v=v)}{' ' * max(1, 44 - len(call.format(v=v)))}# DPV1: {origin(rule)}")
    keys_line = '    keys = [k for k in keys_of(row) if k in df.columns]'
    if 'latest_per_key' in rules or incremental:
        used.append('latest_per_key')
        lines.append(keys_line)
        lines.append('    df = keep_latest_per_key(df, keys, col(row.get("WatermarkColumn")))  # DPV1: '
                     + (origin('latest_per_key') if 'latest_per_key' in rules else 'MERGE on UnicityKeys, newest row wins'))
    if 'dedupe' in rules:
        used.append('dedupe')
        if keys_line not in lines:
            lines.append(keys_line)
        lines.append(f"    df = drop_duplicates(df, keys)                # DPV1: {origin('dedupe')}")
    used += ['loading_date', 'write_overwrite'] + (['write_merge'] if incremental else []) + (['delete_logs'] if incremental and deletes else [])
    if incremental and deletes and 'upper_columns' not in used:
        used.insert(used.index('delete_logs'), 'upper_columns')
    clean = ('# Cleaning of one table: the steps of the DPV1 child notebook, in its order\n'
             'def clean(df, row):\n'
             f'    """{"; ".join(m for k, _, _, m in RULES if k in rules and k in STEPS) or "no cleansing step in DPV1"}."""\n'
             + '\n'.join(lines + ['    return add_loading_date(df)']))
    write_block = ('    if row.get("LoadMethod") == "incremental" and keys and DeltaTable.isDeltaTable(spark, delta_path(name)):\n'
                   '        target = merge_table(df, name, keys, col(row.get("WatermarkColumn")))\n'
                   + ('        apply_delete_logs(row, keys, target)\n' if deletes else '')
                   + '        mode = "merge"\n'
                   '    else:  # full load, or first load of an incremental table\n'
                   '        overwrite_table(df, name)\n'
                   '        mode = "overwrite"\n') if incremental else ('    overwrite_table(df, name)\n    mode = "overwrite"\n')
    load = ('# Load one table: read => clean => write\n'
            'def load_table(row):\n'
            '    name = f"{target_schema}.{(row.get(\'TargetName\') or row[\'TableName\']).lower()}"\n'
            '    df, path = read_table(row)\n'
            '    if df is None:\n'
            '        return {"table": name, "mode": "no new data", "source": path}\n'
            '    df = clean(df, row)\n'
            + ('    keys = [k for k in keys_of(row) if k in df.columns]\n' if incremental else '')
            + write_block
            + '    metrics = DeltaTable.forPath(spark, delta_path(name)).history(1).first()["operationMetrics"] or {}\n'
            '    return {"table": name, "mode": mode, "source": path, "rows": metrics.get("numOutputRows") or metrics.get("numTargetRowsInserted")}')
    helpers = '# Reusable functions (0-shared/templates/raw-to-delta-snippets.py in the migration repository)\n\n' + '\n\n\n'.join(
        lib[n].replace('<ORIGIN>', origin({'upper_columns': 'upper_columns', 'empty_to_null': 'empty_to_null', 'tz_offset_fix': 'tz_offset_fix',
                                           'string_null_over': 'string_null_over', 'string_cut': 'string_cut', 'clamp_1900': 'clamp_1900',
                                           'dedupe': 'dedupe', 'latest_per_key': 'latest_per_key'}.get(n, n))).replace('<SRC>', c.src)
        for n in dict.fromkeys(used))
    lean = incremental and not deletes   # no delete logs: none of the delete-log bookkeeping, size ordering or scheduler pools
    plain_cols = lean and 'upper_columns' not in rules   # column names kept as they are: no col() indirection
    consts = [] if plain_cols else [f'UPPER_COLUMNS = {"upper_columns" in rules}   # DPV1 upper-cased the column names: keys and dates are looked up in upper case']
    setup = (NB_SETUP.replace('<LH_RESOLVE>', LH_RESOLVE).replace('<CONSTANTS>', '\n'.join(consts))
             .replace('<VECTORIZED>', 'spark.conf.set("spark.sql.parquet.enableVectorizedReader", "false")  # DPV1 decimal workaround\n'
                      if 'parquet_vectorized_off' in rules else ''))
    run = NB_RUN_LEAN if lean else NB_RUN.replace('TableName=row.get("TableName"), error=None)', 'TableName=row.get("TableName"), LoadMethod=row.get("LoadMethod"), error=None)') if incremental else NB_RUN
    if lean:
        setup = setup.replace(SETUP_DELETE_BLOCK, 'data_rows = rows\n\n\n').replace('import fnmatch, json, re, time', 'import json, re, time').replace('\n\n\n\n', '\n\n')
        helpers = re.sub(r'def folder_size\(.*?\n\n\n(?=def )', '', helpers, flags=re.S)
    if plain_cols:
        setup = re.sub(r'def col\(name\):.*?\n\n\n', '', setup, flags=re.S).replace('[col(k.strip()) for k', '[k.strip() for k')
        load = load.replace('col(row.get("WatermarkColumn"))', 'row.get("WatermarkColumn")')
        clean = clean.replace('col(row.get("WatermarkColumn"))', 'row.get("WatermarkColumn")')
        write_block = write_block.replace('col(row.get("WatermarkColumn"))', 'row.get("WatermarkColumn")')
    steps = '\n'.join(f'# - {m} (DPV1 `{origin(k)}`)' for k, _, _, m in RULES if k in rules and k not in ('flatten', 'json_root', 'parquet_vectorized_off'))
    intro = '\n'.join([
        f'# # NB_{c.src}_RAW_TO_DELTA',
        f'# Loads the {c.src} tables that copied in this run' + (' (and were flattened by `NB_' + c.src + '_FLATTEN`)' if c.method != 'structured' else '')
        + f' from raw into `dbo` tables of `{c.lh}`, all tables in one Spark session. A table that fails is reported; the others still load.',
        '# ',
        f'# **Replaces (DPV1):** {", ".join("`" + n + "`" for n in legacy_nb) or "-"} (a master notebook that started one child and one META notebook per table).',
        '# ',
        f'# **Method:** {c.method}, ' + ('incremental: MERGE on the keys, newest row wins' + (', delete logs' if deletes else '') if incremental else 'full: each table is replaced') + '.',
        '# ',
        '# **Per table:** read raw => `clean()` => write. Cleaning steps kept from DPV1:',
        steps or '# - none',
        '# ',
        '# The functions come from `0-shared/templates/raw-to-delta-snippets.py` of the migration repository: change them there and regenerate.'])
    text = NOTEBOOK_HEAD + MARKDOWN.format(text=intro) + ''.join(CELL.format(code=x) for x in (NB_PARAMS, setup, helpers, clean, load, run))
    for k, v in {'<LAKEHOUSE_LOGICAL_ID>': lh_id, '<LAKEHOUSE>': c.lh, '<SRC>': c.src, '<RAW_ROOT>': c.raw, '<LANDING_ROOT>': c.landing}.items():
        text = text.replace(k, v)
    return text


MIXED_FILTER = """# Mixed source: the database rows are already raw parquet. Only the file rows are flattened here; the others go on to the loader unchanged.
passthrough = [json.dumps(r) for r in rows if (r.get("SourceFormat") or "table") == "table"]
rows = [r for r in rows if (r.get("SourceFormat") or "table") != "table"]"""


def flatten_text(c, lh_id, rules, where, legacy_nb):
    """NB_<SRC>_FLATTEN (semi-structured sources): landing as delivered => explode => flatten => raw parquet. No cleaning, no table."""
    lib = snippets()
    opts = {'json': {'multiLine': 'false'}, 'csv': {'header': 'true', 'inferSchema': 'false'}, 'xml': {'rowTag': 'row'}, 'excel': {}}
    mixed, excel = getattr(c, 'mixed', False), c.fmt.lower() == 'excel'
    if not mixed:  # one format: its read options only
        opts = {c.fmt.lower(): opts.get(c.fmt.lower(), {})}
    run = FLATTEN_RUN.replace(FLATTEN_RUN[FLATTEN_RUN.index('with ThreadPoolExecutor(max_parallel) as pool:\n    sizes'):FLATTEN_RUN.index('def flatten_with_retry')], '\n\n')
    run = run.replace('    spark.sparkContext.setLocalProperty("spark.scheduler.pool", (row.get("TableName") or "table")[:80])\n', '').replace(', the largest delivery first', '')
    if not mixed:  # passthrough rows exist only in a mixed source
        run = run.replace(run[:run.index('# Run the tables')], '').replace('flattened = passthrough + [', 'flattened = [')
    consts = [f'IS_REST = {c.conn_type == "RestService"}   # REST: one <table>.json per table in the run folder; files: the SourcePath wildcard',
              f'SOURCE_FORMAT = "{c.fmt}"', f'JSON_ROOT = {rules.get("json_root")!r}   # DPV1 explode(col("…")): the array holding the records',
              f'READ_OPTIONS = {json.dumps(opts)}']
    origin = where.get('flatten') or where.get('json_root') or ', '.join(legacy_nb) or 'DPV1 child notebook'
    intro = '\n'.join([
        f'# # NB_{c.src}_FLATTEN',
        f'# Turns the {c.src} files of this run, as delivered in `Files/{c.landing}/<run>/`, into parquet in `Files/{c.raw}/<run>/<table>/`: '
        'the record array is exploded and nested fields are flattened (`a.b` => `a_b`). Only the tables that copied are processed.',
        '# ', f'# **Replaces (DPV1):** the first half of `{origin}` (read LANDING, explode, `flatten_json_df`). No cleaning and no table here: '
        f'`NB_{c.src}_RAW_TO_DELTA` loads the parquet.',
        '# ', '# The functions come from `0-shared/templates/raw-to-delta-snippets.py` of the migration repository.'])
    helpers = '# Reusable functions (0-shared/templates/raw-to-delta-snippets.py in the migration repository)\n\n' + '\n\n\n'.join(
        lib[n].replace('<SRC>', c.src) for n in ('folders', 'flatten', 'flatten_to_raw'))
    helpers = re.sub(r'def folder_size\(.*?\n\n\n(?=def )', '', helpers, flags=re.S)  # only used to order the tables in a full load
    if c.conn_type == 'RestService' and active_loop(c):  # APIs called once per item land <table>~<item>.json next to <table>.json (build_loop_child)
        helpers = helpers.replace('fnmatch.fnmatch(e.name.lower(), pattern)', '(fnmatch.fnmatch(e.name.lower(), pattern) or fnmatch.fnmatch(e.name.lower(), pattern.replace(".json", "~*.json")))')
    if not excel:  # Spark reads the format itself: no pandas branch
        helpers = re.sub(r'    if fmt == "excel":.*?    else:\n        (df = spark\.read[^\n]*)\n', r'    \1\n', helpers, flags=re.S)
    text = NOTEBOOK_HEAD + MARKDOWN.format(text=intro) + ''.join(CELL.format(code=x) for x in (
        FLATTEN_PARAMS, FLATTEN_SETUP.replace('<LH_RESOLVE>', LH_RESOLVE)
        .replace('<MOUNT>', 'notebookutils.fs.mount(LH_ROOT, "/lh_src")   # Excel: pandas reads the files from a local mount path\n' if excel else '')
        .replace('<CONSTANTS>', '\n'.join(consts)), helpers, *([MIXED_FILTER] if mixed else []), run))
    for k, v in {'<LAKEHOUSE_LOGICAL_ID>': lh_id, '<LAKEHOUSE>': c.lh, '<SRC>': c.src, '<RAW_ROOT>': c.raw, '<LANDING_ROOT>': c.landing}.items():
        text = text.replace(k, v)
    return text


def notebook_timeout(c):
    """Timeout of the notebook activities (d.hh:mm:ss): progress.json project_inputs.notebook_timeout, else shared-platform.json, else 4 h.
    Set at build time: Fabric does not take an expression for an activity timeout."""
    import project_inputs
    return project_inputs.load('sds', c.scope).get('notebook_timeout') or c.sp.get('notebook_timeout') or '0.04:00:00'


def build_s3(b, c, lh_id):
    """PL_<SRC>_RAW_TO_DELTA gets only the tables that copied (LoadedTables of S2), never the whole catalog.
    semi-structured: NB_<SRC>_FLATTEN => NB_<SRC>_RAW_TO_DELTA (the tables it flattened); structured: NB_<SRC>_RAW_TO_DELTA.
    Returns LoadedTables (schema and table of every table that reached the lakehouse) and FailedTables (table and error)."""
    rules, where, legacy_nb = legacy_rules(c.S, c.pd)
    nb, pl, fl = f'NB_{c.src}_RAW_TO_DELTA', f'PL_{c.src}_RAW_TO_DELTA', f'NB_{c.src}_FLATTEN'
    p = lambda v: {'type': 'String', 'defaultValue': v}
    lv = lambda n: {'type': 'String', 'variableName': n, 'libraryName': 'VL_MAIN'}
    param = lambda n, v: (n, {'value': b.expr(v), 'type': 'String'})
    semi = c.method != 'structured' or getattr(c, 'mixed', False)  # a mixed source flattens its file rows, then loads everything
    exit_of = lambda act: f"json(activity('{act}').output.result.exitValue)"
    policy = {'timeout': notebook_timeout(c), 'retry': 1, 'retryIntervalInSeconds': 60}
    acts, items = [], []
    if c.has_notebook:
        if semi:
            fl_folder = c.out('2-RAW_TO_DELTA', f'{fl}.Notebook')
            fl_id = b.platform(fl_folder, 'Notebook', fl, f'{c.src}: files as delivered in landing => flattened parquet in raw.')
            write(os.path.join(fl_folder, 'notebook-content.py'), flatten_text(files_ctx(c) if getattr(c, 'mixed', False) else c, lh_id, rules, where, legacy_nb))
            acts.append({'name': 'Flatten landing to raw', 'type': 'TridentNotebook', 'dependsOn': [], 'policy': policy,
                         'description': f'Runs {fl} with the tables that copied: explode and flatten the delivered files, write raw parquet.',
                         'typeProperties': {'notebookId': fl_id, 'workspaceId': b.ZERO, 'sessionTag': f'{c.src.lower()}-raw-to-delta', 'parameters': dict([
                             param('lakehouse_name', VL(V(c, 'LH_NAME'))),
                             param('tables_json', '@string(pipeline().parameters.LoadedTables)'), param('run_partition', '@pipeline().parameters.RunPartition'),
                             param('landing_root', '@pipeline().parameters.LandingRoot'), param('raw_root', '@pipeline().parameters.RawRoot'),
                             param('max_parallel', '@pipeline().parameters.MaxParallel')])}})
            items.append(fl)
        nb_folder = c.out('2-RAW_TO_DELTA', f'{nb}.Notebook')
        nb_id = b.platform(nb_folder, 'Notebook', nb, f'{c.src}: raw parquet => dbo tables, only the tables that copied ({c.method}).')
        write(os.path.join(nb_folder, 'notebook-content.py'), notebook_text(c, lh_id, rules, where, legacy_nb))
        tables = f"@string({exit_of('Flatten landing to raw')}.flattened)" if semi else '@string(pipeline().parameters.LoadedTables)'
        acts.append({'name': 'Load raw to Lakehouse tables', 'type': 'TridentNotebook',
                     'dependsOn': [{'activity': 'Flatten landing to raw', 'dependencyConditions': ['Succeeded']}] if semi else [], 'policy': policy,
                     'description': f'Runs {nb} once with the tables to load; it loads them in parallel in one session and reports loaded and failed tables.',
                     'typeProperties': {'notebookId': nb_id, 'workspaceId': b.ZERO, 'sessionTag': f'{c.src.lower()}-raw-to-delta', 'parameters': dict([
                         param('lakehouse_name', VL(V(c, 'LH_NAME'))),
                         param('tables_json', tables), param('run_partition', '@pipeline().parameters.RunPartition'), param('raw_root', '@pipeline().parameters.RawRoot'),
                         param('target_schema', '@pipeline().parameters.TargetSchema'), param('max_parallel', '@pipeline().parameters.MaxParallel'),
                         param('pipeline_name', '@pipeline().Pipeline')])}})
        items += [nb, pl]
        failed = (f"@union({exit_of('Flatten landing to raw')}.failed, {exit_of('Load raw to Lakehouse tables')}.failed)" if semi
                  else f"@{exit_of('Load raw to Lakehouse tables')}.failed")
        acts.append(return_value(b, [{'activity': 'Load raw to Lakehouse tables', 'dependencyConditions': ['Succeeded']}],
                                 [('LoadedTables', f"@{exit_of('Load raw to Lakehouse tables')}.loaded"), ('FailedTables', failed)]))
        last = ['Flatten landing to raw', 'Load raw to Lakehouse tables'] if semi else ['Load raw to Lakehouse tables']
        variables = {}
    else:  # DPV1 had no notebook for this source: Copy raw parquet => Lakehouse table, for the tables that copied
        row = lambda f: f"json(item()).{f}"
        copy = {'name': 'Raw parquet to table', 'type': 'Copy', 'dependsOn': [], 'policy': {'timeout': '0.02:00:00', 'retry': 2, 'retryIntervalInSeconds': 60},
                'typeProperties': {'source': {'type': 'ParquetSource', 'storeSettings': {'type': 'LakehouseReadSettings', 'recursive': True, 'wildcardFileName': '*.parquet'},
                                              'datasetSettings': {'type': 'Parquet', 'typeProperties': {'location': {'type': 'LakehouseLocation', 'folderPath': b.expr(
                                                  "@{pipeline().parameters.RawRoot}/@{" + row('EntityName') + "}" + ("/@{pipeline().parameters.RunPartition}" if c.raw_dates else "")
                                                  + "@{" + row('FolderTail') + "}")}},
                                                                  'connectionSettings': c.lakehouse_settings(), 'annotations': []}},
                                   'sink': {'type': 'LakehouseTableSink', 'tableActionOption': 'Overwrite',
                                            'datasetSettings': {'type': 'LakehouseTable', 'typeProperties': {'schema': 'dbo', 'table': b.expr(f"@toLower({row('TargetName')})")},
                                                                'connectionSettings': c.lakehouse_settings('Tables'), 'annotations': []}},
                                   'enableStaging': False}}
        acts.append({'name': f'ForEach table in {c.src}', 'type': 'ForEach', 'dependsOn': [],
                     'description': 'DPV1 had no notebook for this source: each raw parquet folder of a table that copied goes to its Lakehouse table (overwrite).',
                     'typeProperties': {'isSequential': False, 'batchCount': 20, 'items': b.expr('@pipeline().parameters.LoadedTables'), 'activities': [
                         copy, append_on(b, 'Add to loaded tables', copy['name'], 'Succeeded', 'LoadedTables', '@item()', 'Table loaded.'),
                         append_on(b, 'Add to failed tables', copy['name'], 'Failed', 'FailedTables',
                                   f"@concat({row('SchemaName')}, '.', {row('TableName')}, ' (load): ', activity('{copy['name']}').error.message)", 'Table and error.')]}})
        acts.append(return_value(b, [{'activity': f'ForEach table in {c.src}', 'dependencyConditions': ['Succeeded']}],
                                 [('LoadedTables', "@variables('LoadedTables')"), ('FailedTables', "@variables('FailedTables')")]))
        items, last = [pl], [f'ForEach table in {c.src}']
        variables = {'LoadedTables': {'type': 'Array', 'defaultValue': []}, 'FailedTables': {'type': 'Array', 'defaultValue': []}}
    acts += [{'name': f'Fail {a_}', 'type': 'Fail', 'dependsOn': [{'activity': a_, 'dependencyConditions': ['Failed']}],
              'typeProperties': {'errorCode': 'RAW_TO_DELTA_FAILED', 'message': f'{pl}: "{a_}" did not run to the end (notebook session or item error); see its run output.'}}
             for a_ in last]
    params = {'LoadedTables': {'type': 'Array', 'defaultValue': []}, 'RawRoot': p(c.raw), 'RunPartition': p(''), 'TargetSchema': p('dbo'), 'MaxParallel': p('8')}
    if semi:
        params['LandingRoot'] = p(c.landing)
    content = {'properties': {'activities': acts, 'parameters': params}}
    if variables:
        content['properties']['variables'] = variables
    if c.has_notebook:
        content['properties']['libraryVariables'] = {n: lv(n) for n in [V(c, 'LH_NAME')]}  # the notebooks look the lakehouse up by this name
    else:
        content['properties']['libraryVariables'] = {n: lv(n) for n in libs(c, lakehouse=True, catalog=False)}  # Lakehouse connection only
    pl_folder = c.out('2-RAW_TO_DELTA', f'{pl}.DataPipeline')
    b.platform(pl_folder, 'DataPipeline', pl, f'{c.src}: tables that copied => ' + ('flattened raw => ' if semi and c.has_notebook else '') + 'dbo tables.')
    write(os.path.join(pl_folder, 'pipeline-content.json'), b.dump(content))
    meaning = {k: m for k, _, _, m in RULES}
    L = [f'# S3 RAW to Lakehouse tables: {c.src}', '', f"- **Items**: {', '.join('`' + i + '`' for i in items)}",
         f"- **Replaces (DPV1)**: {', '.join('`' + x + '`' for x in dict.fromkeys(c.legacy['RAW_TO_DELTA'] + legacy_nb)) or 'none'}",
         f"- **Method**: {c.method}, {'incremental (MERGE on KeyColumns, newest WatermarkColumn wins, delete logs)' if c.incremental else 'full (overwrite)'}",
         '- **Tables**: only those that copied in this run (`LoadedTables` of S2, DPV1 "Append Success Files"); a failed table is reported, the others still load', '',
         '## Steps', '']
    L += ([f'1. `{fl}`: landing files of the tables that copied => explode => flatten => `Files/{c.raw}/<run>/<table>/`',
           f'2. `{nb}`: the tables it flattened => clean => write'] if semi and c.has_notebook else
          [f'1. `{nb}`: raw parquet of the tables that copied => clean => write'] if c.has_notebook else ['1. Copy: raw parquet of each table that copied => Lakehouse table (overwrite)'])
    L += ['3. Return `LoadedTables` and `FailedTables` to the master', '']
    if c.incremental:
        L += ['## Keys for MERGE', '', '- Incremental rows need `KeyColumns` and `WatermarkColumn` in the catalog; a row without keys is overwritten at every run.',
              '- When DPV1 took the key from the notebook (for example a `sys_id` column), add it to the catalog script.', '']
    if c.has_notebook:
        L += ['## DPV1 cleaning steps (one line each in `clean()`)', '', '| Rule | Value | Meaning | Found in |', '| --- | --- | --- | --- |']
        L += [f'| `{k}` | {v} | {meaning[k]} | `{where[k]}` |' for k, v in sorted(rules.items())] or ['| none | - | - | - |']
        L += ['', '## Faster than DPV1', '', '- One notebook run per step, tables in a thread pool of one session (DPV1: a child notebook and a META notebook per table)',
              '- No lake database registration: `saveAsTable` / `MERGE` on Lakehouse managed tables', '- Row counts from the Delta operation metrics, not a second read']
    else:
        L += ['## No notebook', '', 'DPV1 did not cleanse this source in a notebook, so none is created: a Copy writes each raw folder to its table.']
        flows = c.S.get('dataflows') or []
        if flows:
            L += ['', '## Data Flows to review', '', 'A flow that only maps columns is covered by the Copy. Any other logic must be reviewed (skill-spark-notebook-to-fabric):', '']
            L += [f'- `{f}`' for f in flows]
    write_note('sds', c.scope, 'S3-raw-to-tables', '\n'.join(L) + '\n')
    return items


def watermark_step(b, c, depends, loaded):
    """Watermark = start of this run (CET, as DPV1) for the incremental tables that reached the lakehouse in this run only:
    a table that failed keeps its watermark and re-reads the same changes next time. loaded: expression of the loaded list."""
    ts = "@{formatDateTime(convertTimeZone(pipeline().TriggerTime, 'UTC', 'Central European Standard Time'), 'yyyy-MM-dd HH:mm:ss')}"
    wm = '@{pipeline().libraryVariables.' + V(c, 'CATALOG_WATERMARK_TABLE_NAME') + '}'
    # NB_<SRC>_RAW_TO_DELTA returns LoadMethod with each loaded table: no catalog join needed, only the incremental ones get a watermark
    inc = ("l AS (SELECT JSON_VALUE(value, '$.SchemaName') AS SchemaName, JSON_VALUE(value, '$.TableName') AS TableName "
           "FROM OPENJSON('@{replace(string(" + loaded + "), '''', '''''')}') WHERE JSON_VALUE(value, '$.LoadMethod') = 'incremental')")
    sql = (f"WITH {inc}\n"
           f"UPDATE {wm} SET WatermarkVal = '{ts}', UpdatedAt = SYSUTCDATETIME()\n"
           f"WHERE EXISTS (SELECT 1 FROM l WHERE l.SchemaName = {wm}.SchemaName AND l.TableName = {wm}.TableName);\n"
           f"WITH {inc}\n"
           f"INSERT INTO {wm} (SchemaName, TableName, WatermarkVal, UpdatedAt)\n"
           f"SELECT SchemaName, TableName, '{ts}', SYSUTCDATETIME() FROM l\n"
           f"WHERE NOT EXISTS (SELECT 1 FROM {wm} AS w WHERE w.SchemaName = l.SchemaName AND w.TableName = l.TableName);")
    return {'name': 'Update watermarks', 'type': 'Script', 'dependsOn': depends,
            'description': 'Watermark = start of this run for the incremental tables loaded in this run (replaces DPV1 SP_COMMON_UpdateWatermark).',
            'policy': {'timeout': '0.00:10:00', 'retry': 2, 'retryIntervalInSeconds': 30},
            'typeProperties': {'scripts': [{'type': 'NonQuery', 'text': b.expr(sql)}], 'scriptBlockExecutionTimeout': '00:10:00',
                               'datasetSettings': {'type': 'DataWarehouseTable', 'schema': [], 'annotations': [], 'typeProperties': {},
                                                   'connectionSettings': warehouse(b, c)}}}


def dpv1_pagination(S, root=None):
    """paginationRules of the first DPV1 REST Copy of the scope, and the pipeline it comes from.
    A rule that reads another activity's output (DPV1 "is there data?" call) becomes an open range with an end condition
    on the record array, because that activity is not migrated."""
    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get('paginationRules'), dict):
                yield o['paginationRules']
            for v in o.values():
                yield from walk(v)
        elif isinstance(o, list):
            for v in o:
                yield from walk(v)
    for n in S['pipelines']:
        f = os.path.join(paths()['dpv1_export_root'], 'pipeline', n + '.json')
        if not exists(f):
            continue
        for rules in walk(read_json(f)):
            out, adapted = {}, False
            for k, v in rules.items():
                v = v.get('value') if isinstance(v, dict) else v
                if 'activity(' in str(v):
                    out[k] = 'RANGE:0::' + (re.search(r'(\d+)\s*$', str(v)).group(1) if re.search(r'(\d+)\s*$', str(v)) else '1000')
                    adapted = True
                else:
                    out[k] = v
            if adapted:
                out[f"EndCondition:$.{root or 'result'}"] = 'Empty'
            return out, n + (' (adapted: the DPV1 count call is replaced by an end condition on the empty record list)' if adapted else '')
    return None, ''
