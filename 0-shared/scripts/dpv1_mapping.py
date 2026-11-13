"""Object-level DPV1 (Synapse) -> DPV2 (Fabric) mapping for every source dataset and data product scope. Read-only on DPV1.

Builds one JSON consumed by the Migration Hub page (mapper tab):
  - objects : every DPV1 pipeline / notebook / linked service / dataset / trigger / SQL object, stored once
  - sds     : per source dataset scope (up to SPOT_DB source)   -> DP_SDS_<DOMAIN> target
  - dp      : per data product scope (SPOT_DB source -> DW/DM)  -> DP_DPG_<GROUP> target
  - lookup  : master pipelines and DW/DM schemas -> data product scope (the Service #3 inputs)

Usage: python -I analysis/scripts/dpv1_mapping.py "<DPV1 export root>" analysis/config/scope-target-map.json analysis/migration-map.json
"""
import json, os, re, sys
from collections import Counter, defaultdict

SRC, TARGET_CFG, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
REGISTER_PATH = sys.argv[4] if len(sys.argv) > 4 else None
CFG = json.load(open(TARGET_CFG, encoding='utf-8'))
REG = json.load(open(REGISTER_PATH, encoding='utf-8')) if REGISTER_PATH else {'projects': [], 'domain_codes': {}, 'complexity_thresholds': {'Small': 50, 'Medium': 150}}


# ---------------------------------------------------------------- loading
def items(kind):
    d = os.path.join(SRC, kind)
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if f.endswith('.json'):
            try:
                yield f[:-5], json.load(open(os.path.join(d, f), encoding='utf-8-sig'))
            except (ValueError, UnicodeDecodeError):
                pass


def folder(j):
    return ((j.get('properties') or {}).get('folder') or {}).get('name', '')


def walk(acts):
    for a in acts or []:
        yield a
        tp = a.get('typeProperties', {})
        for k in ('activities', 'ifTrueActivities', 'ifFalseActivities', 'defaultActivities'):
            yield from walk(tp.get(k))
        for c in tp.get('cases', []) or []:
            yield from walk(c.get('activities'))


def refs(obj, ref_type):
    out = set()
    def rec(o):
        if isinstance(o, dict):
            if o.get('type') == ref_type and 'referenceName' in o:
                out.add(str(o['referenceName']))
            for v in o.values():
                rec(v)
        elif isinstance(o, list):
            for v in o:
                rec(v)
    rec(obj)
    return out


# Same scope normalisation as project_catalog.py, so scope names match the explorer.
ALIAS = {'EUHREKARETIREMENT': 'EUHREKA', 'EUHREKA_RETIREMENT': 'EUHREKA', 'ESSPLUNK': 'ES-SPLUNK', 'JANUSBI': 'JANUS',
         'EPV2_BI': 'EPV2', 'INTELEX_ISIBI': 'INTELEX', 'SYMPHONY_POWER_BI': 'SYMPHONY', 'DECOMMISSIONNIG_DWH': 'DECOMMISSIONING_DWH',
         'MICRO_SESAME': 'MICROSESAME', 'ESG_COLLECTION_TOOL': 'ESG', 'HSE_TRAINING': 'HSE_TRAINING', 'ERP_BI_CLOUD': 'ERP_CLOUD_BI',
         'ECOSYS_CC': 'ECOSYS_COSTCONTROL', 'MDM_EBX': 'MDM', 'FAIRWAYS': 'FAIRWAYS_GUARANTEES', 'QHSES_BI_STREAM': 'QHSES',
         'GEOS_WORLD': 'GEOS', 'SYMPHONYBI': 'SYMPHONY', 'EPC_MANUFIL': 'EPC', 'EUHREKA_RETIREMNET': 'EUHREKA',
         'DECOMMISSIONING': 'DECOMMISSIONING_DWH', 'ERP_CLOUD_MIGRATION': 'ERP_CLOUD_BI', 'SYMPHONY_POWER_BI': 'SYMPHONY'}
ZONE = [('01_CORE_DATA', 'SRC'), ('01_GLOBAL_DATA_SOURCES', 'SRC'), ('01_DATA_SOURCES', 'SRC'), ('02_PROJECTS', 'DP'),
        ('02_BI_PROJECTS', 'DP'), ('03_INTEGRATION_PROJECTS', 'DP'), ('03_SELF_SERVICE', 'DP'), ('05_BUSR', 'DP'),
        ('99_EXTERNAL_ORCHESTRATION', 'EXT'), ('00_HELPERS', 'SHARED'), ('04_SHARED_TEMPLATES', 'SHARED'), ('04_COMMON', 'SHARED')]
SHARED_SRC = ('00_DSQL_OFFLOAD', 'DATA_SOURCE_MASTERS', 'SETUP', 'DSQL_OFFLOAD', 'CLEAN_STANDARDIZE')


def norm(seg):
    s = re.sub(r'^[\d\s._-]+', '', seg).upper().replace(' ', '_').replace('.', '')
    s = re.sub(r'_?\(.*\)$', '', s)
    return ALIAS.get(s, s)


def zone_entity(f):
    parts = f.split('/')
    z = next((zz for p, zz in ZONE if parts[0].startswith(p)), 'OTHER')
    e = norm(parts[1]) if len(parts) > 1 and z in ('SRC', 'DP', 'EXT') else None
    if z == 'SRC' and e in SHARED_SRC:
        z, e = 'SHARED', None
    return z, e


def env_of(factory):
    f = factory.lower()
    return 'PRD' if 'prd' in f or 'prod' in f else 'UAT' if 'uat' in f else 'DEV' if 'dev' in f else factory


def snake(s):
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s)
    return re.sub(r'[^A-Za-z0-9]+', '_', s).strip('_').upper()


def mask(v):
    s = json.dumps(v) if not isinstance(v, str) else v
    s = re.sub(r'(?i)(password|pwd|accountkey|sharedaccesskey|secret)=[^;"]*', r'\1=***', s)
    return s[:220]


SQL_CREATE = re.compile(r'CREATE\s+(?:OR\s+ALTER\s+)?(PROC(?:EDURE)?|VIEW|TABLE|FUNCTION|EXTERNAL\s+TABLE|SCHEMA)\s+\[?(\w+)\]?(?:\.\[?(\w+)\]?)?', re.I)
SQL_REF = re.compile(r'\b(?:FROM|JOIN|INTO|UPDATE|EXEC(?:UTE)?|TABLE|VIEW)\s+\[?(\w+)\]?\.\[?(\w+)\]?', re.I)


def kind_of(k):
    k = k.upper()
    return 'EXTERNAL' if 'EXTERNAL' in k else 'PROC' if k.startswith('PROC') else k.split()[0]


def sql_text_of_activity(a):
    tp = a.get('typeProperties', {})
    parts = []
    for s in tp.get('scripts', []) or []:
        t = s.get('text')
        parts.append(str(t.get('value', '') if isinstance(t, dict) else t or ''))
    src = tp.get('source', {}) or {}
    for k in ('sqlReaderQuery', 'oracleReaderQuery', 'query', 'sqlReaderStoredProcedureName'):
        v = src.get(k)
        if v:
            parts.append(str(v.get('value', '') if isinstance(v, dict) else v))
    if a['type'] == 'SqlServerStoredProcedure':
        parts.append('EXEC ' + str(tp.get('storedProcedureName', '')))
    return '\n'.join(parts).replace("''", "'")


# ---------------------------------------------------------------- index DPV1
P, NB, LS, DS, TR, SQ, DF = (dict(items(k)) for k in ('pipeline', 'notebook', 'linkedService', 'dataset', 'trigger', 'sqlscript', 'dataflow'))

objects = {'pipeline': {}, 'notebook': {}, 'linkedService': {}, 'dataset': {}, 'trigger': {}, 'sql': {}, 'dataflow': {}}
sql_defined_in = defaultdict(set)   # "schema.name" -> artifacts
vl_vars = defaultdict(dict)         # pipeline -> {VAR: {env: value}}

trig_of = defaultdict(list)
for n, j in TR.items():
    p = j.get('properties', {})
    tps = p.get('typeProperties') or {}
    rec = tps.get('recurrence') or {}
    targets = [x['pipelineReference']['referenceName'] for x in p.get('pipelines', [])]
    objects['trigger'][n] = {'type': p.get('type'), 'state': p.get('runtimeState'), 'pipelines': targets,
                             'schedule': (f"{rec.get('frequency', '')} every {rec.get('interval', '')}" + (f" at {json.dumps(rec.get('schedule'))[:80]}" if rec.get('schedule') else '')).strip() if rec else (p.get('type') or '')}
    for t in targets:
        trig_of[t].append(n)

for n, j in LS.items():
    p = j.get('properties', {})
    tp = p.get('typeProperties', {}) or {}
    details = {k: mask(v) for k, v in tp.items() if k.lower() in ('url', 'baseurl', 'host', 'server', 'connectionstring', 'accountname',
               'servicename', 'database', 'databasename', 'sid', 'port', 'username', 'authenticationtype', 'tenant', 'siteurl', 'endpoint')}
    secrets = sorted({str(x.get('secretName', '')) if not isinstance(x.get('secretName'), dict) else str(x['secretName'].get('value'))
                      for x in [v for v in tp.values() if isinstance(v, dict) and v.get('type') == 'AzureKeyVaultSecret']})
    objects['linkedService'][n] = {'type': p.get('type'), 'runtime': (p.get('connectVia') or {}).get('referenceName') or 'AutoResolve',
                                   'details': details, 'kv_secrets': secrets, 'parameters': sorted((p.get('parameters') or {}).keys())}

for n, j in DS.items():
    p = j.get('properties', {})
    tp = p.get('typeProperties', {}) or {}
    loc = tp.get('location') or {}
    where = tp.get('tableName') or tp.get('table') or loc.get('folderPath') or loc.get('fileName') or tp.get('relativeUrl') or ''
    objects['dataset'][n] = {'type': p.get('type'), 'ls': (p.get('linkedServiceName') or {}).get('referenceName'), 'folder': folder(j),
                             'where': mask(where)[:120]}

