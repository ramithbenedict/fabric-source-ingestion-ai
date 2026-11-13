"""Classify every source dataset and data product of DPV1 into build scenarios, so a project picked later is built the right way.

Usage (from the repository root):
  python -I 0-shared/scripts/classify_scenarios.py              # write 5-migration-hub/scenarios.json + the two scenario catalogs, print the summary
  python -I 0-shared/scripts/classify_scenarios.py --id GAIA    # one scope with its evidence (writes nothing)

Reads migration-map.json and the DPV1 export (DPV1 is never written). Definitions of the scenarios (how each is built, tools, what is open):
2-config/migration/scenarios.json. Catalogs written to 5-migration-hub/scenario-catalog-source-dataset.md and
5-migration-hub/scenario-catalog-data-product.md (generated pages, next to the hub). refresh_hub.py runs it, so the hub page shows the current classification.

Per scope: scenario (where the logic lives), modifiers (what else the code does), evidence (counts), and for data products the code source of the
DACPAC (scripts-complete, ddl-only, pool-required, none-needed) and 'orphans': DPV1 objects named after the scope that no scope lists.
"""
import argparse, collections, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, paths, write

DB = {'Oracle', 'SqlServer', 'AzureSqlDatabase', 'MySql', 'PostgreSql', 'AzurePostgreSql', 'AmazonRedshift'}
FILES = {'Sftp', 'FileServer', 'FtpServer', 'AzureBlobStorage', 'AmazonS3', 'AzureFileStorage', 'OracleCloudStorage', 'HttpServer'}
INTERNAL = {'AzureBlobFS', 'AzureKeyVault', 'AzureTableStorage', 'AzureDataLakeStorage'}
PLATFORM_LS = re.compile(r'metabase|sqlondemand|sqlpool|^generic|keyvault|synapse', re.I)  # platform plumbing, not a source system
MODEL_NB = re.compile(r'(?:_DIM|_FACT|MODEL|_OUT_COPY|CURATED_REWIND)', re.I)
OFFLOAD_NB = re.compile(r'offload|dwh_to_spot|common_master|raw_to_clean|rawtocleans', re.I)
FRAMEWORK = re.compile(r'updatewatermark|reset_watermarks|meta_out_cetas|truncateschema|updatelandingwatermark|copy_into_dsp|views_refresher|_meta_create|metadata_|sp_meta_', re.I)


def dpv1(kind, name):
    p = os.path.join(paths()['dpv1_export_root'], kind, name + '.json')
    if not os.path.exists(p):
        return None
    try:
        return json.loads(open(p, encoding='utf-8-sig', errors='replace').read())
    except ValueError:
        return None


def walk(acts):
    for a in acts or []:
        yield a
        tp = a.get('typeProperties', {})
        for k in ('activities', 'ifTrueActivities', 'ifFalseActivities', 'defaultActivities'):
            yield from walk(tp.get(k))
        for c in tp.get('cases') or []:
            yield from walk(c.get('activities'))


def scripts_of(pipeline):
    """Text of every Script activity of a pipeline (embedded SQL)."""
    out = []
    for a in walk((pipeline or {}).get('properties', {}).get('activities')):
        for s in a.get('typeProperties', {}).get('scripts') or []:
            t = s.get('text')
            out.append(t.get('value', '') if isinstance(t, dict) else (t or ''))
    return out


def pipeline_facts(names):
    """Counts of what the scope's pipelines do, and the called procedures."""
    f, called, text = collections.Counter(), set(), []
    for n in names:
        p = dpv1('pipeline', n)
        if not p:
            continue
        for a in walk(p['properties'].get('activities')):
            t, tp = a['type'], a.get('typeProperties', {})
            if t == 'Copy':
                src, snk = tp.get('source', {}).get('type', ''), tp.get('sink', {}).get('type', '')
                f['copy'] += 1
                f['copy_to_pool'] += snk == 'SqlDWSink'
                f['copy_from_pool'] += src == 'SqlDWSource'
                if src == 'RestSource' and tp['source'].get('paginationRules'):
                    f['pagination'] += 1
                f['excel'] += 'Excel' in src
            elif t in ('SqlPoolStoredProcedure', 'SqlServerStoredProcedure'):
                f['proc_calls'] += 1
                nm = tp.get('storedProcedureName')
                nm = nm.get('value') if isinstance(nm, dict) else nm
                if nm and '@' not in str(nm):
                    called.add(re.sub(r'[\[\]]', '', str(nm)).lower())
            elif t == 'ExecuteDataFlow':
                f['dataflow'] += 1
            elif t == 'WebActivity':
                f['web'] += 1
                j = json.dumps(tp)
                f['web_sharepoint'] += bool(re.search(r'(?i)graph\.microsoft|sharepoint', j))
                f['web_secret'] += bool(re.search(r'vault\.azure|login\.microsoftonline', j))
        text.append(json.dumps(p))
    t = '\n'.join(text)
    f['isinc_refs'] = len(re.findall(r'(?i)item\(\)\.(?:isIncLoad|isFullLoad|WatermarkParam|WatermarkVal)', t))
    return f, called, t


