"""Data validation DPV1 => DPV2 (wf-5): compares the migrated tables and views of a project, read-only on both sides.

Connections come from the VS Code MSSQL extension profiles (settings.json => mssql.connections): server, database, account and tenant.
One Microsoft Entra browser sign-in is cached and used for both servers. No password, no token in files. Only SELECT / WITH statements run.

Usage:
  python -I 0-shared/scripts/validate_data.py profiles                                   # list the MSSQL extension profiles
  python -I 0-shared/scripts/validate_data.py init --service dp --id RMA --dpv1-profile "DP Non-prod" --fabric-profile "WH_DPG_RMA (Warehouse)"
  python -I 0-shared/scripts/validate_data.py run  --service dp --id RMA [--only Actions,Risks] [--sample 50] [--dry-run]
  python -I 0-shared/scripts/validate_data.py report --service dp --id RMA              # rewrite the report from validation-results.json

Writes <project>/data-validation/: validation-config.json (editable) · validation-report.md · validation-results.json
· analysis/validation-details.md · run-history.md. Method: 1-skills/skill-data-validation/SKILL.md.
"""
import argparse, datetime, decimal, fnmatch, glob, json, os, re, struct, sys, time
from collections import Counter

try:
    import pyodbc  # noqa: F401  (user site-packages are hidden by python -I)
except ImportError:
    import site
    sys.path.append(site.getusersitepackages())

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import project_dir, paths  # noqa: E402

READ_ONLY = re.compile(r'^\s*(select|with)\b', re.I)
WRITE = re.compile(r'\b(insert|update|delete|merge|drop|alter|create|truncate|exec|execute|grant|revoke|into|deny)\b', re.I)
ICON = {'pass': '✅', 'warn': '⚠️', 'fail': '❌', 'info': 'ℹ️', 'skip': '⚪', 'accepted': '🟦'}
RANK = {'pass': 0, 'info': 0, 'accepted': 0, 'skip': 1, 'warn': 2, 'fail': 3}
LEVELS = {  # how deep the content checks go; every level runs all the tests
    'quick':    {'full_compare_max_rows': 0, 'sample_rows': 50, 'profile_distinct_max_rows': 0, 'time_budget_min': 5},          # high level, ~5-7 min (the object in progress finishes)
    'standard': {'full_compare_max_rows': 20000, 'sample_rows': 200, 'profile_distinct_max_rows': 1000000, 'time_budget_min': 20},
    'deep':     {'full_compare_max_rows': 100000, 'sample_rows': 500, 'profile_distinct_max_rows': 5000000, 'time_budget_min': 0},  # 0 = no budget
}
DEFAULT_SETTINGS = {
    'level': 'quick',
    # set by the level, can be overridden one by one in validation-config.json:
    # sample_rows: random rows compared per object · full_compare_max_rows: at or below, every row is compared
    # profile_distinct_max_rows: COUNT(DISTINCT) only up to this size · time_budget_min: after it, remaining objects get the cheap tests only
    'row_count_tolerance_pct': 0.0,    # > 0 turns a small row-count difference into a warning instead of a failure
    'trim_strings': True,              # ignore trailing spaces (char padding)
    'float_rel_tolerance': 1e-9,
    'query_timeout_s': 600,
    'max_examples': 5,
    'ignore_columns': [],              # column names ignored everywhere (e.g. load timestamps added in Fabric)
}
FRESHNESS = re.compile(r'(last_?modif|modified|updated?_?(at|on|date)|load_?(date|ts|time)|insert(ed)?_?(date|on)|created_?(date|on)|createddate)', re.I)
TYPE_FAMILY = {
    'int': 'int', 'bigint': 'int', 'smallint': 'int', 'tinyint': 'int', 'bit': 'bit',
    'decimal': 'dec', 'numeric': 'dec', 'money': 'dec', 'smallmoney': 'dec', 'float': 'float', 'real': 'float',
    'date': 'date', 'datetime': 'dt', 'datetime2': 'dt', 'smalldatetime': 'dt', 'datetimeoffset': 'dt', 'time': 'time',
    'char': 'str', 'varchar': 'str', 'nchar': 'str', 'nvarchar': 'str', 'text': 'str', 'ntext': 'str', 'sysname': 'str', 'xml': 'str',
    'binary': 'bin', 'varbinary': 'bin', 'image': 'bin', 'timestamp': 'bin', 'rowversion': 'bin', 'uniqueidentifier': 'guid',
}
# DPV1 type => Fabric type that Fabric Warehouse imposes (unsupported types): reported as info, not as a gap
FABRIC_FORCED = {('nvarchar', 'varchar'), ('nchar', 'char'), ('datetime', 'datetime2'), ('smalldatetime', 'datetime2'), ('money', 'decimal'),
                 ('smallmoney', 'decimal'), ('tinyint', 'smallint'), ('text', 'varchar'), ('ntext', 'varchar'), ('image', 'varbinary'),
                 ('datetimeoffset', 'datetime2'), ('timestamp', 'varbinary'), ('rowversion', 'varbinary'), ('nvarchar', 'nvarchar'), ('xml', 'varchar')}
COMPATIBLE = {frozenset(p) for p in [('int', 'dec'), ('int', 'bit'), ('dec', 'float'), ('int', 'float'), ('dt', 'date'), ('str', 'guid')]}


# ---------------------------------------------------------------- connections
def vscode_settings():
    for p in (os.path.expandvars(r'%APPDATA%\Code\User\settings.json'), os.path.expandvars(r'%APPDATA%\Code - Insiders\User\settings.json'),
              os.path.expanduser('~/.config/Code/User/settings.json'), os.path.expanduser('~/Library/Application Support/Code/User/settings.json')):
        if os.path.exists(p):
            t = open(p, encoding='utf-8').read()
            t = re.sub(r'^\s*//.*$', '', t, flags=re.M)
            t = re.sub(r',(\s*[}\]])', r'\1', t)
            return json.loads(t)
    sys.exit('VS Code settings.json not found: create the connection profiles in the MSSQL extension first.')


def profiles():
    return vscode_settings().get('mssql.connections', [])


def profile(name):
    for c in profiles():
        if c.get('profileName', '').lower() == name.lower():
            return c
    sys.exit(f'MSSQL profile "{name}" not found. Known profiles: ' + ', '.join(c.get('profileName', '?') for c in profiles()))


_cred = {}


def credential(email, tenant):
    key = (email, tenant)
    if key not in _cred:
        try:
            import truststore; truststore.inject_into_ssl()   # Windows certificate store (corporate TLS inspection)
        except ImportError:
            pass
        from azure.identity import AuthenticationRecord, InteractiveBrowserCredential, TokenCachePersistenceOptions
        kw = {'login_hint': email} if email else {}
        if tenant:
            kw['tenant_id'] = tenant
        # the token stays in the OS-encrypted MSAL cache; the record (account id only, no secret) in the user profile lets later runs sign in silently
        rec_path = os.path.join(os.path.expanduser('~'), '.fabric-migration-validation', f"{re.sub(r'[^\w.@-]', '_', email or 'default')}.json")
        if os.path.exists(rec_path):
            kw['authentication_record'] = AuthenticationRecord.deserialize(open(rec_path, encoding='utf-8').read())
        cred = InteractiveBrowserCredential(cache_persistence_options=TokenCachePersistenceOptions(name='fabric-migration-validation'), **kw)
        if 'authentication_record' not in kw:
            rec = cred.authenticate(scopes=['https://database.windows.net/.default'])
            os.makedirs(os.path.dirname(rec_path), exist_ok=True)
            open(rec_path, 'w', encoding='utf-8').write(rec.serialize())
        _cred[key] = cred
    return _cred[key]


def connect(side_cfg, timeout):
    import pyodbc
    p = profile(side_cfg['profile'])
    if p.get('authenticationType') not in ('AzureMFA', 'ActiveDirectoryInteractive', None):
        sys.exit(f'Profile "{p["profileName"]}" uses {p.get("authenticationType")}: only Microsoft Entra (AzureMFA) profiles are supported.')
    db = side_cfg.get('database') or p.get('database')
    if not db:
        sys.exit(f'Profile "{p["profileName"]}" has no database: set "database" for this side in validation-config.json.')
    try:
        tok = credential(p.get('email'), p.get('tenantId')).get_token('https://database.windows.net/.default').token.encode('utf-16-le')
    except Exception as e:   # sign-in cancelled or not completed in the browser within 5 minutes
        sys.exit(f'Sign-in failed for profile "{p["profileName"]}" ({p.get("email")}): {short(str(e), 200)}\n'
                 'Complete the Microsoft Entra sign-in in the browser window that opens, then run again. Nothing was queried.')
    drv = next((d for d in ('ODBC Driver 18 for SQL Server', 'ODBC Driver 17 for SQL Server') if d in pyodbc.drivers()), None)
    if not drv:
        sys.exit('No ODBC Driver 17/18 for SQL Server installed.')
    # read-only session: ApplicationIntent=ReadOnly and the ODBC read-only access mode, on top of the statement guard in q()
    cn = pyodbc.connect(f'DRIVER={{{drv}}};SERVER={p["server"]};DATABASE={db};Encrypt=yes;TrustServerCertificate=no;ApplicationIntent=ReadOnly',
                        attrs_before={1256: struct.pack(f'<I{len(tok)}s', len(tok), tok)}, autocommit=True, readonly=True)
    cn.timeout = timeout
    return cn, {'profile': p['profileName'], 'server': p['server'], 'database': db, 'env': side_cfg.get('environment') or '?'}


def read_only_sql(sql):
    """True only for one SELECT / WITH statement without a write keyword (identifiers and literals ignored)."""
    bare = re.sub(r"'[^']*'", "''", re.sub(r'\[[^\]]*\]', '[]', sql))
    return bool(READ_ONLY.match(sql)) and not WRITE.search(bare) and ';' not in bare.rstrip().rstrip(';') and '--' not in bare and '/*' not in bare