for n, j in DF.items():
    tp = j.get('properties', {}).get('typeProperties', {}) or {}
    objects['dataflow'][n] = {'folder': folder(j), 'sources': len(tp.get('sources', [])), 'sinks': len(tp.get('sinks', [])),
                              'transformations': len(tp.get('transformations', [])), 'script_lines': len(tp.get('scriptLines', []))}

NB_RUN = re.compile(r'''(?:mssparkutils|notebookutils)\.notebook\.run\(\s*f?["']([^"'{}]+)["']|^\s*%run\s+(\S+)''', re.M)
TEXT = {}  # (kind, name) -> lowercased code / JSON, for data-level lineage (who reads whose data)
for n, j in NB.items():
    p = j.get('properties', {})
    code = '\n'.join(''.join(c.get('source', [])) for c in p.get('cells', []) if c.get('cell_type') == 'code')
    TEXT[('notebook', n)] = code.lower()
    kids = {(a or b).strip().split('/')[-1] for a, b in NB_RUN.findall(code)} - {n}
    objects['notebook'][n] = {'folder': folder(j), 'lines': code.count('\n') + 1, 'mssparkutils': 'mssparkutils' in code, 'children': sorted(kids),
                              'jdbc': bool(re.search(r'synapsesql|jdbc', code, re.I)),
                              'abfss': sorted(set(re.findall(r'abfss://[^\s\'"{}]+', code)))[:6],
                              'pool': (p.get('bigDataPool') or {}).get('referenceName'), 'called_by': []}

for n, j in SQ.items():
    q = (((j.get('properties') or {}).get('content') or {}).get('query', '') or '').replace("''", "'")
    for k, s, o in SQL_CREATE.findall(q):
        if o:
            sql_defined_in[f'{s.lower()}.{o.lower()}'].add(('sqlscript', n, kind_of(k)))
    objects['pipeline'].setdefault('__sqlscripts__', {})  # placeholder removed below

objects['pipeline'].pop('__sqlscripts__', None)
sqlscripts = {}
for n, j in SQ.items():
    q = (((j.get('properties') or {}).get('content') or {}).get('query', '') or '').replace("''", "'")
    z, e = zone_entity(folder(j))
    creates = sorted({f"{s.lower()}.{o.lower()}" for k, s, o in SQL_CREATE.findall(q) if o})
    reads = sorted({f'{s.lower()}.{o.lower()}' for s, o in SQL_REF.findall(q)} - set(creates))[:60]
    sqlscripts[n] = {'folder': folder(j), 'zone': z, 'entity': e, 'lines': q.count('\n') + 1, 'creates': creates[:400], 'reads': reads,
                     'catalog_rows': len(re.findall(r'INSERT\s+INTO\s+\[?CATALOG\]?\.', q, re.I))}
objects['sqlscript'] = sqlscripts

for n, j in P.items():
    props = j.get('properties', {})
    acts = list(walk(props.get('activities')))
    z, e = zone_entity(folder(j))
    sql_all = '\n'.join(sql_text_of_activity(a) for a in acts)
    creates = set()
    for k, s, o in SQL_CREATE.findall(sql_all):
        if o:
            key = f'{s.lower()}.{o.lower()}'
            creates.add(key)
            sql_defined_in[key].add(('pipeline', n, kind_of(k)))
    reads = {f'{s.lower()}.{o.lower()}' for s, o in SQL_REF.findall(sql_all)} - creates
    for nb in {str(a['typeProperties'].get('notebook', {}).get('referenceName')) for a in acts if a['type'] == 'SynapseNotebook'}:
        if nb in objects['notebook']:
            objects['notebook'][nb]['called_by'].append(n)
    # environment if-chains: parameter/variable name -> {ENV: value}
    def scan(o, key=None):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, dict) and isinstance(v.get('value'), str) and 'pipeline().DataFactory' in v['value']:
                    pairs = re.findall(r"equals\(\s*pipeline\(\)\.DataFactory\s*,\s*'([^']+)'\s*\)\s*,\s*'([^']*)'", v['value'])
                    if pairs:
                        vl_vars[n][snake(k)] = {env_of(f): val for f, val in pairs}
                else:
                    scan(v, k)
        elif isinstance(o, list):
            for v in o:
                scan(v, key)
    scan(props.get('activities'))
    objects['pipeline'][n] = {
        'folder': folder(j), 'zone': z, 'entity': e, 'acts': len(acts), 'types': dict(Counter(a['type'] for a in acts)),
        'children': sorted({a['typeProperties']['pipeline']['referenceName'] for a in acts if a['type'] == 'ExecutePipeline'}),
        'notebooks': sorted({str(a['typeProperties'].get('notebook', {}).get('referenceName')) for a in acts if a['type'] == 'SynapseNotebook'}),
        'dataflows': sorted({str(a['typeProperties'].get('dataflow', {}).get('referenceName')) for a in acts if a['type'] == 'ExecuteDataFlow'}),
        'datasets': sorted(refs(props, 'DatasetReference')), 'ls': sorted(refs(props, 'LinkedServiceReference')),
        'params': sorted((props.get('parameters') or {}).keys()), 'triggers': trig_of.get(n, []),
        'sql_kb': len(sql_all) // 1024, 'creates': sorted(creates)[:300], 'reads': sorted(reads)[:80],
        'procs_called': sorted({str(a['typeProperties'].get('storedProcedureName')).replace('[', '').replace(']', '') for a in acts if a['type'] == 'SqlServerStoredProcedure'}),
        'env_vars': vl_vars.get(n, {}),
        'activities': [[a['name'], a['type']] for a in acts][:60],
    }

# notebook names passed as pipeline parameters (e.g. IngestionNotebook = "GEOS_WORLD/NTBK_GEOS_CHILD_FULL_RAW_TO_CLEAN")
NB_NAME = re.compile(r'(?<![\w])(' + '|'.join(sorted(map(re.escape, NB), key=len, reverse=True)) + r')(?![\w])') if NB else None
for n, j in P.items():
    TEXT[('pipeline', n)] = json.dumps(j).lower()
    if NB_NAME:
        hits = set(NB_NAME.findall(json.dumps(j))) - set(objects['pipeline'][n]['notebooks'])
        objects['pipeline'][n]['notebooks'] = sorted(set(objects['pipeline'][n]['notebooks']) | hits)
        for nb in hits:
            objects['notebook'][nb]['called_by'].append(n)
for n, j in SQ.items():
    TEXT[('sqlscript', n)] = (((j.get('properties') or {}).get('content') or {}).get('query', '') or '').lower()
for n, nb in objects['notebook'].items():
    for c in nb['children']:
        if c in objects['notebook']:
            objects['notebook'][c]['called_by'].append(f'notebook:{n}')


def nb_closure(nbs):
    """Notebooks plus every notebook they run (mssparkutils.notebook.run, %run)."""
    seen, stack = set(), list(nbs)
    while stack:
        x = stack.pop()
        if x in seen or x not in objects['notebook']:
            continue
        seen.add(x)
        stack.extend(objects['notebook'][x]['children'])
    return seen


called = {c for p in objects['pipeline'].values() for c in p['children']}
callers = defaultdict(set)
for n, p in objects['pipeline'].items():
    for c in p['children']:
        callers[c].add(n)

for key, defs in sql_defined_in.items():
    s, o = key.split('.', 1)
    kinds = sorted({d[2] for d in defs})
    objects['sql'][key] = {'schema': s, 'name': o, 'kind': kinds[0] if kinds else '?', 'defined_in': sorted(f'{d[0]}:{d[1]}' for d in defs)[:6]}


def closure(roots, allowed=None):
    seen = set()
    stack = list(roots)
    while stack:
        n = stack.pop()
        if n in seen or n not in objects['pipeline']:
            continue
        if allowed and objects['pipeline'][n]['zone'] not in allowed and n not in roots:
            continue
        seen.add(n)
        stack.extend(objects['pipeline'][n]['children'])
    return seen


def up_closure(n):
    seen, stack = set(), [n]
    while stack:
        x = stack.pop()
        if x in seen:
            continue
        seen.add(x)
        stack.extend(callers.get(x, ()))
    return seen


# ---------------------------------------------------------------- target rules
def tgt_name(scope):
    return scope.replace('-', '_')


def reg_scope(r):
    return r.get('scope') or norm(r['project'])


REG_BY_SCOPE = defaultdict(list)
for r in REG['projects']:
    REG_BY_SCOPE[reg_scope(r)].append(r)


def domain_of(s):
    # explicit target map first, then the domain stated in the project register
    if s in CFG['domains']:
        return CFG['domains'][s]
    for r in REG_BY_SCOPE.get(s, []):
        code = REG['domain_codes'].get(r['domain'])
        if code:
            return re.sub(r'[^A-Z0-9_]', '', code.upper()) or CFG['defaults']['domain']  # item names allow A-Z, 0-9, _ only (P&C => PC)
    return CFG['defaults']['domain']


def group_of(s):
    return CFG['groups'].get(s, tgt_name(s))


LS_TYPE_MAP = {
    'Oracle': ('Connection', 'Oracle database', True), 'SqlServer': ('Connection', 'SQL Server', True), 'FileServer': ('Connection', 'File system', True),
    'Sftp': ('Connection', 'SFTP', False), 'FtpServer': ('Connection', 'FTP', False), 'HttpServer': ('Connection', 'HTTP', False),
    'RestService': ('Connection', 'REST', False), 'OData': ('Connection', 'OData', False), 'SharePointOnlineList': ('Connection', 'SharePoint Online list', False),
    'AzureSqlDatabase': ('Connection', 'Azure SQL Database', False), 'AzurePostgreSql': ('Connection', 'Azure Database for PostgreSQL', False),
    'AmazonS3': ('Connection', 'Amazon S3', False), 'AmazonRedshift': ('Connection', 'Amazon Redshift', False), 'OracleCloudStorage': ('Connection', 'Oracle Cloud Storage', False),
    'AzureBlobStorage': ('Connection', 'Azure Blob Storage', False), 'AzureFileStorage': ('Connection', 'Azure Files', False), 'AzureTableStorage': ('Connection', 'Azure Table Storage', False),
    'PowerBIWorkspace': ('Connection', 'Power BI (semantic model refresh)', False), 'AzureFunction': ('Connection', 'Azure Function', False),
}