def sql_of(S):
    """All SQL text of a scope: Script activities and SQL scripts ('' quotes undone)."""
    t = ''
    for n in S['pipelines']:
        t += '\n'.join(scripts_of(dpv1('pipeline', n))).replace("''", "'") + '\n'
    for n in S['sqlscripts']:
        s = dpv1('sqlscript', n)
        t += ((s or {}).get('properties', {}).get('content', {}) or {}).get('query', '').replace("''", "'") + '\n'
    return t


def orphans(scope, owned):
    """DPV1 objects whose name contains the scope name and that no scope lists (possible misses of the migration map)."""
    tok = re.compile(r'(?<![A-Za-z])' + r'[_\- ]?'.join(re.escape(x) for x in re.split(r'[_\- ]', scope)) + r'(?![A-Za-z])', re.I)
    root, out = paths()['dpv1_export_root'], []
    for kind in ('pipeline', 'notebook', 'trigger', 'sqlscript', 'dataflow'):
        d = os.path.join(root, kind)
        for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            n = f[:-5]
            if f.endswith('.json') and tok.search(n) and n not in owned:
                out.append(f'{kind}/{n}')
    return out


def sds(scope, S, m, owned):
    import ingestion, create_catalog_view as ccv
    O = m['objects']
    ls, conn_type, method, fmt, dialect = ingestion.source_kind(S, O)
    types = sorted({O['linkedService'].get(r['v1'], {}).get('type', '') for r in S['rows'] if r['v1t'] == 'Linked service' and r['v2t'] == 'Connection'} - {''})
    if not types:
        types = sorted({O['linkedService'].get(n, {}).get('type', '') for n in S['linked_services'] if not PLATFORM_LS.search(n)} - {''})
    kinds = sorted({('pool' if t == 'AzureSqlDW' else 'db' if t in DB else 'rest' if t == 'RestService' else 'sharepoint' if 'SharePoint' in t else 'files' if t in FILES else 'other')
                    for t in types if t not in INTERNAL})
    f, _, text = pipeline_facts(S['pipelines'])
    inc = bool(ccv.legacy_profile(S)['incremental'])
    flags_unused = bool(f['isinc_refs'] == 0 and any(re.search(r'(?i)isIncLoad|isFullLoad', json.dumps(dpv1('sqlscript', n) or {})) for n in S['sqlscripts']))
    ext = [k for k in kinds if k not in ('other', 'pool')]
    if ext:
        main = 'db' if 'db' in ext else ext[0]
        sc = {'db': 'S-DB', 'rest': 'S-REST', 'files': 'S-FILES', 'sharepoint': 'S-FILES'}[main] + ('-INC' if inc else '-FULL')
    elif kinds == ['pool'] or ('pool' in kinds):
        sc = 'S-POOL'
    else:
        sc = 'S-MANUAL'
    mods = []
    if len(ext) > 1 or ('db' in ext and (f['web_sharepoint'] or f['excel'])):
        mods.append('M-MIXED')
    if ingestion.dpv1_switch_queries(S, os.path.join(ROOT, 'none')):
        mods.append('M-SWITCH-QUERIES')
    if f['pagination']:
        mods.append('M-PAGINATION')
    if f['excel']:
        mods.append('M-EXCEL')
    if f['web_secret']:
        mods.append('M-WEB-AUTH')
    if f['web_sharepoint']:
        mods.append('M-SHAREPOINT-GRAPH')
    if S['notebooks']:
        mods.append('M-NOTEBOOK-CLEANSING')
    if S['dataflows']:
        mods.append('M-DATAFLOW')
    if 'rest' in ext and inc:
        mods.append('M-REST-INCREMENTAL')
    if flags_unused:
        mods.append('M-FLAGS-UNUSED')
    modeling = [n for n in S['notebooks'] if MODEL_NB.search(n) and not OFFLOAD_NB.search(n)]
    if len(modeling) >= 2:
        mods.append('M-MODELING-IN-SOURCE')
    ev = {'connectors': types, 'pipelines': len(S['pipelines']), 'notebooks': len(S['notebooks']), 'dataflows': len(S['dataflows']), 'triggers': len(S['triggers']),
          'catalog_tables': S['identified'].get('Catalog table', 0), 'objects': len(S['rows']), 'modeling_notebooks': modeling[:6], 'modeling_notebook_count': len(modeling)}
    return {'scenario': sc, 'modifiers': mods, 'evidence': ev, 'orphans': orphans(scope, owned)}