def q(cn, sql, *params):
    """The only way this script reaches a database: read-only statements, on read-only connections."""
    if not read_only_sql(sql):
        raise RuntimeError('Refused: only one read-only SELECT statement is allowed.')
    cur = cn.cursor()
    cur.execute(sql, *params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def qi(name):
    return '[' + name.replace(']', ']]') + ']'


# ---------------------------------------------------------------- metadata
def objects_in(cn, schema):
    return q(cn, "SELECT o.name, CASE WHEN o.type='V' THEN 'view' ELSE 'table' END kind FROM sys.objects o JOIN sys.schemas s ON s.schema_id=o.schema_id "
                 "WHERE s.name=? AND o.type IN ('U','V') ORDER BY o.name", schema)


def all_objects(cn, schemas):
    if not schemas:
        return []
    return q(cn, f"SELECT s.name sch, o.name, RTRIM(o.type) typ FROM sys.objects o JOIN sys.schemas s ON s.schema_id=o.schema_id "
                 f"WHERE s.name IN ({','.join('?' * len(schemas))}) AND o.type IN ('U','V','P','FN','IF','TF')", *schemas)


def columns_of(cn, schema, name):
    rows = q(cn, "SELECT c.column_id, c.name, t.name type_name, c.max_length, c.precision, c.scale, c.is_nullable, c.collation_name "
                 "FROM sys.columns c JOIN sys.types t ON t.user_type_id=c.user_type_id JOIN sys.objects o ON o.object_id=c.object_id "
                 "JOIN sys.schemas s ON s.schema_id=o.schema_id WHERE s.name=? AND o.name=? ORDER BY c.column_id", schema, name)
    out = []
    for r in rows:
        t = r['type_name'].lower()
        ln = r['max_length']
        if t in ('nvarchar', 'nchar') and ln > 0:
            ln //= 2
        out.append({'name': r['name'], 'type': t, 'length': ln, 'precision': r['precision'], 'scale': r['scale'], 'nullable': bool(r['is_nullable']),
                    'collation': r['collation_name'], 'family': TYPE_FAMILY.get(t, 'other'),
                    'is_max': ln == -1 or t in ('text', 'ntext', 'image', 'xml')})
    return out


def primary_key(cn, schema, name):
    try:
        rows = q(cn, "SELECT c.name, ic.key_ordinal FROM sys.indexes i JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id "
                     "JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id JOIN sys.objects o ON o.object_id=i.object_id "
                     "JOIN sys.schemas s ON s.schema_id=o.schema_id WHERE i.is_primary_key=1 AND s.name=? AND o.name=? ORDER BY ic.key_ordinal", schema, name)
        return [r['name'] for r in rows]
    except Exception:
        return []


def type_text(c):
    t = c['type']
    if t in ('varchar', 'char', 'nvarchar', 'nchar', 'varbinary', 'binary'):
        return f"{t}({'max' if c['length'] == -1 else c['length']})"
    if t in ('decimal', 'numeric'):
        return f"{t}({c['precision']},{c['scale']})"
    if t in ('datetime2', 'time', 'datetimeoffset'):
        return f"{t}({c['scale']})"
    return t


# ---------------------------------------------------------------- config
def vdir(service, project, *parts):
    return project_dir(service, project, 'data-validation', *parts)


def load_config(service, project):
    p = vdir(service, project, 'validation-config.json')
    if not os.path.exists(p):
        sys.exit(f'{os.path.relpath(p, paths()["deliverables_root"])} not found: run  validate_data.py init  first.')
    cfg = json.load(open(p, encoding='utf-8'))
    own = cfg.get('settings', {})
    level = own.get('level', DEFAULT_SETTINGS['level'])
    cfg['settings'] = {**DEFAULT_SETTINGS, **LEVELS[level], **own}
    return cfg


def default_layers(service, project):
    """dp: DW_<P> => OUT_SILV_<P>, DM_<P> => OUT_GOLD_<P> (schemas of the database project). sds: SPOT lake database => Lakehouse schema."""
    P = project.upper()
    if service == 'dp':
        found = set()
        for f in glob.glob(project_dir('dp', project, '3-build', 'fabric-deployment', 'database-projects', 'DPG-*', '**', '*.sql'), recursive=True):
            found |= {m.upper() for m in re.findall(r'CREATE\s+SCHEMA\s+\[?(\w+)\]?', open(f, encoding='utf-8', errors='ignore').read(), re.I)}
        silver = next((s for s in sorted(found) if s.startswith('OUT_SILV_')), f'OUT_SILV_{P}')
        gold = next((s for s in sorted(found) if s.startswith('OUT_GOLD_')), f'OUT_GOLD_{P}')
        return [{'name': 'silver (DW)', 'dpv1_schema': f'DW_{P}', 'fabric_schema': silver},
                {'name': 'gold (DM)', 'dpv1_schema': f'DM_{P}', 'fabric_schema': gold}], {}, None, None
    contract = project_dir('sds', project, 'source-dataset-contract.json')
    objects, dpv1_db, lakehouse, schema = {}, None, f'LH_SDS_{P}', 'dbo'
    if os.path.exists(contract):
        c = json.load(open(contract, encoding='utf-8'))
        lakehouse, schema = c.get('lakehouse', lakehouse), c.get('schema', schema)
        for t in c.get('tables', []):
            spot = next((a for a in t.get('dpv1_access', []) if re.match(r'^spot_\w+\.\w+$', a, re.I)), None)
            if spot:
                dpv1_db = dpv1_db or spot.split('.')[0]
                objects[spot.split('.')[1].lower()] = {'fabric': t['fabric'].split('.')[-1]}
    return [{'name': 'source tables', 'dpv1_schema': 'dbo', 'fabric_schema': schema}], objects, dpv1_db or f'spot_{project.lower()}', lakehouse


def cmd_init(a):
    p = vdir(a.service, a.id, 'validation-config.json')
    if os.path.exists(p) and not a.force:
        sys.exit(f'{p} already exists (edit it, or use --force to recreate it).')
    for n in (a.dpv1_profile, a.fabric_profile):
        profile(n)
    layers, objects, dpv1_db, fabric_db = default_layers(a.service, a.id)
    cfg = {
        'service': a.service, 'project': a.id.upper(),
        'dpv1': {'profile': a.dpv1_profile, 'database': a.dpv1_database or (dpv1_db if a.service == 'sds' else None), 'environment': a.dpv1_env},
        'fabric': {'profile': a.fabric_profile, 'database': a.fabric_database or (fabric_db if a.service == 'sds' else None), 'environment': a.fabric_env},
        'layers': layers,
        'objects': objects,
        'accepted_differences': [],
        'settings': {'level': 'quick'},
        '_help': {
            'objects': 'Per DPV1 object name (lowercase): {"fabric": "<other name>", "key": ["Col"], "skip": "<reason>", "ignore_columns": ["Col"], "where": "<filter on both sides>"}',
            'accepted_differences': '[{"object": "<glob>", "column": "<glob>", "check": "schema|rows|profile|data|keys", "reason": "<why it is accepted>"}]: the finding is kept but marked accepted',
        },
    }
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(cfg, open(p, 'w', encoding='utf-8', newline='\n'), indent=1)
    print(f'Written {p}')
    print(json.dumps({k: cfg[k] for k in ('dpv1', 'fabric', 'layers')}, indent=1))


# ---------------------------------------------------------------- comparisons
def dt_tolerance(c):
    if c['type'] == 'datetime':
        return 0.0034
    if c['type'] == 'smalldatetime':
        return 60.0
    if c['type'] in ('datetime2', 'datetimeoffset', 'time'):
        return 10 ** -(c['scale'] or 0)
    return 0.0


def norm_str(v, trim):
    return v.rstrip() if trim and isinstance(v, str) else v


def same(a, b, rule):
    """(equal, kind): kind names the difference, used to explain the cause."""
    if a is None and b is None:
        return True, ''
    if a is None or b is None:
        other = b if a is None else a
        return False, 'null vs empty' if isinstance(other, str) and other.strip() == '' else 'null vs value'
    if isinstance(a, (datetime.datetime, datetime.date)) and isinstance(b, (datetime.datetime, datetime.date)):
        a2 = a if isinstance(a, datetime.datetime) else datetime.datetime.combine(a, datetime.time())
        b2 = b if isinstance(b, datetime.datetime) else datetime.datetime.combine(b, datetime.time())
        a2, b2 = a2.replace(tzinfo=None), b2.replace(tzinfo=None)
        d = abs((a2 - b2).total_seconds())
        return (True, '') if d <= rule['dt_tol'] + 1e-9 else (False, 'precision' if d < 1 else 'value')
    if isinstance(a, bool) or isinstance(b, bool):
        try:
            return (int(a) == int(b)), 'value'
        except (TypeError, ValueError):
            return False, 'type'
    if isinstance(a, (int, float, decimal.Decimal)) and isinstance(b, (int, float, decimal.Decimal)):
        fa, fb = float(a), float(b)
        tol = max(abs(fa), abs(fb)) * rule['rel_tol'] + rule['abs_tol']
        return (True, '') if abs(fa - fb) <= tol else (False, 'precision' if abs(fa - fb) < 1 else 'value')
    if isinstance(a, (bytes, bytearray)) or isinstance(b, (bytes, bytearray)):
        ha = '0X' + bytes(a).hex().upper() if isinstance(a, (bytes, bytearray)) else str(a).upper()
        hb = '0X' + bytes(b).hex().upper() if isinstance(b, (bytes, bytearray)) else str(b).upper()
        return (ha == hb), 'value'
    sa, sb = norm_str(str(a), rule['trim']), norm_str(str(b), rule['trim'])
    if sa == sb:
        return True, ''
    if sa.strip() == sb.strip():
        return False, 'whitespace'
    if sa.casefold() == sb.casefold():
        return False, 'case'
    try:
        if float(sa) == float(sb):
            return True, ''
    except ValueError:
        pass
    return False, 'value'


def short(v, n=60):
    if isinstance(v, (bytes, bytearray)):
        v = '0x' + bytes(v).hex().upper()
    s = repr(v) if isinstance(v, str) else str(v)
    return s if len(s) <= n else s[:n - 1] + '…'


def compare_schema(c1, c2, ignore):
    f1 = {c['name'].lower(): c for c in c1 if c['name'].lower() not in ignore}
    f2 = {c['name'].lower(): c for c in c2 if c['name'].lower() not in ignore}
    diffs = []
    for n, c in f1.items():
        if n not in f2:
            diffs.append(('fail', c['name'], 'missing in Fabric', type_text(c), '-'))
    for n, c in f2.items():
        if n not in f1:
            diffs.append(('warn', c['name'], 'extra in Fabric', '-', type_text(c)))
    for n in f1.keys() & f2.keys():
        a, b = f1[n], f2[n]
        ta, tb = type_text(a), type_text(b)
        if a['type'] != b['type']:
            if (a['type'], b['type']) in FABRIC_FORCED:
                diffs.append(('info', a['name'], 'type imposed by Fabric', ta, tb))
            elif a['family'] == b['family'] or frozenset((a['family'], b['family'])) in COMPATIBLE:
                diffs.append(('warn', a['name'], 'type changed (compatible)', ta, tb))
            else:
                diffs.append(('fail', a['name'], 'type changed (incompatible)', ta, tb))
        if a['family'] == 'str' == b['family'] and a['length'] != -1 and (b['length'] != -1 and b['length'] < a['length']):
            diffs.append(('warn', a['name'], 'shorter in Fabric (truncation risk)', ta, tb))
        if a['family'] == 'dec' == b['family'] and ((b['scale'] or 0) < (a['scale'] or 0) or (b['precision'] or 0) < (a['precision'] or 0)):
            diffs.append(('warn', a['name'], 'less precision in Fabric', ta, tb))
        if a['family'] == 'dt' == b['family'] and dt_tolerance(b) > dt_tolerance(a) + 1e-9:
            diffs.append(('info', a['name'], 'coarser time precision in Fabric', ta, tb))
        if a['nullable'] and not b['nullable']:
            diffs.append(('warn', a['name'], 'NULL in DPV1, NOT NULL in Fabric (load may fail)', 'NULL', 'NOT NULL'))
    o1 = [c['name'].lower() for c in c1 if c['name'].lower() in f2]
    o2 = [c['name'].lower() for c in c2 if c['name'].lower() in f1]
    if o1 != o2:
        diffs.append(('info', '*', 'column order differs', '', ''))
    return diffs


def profile_exprs(c, alias):
    col, fam = qi(c['name']), c['family']
    e = [f"SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END) AS [{alias}_nulls]"]
    if fam in ('int', 'dec', 'float', 'bit'):
        cast = 'float' if fam == 'float' else 'decimal(38,6)'
        src = f'CAST({col} AS int)' if fam == 'bit' else col
        e += [f"MIN({src}) AS [{alias}_min]", f"MAX({src}) AS [{alias}_max]", f"SUM(CAST({src} AS {cast})) AS [{alias}_sum]"]
    elif fam in ('dt', 'date', 'time'):
        e += [f"MIN({col}) AS [{alias}_min]", f"MAX({col}) AS [{alias}_max]"]
    elif fam == 'str':
        e += [f"MIN(LEN({col})) AS [{alias}_minlen]", f"MAX(LEN({col})) AS [{alias}_maxlen]"]
    elif fam == 'bin':
        e += [f"MAX(DATALENGTH({col})) AS [{alias}_maxlen]"]
    return e


def run_profile(cn, fq, cols, where, rows, settings):
    out, chunk = {}, 40
    for i in range(0, len(cols), chunk):
        part = cols[i:i + chunk]
        exprs = []
        for j, c in enumerate(part):
            a = f'c{i + j}'
            exprs += profile_exprs(c, a)
            if not c['is_max'] and c['family'] not in ('bin',) and rows <= settings['profile_distinct_max_rows']:
                exprs.append(f"COUNT(DISTINCT {qi(c['name'])}) AS [{a}_distinct]")
        r = q(cn, f"SELECT {', '.join(exprs)} FROM {fq}{where}")[0]
        for j, c in enumerate(part):
            a = f'c{i + j}_'
            out[c['name'].lower()] = {k[len(a):]: v for k, v in r.items() if k.startswith(a)}
    return out


def accepted(cfg, obj, column, check):
    for d in cfg.get('accepted_differences', []):
        if fnmatch.fnmatch(obj.lower(), d.get('object', '*').lower()) and fnmatch.fnmatch((column or '').lower(), d.get('column', '*').lower()) \
                and fnmatch.fnmatch(check, d.get('check', '*')):
            return d.get('reason', 'accepted')
    return None


def worst(statuses):
    s = [x for x in statuses if x]
    return max(s, key=lambda x: RANK[x]) if s else 'pass'


def guess_key(c_common, pk1, pk2, pk_by_name, name, override):
    names = {c['name'].lower(): c['name'] for c in c_common}
    for cand, src in ((override, 'config'), (pk2, 'Fabric primary key'), (pk1, 'DPV1 primary key'), (pk_by_name.get(name.lower()), 'primary key of the same object in another layer')):
        if cand and all(k.lower() in names for k in cand):
            return [names[k.lower()] for k in cand], src
    for cand in ('id', f'{name.lower()}id', f'{name.lower().rstrip("s")}id', f'{name.lower()}_id'):
        if cand in names:
            return [names[cand]], 'column name (heuristic)'
    return [], ''


def fetch_rows(cn, fq, cols, where, key, keys_subset=None):
    sel = ', '.join(qi(c) for c in cols)
    if keys_subset is None:
        return q(cn, f'SELECT {sel} FROM {fq}{where}')
    rows, chunk = [], max(1, 400 // max(1, len(key)))
    for i in range(0, len(keys_subset), chunk):
        part = keys_subset[i:i + chunk]
        cond = ' OR '.join('(' + ' AND '.join(f'{qi(k)} = ?' for k in key) + ')' for _ in part)
        extra = f' AND ({where[7:]})' if where else ''
        rows += q(cn, f'SELECT {sel} FROM {fq} WHERE ({cond}){extra}', *[v for kv in part for v in kv])
    return rows


def compare_rows(r1, r2, cols, key, rules, settings, fresh=None, cutoff=None):
    """Key compare (or whole-row multiset without a key). With fresh/cutoff (Fabric newer than DPV1), a Fabric row whose fresh column is after
    the DPV1 snapshot is 'changed after the snapshot' (expected), not a mismatch."""
    res = {'compared': 0, 'matched': 0, 'mismatched_rows': 0, 'missing_in_fabric': 0, 'extra_in_fabric': 0, 'changed_after_snapshot': 0,
           'new_after_snapshot': 0, 'columns': {}, 'column_kinds': {}, 'kinds': Counter(), 'examples': []}
    lk = [k.lower() for k in key]

    def after(row):
        v = row.get(fresh) if fresh and cutoff else None
        return isinstance(v, datetime.datetime) and v.replace(tzinfo=None) > cutoff

    def kv(r):
        return tuple(norm_str(r[k], True).upper() if isinstance(r[k], str) else r[k] for k in key)
    if key:
        m1, m2 = {kv(r): r for r in r1}, {kv(r): r for r in r2}
        for k, a in m1.items():
            b = m2.get(k)
            if b is None:
                res['missing_in_fabric'] += 1
                if len(res['examples']) < settings['max_examples']:
                    res['examples'].append({'key': short(k), 'column': '(row)', 'dpv1': 'present', 'fabric': 'missing', 'kind': 'missing row'})
                continue
            res['compared'] += 1
            diffs = []
            for c in cols:
                if c.lower() in lk:
                    continue
                ok, kind = same(a[c], b[c], rules[c.lower()])
                if not ok:
                    diffs.append((c, kind))
            if not diffs:
                res['matched'] += 1
            elif after(b):
                res['changed_after_snapshot'] += 1
            else:
                res['mismatched_rows'] += 1
                for c, kind in diffs:
                    res['columns'][c] = res['columns'].get(c, 0) + 1
                    res['column_kinds'].setdefault(c, set()).add(kind)
                    res['kinds'][kind] += 1
                    if len(res['examples']) < settings['max_examples'] * 3 and not any(e['column'] == c for e in res['examples']):
                        res['examples'].append({'key': short(k), 'column': c, 'dpv1': short(a[c]), 'fabric': short(b[c]), 'kind': kind})
        extra = [r for k, r in m2.items() if k not in m1]
        res['new_after_snapshot'] = sum(1 for r in extra if after(r))
        res['extra_in_fabric'] = len(extra) - res['new_after_snapshot']
        res['column_kinds'] = {c: sorted(v) for c, v in res['column_kinds'].items()}
    else:
        def fp(r):
            out = []
            for c in cols:
                v = r[c]
                if isinstance(v, str):
                    v = norm_str(v, settings['trim_strings'])
                elif isinstance(v, datetime.datetime):
                    v = v.replace(tzinfo=None, microsecond=0)
                elif isinstance(v, (float, decimal.Decimal)):
                    v = round(float(v), 6)
                elif isinstance(v, bool):
                    v = int(v)
                elif isinstance(v, (bytes, bytearray)):
                    v = bytes(v).hex()
                out.append(v)
            return tuple(out)
        c1, c2 = Counter(fp(r) for r in r1), Counter(fp(r) for r in r2)
        res['compared'] = sum(c1.values())
        res['missing_in_fabric'] = sum((c1 - c2).values())
        res['extra_in_fabric'] = sum((c2 - c1).values())
        res['matched'] = res['compared'] - res['missing_in_fabric']
        res['mismatched_rows'] = 0
        for row in list((c1 - c2).keys())[:settings['max_examples']]:
            res['examples'].append({'key': '(no key)', 'column': '(row)', 'dpv1': short(dict(zip(cols, row)), 120), 'fabric': 'no identical row', 'kind': 'row not found'})
    res['kinds'] = dict(res['kinds'])
    return res


# ---------------------------------------------------------------- one pair
class LightMode(Exception):
    """Time budget used up: the content tests (T4, T5) of this object are not run."""


def validate_pair(cfg, cn1, cn2, layer, o1, o2, pk_by_name, light=False):
    s, name = cfg['settings'], o1['name']
    oc = cfg.get('objects', {}).get(name.lower(), {})
    label = f"{layer['dpv1_schema']}.{name}"
    r = {'layer': layer['name'], 'dpv1': label, 'dpv1_kind': o1['kind'], 'fabric': f"{layer['fabric_schema']}.{o2['name']}" if o2 else None,
         'fabric_kind': o2['kind'] if o2 else None, 'checks': {}, 'findings': []}

    def finding(sev, check, text, column=None, cause='', fix='', owner='agent'):
        acc = accepted(cfg, name, column, check)
        if acc and sev in ('warn', 'fail', 'accepted'):
            sev, text = 'accepted', f'{text} (accepted: {acc})'
        r['findings'].append({'severity': sev, 'check': check, 'object': label, 'column': column, 'finding': text, 'cause': cause, 'fix': fix, 'owner': owner})
        return sev

    if oc.get('skip'):
        r['status'] = 'skip'
        r['checks']['exists'] = {'status': 'skip', 'note': oc['skip']}
        return r
    if not o2:
        r['checks']['exists'] = {'status': finding('fail', 'exists', 'object missing in Fabric', cause='not built, not deployed or renamed',
                                                   fix='build it in the database project (or map the new name in validation-config.json objects)')}
        r['status'] = 'fail'
        return r
    r['checks']['exists'] = {'status': 'pass', 'note': f"{o1['kind']} => {o2['kind']}" if o1['kind'] != o2['kind'] else ''}
    fq1, fq2 = f"{qi(layer['dpv1_schema'])}.{qi(name)}", f"{qi(layer['fabric_schema'])}.{qi(o2['name'])}"
    where = f" WHERE {oc['where']}" if oc.get('where') else ''
    ignore = {c.lower() for c in s['ignore_columns'] + oc.get('ignore_columns', [])}

    # schema
    c1, c2 = columns_of(cn1, layer['dpv1_schema'], name), columns_of(cn2, layer['fabric_schema'], o2['name'])
    diffs = compare_schema(c1, c2, ignore)
    sts = []
    for sev, col, what, t1, t2 in diffs:
        cause = {'missing in Fabric': 'column dropped in translation', 'type changed (incompatible)': 'wrong type in the DDL'}.get(what, '')
        sts.append(finding(sev, 'schema', f'{what}: {t1} => {t2}' if t1 or t2 else what, col, cause,
                           'fix the column in the database project table or view' if sev == 'fail' else '', 'agent'))
    r['checks']['schema'] = {'status': worst(sts) if sts else 'pass', 'dpv1_columns': len(c1), 'fabric_columns': len(c2),
                             'diffs': [dict(zip(('severity', 'column', 'difference', 'dpv1', 'fabric'), d)) for d in diffs]}
    f2 = {c['name'].lower(): c for c in c2}
    common = [c for c in c1 if c['name'].lower() in f2 and c['name'].lower() not in ignore]
    rules = {}
    for c in common:
        b = f2[c['name'].lower()]
        rules[c['name'].lower()] = {'dt_tol': max(dt_tolerance(c), dt_tolerance(b)), 'rel_tol': s['float_rel_tolerance'], 'trim': s['trim_strings'],
                                    'abs_tol': 0.5 * 10 ** -min(c['scale'] or 0, b['scale'] or 0) if c['family'] == 'dec' or b['family'] == 'dec' else 0.0}

    # row count
    n1 = q(cn1, f'SELECT COUNT_BIG(*) n FROM {fq1}{where}')[0]['n']
    n2 = q(cn2, f'SELECT COUNT_BIG(*) n FROM {fq2}{where}')[0]['n']
    diff = n2 - n1
    pct = (abs(diff) / n1 * 100) if n1 else (0 if not n2 else 100)

    # column profile + freshness (which side holds the newer data)
    fr, cutoff, fresh = None, None, None
    try:
        if light:
            raise LightMode
        p1 = run_profile(cn1, fq1, common, where, n1, s)
        p2 = run_profile(cn2, fq2, [f2[c['name'].lower()] for c in common], where, n2, s)
        cands = [c['name'] for c in common if FRESHNESS.search(c['name']) and c['family'] in ('dt', 'date')]
        fresh = next((c for c in cands if re.search(r'modif|updat', c, re.I)), cands[0] if cands else None)
        if fresh:
            m1, m2 = p1[fresh.lower()].get('max'), p2[fresh.lower()].get('max')
            fr = {'column': fresh, 'dpv1_max': short(m1), 'fabric_max': short(m2)}
            if isinstance(m1, datetime.datetime) and isinstance(m2, datetime.datetime):
                fr['lag_days'] = round((m1 - m2).total_seconds() / 86400, 2)   # > 0: Fabric older; < 0: Fabric newer
                if m2 > m1:
                    cutoff = m1.replace(tzinfo=None)
        drift = cutoff is not None or diff != 0
        pd, real, coll = [], {}, []
        for c in common:
            n = c['name'].lower()
            for m, v1 in p1.get(n, {}).items():
                if m not in p2.get(n, {}):
                    continue
                v2 = p2[n][m]
                ok, _ = same(v1, v2, {**rules[n], 'abs_tol': max(rules[n]['abs_tol'], 1e-6)}) if m in ('min', 'max', 'sum') else (v1 == v2, '')
                if ok:
                    continue
                pd.append({'column': c['name'], 'metric': m, 'dpv1': short(v1), 'fabric': short(v2)})
                if m == 'distinct' and c['family'] == 'str' and not drift:
                    coll.append(c['name'])
                elif not accepted(cfg, name, c['name'], 'profile'):
                    real.setdefault(c['name'], []).append(m)
        sts = []
        if real and drift:
            sts.append(finding('warn', 'profile', f'{len(real)} column(s) profile differently ({", ".join(list(real)[:8])}{"…" if len(real) > 8 else ""})',
                               cause='expected while the row counts or the snapshot dates differ; the data check shows the real gaps', owner='manual'))
        elif real:
            sts.append(finding('fail', 'profile', 'same row count but different values: ' + '; '.join(f'{k} ({", ".join(v)})' for k, v in list(real.items())[:8]),
                               cause='values changed by the load logic or a cast', fix='compare the column expressions of the load procedure with DPV1'))
        if coll:
            sts.append(finding('warn', 'profile', f'distinct count differs only on text: {", ".join(coll)}',
                               cause='collation: DPV1 case-insensitive, Fabric case-sensitive (or trailing spaces)', owner='manual'))
        r['checks']['profile'] = {'status': worst(sts) if sts else 'pass', 'columns': len(common), 'diffs': pd, 'freshness': fr}
    except LightMode:
        r['checks']['profile'] = {'status': 'skip', 'note': 'time budget used up', 'diffs': [], 'freshness': None}
    except Exception as e:
        r['checks']['profile'] = {'status': finding('warn', 'profile', f'profile query failed: {short(str(e), 200)}', owner='manual'), 'diffs': [], 'freshness': fr}

    if diff == 0:
        st = 'pass'
    elif n2 == 0:
        st = finding('fail', 'rows', f'Fabric is empty, DPV1 has {n1:,} rows', cause='load not run or failed',
                     fix='run the process pipeline, check the loader of this object', owner='manual')
    elif cutoff is not None:
        st = finding('warn', 'rows', f'row count differs by {diff:+,} ({pct:.2f}%)',
                     cause=f'Fabric holds changes made after the DPV1 snapshot ({fresh} up to {fr["dpv1_max"]} in DPV1, {fr["fabric_max"]} in Fabric)',
                     fix='judge the gap with the data check (rows unchanged since the snapshot)', owner='manual')
    elif pct <= s['row_count_tolerance_pct']:
        st = finding('warn', 'rows', f'row count differs by {diff:+,} ({pct:.2f}%, within tolerance)', owner='manual')
    else:
        older = bool(fr and (fr.get('lag_days') or 0) > 0)
        st = finding('fail', 'rows', f'row count differs by {diff:+,} ({pct:.2f}%)',
                     cause='Fabric data is older than DPV1: reload' if older else 'filter or join of the load differs from DPV1',
                     fix='run the source dataset and process pipelines' if older else 'compare the load procedure with DPV1', owner='manual' if older else 'agent')
    r['checks']['rows'] = {'status': st, 'dpv1': n1, 'fabric': n2, 'diff': diff, 'pct': round(pct, 4)}

    # keys
    pk1, pk2 = primary_key(cn1, layer['dpv1_schema'], name), primary_key(cn2, layer['fabric_schema'], o2['name'])
    key, ksrc = guess_key(common, pk1, pk2, pk_by_name, name, oc.get('key'))
    kchk = {'key': key, 'source': ksrc, 'status': 'pass'}
    if key:
        kc = ', '.join(qi(k) for k in key)
        nn = ' OR '.join(f'{qi(k)} IS NULL' for k in key)
        sts = []
        for side, cn, fq in (('dpv1', cn1, fq1), ('fabric', cn2, fq2)):
            d = q(cn, f'SELECT COUNT_BIG(*) n FROM (SELECT {kc} FROM {fq}{where} GROUP BY {kc} HAVING COUNT_BIG(*) > 1) d')[0]['n']
            nl = q(cn, f'SELECT COUNT_BIG(*) n FROM {fq} WHERE ({nn}){(" AND " + oc["where"]) if oc.get("where") else ""}')[0]['n']
            kchk[f'{side}_duplicate_keys'], kchk[f'{side}_null_keys'] = d, nl
        if kchk['fabric_duplicate_keys'] > kchk['dpv1_duplicate_keys']:
            sts.append(finding('fail', 'keys', f"{kchk['fabric_duplicate_keys']:,} duplicate keys ({', '.join(key)}) in Fabric, {kchk['dpv1_duplicate_keys']:,} in DPV1",
                               cause='load not idempotent (primary keys are NOT ENFORCED in Fabric)', fix='delete or merge before insert in the load procedure'))
        elif kchk['dpv1_duplicate_keys']:
            sts.append(finding('info', 'keys', f"key ({', '.join(key)}) is not unique in DPV1 either ({kchk['dpv1_duplicate_keys']:,} duplicates)", owner='manual'))
        if kchk['fabric_null_keys'] > kchk['dpv1_null_keys']:
            sts.append(finding('fail', 'keys', f"{kchk['fabric_null_keys']:,} rows with a NULL key in Fabric", cause='join or cast in the load returns NULL'))
        kchk['status'] = worst(sts) if sts else 'pass'
    else:
        kchk['status'] = finding('warn', 'keys', 'no business key found: data compared as whole rows only when small',
                                 fix='add "key" for this object in validation-config.json', owner='manual')
    r['checks']['keys'] = kchk

    # data: full compare when small, random sample otherwise; like-for-like when Fabric is newer
    cols = [c['name'] for c in common]
    try:
        if light:
            raise LightMode
        if max(n1, n2) <= s['full_compare_max_rows']:
            mode = 'full'
            d1, d2 = fetch_rows(cn1, fq1, cols, where, key), fetch_rows(cn2, fq2, [f2[c.lower()]['name'] for c in cols], where, key)
            d2 = [{c: row[f2[c.lower()]['name']] for c in cols} for row in d2]
        elif key:
            mode = f"sample {s['sample_rows']}"
            kc = ', '.join(qi(k) for k in key)
            sample = [tuple(row[k] for k in key) for row in q(cn1, f"SELECT TOP ({int(s['sample_rows'])}) {kc} FROM {fq1}{where} ORDER BY NEWID()")]
            d1 = fetch_rows(cn1, fq1, cols, where, key, sample)
            d2 = fetch_rows(cn2, fq2, [f2[c.lower()]['name'] for c in cols], where, [f2[k.lower()]['name'] for k in key], sample)
            d2 = [{c: row[f2[c.lower()]['name']] for c in cols} for row in d2]
        else:
            mode, d1, d2 = 'not run (no key, too many rows for a full compare)', None, None
        if d1 is None:
            r['checks']['data'] = {'status': 'skip', 'mode': mode}
        else:
            acc_cols = [c for c in cols if accepted(cfg, name, c, 'data')]
            res = compare_rows(d1, d2, [c for c in cols if c not in acc_cols], key, rules, s, fresh if key else None, cutoff)
            res['mode'] = mode
            res['snapshot'] = fr['dpv1_max'] if cutoff else None
            res['accepted_columns'] = acc_cols
            sts = []
            if res['missing_in_fabric']:
                sts.append(finding('warn' if cutoff else 'fail', 'data', f"{res['missing_in_fabric']:,} DPV1 rows ({mode}) not found in Fabric",
                                   cause='deleted in the source after the DPV1 snapshot, or dropped by a filter or join of the load' if cutoff else
                                   'filter or join in the load drops rows', fix='check a few keys from validation-details.md in the source', owner='agent'))
            if res['extra_in_fabric'] and mode == 'full':
                sts.append(finding('warn', 'data', f"{res['extra_in_fabric']:,} Fabric rows not in DPV1 (not explained by later changes)",
                                   cause='a filter of DPV1 is missing in the load, or rows without a change date', owner='agent'))
            if res['columns']:
                cosmetic = {'whitespace', 'case', 'precision', 'null vs empty'}
                kinds = set().union(*map(set, res['column_kinds'].values()))
                top = sorted(res['columns'].items(), key=lambda x: -x[1])
                text = ', '.join(f"{c} {n:,} ({'/'.join(res['column_kinds'][c])})" for c, n in top[:8]) + ('…' if len(top) > 8 else '')
                sts.append(finding('warn' if kinds <= cosmetic else 'fail', 'data',
                                   f"{res['mismatched_rows']:,} of {res['compared']:,} rows differ{' although unchanged since the DPV1 snapshot' if cutoff else ''}: {text}",
                                   cause='type, rounding, trim or case changed' if kinds <= cosmetic else 'column expression or source of the load differs from DPV1',
                                   fix='align the column expressions of the load procedure or view with DPV1 (examples in validation-details.md)'))
            for c in acc_cols:
                finding('accepted', 'data', 'column not compared', c)
            res['status'] = worst(sts) if sts else 'pass'
            r['checks']['data'] = res
    except LightMode:
        r['checks']['data'] = {'status': 'skip', 'mode': 'not run (time budget used up)'}
    except Exception as e:
        r['checks']['data'] = {'status': finding('warn', 'data', f'data compare failed: {short(str(e), 200)}', owner='manual')}
    r['status'] = worst(ch.get('status') for ch in r['checks'].values())
    return r


# ---------------------------------------------------------------- project-level checks
def repo_objects(project):
    """Objects the database project creates (dp): what should be deployed in the Warehouse."""
    out = {}
    for f in glob.glob(project_dir('dp', project, '3-build', 'fabric-deployment', 'database-projects', 'DPG-*', '**', '*.sql'), recursive=True):
        t = open(f, encoding='utf-8', errors='ignore').read()
        for kind, sch, name in re.findall(r'CREATE\s+(?:OR\s+ALTER\s+)?(TABLE|VIEW|PROC(?:EDURE)?|FUNCTION)\s+\[?(\w+)\]?\.\[?(\w+)\]?', t, re.I):
            out[(sch.upper(), name.upper())] = {'kind': kind.upper().replace('PROCEDURE', 'PROC'), 'file': os.path.relpath(f, project_dir('dp', project))}
    return out


def cmd_run(a):
    cfg = load_config(a.service, a.id)
    s = cfg['settings']
    if a.level:
        s.update(LEVELS[a.level], level=a.level)
    if a.sample:
        s['sample_rows'] = a.sample
    only = {x.strip().lower() for x in a.only.split(',')} if a.only else None
    if a.dry_run:
        print(json.dumps({k: cfg[k] for k in ('dpv1', 'fabric', 'layers')}, indent=1))
        for side in ('dpv1', 'fabric'):
            p = profile(cfg[side]['profile'])
            print(f"{side}: {p['server']} / {cfg[side].get('database') or p.get('database')} as {p.get('email')}")
        return
    t0 = time.time()
    print('Signing in (Microsoft Entra, browser; cached after the first time)...')
    cn1, e1 = connect(cfg['dpv1'], s['query_timeout_s'])
    cn2, e2 = connect(cfg['fabric'], s['query_timeout_s'])
    env = {'dpv1': e1, 'fabric': e2}
    for side, cn in (('dpv1', cn1), ('fabric', cn2)):
        try:
            env[side]['collation'] = q(cn, "SELECT CAST(DATABASEPROPERTYEX(DB_NAME(), 'Collation') AS varchar(128)) c")[0]['c']
        except Exception:
            env[side]['collation'] = '?'
    results, inventory, findings_global = [], [], []

    def gfind(sev, check, obj, text, cause='', fix='', owner='agent'):
        findings_global.append({'severity': sev, 'check': check, 'object': obj, 'column': None, 'finding': text, 'cause': cause, 'fix': fix, 'owner': owner})

    pk_by_name = {}
    pairs = []
    for layer in cfg['layers']:
        l1, l2 = objects_in(cn1, layer['dpv1_schema']), objects_in(cn2, layer['fabric_schema'])
        by2 = {o['name'].lower(): o for o in l2}
        used = set()
        for o in l1:
            oc = cfg.get('objects', {}).get(o['name'].lower(), {})
            o2 = by2.get((oc.get('fabric') or o['name']).lower())
            if o2:
                used.add(o2['name'].lower())
            pairs.append((layer, o, o2))
        extra = [o['name'] for o in l2 if o['name'].lower() not in used]
        inventory.append({'layer': layer['name'], 'dpv1_schema': layer['dpv1_schema'], 'fabric_schema': layer['fabric_schema'],
                          'dpv1_tables': sum(o['kind'] == 'table' for o in l1), 'dpv1_views': sum(o['kind'] == 'view' for o in l1),
                          'fabric_tables': sum(o['kind'] == 'table' for o in l2), 'fabric_views': sum(o['kind'] == 'view' for o in l2),
                          'paired': len(used), 'missing_in_fabric': [o['name'] for lay, o, o2 in pairs if lay is layer and not o2
                                                                    and not cfg.get('objects', {}).get(o['name'].lower(), {}).get('skip')],
                          'extra_in_fabric': extra})
        if not l1:
            gfind('fail', 'inventory', layer['dpv1_schema'], f"no table or view found in DPV1 schema {layer['dpv1_schema']}",
                  fix='check the layer schemas in validation-config.json and the profile database', owner='manual')
        if not l2:
            gfind('fail', 'inventory', layer['fabric_schema'], f"no table or view found in Fabric schema {layer['fabric_schema']}",
                  cause='database project not deployed, or wrong profile/database', owner='manual')
        for x in extra:
            gfind('warn', 'inventory', f"{layer['fabric_schema']}.{x}", 'object in Fabric with no DPV1 counterpart', fix='map it in validation-config.json or confirm it is new', owner='manual')
        for o in l1:
            pk = primary_key(cn1, layer['dpv1_schema'], o['name'])
            if pk:
                pk_by_name.setdefault(o['name'].lower(), pk)
        for o in l2:
            pk = primary_key(cn2, layer['fabric_schema'], o['name'])
            if pk:
                pk_by_name[o['name'].lower()] = pk

    budget = s.get('time_budget_min') or 0
    print(f"Level {s['level']}: {s['sample_rows']} random rows per object, full compare up to {s['full_compare_max_rows']:,} rows"
          + (f", time budget {budget} min" if budget else ''))
    light_objects = 0
    for layer, o1, o2 in pairs:
        if only and o1['name'].lower() not in only:
            continue
        light = bool(budget) and time.time() - t0 > budget * 60   # over budget: inventory, schema, row count and keys only
        light_objects += light
        print(f"  {layer['dpv1_schema']}.{o1['name']}{' (light)' if light else ''} ...", end='', flush=True)
        try:
            r = validate_pair(cfg, cn1, cn2, layer, o1, o2, pk_by_name, light)
        except Exception as e:
            r = {'layer': layer['name'], 'dpv1': f"{layer['dpv1_schema']}.{o1['name']}", 'fabric': o2 and f"{layer['fabric_schema']}.{o2['name']}",
                 'status': 'fail', 'checks': {'error': {'status': 'fail', 'note': short(str(e), 300)}},
                 'findings': [{'severity': 'fail', 'check': 'error', 'object': f"{layer['dpv1_schema']}.{o1['name']}", 'column': None,
                               'finding': f'validation failed: {short(str(e), 300)}', 'cause': 'query error (object broken, permission, timeout)', 'fix': '', 'owner': 'manual'}]}
        print(f" {ICON[r['status']]}")
        results.append(r)

    # deployed vs repository (dp) and Fabric view health
    drift, views = {'status': 'skip'}, {'status': 'skip', 'broken': []}
    if a.service == 'dp' and not only:
        repo = repo_objects(cfg['project'])
        schemas = sorted({k[0] for k in repo})
        dep = {(r['sch'].upper(), r['name'].upper()): r['typ'] for r in all_objects(cn2, schemas)}
        missing = sorted(f'{s_}.{n}' for (s_, n) in repo if (s_, n) not in dep)
        extra = sorted(f'{s_}.{n}' for (s_, n) in dep if (s_, n) not in repo)
        drift = {'status': 'fail' if missing else ('warn' if extra else 'pass'), 'repo_objects': len(repo), 'deployed_objects': len(dep),
                 'not_deployed': missing, 'not_in_repo': extra}
        for m in missing:
            gfind('fail', 'deployment', m, 'in the database project but not in the Warehouse', cause='DACPAC not deployed since this object was added',
                  fix='run the DACPAC pipeline (ci-cd-dacpac)', owner='manual')
        for x in extra:
            gfind('warn', 'deployment', x, 'in the Warehouse but not in the database project', cause='created by hand or left from an older build',
                  fix='add it to the database project or drop it (DACPAC drop option)', owner='manual')
        broken = []
        for (s_, n), typ in dep.items():
            if typ == 'V':
                try:
                    q(cn2, f'SELECT TOP 0 * FROM {qi(s_)}.{qi(n)}')
                except Exception as e:
                    broken.append({'view': f'{s_}.{n}', 'error': short(str(e), 300)})
                    gfind('fail', 'view health', f'{s_}.{n}', f'view does not run: {short(str(e), 160)}', cause='reads a column or object that does not exist',
                          fix='fix the view in the database project and redeploy')
        views = {'status': 'fail' if broken else 'pass', 'checked': sum(1 for t in dep.values() if t == 'V'), 'broken': broken}

    out = {'service': a.service, 'project': cfg['project'], 'run_at': f'{datetime.datetime.now():%Y-%m-%d %H:%M}',
           'duration_s': round(time.time() - t0, 1), 'partial': bool(only), 'light_objects': light_objects, 'environment': env, 'settings': s, 'inventory': inventory,
           'deployment_drift': drift, 'view_health': views, 'objects': results, 'global_findings': findings_global}
    os.makedirs(vdir(a.service, a.id, 'analysis'), exist_ok=True)
    json.dump(out, open(vdir(a.service, a.id, 'validation-results.json'), 'w', encoding='utf-8', newline='\n'), indent=1, default=str)
    write_report(out)
    print(f"\nVerdict: {verdict(out)[1]}\nReport: {os.path.relpath(vdir(a.service, a.id, 'validation-report.md'), os.getcwd())}")


# ---------------------------------------------------------------- report
TESTS = [  # id, check key, category, name, what it proves
    ('T1', 'exists', '🏗️ Structure', 'Object inventory', 'every DPV1 table / view has its Fabric object'),
    ('T2', 'schema', '🏗️ Structure', 'Schema', 'same columns, compatible types, lengths, precision, nullability'),
    ('T3', 'rows', '📊 Volume', 'Row count', 'same number of rows'),
    ('T4', 'profile', '🔬 Content', 'Column profile', 'same NULLs, distinct values, min, max, sum, text lengths per column'),
    ('T5', 'data', '🔬 Content', 'Row-by-row data', 'same values, row by row (all rows, or random keys for big tables)'),
    ('T6', 'keys', '🔑 Integrity', 'Keys', 'no duplicate or NULL business key in Fabric (primary keys are NOT ENFORCED)'),
    ('T7', 'freshness', '⏱️ Freshness', 'Data freshness', 'both sides hold data up to the same change date'),
    ('T8', 'deployment', '🚀 Deployment', 'Warehouse = database project', 'every object of the repository is deployed, nothing extra'),
    ('T9', 'view health', '🚀 Deployment', 'Views run', 'every Warehouse view runs'),
]
TEST_OF = {t[1]: t for t in TESTS}
TEST_OF.update({'inventory': TEST_OF['exists'], 'error': ('T0', 'error', '⚙️ Execution', 'Execution', 'the queries of the object ran')})
NATURE = {
    'migration': ('🔴', 'Migration gap', 'the Fabric code or deployment differs from DPV1', 'fix it (agent or manual), then validate again'),
    'timing': ('🟡', 'Data timing / environment', 'the two sides hold different loads (other environment or other load date)', 'no code fix: re-run on the same environment, loaded the same day'),
    'platform': ('⚪', 'Platform behaviour', 'Fabric works differently from Synapse (collation, types)', 'check joins, filters and consumers'),
    'accepted': ('🔵', 'Accepted', 'owner decision recorded in validation-config.json', 'none'),
}


def env_differs(out):
    a, b = out['environment']['dpv1'].get('env', '?'), out['environment']['fabric'].get('env', '?')
    return a != b or '?' in (a, b)


def freshness_of(r):
    return ((r['checks'].get('profile') or {}).get('freshness')) or {}


def fresh_status(r):
    f = freshness_of(r)
    if not f:
        return 'skip'
    return 'pass' if not f.get('lag_days') else 'warn'


def all_findings(out):
    """Every finding with its test (T1-T9), category and nature, sorted for the report; gaps get IDs V001..."""
    lag = {r['dpv1']: bool(freshness_of(r).get('lag_days')) for r in out['objects']}
    diff_env = env_differs(out)
    fs = list(out['global_findings']) + [f for r in out['objects'] for f in r['findings']]
    for f in fs:
        t = TEST_OF.get(f['check'], TEST_OF['error'])
        f['test'], f['category'], f['test_name'] = t[0], t[2], t[3]
        cause = (f.get('cause') or '').lower()
        if f['severity'] == 'accepted':
            f['nature'] = 'accepted'
        elif 'collation' in cause or f['severity'] == 'info':
            f['nature'] = 'platform'
        elif f['check'] in ('rows', 'profile', 'data') and (diff_env or lag.get(f['object']) or 'snapshot' in cause or 'older' in cause):
            f['nature'] = 'timing'
        else:
            f['nature'] = 'migration'
    order = {k: i for i, k in enumerate(NATURE)}
    fs.sort(key=lambda f: (order[f['nature']], f['test'], -RANK[f['severity']], f['object']))
    n = 0
    for f in fs:
        f.pop('id', None)
        if f['severity'] in ('fail', 'warn'):
            n += 1
            f['id'] = f'V{n:03d}'
    return fs


def verdict(out):
    objs = out['objects']
    if objs and all(r['checks'].get('rows', {}).get('fabric') == 0 for r in objs if 'rows' in r['checks']):
        return 'fail', '❌ Fabric is not loaded yet: every compared object is empty'
    fs = all_findings(out)
    mig = worst([f['severity'] for f in fs if f['nature'] == 'migration'])
    rest = worst([f['severity'] for f in fs if f['nature'] in ('timing', 'platform')])
    if mig == 'fail':
        return 'fail', '❌ Not equivalent: migration gaps to fix'
    if mig == 'warn':
        return 'warn', '⚠️ Equivalent with warnings: migration warnings to review'
    if rest in ('fail', 'warn'):
        return 'warn', '⚠️ No migration gap found; data differences come from data timing / environment (confirm on the same environment)'
    return 'pass', '✅ Equivalent: DPV2 matches DPV1'


def cnt(objs, check, st):
    return sum(1 for r in objs if r['checks'].get(check, {}).get('status') in st)


def same_env_note(e):
    a, b = e['dpv1'].get('env', '?'), e['fabric'].get('env', '?')
    if a != '?' and a == b:
        return []
    return [f"> ⚠️ **Environments: DPV1 {a}, Fabric {b}.** {'They differ' if '?' not in (a, b) else 'Not confirmed'}: row counts and data differences are "
            'indicative only and are classed 🟡 *Data timing / environment*. Structure, keys, deployment and view checks are fully valid. '
            'Re-run with profiles of the same environment, loaded the same day, for a data verdict.', '']


SCORE_WEIGHTS = [  # category, checks, weight: only 🔴 migration findings lower the score
    ('🏗️ Structure', ('exists', 'schema'), 30), ('🔬 Content', ('profile', 'data'), 25), ('📊 Volume', ('rows',), 15),
    ('🔑 Integrity', ('keys',), 15), ('🚀 Deployment', ('deployment', 'view health'), 15)]
GRADES = [(95, 'A', 'Excellent'), (85, 'B', 'Good'), (70, 'C', 'Fair'), (50, 'D', 'Poor'), (0, 'E', 'Bad')]


def conclusion(out, fs):
    """Score /100 and grade, readiness for the upper environment, blocking points, conditions, confidence."""
    objs, diff_env = out['objects'], env_differs(out)
    mig = {}
    for f in fs:
        if f['nature'] == 'migration' and f['severity'] in ('fail', 'warn'):
            k = (f['object'], f['check'])
            mig[k] = worst([mig.get(k), f['severity']])
    pts = {'pass': 1.0, 'warn': 0.5, 'fail': 0.0}
    cats, total, weight = [], 0.0, 0
    for cat, checks, w in SCORE_WEIGHTS:
        vals = []
        if cat.endswith('Deployment'):
            for key, block in (('deployment', out['deployment_drift']), ('view health', out['view_health'])):
                if block.get('status') not in (None, 'skip'):
                    vals.append(pts.get(block['status'], 1.0))
        elif not (diff_env and cat.endswith(('Content', 'Volume'))):   # data tests are not assessable across environments
            for r in objs:
                for c in checks:
                    if c in r['checks'] and r['checks'][c].get('status') != 'skip':
                        vals.append(pts[mig.get((r['dpv1'], c), 'pass')])
        if vals:
            s = sum(vals) / len(vals)
            cats.append((cat, round(s * 100), w))
            total, weight = total + s * w, weight + w
        else:
            cats.append((cat, None, w))
    score = round(total / weight * 100) if weight else 0
    grade = next(g for g in GRADES if score >= g[0])
    blocking = [f for f in fs if f['nature'] == 'migration' and f['severity'] == 'fail']
    warns = [f for f in fs if f['nature'] == 'migration' and f['severity'] == 'warn']
    empty = objs and all(r['checks'].get('rows', {}).get('fabric') == 0 for r in objs if 'rows' in r['checks'])
    complete = not out['partial'] and (out['service'] == 'sds' or out['deployment_drift'].get('status') != 'skip')
    conditions = []
    if diff_env:
        conditions.append('confirm the data tests (T3-T5) with both profiles on the same environment, loaded the same day')
    if warns:
        conditions.append(f"review the {len(warns)} migration warning(s): {', '.join(f['id'] for f in warns[:10])}{'…' if len(warns) > 10 else ''}")
    if empty:
        decision = ('🔴', 'NOT READY', 'Fabric is not loaded: run the pipelines, then validate again.')
    elif blocking:
        decision = ('🔴', 'NOT READY for the upper environment', f'{len(blocking)} blocking migration gap(s) must be fixed first.')
    elif not complete:
        decision = ('⚪', 'NOT DECIDED', 'partial run: run all objects (deployment and view checks included) before deciding.')
    elif conditions:
        decision = ('🟡', 'READY WITH CONDITIONS', 'no blocking migration gap; promote once the conditions below are met.')
    else:
        decision = ('🟢', 'READY for the upper environment', 'no migration gap: structure, data, keys and deployment match DPV1.')
    confidence = 'Low (partial run)' if out['partial'] else ('Medium (different environments: data tests not assessable)' if diff_env else
                 ('Medium (large tables sampled)' if any(str(r['checks'].get('data', {}).get('mode', '')).startswith('sample') for r in objs) else 'High (same environment, full compare)'))
    assessed = f"scored on {sum(1 for x in cats if x[1] is not None)} of {len(cats)} categories"
    return {'assessed': assessed, 'score': score, 'grade': grade[1], 'grade_text': grade[2], 'categories': cats, 'decision': decision, 'blocking': blocking,
            'conditions': conditions, 'confidence': confidence}


def conclusion_md(c):
    ic, label, why = c['decision']
    L = ['## ✅ Conclusion' if ic == '🟢' else '## 🧭 Conclusion', '',
         '| Rating | Readiness for the upper environment | Confidence |', '| :---: | --- | --- |',
         f"| **{c['score']}/100 · {c['grade']} ({c['grade_text']})**<br>{c['assessed']} | {ic} **{label}**: {why} | {c['confidence']} |", '',
         '| Category | Weight | Score |', '| --- | ---: | ---: |']
    L += [f"| {cat} | {w} | {f'{s}/100' if s is not None else 'not assessable'} |" for cat, s, w in c['categories']]
    L.append('')
    if c['blocking']:
        L += ['**Must be fixed before promotion:**', '']
        L += [f"- {f['id']} · {f['test']} {f['test_name']} · `{f['object']}`{(' ' + f['column']) if f['column'] else ''}: {f['finding']} => {f['fix'] or 'see §4'} ({f['owner']})"
              for f in c['blocking'][:15]]
        if len(c['blocking']) > 15:
            L.append(f"- … and {len(c['blocking']) - 15} more in §4")
        L.append('')
    if c['conditions']:
        L += ['**Conditions:**', ''] + [f'- {x}' for x in c['conditions']] + ['']
    L += ['_Score: share of tests without a 🔴 migration finding (⚠️ counts half), weighted by category. 🟡 timing, ⚪ platform and 🔵 accepted findings do not lower it._', '']
    return L


def esc(x):
    return str(x).replace('|', '/').replace('\n', ' ')


def write_report(out):
    svc, P = out['service'], out['project']
    objs, fs = out['objects'], all_findings(out)
    vst, vtxt = verdict(out)
    n = len(objs)
    e = out['environment']
    ok = ('pass', 'info', 'accepted')
    con = conclusion(out, fs)
    path = vdir(svc, P, 'validation-report.md')
    kept = ''
    if os.path.exists(path):   # the agent's analysis (V3) survives a regeneration
        old = open(path, encoding='utf-8').read()
        if '\n## 9. Analysis' in old:
            kept = old[old.index('\n## 9. Analysis'):]
    L = [f"# 🧪 Data validation report · {P} ({'data product' if svc == 'dp' else 'source dataset'})", '',
         '| | |', '| --- | --- |',
         f"| **Readiness** | {con['decision'][0]} **{con['decision'][1]}** · rating **{con['score']}/100 ({con['grade']}, {con['grade_text']})**, {con['assessed']} |",
         f'| **Verdict** | {vtxt} |',
         f"| **Run** | {out['run_at']} · {round(out['duration_s'] / 60, 1)} min · level **{out['settings'].get('level', 'deep')}** · "
         f"{'partial run (--only)' if out['partial'] else 'all objects'}"
         f"{f' · {n_light} object(s) after the time budget: content tests not run' if (n_light := out.get('light_objects')) else ''} |",
         f"| **DPV1** | {e['dpv1'].get('env', '?')} · profile `{e['dpv1']['profile']}` · database `{e['dpv1']['database']}` |",
         f"| **Fabric** | {e['fabric'].get('env', '?')} · profile `{e['fabric']['profile']}` · database `{e['fabric']['database']}` |",
         '| **Access** | read-only on both sides (single `SELECT` statements, read-only connections) |', '']
    L += same_env_note(e) + conclusion_md(con)

    # 1. scorecard per test
    L += ['## 1. Scorecard by test', '', 'Each line counts objects (or Warehouse objects for 🚀). ✅ pass · ⚠️ warning · ❌ failure · ⚪ not run', '',
          '| Category | Test | What it proves | ✅ | ⚠️ | ❌ | ⚪ |', '| --- | --- | --- | ---: | ---: | ---: | ---: |']
    for tid, key, cat, name, what in TESTS:
        if key == 'freshness':
            st = [fresh_status(r) for r in objs]
        elif key == 'deployment':
            d = out['deployment_drift']
            if d.get('status') == 'skip':
                L.append(f'| {cat} | **{tid}** {name} | {what} | - | - | - | run all objects |')
                continue
            L.append(f"| {cat} | **{tid}** {name} | {what} | {d['deployed_objects'] - len(d['not_in_repo'])} | {len(d['not_in_repo'])} | {len(d['not_deployed'])} | 0 |")
            continue
        elif key == 'view health':
            v = out['view_health']
            if v.get('status') == 'skip':
                L.append(f'| {cat} | **{tid}** {name} | {what} | - | - | - | run all objects |')
                continue
            L.append(f"| {cat} | **{tid}** {name} | {what} | {v['checked'] - len(v['broken'])} | 0 | {len(v['broken'])} | 0 |")
            continue
        else:
            st = [r['checks'].get(key, {}).get('status', 'skip') for r in objs]
        L.append(f"| {cat} | **{tid}** {name} | {what} | {sum(s in ok for s in st)} | {sum(s == 'warn' for s in st)} | {sum(s == 'fail' for s in st)} | {sum(s == 'skip' for s in st)} |")

    # 2. findings by nature
    L += ['', '## 2. Findings by nature', '', 'Every finding is classed by what causes it, so the real migration gaps stand apart.', '',
          '| Nature | Meaning | ❌ | ⚠️ | Other | What to do | Section |', '| --- | --- | ---: | ---: | ---: | --- | --- |']
    for k, (ic, name, meaning, todo) in NATURE.items():
        sub = [f for f in fs if f['nature'] == k]
        sec = {'migration': '[§4](#4-migration-gaps-to-fix)', 'timing': '[§5](#5-data-timing--environment-differences)',
               'platform': '[§6](#6-platform-behaviour-and-accepted-differences)', 'accepted': '[§6](#6-platform-behaviour-and-accepted-differences)'}[k]
        L.append(f"| {ic} **{name}** | {meaning} | {sum(f['severity'] == 'fail' for f in sub)} | {sum(f['severity'] == 'warn' for f in sub)} "
                 f"| {sum(f['severity'] not in ('fail', 'warn') for f in sub)} | {todo} | {sec} |")

    # 3. per object
    L += ['', '## 3. Results per object', '',
          'Columns follow the test categories: 🏗️ T1-T2 · 📊 T3 · 🔬 T4-T5 · 🔑 T6 · ⏱️ T7.', '']
    for layer in dict.fromkeys(r['layer'] for r in objs):
        L += [f'### {layer}', '', '| Object (DPV1 => Fabric) | 🏗️ Structure | 📊 Rows DPV1 | 📊 Rows Fabric | 📊 Δ | 🔬 Profile | 🔬 Data | 🔑 Keys | ⏱️ Freshness | Status |',
              '| --- | :---: | ---: | ---: | ---: | :---: | --- | :---: | --- | :---: |']
        for r in (r for r in objs if r['layer'] == layer):
            c = r['checks']
            ic = lambda k: ICON[c[k]['status']] if k in c else '⚪'
            struct = ICON[worst([c.get('exists', {}).get('status'), c.get('schema', {}).get('status')])]
            rows = c.get('rows')
            fr = freshness_of(r)
            frt = '-' if not fr else ('same' if not fr.get('lag_days') else (f"Fabric newer by {-fr['lag_days']:.0f} d" if fr['lag_days'] < 0 else f"Fabric older by {fr['lag_days']:.0f} d"))
            data = c.get('data', {})
            dt = ic('data') + (f" {data['matched']:,}/{data['compared']:,} ({data['mode']})" if 'compared' in data else f" {data.get('mode', '')}") \
                + (f" +{data.get('changed_after_snapshot', 0):,} changed later" if data.get('snapshot') else '')
            name = f"`{r['dpv1']}` => `{r.get('fabric') or 'missing'}`"
            if rows:
                L.append(f"| {name} | {struct} | {rows['dpv1']:,} | {rows['fabric']:,} | {rows['diff']:+,} | {ic('profile')} | {dt} | {ic('keys')} | {frt} | {ICON[r['status']]} |")
            else:
                L.append(f"| {name} | {struct} | - | - | - | {ic('profile')} | {dt} | {ic('keys')} | {frt} | {ICON[r['status']]} |")
        L.append('')

    def table(sub, with_fix=True):
        if not sub:
            return ['None.', '']
        h = ['| ID | | Test | Object | Column | Finding | Likely cause |' + (' Fix | Owner |' if with_fix else ''),
             '| --- | :---: | --- | --- | --- | --- | --- |' + (' --- | --- |' if with_fix else '')]
        for f in sub:
            h.append(f"| {f.get('id', '-')} | {ICON[f['severity']]} | {f['test']} {f['test_name']} | `{f['object']}` | {f['column'] or '-'} | {esc(f['finding'])} "
                     f"| {esc(f['cause'] or '-')} |" + (f" {esc(f['fix'] or '-')} | {f['owner']} |" if with_fix else ''))
        return h + ['']

    # 4. migration gaps, grouped by category
    mig = [f for f in fs if f['nature'] == 'migration' and f['severity'] in ('fail', 'warn')]
    L += ['## 4. Migration gaps to fix', '', 'Owner: **agent** = a code fix in this repository (m-bug-fixer) · **manual** = a run, a deployment, an access or an owner decision.', '']
    if not mig:
        L += ['✅ None.', '']
    for cat in dict.fromkeys(t[2] for t in TESTS + [TEST_OF['error']]):
        sub = [f for f in mig if f['category'] == cat]
        if sub:
            L += [f"### {cat} ({sum(f['severity'] == 'fail' for f in sub)} ❌ · {sum(f['severity'] == 'warn' for f in sub)} ⚠️)", ''] + table(sub)

    # 5. timing / environment
    tim = [f for f in fs if f['nature'] == 'timing' and f['severity'] in ('fail', 'warn')]
    L += ['## 5. Data timing / environment differences', '',
          'Expected while the two sides hold different loads. Not counted as migration gaps; confirm them with a run on the same environment.', '']
    L += table(tim, with_fix=False)

    # 6. platform + accepted + info
    plat = [f for f in fs if f['nature'] == 'platform' and f['severity'] != 'info']
    acc = [f for f in fs if f['nature'] == 'accepted']
    info = Counter(re.sub(r':.*', '', f['finding']) for f in fs if f['severity'] == 'info')
    L += ['## 6. Platform behaviour and accepted differences', '']
    if plat:
        L += ['**⚪ Platform behaviour**', ''] + table(plat, with_fix=False)
    if acc:
        L += ['**🔵 Accepted (owner decisions)**', '', '| Test | Object | Column | Finding |', '| --- | --- | --- | --- |']
        L += [f"| {f['test']} {f['test_name']} | `{f['object']}` | {f['column'] or '-'} | {esc(re.sub(r' [(]accepted: .*[)]$', '', f['finding']))} |" for f in acc]
        reasons = dict.fromkeys(m.group(1) for f in acc for m in [re.search(r'[(]accepted: (.*)[)]$', f['finding'])] if m)
        L += [''] + [f'Reason: {x}' for x in reasons] + ['']
    if info:
        L += ['**ℹ️ Expected by design** (details in [analysis/validation-details.md](analysis/validation-details.md))', '',
              '| Difference | Occurrences |', '| --- | ---: |'] + [f'| {k} | {v} |' for k, v in info.most_common()] + ['']
    if not (plat or acc or info):
        L += ['None.', '']

    # 7. improvements, 8. environment
    L += ['## 7. Improvements', ''] + [f'{i}. {x}' for i, x in enumerate(improvements(out, fs), 1)] + ['']
    L += ['## 8. Environment and re-run', '', '| Side | Environment | Profile | Server | Database | Collation |', '| --- | --- | --- | --- | --- | --- |']
    for side in ('dpv1', 'fabric'):
        L.append(f"| {side.upper()} | {e[side].get('env', '?')} | {e[side]['profile']} | `{e[side]['server']}` | {e[side]['database']} | {e[side].get('collation', '?')} |")
    L += ['', f"- Re-run: `python -I 0-shared/scripts/validate_data.py run --service {svc} --id {P}` (one object: `--only <name>`)",
          '- Details per object: [analysis/validation-details.md](analysis/validation-details.md) · history: [run-history.md](run-history.md)',
          '- Machine-readable: `validation-results.json` · settings, keys and accepted differences: `validation-config.json`', '']
    text = '\n'.join(L) + (kept if kept else '\n## 9. Analysis\n\n_Written by the m-data-validator after reviewing the gaps (wf-5 V3)._\n')
    open(path, 'w', encoding='utf-8', newline='\n').write(text)
    write_details(out, fs)
    hist = vdir(svc, P, 'run-history.md')
    if not os.path.exists(hist):
        open(hist, 'w', encoding='utf-8', newline='\n').write('# Data validation runs\n\n| Run | Scope | Environments | Rating | Readiness | Objects | 🔴 migration ❌ | 🔴 migration ⚠️ | 🟡 timing | Rows equal | Data passed |\n'
                                                               '| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |\n')
    line = (f"| {out['run_at']} | {'partial' if out['partial'] else 'all'} | {e['dpv1'].get('env', '?')} => {e['fabric'].get('env', '?')} | {con['score']} ({con['grade']}) | {con['decision'][0]} {con['decision'][1]} | {n} "
            f"| {sum(f['nature'] == 'migration' and f['severity'] == 'fail' for f in fs)} | {sum(f['nature'] == 'migration' and f['severity'] == 'warn' for f in fs)} "
            f"| {sum(f['nature'] == 'timing' and f['severity'] in ('fail', 'warn') for f in fs)} | {cnt(objs, 'rows', ok)} | {cnt(objs, 'data', ok)} |\n")
    if line.split(' | ')[0] not in open(hist, encoding='utf-8').read():   # one line per run, also when the report is regenerated
        open(hist, 'a', encoding='utf-8', newline='\n').write(line)


def improvements(out, fs):
    objs, imp = out['objects'], []
    e = out['environment']
    if e['dpv1'].get('collation', '').upper().find('_CI_') >= 0 and 'BIN' in e['fabric'].get('collation', '').upper():
        imp.append(f"Collation: DPV1 is case-insensitive ({e['dpv1']['collation']}), Fabric is case-sensitive ({e['fabric']['collation']}). "
                   "Joins and filters on text can return fewer rows; check `WHERE`/`JOIN` on text columns, or create the Warehouse with a case-insensitive collation.")
    lags = [((r['checks'].get('profile') or {}).get('freshness') or {}).get('lag_days') for r in objs]
    newer, older = sum(1 for x in lags if x and x < 0), sum(1 for x in lags if x and x > 0)
    if newer or older:
        imp.append(f"Data dates differ: {newer} object(s) newer in Fabric, {older} older in Fabric. Compare the same environment, with the DPV1 and Fabric loads "
                   "run the same day, so that row-count and data differences only show logic gaps.")
    nokey = [r['dpv1'] for r in objs if r['checks'].get('keys', {}).get('status') == 'warn' and not r['checks']['keys'].get('key')]
    if nokey:
        imp.append(f"No business key for {len(nokey)} object(s) ({', '.join(nokey[:5])}{'…' if len(nokey) > 5 else ''}): add `key` in validation-config.json to compare rows by key.")
    big = [r['dpv1'] for r in objs if str(r['checks'].get('data', {}).get('mode', '')).startswith('sample')]
    if big:
        imp.append(f"{len(big)} object(s) were sampled ({out['settings']['sample_rows']} rows). Raise `sample_rows` or `full_compare_max_rows` for a stronger check before go-live.")
    forced = sum(1 for f in fs if f['severity'] == 'info' and 'imposed by Fabric' in f['finding'])
    if forced:
        imp.append(f"{forced} column type(s) changed because Fabric Warehouse does not support the DPV1 type (nvarchar, datetime, money...). "
                   "Check that consumers (Power BI, Dataiku) accept the new types.")
    if any(f['check'] == 'keys' and f['severity'] == 'fail' for f in fs):
        imp.append('Primary keys are NOT ENFORCED in Fabric: add a duplicate-key check to the process pipeline after each load.')
    if out['deployment_drift'].get('status') == 'skip' and out['service'] == 'dp':
        imp.append('Run the full validation (without --only) to check that the Warehouse matches the database project and that every view runs.')
    imp.append('Schedule this validation after each DEV/UAT load until go-live and compare run-history.md between runs.')
    return imp


def write_details(out, fs):
    L = [f"# 🔎 Validation details · {out['project']}", '', f"Run {out['run_at']}. Summary: [../validation-report.md](../validation-report.md). "
         'Tests: 🏗️ T2 Schema · 🔑 T6 Keys · ⏱️ T7 Freshness · 🔬 T4 Column profile · 🔬 T5 Row-by-row data.', '']
    for r in out['objects']:
        c = r['checks']
        L += [f"## `{r['dpv1']}` => `{r.get('fabric') or 'missing'}` {ICON[r['status']]}", '']
        sch = c.get('schema')
        if sch:
            L.append(f"**🏗️ T2 Schema** · columns: DPV1 {sch['dpv1_columns']}, Fabric {sch['fabric_columns']}.")
            if sch['diffs']:
                L += ['', '| | Column | Difference | DPV1 | Fabric |', '| :---: | --- | --- | --- | --- |']
                L += [f"| {ICON[d['severity']]} | {d['column']} | {d['difference']} | {d['dpv1']} | {d['fabric']} |" for d in sch['diffs']]
        k = c.get('keys')
        if k and k.get('key'):
            L += ['', f"**🔑 T6 Keys** · key `{', '.join(k['key'])}` ({k['source']}): duplicates DPV1 {k['dpv1_duplicate_keys']:,} / Fabric {k['fabric_duplicate_keys']:,}; "
                      f"NULL keys DPV1 {k['dpv1_null_keys']:,} / Fabric {k['fabric_null_keys']:,}."]
        p = c.get('profile') or {}
        if p.get('freshness'):
            f = p['freshness']
            L += ['', f"**⏱️ T7 Freshness** · `{f['column']}`: DPV1 max {f['dpv1_max']}, Fabric max {f['fabric_max']}" + (f", lag {f['lag_days']} days." if f.get('lag_days') else '.')]
        if p.get('diffs'):
            L += ['', '**🔬 T4 Column profile** · differences:', '', '| Column | Metric | DPV1 | Fabric |', '| --- | --- | --- | --- |'] + [f"| {d['column']} | {d['metric']} | {d['dpv1']} | {d['fabric']} |" for d in p['diffs']]
        d = c.get('data') or {}
        if 'compared' in d:
            L += ['', f"**🔬 T5 Row-by-row data** ({d['mode']}): {d['compared']:,} compared, {d['matched']:,} identical, {d['mismatched_rows']:,} different, "
                      f"{d['missing_in_fabric']:,} missing in Fabric, {d['extra_in_fabric']:,} extra in Fabric"
                      + (f"; DPV1 snapshot {d['snapshot']}: {d.get('changed_after_snapshot', 0):,} rows changed and {d.get('new_after_snapshot', 0):,} rows created "
                         f"after it in Fabric (expected, not counted as gaps)" if d.get('snapshot') else '') + '.']
            if d.get('accepted_columns'):
                L.append(f"Not compared (accepted differences): {', '.join(d['accepted_columns'])}.")
            if d['examples']:
                L += ['', '| Key | Column | DPV1 | Fabric | Kind |', '| --- | --- | --- | --- | --- |']
                L += [f"| {x['key']} | {x['column']} | {x['dpv1'].replace('|', '/')} | {x['fabric'].replace('|', '/')} | {x['kind']} |" for x in d['examples']]
        elif d:
            L += ['', f"Data: {d.get('mode', '')} {d.get('note', '')}"]
        if 'error' in c:
            L += ['', f"Error: {c['error']['note']}"]
        L.append('')
    d = out['deployment_drift']
    if d.get('status') != 'skip':
        L += ['## 🚀 T8 Warehouse vs database project · T9 Views', '', f"Repository {d['repo_objects']} objects, Warehouse {d['deployed_objects']}.", '',
              f"- Not deployed: {', '.join(d['not_deployed']) or 'none'}", f"- Not in the database project: {', '.join(d['not_in_repo']) or 'none'}", '']
        if out['view_health']['broken']:
            L += ['Broken views:', ''] + [f"- `{b['view']}`: {b['error']}" for b in out['view_health']['broken']] + ['']
    open(vdir(out['service'], out['project'], 'analysis', 'validation-details.md'), 'w', encoding='utf-8', newline='\n').write('\n'.join(L))


def cmd_report(a):
    p = vdir(a.service, a.id, 'validation-results.json')
    if not os.path.exists(p):
        sys.exit('No validation-results.json: run  validate_data.py run  first.')
    out = json.load(open(p, encoding='utf-8'))
    cfg = load_config(a.service, a.id)
    for side in ('dpv1', 'fabric'):   # environment labels set or corrected in the config after the run
        if cfg[side].get('environment'):
            out['environment'][side]['env'] = cfg[side]['environment']
    for f in out['global_findings'] + [f for r in out['objects'] for f in r['findings']]:   # differences accepted after the run
        reason = accepted(cfg, f['object'].split('.')[-1], f.get('column'), f['check'])
        if reason and f['severity'] in ('warn', 'fail'):
            f['severity'], f['finding'] = 'accepted', f"{f['finding']} (accepted: {reason})"
    write_report(out)
    print(verdict(out)[1])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('profiles')
    i, r, rp = sub.add_parser('init'), sub.add_parser('run'), sub.add_parser('report')
    for x in (i, r, rp):
        x.add_argument('--service', choices=['sds', 'dp'], required=True)
        x.add_argument('--id', required=True)
    i.add_argument('--dpv1-profile', required=True); i.add_argument('--fabric-profile', required=True)
    i.add_argument('--dpv1-database'); i.add_argument('--fabric-database'); i.add_argument('--force', action='store_true')
    i.add_argument('--dpv1-env', help='environment the DPV1 profile reads, e.g. UAT'); i.add_argument('--fabric-env', help='environment the Fabric profile reads, e.g. DEV')
    r.add_argument('--only', help='comma-separated object names'); r.add_argument('--sample', type=int); r.add_argument('--dry-run', action='store_true')
    r.add_argument('--level', choices=list(LEVELS), help='quick (default, ~5-7 min, high level) · standard · deep (every row up to 100 000 rows, slow)')
    a = ap.parse_args()
    if a.cmd == 'profiles':
        for c in profiles():
            print(f"{c.get('profileName', '?'):45} {c.get('server', ''):95} {c.get('database', '') or '-':20} {c.get('authenticationType', '')}")
    elif a.cmd == 'init':
        cmd_init(a)
    elif a.cmd == 'run':
        cmd_run(a)
    else:
        cmd_report(a)


if __name__ == '__main__':
    main()