def map_ls(n, scope_tag, service='sds'):
    ls = objects['linkedService'].get(n, {'type': '?', 'runtime': '?'})
    t = ls['type']
    gw = 'SelfHosted' in (ls.get('runtime') or '')
    if re.search(r'METABASE|CATALOG', n, re.I):
        if service == 'dp':  # the catalog drives source ingestion; a data product reads LH_INP_SDS_<SRC> instead
            return 'drop', '-', '-', 'Catalog belongs to the source datasets ([CATALOG].[<source>_catalog]); the data product reads LH_INP_SDS_<SRC>'
        return 'replace', 'Catalog view', f'[CATALOG].[{scope_tag.lower()}_catalog] in the catalog warehouse', f'VL_MAIN: {scope_tag}_CATALOG_VIEW_NAME; warehouse: {scope_tag}_CATALOG_WAREHOUSE_* (CATALOG_WAREHOUSE_* when a common catalog warehouse is chosen in framing)'
    if t in ('AzureBlobFS', 'AzureDataLakeStore'):
        # DPV1 zones (RAW / CLEANSED / CURATED) were Synapse storage; in Fabric, OneLake is built into the Lakehouse and reached by path
        return 'drop', '-', '-', 'ADLS zone of DPV1: OneLake is built into the Lakehouse, no connection needed'
    if t in ('AzureSqlDW',):
        return 'drop', 'Warehouse', 'Fabric Warehouse / Lakehouse SQL endpoint (internal)', 'Dedicated or serverless pool no longer used'
    if t == 'AzureKeyVault':
        return 'replace', 'Connection credential', 'Secrets referenced from the Fabric connection', 'Key Vault reference'
    kind, label, onprem = LS_TYPE_MAP.get(t, ('Connection', t or '?', False))
    name = f"CONN_{scope_tag}_{snake(t or 'SRC')}_<ENV>"
    via = 'on-premises data gateway' if gw or onprem else 'cloud connection'
    return 'translate', kind, f'{name} ({label}, {via})', f'VL_MAIN: {snake(scope_tag)}_{snake(t or "SRC")}_CONN_ID'


def sds_pipeline_rule(n, s):
    u = n.upper()
    if re.search(r'DWH_TO_SPOT|CETAS|_SPOT\b|TO_SPOT', u): return 'drop', '-', '-', 'Copy-back of the Dedicated Pool: OneLake makes it unnecessary'
    if re.search(r'MAIL|NOTIFICATION|_LOG_|SUCCESS_LOG|FAILURE_LOG', u): return 'merge', 'Pipeline', 'PL_COMMON_NOTIFICATION / logging framework', 'Per-source wrapper'
    if re.search(r'CLNMETA|CLNDATA|RAW_TO_CLEAN', u): return 'merge', 'Pipeline', f'2-RAW_TO_DELTA/PL_{s}_RAW_TO_DELTA', 'RAW → Lakehouse tables with history (no cleansed zone)'
    if re.search(r'META|DB_BUILD|EXECUTE_\w*SCRIPT|CATALOG|INIT', u): return 'replace', 'Metabase / CI-CD', 'METABASE table list + CI/CD deployment', 'Runtime DDL and catalog building'
    if re.search(r'RAWDATA|TO_ADLS|SOURCE_TO_RAW|EXTRACT|_RAW_|COPY', u) and not re.search(r'CLN|CLEAN', u):
        return 'merge', 'Pipeline', f'1-SOURCE_TO_RAW/PL_{s}_SOURCE_TO_RAW', 'Source → Files/landing (source format) → Files/raw (parquet) (FULL / INCREMENTAL)'
    if re.search(r'CLN|CLEAN|RAW_TO|DELTA|TO_SPOTDB|OFFLOAD', u): return 'merge', 'Pipeline', f'2-RAW_TO_DELTA/PL_{s}_RAW_TO_DELTA', 'RAW → Lakehouse tables with history (no cleansed zone)'
    if re.search(r'ORCH|MASTER|_EXT$|_EXT_', u): return 'rebuild', 'Pipeline', f'0-ORCHESTRATION/PL_{s}_MASTER_ORCHESTRATOR', 'Rebuilt from the simplified graph'
    return 'review', 'Pipeline', f'(review) PL_{s}_…', 'No rule matched: classify manually'


def dp_pipeline_rule(n, g):
    u = n.upper()
    if re.search(r'DWH_TO_SPOT|CETAS|_SPOT\b|TO_SPOT', u): return 'drop', '-', '-', 'SPOT_DB DWH copy-back: consumers read WH_DPG / shortcuts'
    if re.search(r'MAIL|NOTIFICATION|_LOG_|SUCCESS_LOG|FAILURE_LOG', u): return 'merge', 'Pipeline', 'PL_COMMON_NOTIFICATION / logging framework', 'Per-project wrapper'
    if re.search(r'META|DB_BUILD|EXECUTE_\w*SCRIPT|CATALOG|INIT', u): return 'replace', 'DACPAC', f'DPG-{g} database project (CI/CD)', 'Runtime DDL deployment → DACPAC'
    if re.search(r'POWERBI|REFRESH', u): return 'translate', 'Pipeline activity', f'PL_{g}_PROCESS_DATA_PRODUCT · semantic model refresh', 'Power BI refresh step'
    if re.search(r'RAWDATA|TO_ADLS|CLNDATA|RAW_TO_CLEAN', u): return 'upstream', 'Source dataset', 'Handled by Source Dataset Migration', 'Source step inside a product chain'
    if re.search(r'INP|LDW|PREMODEL|_OUT\b|_OUT_|TRAN_OUT|CUR|PROP_STG|_STG|STAGE', u):
        return 'collapse', 'DACPAC', f'DPG-{g}/01-silver-*/2-intermediate (CTEs inside load procedures)', 'CURATED / serverless / STG hop removed'
    if re.search(r'_DM\b|_DM_|DATAMART', u): return 'translate', 'Pipeline', f'ORCHESTRATION/PL_{g}_PROCESS_DATA_PRODUCT (gold step)', 'Gold refresh'
    if re.search(r'_DW|DWH|DIM|FACT|DPSP|BUILD|TRAN|PROP', u): return 'translate', 'Pipeline', f'ORCHESTRATION/PL_{g}_PROCESS_DATA_PRODUCT (silver step)', 'Stored-procedure batches'
    if re.search(r'ORCH|MASTER|_EXT', u): return 'rebuild', 'Pipeline', f'ORCHESTRATION/PL_{g}_MASTER_ORCHESTRATOR', 'Rebuilt from the simplified graph'
    return 'review', 'Pipeline', f'(review) PL_{g}_…', 'No rule matched: classify manually'


def nb_rule(n, s, side):
    u = n.upper()
    if re.search(r'SPOT|OFFLOAD', u): return 'drop', '-', '-', 'Copy-back / offload notebook'
    if re.search(r'RAW_TO_CLEAN|RAW_TO_DELTA|CLEANSED|CLEAN', u): return 'merge', 'Notebook', f'2-RAW_TO_DELTA/NB_{s}_RAW_TO_DELTA', 'Variants merge into one catalog-driven notebook'
    base = re.sub(r'^(NTBK|NB)_?', '', u)
    base = re.sub(rf'^(CHILD_)?{re.escape(s)}_?', '', base) or 'LOGIC'
    loc = f'2-RAW_TO_DELTA/NB_{s}_{base}' if side == 'sds' else f'ORCHESTRATION/NB_{s}_{base}'
    return 'translate', 'Notebook', loc, 'Port: mssparkutils → notebookutils, Lakehouse paths, VL_MAIN'


def sql_rule(key, kind, g):
    s, o = key.split('.', 1)
    sl = s.lower()
    if kind == 'EXTERNAL' or sl.startswith(('inp', 'ext')) and kind in ('TABLE', 'EXTERNAL'):
        return 'replace', 'Lakehouse', f'LH_INP_SDS_* shortcut table → DPG-{g}/…/1-input', 'External table over ADLS → internal shortcut'
    if sl in ('out', 'stg', 'stage') or sl.startswith(('stg_', 'out_')):
        return 'drop', '-', '-', 'CETAS / staging copy removed'
    if sl.startswith(('dw_', 'dw', 'dwh', 'c_', 'cur')) and kind == 'TABLE':
        return 'translate', 'Warehouse table', f'DPG-{g}/01-silver-{g.lower()}/4-output/{o}', 'Silver table, moved through DACPAC (no DISTRIBUTION / CCI)'
    if sl.startswith(('dw_', 'dw', 'dwh', 'c_', 'cur')) and kind.startswith('PROC'):
        return 'translate', 'Stored procedure', f'DPG-{g}/01-silver-{g.lower()}/3-processing/{o}', 'T-SQL load procedure, moved through DACPAC, reads LH_INP_SDS'
    if sl.startswith(('dm_', 'dm', 'gsp', 'spbi', 'rpt')):
        return 'translate', 'Warehouse view', f'DPG-{g}/02-gold-{g.lower()}/4-output/{o}', 'Gold CRDP'
    if sl.startswith(('inp', 'ldw', 'proj')) or kind in ('VIEW',) or o.lower().startswith('sp_create_'):
        return 'collapse', 'Stored procedure', f'DPG-{g}/01-silver-{g.lower()}/2-intermediate (CTE)', 'Serverless view hop absorbed into silver load'
    if sl == 'catalog':
        return 'replace', 'Metabase', 'METABASE catalog table', 'Pipeline parameter catalog'
    if sl.startswith('rpl'):
        return 'review', 'Source dataset', 'LH_SDS_* table (replica)', 'Replica belongs to the source dataset'
    return 'review', 'Warehouse', f'DPG-{g}/00-global or review', 'No rule matched'


# ---------------------------------------------------------------- scopes
by_entity = defaultdict(lambda: {'SRC': set(), 'DP': set(), 'EXT': set()})
for n, p in objects['pipeline'].items():
    if p['entity'] and p['zone'] in ('SRC', 'DP', 'EXT'):
        by_entity[p['entity']][p['zone']].add(n)