def dp(scope, S, m, owned):
    f, called, text = pipeline_facts(S['pipelines'])
    sql = sql_of(S)
    c = lambda rx: len(re.findall(rx, sql, re.I))
    ldw_proc = c(r'create\s+(?:or\s+alter\s+)?proc(?:edure)?\s+\[?ldw\]?\.\[?sp_create')
    ldw_view = c(r'create\s+(?:or\s+alter\s+)?view\s+\[?ldw')
    out_n = c(r'create\s+(?:or\s+alter\s+)?(?:view|proc(?:edure)?)\s+\[?out\]?\.')
    cetas = c(r'create\s+external\s+table\s+\S+\s+with[\s\S]{0,300}?\bas\s+select')
    views = c(r'create\s+(?:or\s+alter\s+)?view\s')
    pool_tables = c(r'create\s+table\s+\[?(?:dw|dm|stg)\w*\]?\.')
    defined = {re.sub(r'[\[\]]', '', x).lower() for x in re.findall(r'(?i)create\s+(?:or\s+alter\s+)?proc(?:edure)?\s+([\[\]\w\.]+)', sql)}
    pool_procs = len([d for d in defined if re.match(r'(dw|dm)', d)])
    missing = sorted(x for x in called if x not in defined and not FRAMEWORK.search(x))
    fw = sorted(x for x in called if FRAMEWORK.search(x))
    serverless = bool(re.search(r'(?i)ssp_db_build|serverless', ' '.join(S['pipelines'])))
    if S['dataflows'] and f['dataflow']:
        sc = 'D-DATAFLOW'
    elif ldw_proc or ldw_view:
        sc = 'D-LDW'
    elif len(called) - len(fw) > 2 or pool_procs:
        sc = 'D-PROC'
    elif [n for n in S['notebooks'] if MODEL_NB.search(n) and not OFFLOAD_NB.search(n)]:
        sc = 'D-SPARK'
    elif f['copy_to_pool']:
        sc = 'D-COPY'
    elif S['notebooks']:
        sc = 'D-SPARK'
    elif views or serverless:
        sc = 'D-SERVERLESS-VIEWS'
    else:
        sc = 'D-NONE'
    if missing and (not defined or len(missing) >= max(2, 0.3 * len(called))):
        dacpac = 'pool-required'
    elif pool_procs or called - set(fw):
        dacpac = 'scripts-complete'
    elif pool_tables:
        dacpac = 'ddl-only'
    else:
        dacpac = 'none-needed'
    mods = []
    if ldw_proc:
        mods.append('M-LDW-SP-CREATE')
    if ldw_view and not ldw_proc:
        mods.append('M-LDW-DIRECT-VIEWS')
    if out_n:
        mods.append('M-OUT-VIEWS')
    if cetas:
        mods.append('M-CETAS')
    if f['copy_from_pool'] or re.search(r'(?i)dwh_to_spot|sqldw_to_spot', text):
        mods.append('M-SPOT-COPY-BACK')
    if S['notebooks'] and sc != 'D-SPARK':
        mods.append('M-SPARK-NOTEBOOKS')
    if S['dataflows']:
        mods.append('M-DATAFLOW')
    if len(S['upstream']) > 2:
        mods.append('M-MANY-SOURCES')
    if pool_tables:
        mods.append('M-DDL-IN-SCRIPTS' if any(re.search(r'(?i)datamodel|ddl', x) for x in S['sqlscripts']) else 'M-DDL-EMBEDDED')
    if dacpac == 'pool-required':
        mods.append('M-POOL-ONLY-CODE')
    if fw:
        mods.append('M-FRAMEWORK-PROCS')
    n = len(S['rows'])
    ev = {'pipelines': len(S['pipelines']), 'sqlscripts': len(S['sqlscripts']), 'notebooks': len(S['notebooks']), 'dataflows': len(S['dataflows']), 'upstream': S['upstream'],
          'dw_dm_objects': len(S['sqlobjects']), 'ldw_views': ldw_view, 'ldw_view_procs': ldw_proc, 'out_objects': out_n, 'cetas': cetas, 'views_in_sql': views,
          'pool_table_ddl': pool_tables, 'procs_defined': len(defined), 'procs_called': len(called), 'procs_missing': missing[:6], 'procs_missing_count': len(missing),
          'framework_procs': fw[:4], 'copy_to_pool': f['copy_to_pool'], 'size': 'S' if n < 30 else 'M' if n < 100 else 'L', 'objects': n}
    return {'scenario': sc, 'modifiers': mods, 'dacpac_source': dacpac, 'evidence': ev, 'orphans': orphans(scope, owned)}