def catalog_tables(scope):
    rows = []
    key = scope.replace('_', '').upper()
    for n, j in SQ.items():
        if not re.sub(r'[^A-Z0-9]', '', n.upper()).endswith(key) and f'[CATALOG].[{scope}]' not in (((j.get('properties') or {}).get('content') or {}).get('query', '') or '').upper():
            continue
        q = (((j.get('properties') or {}).get('content') or {}).get('query', '') or '')
        found = []
        for m in re.finditer(r"^\s*INSERT\s+INTO\s+\[?CATALOG\]?\.\[?\w+\]?\s*VALUES\s*\(\s*'+([^']*)'+\s*,\s*'+([^']*)'+\s*,\s*'*(\d)", q, re.I | re.M):  # skips commented-out rows
            found.append({'schema': m.group(1), 'table': m.group(2), 'incremental': m.group(3) == '1', 'from': n})
        qq = q.replace("''", "'") if re.search(r"VALUES\s*\(\s*''\w", q) else q
        nc = re.sub(r'^[ \t]*--[^\n]*$', '', re.sub(r'/\*.*?\*/', '', qq, flags=re.S), flags=re.M)
        if len(found) < len(re.findall(r'INSERT\s+INTO\s+\[?CATALOG\]?', nc, re.I)):  # other layouts: values over several lines, a column list, several tuples per INSERT
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from create_catalog_view import insert_statements, split_values
            alt = []
            api = re.search(r'\[?ApiName\]?\s+\[?VARCHAR', nc, re.I) is not None  # REST layout: ApiName, isActive, ParamName, UnicityKeys, WatermarkVal
            for names, body in insert_statements(nc):
                v = [x.strip().strip("'") for x in split_values(body)]
                if api and not names:
                    if v and v[0] and (len(v) < 2 or v[1] != '0'):  # isActive = 0 is not migrated
                        alt.append({'schema': scope, 'table': v[0], 'incremental': len(v) > 4, 'from': n})
                    continue
                d = dict(zip([x.lower() for x in names], v)) if names else {'schemaname': v[0] if v else '', 'tablename': v[1] if len(v) > 1 else '', 'isincload': v[2] if len(v) > 2 else ''}
                if d.get('tablename'):
                    alt.append({'schema': d.get('schemaname') or d.get('source', ''), 'table': d['tablename'], 'incremental': d.get('isincload', '') == '1', 'from': n})
            if len(alt) > len(found):
                found = alt
        rows += found
    seen, out = set(), []
    for r in rows:
        if (r['schema'], r['table']) not in seen:
            seen.add((r['schema'], r['table'])); out.append(r)
    return out


def row(v1_type, v1_name, action, v2_type, v2_target, note, ws=''):
    return {'v1t': v1_type, 'v1': v1_name, 'a': action, 'v2t': v2_type, 'v2': v2_target, 'ws': ws, 'n': note}


# Shared framework pipelines and notebooks (generic, called by many scopes): what replaces each one in Fabric.
# Every shared object gets an explicit action here, so no scope relies on a "migrated once" that nobody owns.
SHARED_RULES = [
    (r'MAIL_NOTIFICATION|SEND_MAIL|NOTIF', 'drop', 'Activator job alert', 'Activator alert on the master orchestrator (failure / success)'),
    (r'FETCH_PIPELINES_FAILURES|MONITOR|AUTO_TICKETING|LOG_CORRELATION', 'replace', 'Workspace monitoring', 'Workspace monitoring + Monitor Hub; Activator for alerts'),
    (r'METABASE_CATALOG|CATALOG_CREATION|CREATE_INP_VIEWS_CATALOG|TEMPLATE_CATALOG', 'replace', 'Catalog view', 'Catalog view [CATALOG].[<source>_catalog] built by create_catalog_view.py'),
    (r'TRIGGER_TOGGLE', 'drop', 'Schedule', 'Fabric schedules are switched on and off on the item'),
    (r'DB_BUILD|EXECUTE_\w*SCRIPT|GENERATOR_|SP_GENERATOR', 'replace', 'DACPAC', 'DACPAC deployment (fabric-cicd) of the database project'),
    (r'DWH_TO_SPOT|TO_SPOT|PROVISION_SPOT|SPOT_CREATION|SPOT_VIEW|SQLDW_TO_SPOT|OFFLOAD|CETAS|EXTRACT_TABLE', 'drop', '-', 'Copy-back to SPOT_DB not needed: gold views are read in place (SQL endpoint, shortcuts)'),
    (r'COPY_TO_STG', 'collapse', 'Stored procedure', 'STG hop absorbed into the silver load procedures'),
    (r'META_RAW_TO_CLEAN|MASTER_RAW_TO_CLEAN|RAW_TO_CLEAN', 'merge', 'Notebook', 'Merged into NB_<SOURCE>_RAW_TO_DELTA of each source dataset'),
    (r'UPDATE_?WATERMARK', 'merge', 'Notebook', 'Watermark kept in the catalog view, updated by the incremental load of each source'),
]


def shared_rule(n):
    for rx, a, t, tg in SHARED_RULES:
        if re.search(rx, n, re.I):
            return a, t, tg
    return 'review', 'Shared framework', 'No shared rule matched: decide the Fabric replacement (scope-decisions.json)'


def shared_row(n, kind='Pipeline'):
    a, t, tg = shared_rule(n)
    return row(kind, n, a, t if a != 'drop' else '-', tg if a != 'drop' else '-', f'Shared framework, used by several scopes: {tg}', '-')


_DEC_PATH = os.path.join(os.path.dirname(TARGET_CFG), 'scope-decisions.json')
DECISIONS = json.load(open(_DEC_PATH, encoding='utf-8')) if os.path.exists(_DEC_PATH) else {}


def apply_decisions(kind, scope, rows):
    """Owner decisions (2-config/migration/scope-decisions.json) override the rules for named objects."""
    dec = DECISIONS.get(kind, {}).get(scope, {})
    for r in rows:
        d = dec.get(r['v1'])
        if d:
            r['a'] = d['action']
            if d['action'] == 'drop':
                r['v2t'], r['v2'], r['ws'] = '-', '-', '-'
            elif d['action'] in ('product', 'upstream'):
                r['v2t'], r['v2'], r['ws'] = ('Data product' if d['action'] == 'product' else 'Source dataset'), d.get('target', r['v2']), '-'
            elif d.get('target'):
                r['v2'] = d['target']
            r['n'] = f"Owner decision {d.get('date', '')} ({d.get('decided_by', 'owner')}): {d.get('reason', '')}"
    return rows


def assets_of(pipes):
    nbs, dfs, dss, lss, trs = set(), set(), set(), set(), set()
    for n in pipes:
        p = objects['pipeline'][n]
        nbs |= set(p['notebooks']); dfs |= set(p['dataflows']); dss |= set(p['datasets']); lss |= set(p['ls']); trs |= set(p['triggers'])
    nbs = nb_closure(nbs)
    for d in dss:
        l = objects['dataset'].get(d, {}).get('ls')
        if l:
            lss.add(l)
    return nbs, dfs, dss, lss, trs


def vl_rows(pipes, ws):
    out = {}
    for n in sorted(pipes):  # first pipeline in name order gives the values: same result on every run
        for var, vals in objects['pipeline'][n]['env_vars'].items():
            out.setdefault(var, {'values': vals, 'used_by': []})['used_by'].append(n)
    return [{'var': v, 'values': d['values'], 'used_by': sorted(d['used_by'])[:6], 'ws': ws} for v, d in sorted(out.items())]


def build_sds(scope):
    s = tgt_name(scope)
    dom = domain_of(scope)
    ws = f'DP_SDS_{dom}_<ENV>'
    own = by_entity[scope]['SRC'] | {x for x in by_entity[scope]['EXT'] if closure([x]) & by_entity[scope]['SRC'] or not by_entity[scope]['DP']}
    reach = closure(own)
    pipes = {x for x in reach if objects['pipeline'][x]['zone'] in ('SRC', 'EXT', 'SHARED', 'OTHER')}
    # RAW->CLEANSED steps stored in a project folder (e.g. PL_CLNMETA_GAIA_CSV) are still source ingestion
    pipes |= {x for x in reach if objects['pipeline'][x]['zone'] == 'DP'
              and any(re.search(r'RAW_TO_CLEAN', nb, re.I) for y in closure([x]) for nb in objects['pipeline'][y]['notebooks'])}
    downstream = sorted({objects['pipeline'][x]['entity'] for x in reach if objects['pipeline'][x]['zone'] == 'DP' and objects['pipeline'][x]['entity']})
    shared = sorted(x for x in pipes if objects['pipeline'][x]['zone'] == 'SHARED')
    nbs, dfs, dss, lss, trs = assets_of(pipes)
    nbs |= {n for n, nb in objects['notebook'].items() if norm((nb['folder'] or '').split('/')[0] or 'x') == scope and not nb['called_by']}
    cat = catalog_tables(scope)
    scripts = sorted(n for n, q in sqlscripts.items() if q['zone'] == 'SRC' and q['entity'] == scope)
    dp_zone = {n for n, p in objects['pipeline'].items() if p['zone'] == 'DP'}
    entry_like = {x for x in own if x not in called or objects['pipeline'][x]['triggers'] or objects['pipeline'][x]['zone'] == 'EXT'}
    rows = []
    for n in sorted(pipes):
        if n in shared:
            rows.append(shared_row(n)); continue
        p = objects['pipeline'][n]
        runs_raw2clean = any(re.search(r'RAW_TO_CLEAN', nb, re.I) for y in closure([n]) for nb in objects['pipeline'][y]['notebooks'])
        drives_product = n not in entry_like and not runs_raw2clean and bool(closure([n]) & dp_zone)  # e.g. 03_PL_TRAN_GAIA_ORCH_PREMODELIZED
        if (p['zone'] == 'DP' and not runs_raw2clean) or drives_product or re.search(r'DB_BUILD|EXECUTE_\w*SCRIPT', n, re.I) or any(re.match(r'^(dw|dm|ldw|out|stg|proj)(_|$)', c) for c in p['creates']):
            rows.append(row('Pipeline', n, 'product', 'Data product', f'Data Product Migration: {p["entity"] or scope}', 'Product step or product DDL reached from the source master', '-')); continue
        a, t, tg, note = sds_pipeline_rule(n, s)
        rows.append(row('Pipeline', n, a, t, tg, note, ws if t != '-' else '-'))
    for n in sorted(nbs):
        a, t, tg, note = nb_rule(n, s, 'sds')
        rows.append(row('Notebook', n, a, t, tg, note, ws if t != '-' else '-'))
    for n in sorted(dfs):
        rows.append(row('Data flow', n, 'rewrite', 'Notebook', f'2-RAW_TO_DELTA/NB_{s}_{snake(n)}', 'No Mapping Data Flow in Fabric → PySpark', ws))
    for n in sorted(lss):
        a, t, tg, note = map_ls(n, s)
        rows.append(row('Linked service', n, a, t, tg, note, 'Fabric connections (tenant)' if t == 'Connection' else ws))
    for n in sorted(dss):
        d = objects['dataset'].get(n, {})
        rows.append(row('Dataset', n, 'drop', '-', '-', f"Datasets do not exist in Fabric: source / sink settings sit in the activity · {d.get('type')} {d.get('where', '')}"[:140], '-'))
    for n in sorted(trs):
        t = objects['trigger'].get(n, {})
        rows.append(row('Trigger', n, 'translate', 'Schedule', f'Schedule on PL_{s}_MASTER_ORCHESTRATOR', f"{t.get('type')} · {t.get('state')} · {t.get('schedule', '')}"[:120], ws))
    for n in scripts:
        info = f"{sqlscripts[n]['lines']} lines, creates {len(sqlscripts[n]['creates'])} objects"
        if re.match(r'^catalog', n, re.I):
            rows.append(row('SQL script', n, 'replace', 'Catalog view', f'Catalog warehouse (WH_CATALOG_{s}, or the common one chosen in framing): [CATALOG].[{s.lower()}_catalog] (create_catalog_view.py)', info + '; rows and columns carried into the view', ws))
        else:
            rows.append(row('SQL script', n, 'review', 'SQL script', f'(review) LH_SDS_{s} SQL endpoint or drop', info + '; not a catalog script: confirm whether it is still needed', ws))
    for c in cat:
        rows.append(row('Source table', f"{c['schema']}.{c['table']}", 'translate', 'Lakehouse table',
                        f"LH_SDS_{s}: Files/raw (parquet) => dbo.{c['table'].lower()}", ('incremental' if c['incremental'] else 'full') + ', ingested from the source', ws))
    rows = apply_decisions('sds', scope, rows)
    vl = vl_rows(pipes, ws) + [{'var': f'LH_SDS_{s}_ID', 'values': {'DEV': '<guid>', 'UAT': '<guid>', 'PRD': '<guid>'}, 'used_by': ['all'], 'ws': ws}]
    entry = sorted(x for x in own if x not in called or objects['pipeline'][x]['triggers'] or objects['pipeline'][x]['zone'] == 'EXT')
    return {'scope': scope, 'kind': 'sds', 'domain': dom, 'domain_confirmed': scope in CFG['confirmed'], 'ws': ws, 'folder': s, 'lakehouse': f'LH_SDS_{s}',
            'entry': entry, 'pipelines': sorted(pipes), 'shared': shared, 'notebooks': sorted(nbs), 'dataflows': sorted(dfs), 'datasets': sorted(dss),
            'linked_services': sorted(lss), 'triggers': sorted(trs), 'sqlscripts': scripts, 'catalog': cat, 'downstream': downstream,
            'rows': rows, 'vl': vl, 'counts': dict(Counter(r['a'] for r in rows))}


def scope_schemas(pipes, scripts, scope):
    key = scope.lower().replace('-', '_')
    cands = Counter()
    for n in pipes:
        p = objects['pipeline'][n]
        for x in p['creates'] + p['reads'] + p['procs_called']:
            if '.' in x:
                cands[x.split('.')[0].lower()] += 1
    for n in scripts:
        for x in sqlscripts[n]['creates']:
            cands[x.split('.')[0]] += 1
    generic = {'dbo', 'sys', 'information_schema', 'master', 'catalog', 'pipeline', 'item', 'activity', 'variables'}
    cands = Counter({s: c for s, c in cands.items() if re.fullmatch(r'\w+', s)})  # drop fragments of dynamic expressions
    keep = {s for s, c in cands.items() if s not in generic and (key in s or re.match(r'^(dw|dm|inp|ldw|c|out|stg|proj)_', s) and key.split('_')[0] in s)}
    keep |= {s for s, c in cands.items() if s in ('out', 'ldw', 'inp', 'stg') and c >= 1}
    return sorted(keep)


def build_dp(scope):
    g = group_of(scope)
    ws = f'DP_DPG_{g}_<ENV>'
    own = by_entity[scope]['DP'] | {x for x in by_entity[scope]['EXT'] if closure([x]) & by_entity[scope]['DP']}
    # a source-zone master that orchestrates this product (e.g. 00_PL_GAIA_ORCH_MASTER) is an entry point too
    dp_all = {n for n, p in objects['pipeline'].items() if p['zone'] == 'DP'}
    product_src = {x for x in by_entity[scope]['SRC'] if closure([x]) & dp_all}   # source-folder pipelines that drive product steps
    masters = {x for x in product_src if not (callers.get(x, set()) & product_src)}
    reach = closure(own | masters)
    product_src = {x for x in reach if objects['pipeline'][x]['zone'] == 'SRC' and closure([x]) & dp_all}
    pipes = {x for x in reach if objects['pipeline'][x]['zone'] in ('DP', 'EXT', 'SHARED', 'OTHER')} | product_src
    # source-folder pipelines that deploy product DDL (e.g. PL_META_PROJ_GAIA_EXECUTE_DEDICATED_SCRIPT) belong to the product
    ddl = {x for x in reach if objects['pipeline'][x]['zone'] == 'SRC' and (
        any(re.match(r'^(dw|dm|ldw|out|stg|proj|c)(_|$)', c) for c in objects['pipeline'][x]['creates'])
        or re.search(r'DB_BUILD|EXECUTE_\w*SCRIPT', x, re.I))}
    # pipelines (other than masters) whose call tree runs a RAW->CLEANSED notebook are source ingestion
    raw2clean = {x for x in pipes - masters if any(re.search(r'RAW_TO_CLEAN', nb, re.I) for y in closure([x]) for nb in objects['pipeline'][y]['notebooks'])
                 and not re.search(r'ORCH_MASTER|^00_', x)}
    # copy-back roots named after the scope (e.g. PL_MASTER_GAIABI_DWH_TO_SPOT) are not called by the product chain
    tok = re.compile(rf'(?<![A-Z0-9]){re.escape(scope.replace("-", "_").upper())}')
    copyback = {n for n in objects['pipeline'] if n not in called and tok.search(n.upper()) and re.search(r'DWH_TO_SPOT|CETAS|_SPOT\b|TO_SPOT', n, re.I)}
    pipes = (pipes | ddl | closure(copyback)) - raw2clean
    upstream_steps = sorted((x for x in reach if objects['pipeline'][x]['zone'] == 'SRC' and x not in product_src and x not in ddl), key=str)
    upstream_steps = sorted(set(upstream_steps) | raw2clean)
    upstream = sorted({objects['pipeline'][x]['entity'] for x in upstream_steps if objects['pipeline'][x]['entity']} - {None})
    shared = sorted(x for x in pipes if objects['pipeline'][x]['zone'] == 'SHARED')
    nbs, dfs, dss, lss, trs = assets_of(pipes)
    scripts = sorted(n for n, q in sqlscripts.items() if q['zone'] == 'DP' and q['entity'] == scope)
    schemas = scope_schemas(pipes, scripts, scope)
    for s in schemas:  # inp_<src> schemas reveal input sources
        m = re.match(r'^(?:inp|rpl)_(\w+)', s)
        if m and norm(m.group(1)) in by_entity and norm(m.group(1)) != scope:
            upstream.append(norm(m.group(1)))
    if by_entity[scope]['SRC']:
        upstream.append(scope)
    upstream = sorted(set(upstream))
    sqlobjs = sorted(k for k, v in objects['sql'].items() if v['schema'] in schemas and any(
        d.split(':', 1)[1] in pipes or d.split(':', 1)[1] in scripts for d in v['defined_in']))
    if not sqlobjs:
        sqlobjs = sorted(k for k, v in objects['sql'].items() if v['schema'] in schemas)[:400]
    # objects the product reads or calls whose DDL is not in the repo (lives in the Synapse databases)
    refd = defaultdict(set)
    for n in pipes:
        for x in objects['pipeline'][n]['reads'] + objects['pipeline'][n]['procs_called']:
            refd[x.lower()].add(f'pipeline:{n}')
    for n in scripts:
        for x in sqlscripts[n]['reads']:
            refd[x.lower()].add(f'sqlscript:{n}')
    for x, by in refd.items():
        if '.' not in x or x in objects['sql']:
            continue
        s_, o_ = x.split('.', 1)
        if s_ in schemas and re.fullmatch(r'\w+', o_) and re.match(r'^(dw|dm|c_|cur|gsp|spbi)', s_):
            objects['sql'][x] = {'schema': s_, 'name': o_, 'kind': 'PROC' if re.match(r'(u?sp|p)_', o_) else 'REF', 'defined_in': sorted(by)[:3], 'ref_only': True}
            sqlobjs.append(x)
    sqlobjs = sorted(set(sqlobjs))
    rows = []
    for n in sorted(pipes):
        if n in shared:
            rows.append(shared_row(n)); continue
        a, t, tg, note = dp_pipeline_rule(n, g)
        if n in masters:
            a, t, tg, note = 'rebuild', 'Pipeline', f'ORCHESTRATION/PL_{g}_MASTER_ORCHESTRATOR', 'Master spans source + product: product steps only'
        rows.append(row('Pipeline', n, a, t, tg, note, ws if t not in ('-', 'Source dataset') else '-'))
    for n in upstream_steps:
        rows.append(row('Pipeline', n, 'upstream', 'Source dataset', f'Source Dataset Migration: {objects["pipeline"][n]["entity"]}', 'Source step called by this product', '-'))
    for n in sorted(nbs):
        a, t, tg, note = nb_rule(n, g, 'dp')
        rows.append(row('Notebook', n, a, t, tg, note, ws if t != '-' else '-'))
    for n in sorted(dfs):
        rows.append(row('Data flow', n, 'rewrite', 'T-SQL procedure or Notebook', f'DPG-{g}/01-silver-*/3-processing or NB_{g}_{snake(n)}', 'No Mapping Data Flow in Fabric', ws))
    for n in sorted(lss):
        a, t, tg, note = map_ls(n, g, 'dp')
        rows.append(row('Linked service', n, a, t, tg, note, 'Fabric connections (tenant)' if t == 'Connection' else ws))
    for n in sorted(dss):
        d = objects['dataset'].get(n, {})
        rows.append(row('Dataset', n, 'drop', '-', '-', f"Datasets do not exist in Fabric: settings sit in the activity or in three-part names · {d.get('type')} {d.get('where', '')}"[:140], '-'))
    for n in sorted(trs):
        t = objects['trigger'].get(n, {})
        rows.append(row('Trigger', n, 'translate', 'Schedule', f'Schedule on PL_{g}_MASTER_ORCHESTRATOR', f"{t.get('type')} · {t.get('state')} · {t.get('schedule', '')}"[:120], ws))
    for n in scripts:
        rows.append(row('SQL script', n, 'translate', 'DACPAC', f'DPG-{g} (objects split per file)', f"{sqlscripts[n]['lines']} lines, creates {len(sqlscripts[n]['creates'])} objects", ws))
    for k in sqlobjs:
        v = objects['sql'][k]
        a, t, tg, note = sql_rule(k, 'TABLE' if v['kind'] == 'REF' else v['kind'], g)
        where = 'referenced only, DDL not in repo: extract from the Synapse database' if v.get('ref_only') else f"defined in {v['defined_in'][0] if v['defined_in'] else '?'}"
        label = 'SQL table (referenced)' if v['kind'] == 'REF' else f"SQL {v['kind'].lower()}"
        rows.append(row(label, k, a, t, tg, f'{note} · {where}', ws if t != '-' else '-'))
    rows = apply_decisions('dp', scope, rows)
    vl = vl_rows(pipes, ws) + [{'var': f'WH_DPG_{g}_ID', 'values': {'DEV': '<guid>', 'UAT': '<guid>', 'PRD': '<guid>'}, 'used_by': ['all'], 'ws': ws}] + \
         [{'var': f'LH_INP_SDS_{tgt_name(u)}_ID', 'values': {'DEV': '<guid>', 'UAT': '<guid>', 'PRD': '<guid>'}, 'used_by': ['shortcuts'], 'ws': ws} for u in upstream]
    entry = sorted(x for x in own | masters if x not in called or objects['pipeline'][x]['triggers'] or objects['pipeline'][x]['zone'] == 'EXT')
    return {'scope': scope, 'kind': 'dp', 'group': g, 'group_confirmed': scope in CFG['groups'], 'ws': ws, 'warehouse': f'WH_DPG_{g}', 'dbproject': f'DPG-{g}',
            'entry': entry, 'masters': sorted(masters), 'pipelines': sorted(pipes), 'shared': shared, 'upstream': upstream, 'upstream_steps': upstream_steps,
            'notebooks': sorted(nbs), 'dataflows': sorted(dfs), 'datasets': sorted(dss), 'linked_services': sorted(lss), 'triggers': sorted(trs),
            'sqlscripts': scripts, 'schemas': schemas, 'sqlobjects': sqlobjs, 'rows': rows, 'vl': vl, 'counts': dict(Counter(r['a'] for r in rows))}