def classify(m, only=None):
    owned = {r['v1'] for svc in ('sds', 'dp') for S in m[svc].values() for r in S['rows']}
    out = {'sds': {}, 'dp': {}}
    for scope, S in sorted(m['sds'].items()):
        if not only or scope == only:
            out['sds'][scope] = sds(scope, S, m, owned)
    for scope, S in sorted(m['dp'].items()):
        if not only or scope == only:
            out['dp'][scope] = dp(scope, S, m, owned)
    return out


def definitions():
    return json.load(open(os.path.join(ROOT, '2-config', 'migration', 'scenarios.json'), encoding='utf-8'))


CATALOG = {'sds': '5-migration-hub/scenario-catalog-source-dataset.md', 'dp': '5-migration-hub/scenario-catalog-data-product.md'}


def write_catalogs(out, defs):
    for svc, title, who in (('sds', 'Source dataset scenarios', 'source dataset'), ('dp', 'Data product scenarios', 'data product')):
        D, by, modc = defs[svc], collections.defaultdict(list), collections.defaultdict(list)
        for k, v in out[svc].items():
            by[v['scenario']].append(k)
            for x in v['modifiers']:
                modc[x].append(k)
        L = [f'# {title}', '', f'Generated by `0-shared/scripts/classify_scenarios.py` from `2-config/migration/scenarios.json` and the DPV1 export. Do not edit. When a {who} is picked, find it in the table, then follow the scenario and its modifiers.', '',
             'Status: ready = built and reviewed in a pilot, partial = built but not verified in Fabric, gap = the build does not cover it yet.', '',
             '| Scenario | Status | Scopes | Which |', '| --- | --- | --- | --- |']
        for sid, d in D['scenarios'].items():
            ks = by.get(sid, [])
            L.append(f"| `{sid}` {d['title']} | {d['status']} | {len(ks)} | {', '.join(ks) or '-'} |")
        L += ['', '## Modifiers', '', '| Modifier | Status | Scopes | How it is handled |', '| --- | --- | --- | --- |']
        for mid, d in D['modifiers'].items():
            ks = modc.get(mid, [])
            L.append(f"| `{mid}` {d['title']} | {d['status']} | {len(ks)}: {', '.join(ks[:8])}{' ...' if len(ks) > 8 else ''} | {d['how']} |")
        if svc == 'dp':
            L += ['', '## Code source of the DACPAC', '', '| Value | Meaning | Products |', '| --- | --- | --- |']
            dc = collections.defaultdict(list)
            for k, v in out['dp'].items():
                dc[v['dacpac_source']].append(k)
            for k, t in D['dacpac_source'].items():
                L.append(f"| `{k}` | {t} | {', '.join(dc.get(k, [])) or '-'} |")
        for sid, d in D['scenarios'].items():
            L += ['', f"## `{sid}` {d['title']}", '', f"- **Status**: {d['status']}", f"- **Detected when**: {d['detect']}", '- **How it is built**:']
            L += [f'  {i}. {s}' for i, s in enumerate(d['build'], 1)]
            L += [f"- **Tools**: {', '.join('`' + t + '`' for t in d['tools']) or 'none'}", f"- **Skills**: {', '.join('`' + t + '`' for t in d['refs']) or 'none'}"]
            L += [f"- **Open**: {o}" for o in d['open']] or []
        write(os.path.join(ROOT, CATALOG[svc]), '\n'.join(L) + '\n')


def write_outputs(out, hub):
    """5-migration-hub/scenarios.json and the two scenario catalogs (called by refresh_hub.py and by main)."""
    write(os.path.join(hub, 'scenarios.json'), json.dumps(out, indent=1, sort_keys=True, ensure_ascii=False) + '\n')
    write_catalogs(out, definitions())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--id')
    a = ap.parse_args()
    P = paths()
    m = json.load(open(os.path.join(P['hub_root'], 'migration-map.json'), encoding='utf-8-sig'))
    if a.id:
        q = a.id.upper()
        out = classify(m, q)
        print(json.dumps({k: v for k, v in out.items() if v}, indent=1, ensure_ascii=False))
        return
    out = classify(m)
    write_outputs(out, P['hub_root'])
    for svc in ('sds', 'dp'):
        by = collections.defaultdict(list)
        for k, v in out[svc].items():
            by[v['scenario']].append(k)
        print(f'\n== {svc}: {len(out[svc])} scopes')
        for sc, ks in sorted(by.items()):
            print(f'  {sc:20} {len(ks):3}  {", ".join(ks)}')
        print('  modifiers:', dict(collections.Counter(x for v in out[svc].values() for x in v['modifiers']).most_common()))
    print('\norphans (objects named after a scope that no scope lists):', {k: len(v['orphans']) for s in out.values() for k, v in s.items() if v['orphans']})
    print('dacpac source:', dict(collections.Counter(v['dacpac_source'] for v in out['dp'].values())))


if __name__ == '__main__':
    main()