sds = {e: build_sds(e) for e, z in sorted(by_entity.items()) if z['SRC']}
dp = {e: build_dp(e) for e, z in sorted(by_entity.items()) if z['DP'] or (z['EXT'] and not z['SRC'])}

# ---------------------------------------------------------------- data lineage: which data products read the data of each source dataset
# DPV1 exposed a source to products through ADLS folders (DATASOURCE=<X>), SPOT lake databases (<Prefix>_<Project>, e.g. SPOT_GEOS_WORLD)
# and replication views (rpl_<source>). A data product that names one of them in its pipelines, SQL scripts or notebooks consumes the source.
def data_tokens(d):
    toks = {}
    for n in d['pipelines']:
        if n in d['shared']:
            continue
        j = P.get(n, {})
        for t in re.findall(r'DATASOURCE=([A-Za-z0-9_]+)', json.dumps(j), re.I):
            toks[f'datasource={t.lower()}'] = f'ADLS folder DATASOURCE={t.upper()}'
        prm = (j.get('properties') or {}).get('parameters') or {}
        pre, prj = (prm.get('Prefix') or {}).get('defaultValue'), (prm.get('Project') or {}).get('defaultValue')
        if isinstance(pre, str) and isinstance(prj, str) and pre and prj:
            toks[f'{pre}_{prj}'.lower()] = f'SPOT lake database {pre}_{prj}'
    for n in d['sqlscripts']:
        for c in sqlscripts[n]['creates']:
            sch = c.split('.')[0]
            if re.match(r'^(rpl|inp|spot|src)_', sch):
                toks[sch] = f'views {sch}.* ({n})'
    toks.setdefault(f"rpl_{d['scope'].lower()}", f"replication views rpl_{d['scope'].lower()}.*")
    return toks


def texts_of(d):
    for n in set(d['pipelines']) - set(d['shared']):
        yield 'pipeline', n
    for n in d['sqlscripts']:
        yield 'sqlscript', n
    for n in d['notebooks']:
        yield 'notebook', n


for e, d in sds.items():
    d['data_tokens'] = data_tokens(d)
for e, d in sds.items():
    rx = re.compile(r'(?<![a-z0-9_])(' + '|'.join(map(re.escape, sorted(d['data_tokens'], key=len, reverse=True))) + r')(?![a-z0-9])')
    cons = {}
    for g, x in dp.items():
        for kind, n in texts_of(x):
            for t in sorted(set(rx.findall(TEXT.get((kind, n), '')))):
                cons.setdefault(g, []).append(f'{kind} {n} reads {d["data_tokens"][t]}')
    d['consumers'] = [{'dp': g, 'evidence': sorted(set(ev))[:8]} for g, ev in sorted(cons.items())]
    for g in cons:  # the product now knows this source is an input, even when no pipeline calls it
        if e not in dp[g]['upstream']:
            dp[g]['upstream'] = sorted(set(dp[g]['upstream']) | {e})
            dp[g].setdefault('upstream_data', []).append(e)
    d['downstream'] = sorted(set(d['downstream']) | set(cons))

# owner decision: a source the product does not use (scope-decisions.json, key exclude_inputs) is not an input
for g, ex in DECISIONS.get('exclude_inputs', {}).items():
    if g in dp:
        for e in ex:
            if e in dp[g]['upstream']:
                dp[g]['upstream'] = [u for u in dp[g]['upstream'] if u != e]
                dp[g]['upstream_data'] = [u for u in dp[g].get('upstream_data', []) if u != e]
            if e in sds:
                sds[e]['downstream'] = [x for x in sds[e]['downstream'] if x != g]
                sds[e]['consumers'] = [c for c in sds[e].get('consumers', []) if c['dp'] != g]

# data product => data product: a product that reads the DW / DM schemas of another product depends on it
own_schemas = {g: {s for s in d['schemas'] if re.match(r'^(dw|dm|gsp|spbi|rpt|cur|c)_', s)} for g, d in dp.items()}
schema_owner = {}
for g, ss in own_schemas.items():
    for s_ in ss:
        schema_owner.setdefault(s_, g)
# products also published their results to SPOT copy-back databases (SPOT_<X>_DWH) and CLEANSED/DATASOURCE=<X>_DWH folders
for g, d in dp.items():
    for n in d['pipelines']:
        j = P.get(n, {})
        prm = (j.get('properties') or {}).get('parameters') or {}
        dest = (prm.get('DestinationDatabase') or {}).get('defaultValue')
        pre, prj = (prm.get('Prefix') or {}).get('defaultValue'), (prm.get('Project') or {}).get('defaultValue')
        cands = [dest] + ([f'{pre}_{prj}'] if isinstance(pre, str) and isinstance(prj, str) else [])
        cands += [f'datasource={t}' for t in re.findall(r'DATASOURCE=([A-Za-z0-9_]+_(?:DWH|DM))', json.dumps(j), re.I)]
        for t in cands:
            if isinstance(t, str) and re.search(r'(dwh|_dm)', t, re.I):
                schema_owner.setdefault(t.lower(), g)
                own_schemas[g].add(t.lower())
for g, d in dp.items():
    d['read_by_products'] = []
for g, d in dp.items():
    mine = own_schemas[g]
    other = {s_: o for s_, o in schema_owner.items() if o != g and s_ not in mine}
    if not other:
        d['reads_products'] = []
        continue
    rx = re.compile(r'(?<![a-z0-9_])\[?(' + '|'.join(map(re.escape, sorted(other, key=len, reverse=True))) + r')\]?(?![a-z0-9_])')
    hits = {}
    for kind, n in texts_of(d):
        if re.search(r'COMMON|GENERIC|HELPER|TEMPLATE|TO_SPOT|OFFLOAD', n, re.I):  # shared and copy-back code name products as examples, not as inputs
            continue
        for s_ in sorted(set(rx.findall(TEXT.get((kind, n), '')))):
            hits.setdefault(other[s_], []).append(f'{kind} {n} reads {s_}')
    d['reads_products'] = [{'dp': o, 'evidence': sorted(set(ev))[:6]} for o, ev in sorted(hits.items())]
for g, d in dp.items():
    for x in d['reads_products']:
        dp[x['dp']].setdefault('read_by_products', []).append({'dp': g, 'evidence': x['evidence']})

lookup = {}
for e, d in dp.items():
    for m in d['entry'] + d['masters']:
        lookup[m.upper()] = e
for e, d in dp.items():  # any other pipeline of the product (e.g. a nested master) also resolves to it
    for m in d['pipelines']:
        if m not in d['shared']:
            lookup.setdefault(m.upper(), e)
for e, d in dp.items():
    for s in d['schemas']:
        if re.match(r'^(dw|dm)_', s):
            lookup.setdefault(s.upper(), e)


# ---------------------------------------------------------------- identification evidence + completeness check
def evidence(d):
    """Why each object is in the scope, so a reviewer can validate the boundary."""
    scope, ev = d['scope'], {}
    inscope = set(d['pipelines']) | set(d.get('upstream_steps', []))
    entries = set(d['entry'])
    for n in sorted(inscope):
        p = objects['pipeline'][n]
        if n in entries:
            how = f"trigger {', '.join(p['triggers'])}" if p['triggers'] else 'external orchestration folder' if p['zone'] == 'EXT' else 'not called by any pipeline'
            ev[n] = ('Entry point', how)
        elif p['entity'] == scope:
            ev[n] = ('Scope folder', p['folder'])
        else:
            parent = next((c for c in sorted(callers.get(n, ())) if c in inscope), None)
            ev[n] = ('Called by', parent or '?')
    for n in d['notebooks']:
        by = sorted(c for c in objects['notebook'].get(n, {}).get('called_by', []) if c in inscope)
        ev[n] = ('Called by', by[0]) if by else ('Scope folder', objects['notebook'].get(n, {}).get('folder', ''))
    for n in d['dataflows']:
        ev[n] = ('Called by', next((x for x in sorted(inscope) if n in objects['pipeline'][x]['dataflows']), '?'))
    for n in d['datasets']:
        ev[n] = ('Used by', next((x for x in sorted(inscope) if n in objects['pipeline'][x]['datasets']), '?'))
    for n in d['linked_services']:
        by = next((x for x in sorted(inscope) if n in objects['pipeline'][x]['ls']), None)
        ev[n] = ('Used by', by) if by else ('Used by', 'dataset ' + next((x for x in d['datasets'] if objects['dataset'].get(x, {}).get('ls') == n), '?'))
    for n in d['triggers']:
        ev[n] = ('Starts', ', '.join(x for x in objects['trigger'][n]['pipelines'] if x in inscope))
    for n in d['sqlscripts']:
        ev[n] = ('Scope folder', sqlscripts[n]['folder'])
    for c in d.get('catalog', []):
        ev[f"{c['schema']}.{c['table']}"] = ('Catalog table', c['from'])
    for k in d.get('sqlobjects', []):
        v = objects['sql'][k]
        ev[k] = ('Referenced by' if v.get('ref_only') else 'Defined in', (v['defined_in'] or ['?'])[0])
    for r in d['rows']:
        e = ev.get(r['v1'])
        r['by'] = f'{e[0]}: {e[1]}' if e else ''
    d['identified'] = dict(Counter(e[0] for e in ev.values()))


def candidates(d, other):
    """Objects anywhere in DPV1 whose name or folder starts with the scope name but are not in this scope."""
    tok = re.escape(d['scope'].replace('-', '_').upper())
    rx = re.compile(rf'(?<![A-Z0-9]){tok}')
    mine = {'pipeline': set(d['pipelines']) | set(d.get('upstream_steps', [])), 'notebook': set(d['notebooks']), 'sqlscript': set(d['sqlscripts']),
            'dataflow': set(d['dataflows']), 'linkedService': set(d['linked_services']), 'dataset': set(d['datasets']), 'trigger': set(d['triggers'])}
    theirs = {k: set(other.get(f, [])) for k, f in (('pipeline', 'pipelines'), ('notebook', 'notebooks'), ('sqlscript', 'sqlscripts'), ('dataflow', 'dataflows'),
                                                     ('linkedService', 'linked_services'), ('dataset', 'datasets'), ('trigger', 'triggers'))} if other else {}
    srcs = {'pipeline': P, 'notebook': NB, 'sqlscript': SQ, 'dataflow': DF, 'linkedService': LS, 'dataset': DS, 'trigger': TR}
    out = []
    for kind, items_ in srcs.items():
        for n, j in items_.items():
            hit = rx.search(n.upper().replace('-', '_')) or rx.search(folder(j).upper().replace(' ', '_'))
            if not hit or n in mine[kind]:
                continue
            owners = [o for o in OWNERS.get((kind, n), []) if o != f"{d['kind']}:{d['scope']}"]
            status = 'other service' if n in theirs.get(kind, ()) else ('in ' + ', '.join(owners[:3])) if owners else 'not included'
            dec = DECISIONS.get(d['kind'], {}).get(d['scope'], {}).get(n)
            if status == 'not included' and dec:  # the owner decided where it goes
                status = f"owner decision: {dec['action']}" + (f" ({dec['target']})" if dec.get('target') else '')
            out.append({'kind': kind, 'name': n, 'folder': folder(j)[:80], 'status': status})
    d['candidates'] = sorted(out, key=lambda x: (x['status'] != 'not included', x['kind'], x['name']))


OWNERS = defaultdict(list)  # (kind, name) -> scopes that include the object
for d in list(sds.values()) + list(dp.values()):
    tag_ = f"{d['kind']}:{d['scope']}"
    for kind, fld in (('pipeline', 'pipelines'), ('pipeline', 'upstream_steps'), ('notebook', 'notebooks'), ('sqlscript', 'sqlscripts'),
                      ('dataflow', 'dataflows'), ('linkedService', 'linked_services'), ('dataset', 'datasets'), ('trigger', 'triggers')):
        for n in d.get(fld, []):
            if tag_ not in OWNERS[(kind, n)]:
                OWNERS[(kind, n)].append(tag_)

for e, d in sds.items():
    evidence(d); candidates(d, dp.get(e))
for e, d in dp.items():
    evidence(d); candidates(d, sds.get(e))

# ---------------------------------------------------------------- estate-level statistics for the Overview
trig_targets = {t for v in objects['trigger'].values() for t in v['pipelines']}
reached = closure(trig_targets | {n for n, p in objects['pipeline'].items() if p['zone'] == 'EXT'})
FEATS = {'DISTRIBUTION': r'DISTRIBUTION\s*=', 'IDENTITY': r'\bIDENTITY\s*\(', 'TEMP_TABLE': r'#\w+', 'EXTERNAL_TABLE': r'EXTERNAL\s+TABLE', 'OPENROWSET': r'OPENROWSET'}
sql_texts = [(((j.get('properties') or {}).get('content') or {}).get('query', '') or '') for j in SQ.values()]
overview = {
    'zones': dict(Counter(p['zone'] for p in objects['pipeline'].values())),
    'activities': sum(p['acts'] for p in objects['pipeline'].values()),
    'triggers': len(TR), 'triggers_started': sum(1 for t in objects['trigger'].values() if t['state'] == 'Started'),
    'dataflows': len(DF), 'unreachable': len(objects['pipeline']) - len(reached),
    'copyback': sum(1 for n in objects['pipeline'] if re.search(r'DWH_TO_SPOT|CETAS|_SPOT\b|TO_SPOT', n, re.I)),
    'clone_test': sum(1 for n in objects['pipeline'] if re.search(r'clone|_test|test_|_tmp|temp|oneshot|backup|_bkp', n, re.I)),
    'mail_calls': sum(p['children'].count('PL_GENERIC_MAIL_NOTIFICATION') for p in objects['pipeline'].values()),
    'embedded_ddl': sum(1 for p in objects['pipeline'].values() if p['sql_kb'] >= 20),
    'env_ifchain': sum(1 for j in P.values() if 'pipeline().DataFactory' in json.dumps(j)),
    'sql_features': {k: sum(1 for q in sql_texts if re.search(r, q, re.I)) for k, r in FEATS.items()},
    'self_hosted_ls': sum(1 for l in objects['linkedService'].values() if 'SelfHosted' in (l['runtime'] or '')),
}

# keep only objects referenced by some scope, to keep the page light
used = defaultdict(set)
for d in list(sds.values()) + list(dp.values()):
    used['pipeline'] |= set(d['pipelines']) | set(d.get('upstream_steps', []))
    used['notebook'] |= set(d['notebooks']); used['dataflow'] |= set(d['dataflows']); used['dataset'] |= set(d['datasets'])
    used['linkedService'] |= set(d['linked_services']); used['trigger'] |= set(d['triggers']); used['sql'] |= set(d.get('sqlobjects', []))
    used['sqlscript'] |= set(d['sqlscripts'])
# ---------------------------------------------------------------- estate register: every object of the export is accounted for
# In a scope (sds / dp rows) | shared framework (SHARED_RULES) | platform (runtime, network, Spark, identity) | unassigned with a reason.
TEST_RX = re.compile(r'clone|_test\b|test_|^test|_tmp|temp|oneshot|backup|_bkp|_old\b|_old_|dummy|\bpoc\b|poc_|_copy\b|_examples?\b|^testing$', re.I)
SCOPE_RX = [(f"{k}:{s}", re.compile(rf'(?<![A-Z0-9]){re.escape(s.replace("-", "_").upper())}(?![A-Z0-9])')) for k, coll in (('sds', sds), ('dp', dp)) for s in coll]
covered = {k: set(v) for k, v in used.items()}
estate_rows = []


def erow(kind, n, fold, cat, a, t, tg, note):
    estate_rows.append({'kind': kind, 'name': n, 'folder': fold, 'cat': cat, 'a': a, 'v2t': t, 'v2': tg, 'n': note})


ref_by = defaultdict(set)  # linked service / dataset -> pipelines or datasets that use it
for n, p in objects['pipeline'].items():
    for x in p['ls'] + p['datasets']:
        ref_by[x].add(n)
for n, d_ in objects['dataset'].items():
    if d_.get('ls'):
        ref_by[d_['ls']].add(n)
srcs_all = {'pipeline': P, 'notebook': NB, 'dataflow': DF, 'dataset': DS, 'linkedService': LS, 'trigger': TR, 'sqlscript': SQ}
for kind, coll in srcs_all.items():
    for n, j in coll.items():
        if n in covered.get(kind, set()):
            continue
        fold = folder(j)
        hay = f'{n} {fold}'.upper().replace(' ', '_').replace('-', '_')
        match = next((s for s, rx in SCOPE_RX if rx.search(hay)), None)
        if TEST_RX.search(n):
            erow(kind, n, fold, 'unused: test, old or copy', 'drop', '-', '-', 'Name marks a test, backup or old copy')
        elif kind in ('pipeline', 'notebook', 'sqlscript') and (re.search(r'GENERIC|COMMON|HELPER|TEMPLATE|GENERATOR', n, re.I) or re.match(r'00_HELPERS|04_SHARED', fold)):
            a, t, tg = shared_rule(n)
            erow(kind, n, fold, 'shared framework', a, t, tg, 'Generic object, not called by any scope')
        elif match:
            erow(kind, n, fold, f'name matches {match}', 'review', match, f'Confirm in {match} (add to the scope rules or record a decision)', 'Not reached by the scope rules')
        elif kind == 'trigger':
            tg = objects['trigger'][n]['pipelines']
            erow(kind, n, fold, 'trigger of unassigned pipelines' if tg else 'unused: trigger with no pipeline', 'review' if tg else 'drop', 'Schedule' if tg else '-',
                 ', '.join(tg[:4]) or '-', f"{objects['trigger'][n]['state']} · {objects['trigger'][n]['schedule']}"[:120])
        elif kind in ('linkedService', 'dataset') and not ref_by.get(n):
            erow(kind, n, fold, 'unused: not referenced', 'drop', '-', '-', 'No pipeline or dataset uses it')
        elif kind == 'pipeline' and n not in called and not objects['pipeline'][n]['triggers']:
            erow(kind, n, fold, 'unused: never started', 'review', '-', 'Confirm it is obsolete (no trigger, no caller)', f"folder {fold or '(root)'}")
        elif kind in ('dataflow', 'notebook') and not any(n in p.get('dataflows' if kind == 'dataflow' else 'notebooks', []) for p in objects['pipeline'].values()):
            erow(kind, n, fold, 'unused: never started', 'review', '-', 'Confirm it is obsolete (no pipeline runs it)', f"folder {fold or '(root)'}")
        else:
            erow(kind, n, fold, 'unassigned', 'review', '-', 'Owner decision needed: assign to a scope or drop', f"used by {', '.join(sorted(ref_by.get(n, []))[:3]) or 'unassigned objects'}")

# platform objects: the Synapse workspace itself
PLATFORM = [('integrationRuntime', lambda j: ('translate', 'Gateway', 'On-premises data gateway (one per network zone)', 'Self-hosted IR') if j['properties'].get('type') == 'SelfHosted'
              else ('drop', '-', '-', 'Fabric runs pipelines and Spark without an integration runtime')),
            ('credential', lambda j: ('replace', 'Workspace identity', 'Fabric workspace identity / connection credentials', 'Synapse workspace managed identity')),
            ('sparkConfiguration', lambda j: ('translate', 'Environment', 'Fabric Environment with the same Spark properties', 'Spark configuration')),
            ('templates', None), ('managedVirtualNetwork', None)]
for kind, fn in PLATFORM:
    base = os.path.join(SRC, kind)
    if not os.path.isdir(base):
        continue
    if kind == 'templates':
        for t in sorted(os.listdir(base)):
            erow('platform', f'template {t}', kind, 'platform', 'drop', '-', '-', 'Synapse gallery template, not deployed')
        continue
    for root_, _, files_ in os.walk(base):
        for f in sorted(files_):
            p_ = os.path.join(root_, f)
            name = os.path.splitext(f)[0] if f.endswith('.json') else os.path.relpath(p_, base)
            if kind == 'templates':
                erow('platform', f'template {os.path.relpath(p_, base)}', kind, 'platform', 'drop', '-', '-', 'Synapse gallery template, not deployed')
                continue
            try:
                j = json.load(open(p_, encoding='utf-8-sig'))
            except (ValueError, UnicodeDecodeError):
                continue
            if kind == 'managedVirtualNetwork':
                if 'managedPrivateEndpoint' in root_:
                    tgt = str((j.get('properties') or {}).get('privateLinkResourceId', ''))
                    zone = re.search(r'(raw|cleansed|curated)\d*$', name, re.I) or 'synapse' in name.lower()
                    erow('platform', f'managed private endpoint {name}', kind, 'platform', 'drop' if zone else 'translate', '-' if zone else 'Managed private endpoint',
                         '-' if zone else 'Fabric managed private endpoint to the same resource', ('DPV1 storage or Synapse: not used by Fabric' if zone else mask(tgt.split('/')[-1]))[:120])
                else:
                    erow('platform', 'managed virtual network', kind, 'platform', 'replace', 'Workspace network', 'Fabric workspace outbound access / managed private endpoints', 'Synapse managed VNet')
                continue
            a, t, tg, note = fn(j)
            erow('platform', f'{kind} {name}', kind, 'platform', a, t, tg, note)
for f in ('publish_config.json',):
    if os.path.exists(os.path.join(SRC, f)):
        erow('platform', f, '', 'platform', 'drop', '-', '-', 'Fabric workspaces use Git integration instead of the Synapse publish branch')
for r in estate_rows:  # owner decisions on estate objects
    d_ = DECISIONS.get('estate', {}).get(r['name'])
    if d_:
        r['a'], r['n'] = d_['action'], f"Owner decision {d_.get('date', '')} ({d_.get('decided_by', 'owner')}): {d_.get('reason', '')}"
estate_totals = {}
for kind, coll in srcs_all.items():
    rows_k = [r for r in estate_rows if r['kind'] == kind]
    estate_totals[kind] = {'total': len(coll), 'in_scope': len(coll) - len(rows_k), 'shared': sum(r['cat'] == 'shared framework' for r in rows_k),
                           'unused': sum(r['cat'].startswith('unused') for r in rows_k), 'to_decide': sum(r['a'] == 'review' for r in rows_k)}
estate_totals['platform'] = {'total': sum(r['kind'] == 'platform' for r in estate_rows), 'in_scope': 0, 'shared': 0, 'unused': 0,
                             'to_decide': sum(r['kind'] == 'platform' and r['a'] == 'review' for r in estate_rows)}
estate = {'totals': estate_totals, 'rows': estate_rows}

slim = {k: {n: v for n, v in objects[k].items() if n in used[k]} for k in used}
for p in slim['pipeline'].values():
    p['creates'] = p['creates'][:40]; p['reads'] = p['reads'][:30]

for p in slim['pipeline'].values():
    p['activities'] = p['activities'][:25]

# ---------------------------------------------------------------- project register reconciliation
TH = REG['complexity_thresholds']


def complexity(n):
    return 'Small' if n <= TH['Small'] else 'Medium' if n <= TH['Medium'] else 'High'


projects = []
for scope in sorted(set(sds) | set(dp)):
    pipes = (set(sds[scope]['pipelines']) if scope in sds else set()) | (set(dp[scope]['pipelines']) if scope in dp else set())
    pipes -= set(sds.get(scope, {}).get('shared', [])) | set(dp.get(scope, {}).get('shared', []))
    acts = sum(objects['pipeline'][x]['acts'] for x in pipes)
    tables = sum(1 for k in dp.get(scope, {}).get('sqlobjects', []) if objects['sql'][k]['kind'] in ('TABLE', 'REF') and re.match(r'^(dw|dm)', objects['sql'][k]['schema']))
    regs = REG_BY_SCOPE.get(scope, [])
    projects.append({'scope': scope, 'has_sds': scope in sds, 'has_dp': scope in dp,
                     'detected': {'pipelines': len(pipes), 'activities': acts, 'dwh_tables': tables, 'objects': len(pipes) + acts + tables,
                                  'complexity': complexity(len(pipes) + acts + tables)},
                     'register': regs, 'status': 'registered' if regs else 'new in repo (not in register)',
                     'domain': domain_of(scope) if scope in sds else (REG['domain_codes'].get(regs[0]['domain']) if regs else None),
                     'domain_name': regs[0]['domain'] if regs else None})
missing = [r for r in REG['projects'] if reg_scope(r) not in sds and reg_scope(r) not in dp]
for r in missing:
    hits = sorted({n for n in P if r['project'].upper().replace(' ', '_') in n.upper()} | {n for n in NB if r['project'].upper() in n.upper()})[:8]
    projects.append({'scope': reg_scope(r), 'has_sds': False, 'has_dp': False, 'detected': None, 'register': [r],
                     'status': 'in register, no scope folder in repo', 'name_hits': hits, 'domain': REG['domain_codes'].get(r['domain']), 'domain_name': r['domain']})

meta = {'source_root': SRC, 'pipelines_total': len(P), 'notebooks_total': len(NB), 'sqlscripts_total': len(SQ), 'linked_services_total': len(LS),
        'sds_scopes': len(sds), 'dp_scopes': len(dp)}
meta['overview'] = overview
meta['dataflows_total'] = len(DF)
meta['register_projects'] = len(REG['projects'])
meta['new_in_repo'] = sum(p['status'].startswith('new') for p in projects)
meta['register_not_found'] = len(missing)
json.dump({'meta': meta, 'objects': slim, 'sds': sds, 'dp': dp, 'lookup': lookup, 'projects': projects, 'estate': estate},
          open(OUT, 'w', encoding='utf-8'), separators=(',', ':'), default=list)
print(json.dumps(meta))
print('new in repo:', [p['scope'] for p in projects if p['status'].startswith('new')])
print('register not found:', [(p['scope'], p.get('name_hits', [])[:3]) for p in projects if p['status'].startswith('in register')])
for name in ('GAIA',):
    print('SDS', name, sds[name]['counts'], len(sds[name]['catalog']), 'catalog tables', 'downstream', sds[name]['downstream'])
    print('DP ', name, dp[name]['counts'], 'schemas', dp[name]['schemas'], 'upstream', dp[name]['upstream'], 'masters', dp[name]['masters'])
print('lookup sample', {k: v for k, v in list(lookup.items()) if 'GAIA' in k})
print('size KB', os.path.getsize(OUT) // 1024)
