"""wf-2 S1-S4: generate the Fabric items of a source dataset (Fabric Git format), with the ingestion method DPV1 uses.

Usage (from the repository root):
  python -I 0-shared/scripts/build_source_dataset.py --id GEOS [--stage S1|S2|S3|S4|all]

  S1  LH_SDS_<SRC>.Lakehouse
  S2  1-SOURCE_TO_RAW/PL_<SRC>_SOURCE_TO_RAW      Lookup on the catalog view, one Copy per row:
                                                  structured => parquet straight to Files/raw; semi-structured => Files/landing as delivered
  S3  2-RAW_TO_DELTA/NB_<SRC>_RAW_TO_DELTA        one notebook per source (only when DPV1 used a notebook), all tables in one session
      2-RAW_TO_DELTA/PL_<SRC>_RAW_TO_DELTA        runs it (or Copies raw parquet to tables when DPV1 had no notebook)
  S4  0-ORCHESTRATION/PL_<SRC>_MASTER_ORCHESTRATOR  S2 => S3 with the same run folder, then the watermark update (incremental)
The methods (structured / semi-structured, full / incremental) are in ingestion.py; design in
3-workflows/wf-2-migration-source-dataset/ingestion-design.md.
Output: 4-migration-project-deliverables/source-dataset/<src>/3-build/fabric-deployment/<WORKSPACE>/<SRC>/… and 3-build/build-notes/<stage>.md

Identifiers follow the Fabric-AI-DEV-REPO known issues:
  - same-workspace references (notebookId, default lakehouse, ExecutePipeline) use the item's .platform logicalId and the zero workspace GUID
  - Lakehouse and Warehouse connections (artifactId, endpoint, workspaceId) are VL_MAIN expressions resolved at run time, never ids written in the
    file: a pipeline then depends on no other item at sync time, so items deploy together in one Git sync (deployment-design.md)
  - connections and the catalog view name are read from VL_MAIN at run time
"""
import argparse, glob, json, os, re, sys, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, paths, load_map, resolve_scope, write, write_note, track_event, project_dir, deploy_dir, notes_path, work_path, read_json, exists, vl_name
from create_variable_library import catalog_view, cfg
import ingestion

ZERO = '00000000-0000-0000-0000-000000000000'
PLATFORM = 'https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json'
expr = lambda v: {'value': v, 'type': 'Expression'}
dump = lambda o: json.dumps(o, indent=2, ensure_ascii=False) + '\n'


def logical_id(folder):
    p = os.path.join(folder, '.platform')
    try:
        lid = read_json(p)['config']['logicalId']
        if lid and lid != ZERO:
            return lid
    except (OSError, ValueError, KeyError):
        pass
    # not in the build yet: the item of the deployment repo keeps its id (a new id would make Git sync see another item), else a stable id from the item's path (a rebuild gives the same one)
    parts = os.path.normpath(folder).split(os.sep)
    if 'fabric-deployment' in parts and '3-build' in parts:
        i, rel = parts.index('fabric-deployment'), '/'.join(parts[parts.index('fabric-deployment') + 1:])
        service, project = {'source-dataset': 'sds', 'data-product': 'dp'}.get(parts[parts.index('3-build') - 2]), parts[parts.index('3-build') - 1]
        try:
            import project_inputs
            repo = project_inputs.load(service, project).get('deployment_repo')
            lid = read_json(os.path.join(repo, *rel.split('/'), '.platform'))['config']['logicalId'] if repo else None
            if lid and lid != ZERO:
                return lid
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f'{project}/{rel}'))
    return str(uuid.uuid4())


def platform(folder, typ, name, description):
    write(os.path.join(folder, '.platform'), dump({'$schema': PLATFORM, 'metadata': {'type': typ, 'displayName': name, 'description': description},
                                                   'config': {'version': '2.0', 'logicalId': logical_id(folder)}}))
    return read_json(os.path.join(folder, '.platform'))['config']['logicalId']


class Ctx:
    def __init__(self, sid):
        m = load_map()
        self.scope, _ = resolve_scope(m, 'sds', sid)
        S = self.S = m['sds'][self.scope]
        self.O = m['objects']
        self.src = S['folder']
        self.ws = S['ws'].replace('_<ENV>', '')
        self.lh = S['lakehouse']
        self.sp = cfg('shared-platform.json')
        self.view = f"{self.sp['catalog_schema']}.{catalog_view(self.sp, self.src)}"
        self.pd = project_dir('sds', self.scope)
        legacy = os.path.join(self.pd, '2-legacy-code', 'pipelines')
        dest = ''
        for p in glob.glob(os.path.join(legacy, '*.json')):
            params = read_json(p)['properties'].get('parameters') or {}
            dest = dest or (params.get('DestFolderRaw') or {}).get('defaultValue', '')
        inst = re.search(r'DATASOURCE=([A-Za-z0-9_]+)', dest, re.I)
        inst = inst.group(1).lower() if inst else ''
        self.system = self.src.lower()
        self.instance = re.sub(rf'^{self.system}_?', '', inst) or 'main'
        self.landing = f'landing/{self.system}'
        self.raw = f'raw/{self.system}'
        self.conn_ls, self.conn_type, self.method, self.fmt, self.dialect = ingestion.source_kind(S, self.O)
        conn_row = next((r for r in S['rows'] if r['v1'] == self.conn_ls and r['v2t'] == 'Connection'), None)
        self.conn_var = re.sub(r'^CONN_|_<ENV>$', '', conn_row['v2'].split(' (')[0]) + '_CONN_ID' if conn_row else ''
        self.files, self.mixed, self.conn_key = {}, False, None  # files ingested next to the database (ingestion.file_inputs): a second input group
        fi = ingestion.file_inputs(self.src) if self.method == 'structured' else {}
        if fi.get('tables'):
            row2 = next((r for r in S['rows'] if r['v1'] == fi['connection'] and r['v2t'] == 'Connection'), None)
            fi['conn_var'] = (re.sub(r'^CONN_|_<ENV>$', '', row2['v2'].split(' (')[0]) + '_CONN_ID') if row2 else f"{self.src}_FILES_CONN_ID"
            self.files, self.mixed, self.conn_key = fi, True, 'main'
        self.has_notebook = bool(S['notebooks'])  # notebooks only where DPV1 had one
        root = ingestion.legacy_rules(S, self.pd)[0].get('json_root')
        self.pagination, self.pagination_from = ingestion.dpv1_pagination(S, root) if self.conn_type == 'RestService' else (None, '')
        self.json_multiline = False
        import scope_tree  # date tree in raw only when DPV1 had one (structured); semi-structured runs are always dated
        self.layout = scope_tree.layout('sds', self.scope, S)
        self.raw_dates = self.method != 'structured' or self.layout['raw_dates']
        prof = work_path('sds', self.scope, 'catalog-profile.json')  # written by create_catalog_view.py (S1)
        self.profile = read_json(prof) if exists(prof) else {}
        self.incremental = bool(self.profile.get('incremental'))
        self.legacy = {k: [r['v1'] for r in S['rows'] if r['a'] in ('merge', 'rebuild', 'translate') and k in r['v2']]
                       for k in ('SOURCE_TO_RAW', 'RAW_TO_DELTA', 'MASTER_ORCHESTRATOR')}

    def tree_text(self):
        if self.method == 'structured':
            return f"Files/{self.raw}/<table>/" + ('<yyyy>/<mm>/<dd>/<HHhMM>/' if self.raw_dates else '') + '[HISTORY|DELETE_LOGS]'
        return f'Files/{self.landing}/<yyyy>/<mm>/<dd>/<HHhMM>/ (all tables, as delivered)'

    def out(self, *parts):
        return deploy_dir('sds', self.scope, self.ws, self.src, *parts)

    def lakehouse_settings(self, root='Files'):
        return {'name': self.lh.lower(), 'properties': {
            'annotations': [], 'type': 'Lakehouse',
            'typeProperties': {'workspaceId': '@pipeline().DataFactory', 'artifactId': f'@pipeline().libraryVariables.LH_SDS_{self.src}_ID', 'rootFolder': root},
            'externalReferences': {'connection': f"@pipeline().libraryVariables.{vl_name(self.src, 'LH_CONN_ID')}"}}}


def build_s1(c):
    folder = c.out(f'{c.lh}.Lakehouse')
    zones = 'Files/raw (parquet), dbo tables' if c.method == 'structured' else 'Files/landing (as delivered), Files/raw (parquet), dbo tables'
    lid = platform(folder, 'Lakehouse', c.lh, f'Source dataset {c.src}: {zones}.')
    write(os.path.join(folder, 'lakehouse.metadata.json'), '{"defaultSchema":"dbo"}\n')
    write_note('sds', c.scope, 'S1-lakehouse', '\n'.join([
        f'# S1 Lakehouse: {c.src}', '', f'- **Item**: `{c.ws}/{c.src}/{c.lh}.Lakehouse` (logicalId `{lid}`)', '- **Schemas**: default schema `dbo` (schemas enabled)',
        (f'- **Files**: `{c.tree_text()}` (parquet written once by the Copy; ' + ('a folder per run, as DPV1' if c.raw_dates else 'one folder per table, overwritten at each run') + ')'
         if c.method == 'structured' else f'- **Files**: `Files/{c.landing}/<yyyy>/<mm>/<dd>/<HHhMM>/` (all tables as delivered) and `Files/{c.raw}/<yyyy>/<mm>/<dd>/<HHhMM>/<table>/` (parquet)'),
        '- **Shortcuts**: none. The source dataset ingests directly from the source.',
        f"- **Replaces (DPV1)**: ADLS RAW and CLEANSED zones `DATASOURCE={c.src}_{c.instance.upper()}` and the SPOT_DB source views", '']))
    return [f'{c.lh}.Lakehouse']


def build_s2(c):
    if not c.conn_type:
        raise SystemExit(f'{c.src}: no source connection found in DPV1 (linked service): build S2 by hand with the ingestion skills.')
    return ingestion.build_s2(sys.modules[__name__], c)


def build_s3(c):
    lh_folder = c.out(f'{c.lh}.Lakehouse')
    if not exists(os.path.join(lh_folder, '.platform')):
        raise SystemExit(f'{c.src}: build S1 first (the notebook binds to the lakehouse logicalId).')
    return ingestion.build_s3(sys.modules[__name__], c, read_json(os.path.join(lh_folder, '.platform'))['config']['logicalId'])


def legacy_schedule(c):
    """Recurrence of the DPV1 triggers of the scope, read from the export (documented, never activated)."""
    out = []
    for t in c.S['triggers']:
        p = os.path.join(paths()['dpv1_export_root'], 'trigger', t + '.json')
        props = read_json(p)['properties'] if exists(p) else {}
        rec = (props.get('typeProperties') or {}).get('recurrence') or {}
        sch = rec.get('schedule') or {}
        times = [f'{h:02d}:{m:02d}' for h in sch.get('hours', []) for m in (sch.get('minutes') or [0])]
        out.append({'trigger': t, 'state': props.get('runtimeState', '?'), 'type': props.get('type', '?'), 'frequency': rec.get('frequency', ''),
                    'interval': rec.get('interval', ''), 'days': sch.get('weekDays') or sch.get('monthDays') or [], 'times': times,
                    'timezone': rec.get('timeZone', ''), 'pipelines': [x['pipelineReference']['referenceName'] for x in props.get('pipelines', [])]})
    return out


def build_s4(c):
    children = {}
    for stage, folder, name in (('S2', '1-SOURCE_TO_RAW', f'PL_{c.src}_SOURCE_TO_RAW'), ('S3', '2-RAW_TO_DELTA', f'PL_{c.src}_RAW_TO_DELTA')):
        plat = os.path.join(c.out(folder, f'{name}.DataPipeline'), '.platform')
        if not exists(plat):
            raise SystemExit(f'{c.src}: build {stage} first (the master calls {name} by its logicalId, KI-012).')
        children[name] = read_json(plat)['config']['logicalId']
    s2, s3 = f'PL_{c.src}_SOURCE_TO_RAW', f'PL_{c.src}_RAW_TO_DELTA'
    pp = lambda n: expr(f'@pipeline().parameters.{n}')
    run = lambda act, child, params, dep: {
        'name': act, 'type': 'ExecutePipeline', 'policy': {'secureInput': False}, 'dependsOn': dep,
        'description': f'Runs {child} and waits for it.',
        'typeProperties': {'pipeline': {'referenceName': children[child], 'type': 'PipelineReference'}, 'waitOnCompletion': True,
                           'parameters': {k: pp(k) for k in params}}}
    fail = lambda act, code, msg: {'name': f'Fail {act}', 'type': 'Fail', 'dependsOn': [{'activity': act, 'dependencyConditions': ['Failed']}],
                                   'typeProperties': {'errorCode': code, 'message': msg}}
    roots = ['RawRoot'] + (['LandingRoot'] if c.method != 'structured' else [])
    acts = [{'name': 'Set run partition', 'type': 'SetVariable', 'dependsOn': [],
             'description': 'One run folder yyyy/MM/dd/HHhmm for both children (DPV1 folder tree), from the trigger time.',
             'typeProperties': {'variableName': 'Run', 'value': expr(ingestion.RUN_DEFAULT)}},
            run('Execute Source to RAW', s2, roots, [{'activity': 'Set run partition', 'dependencyConditions': ['Succeeded']}]),
            run('Execute RAW to Lakehouse', s3, roots + ['MaxParallel'], [{'activity': 'Execute Source to RAW', 'dependencyConditions': ['Succeeded']}]),
            fail('Execute Source to RAW', 'MASTER_SOURCE_TO_RAW_FAILED', f'PL_{c.src}_MASTER_ORCHESTRATOR stopped: {s2} did not run to the end. Open its run.'),
            fail('Execute RAW to Lakehouse', 'MASTER_RAW_TO_DELTA_FAILED', f'PL_{c.src}_MASTER_ORCHESTRATOR stopped: {s3} did not run to the end. Open its run.')]
    for a in acts[1:3]:
        a['typeProperties']['parameters']['RunPartition'] = expr("@variables('Run')")
    ret = lambda act, key: f"activity('{act}').output.pipelineReturnValue.{key}"
    # only the tables that copied go on to the lakehouse (DPV1 "Append Success Files")
    acts[2]['typeProperties']['parameters']['LoadedTables'] = expr('@' + ret('Execute Source to RAW', 'LoadedTables'))
    s3_ok = [{'activity': 'Execute RAW to Lakehouse', 'dependencyConditions': ['Succeeded']}]
    acts += [{'name': 'Collect failed tables', 'type': 'SetVariable', 'dependsOn': s3_ok,
              'description': 'Tables that failed to copy (S2) or to load (S3), each with its error.',
              'typeProperties': {'variableName': 'Failed', 'value': expr(
                  f"@union({ret('Execute Source to RAW', 'FailedTables')}, {ret('Execute RAW to Lakehouse', 'FailedTables')})")}},
             {'name': 'Any table failed', 'type': 'IfCondition', 'dependsOn': [{'activity': 'Collect failed tables', 'dependencyConditions': ['Succeeded']}],
              'description': 'The other tables are loaded; the run still ends Failed and names every failed table with its error.',
              'typeProperties': {'expression': expr("@greater(length(variables('Failed')), 0)"), 'ifTrueActivities': [
                  {'name': 'Fail with failed tables', 'type': 'Fail', 'dependsOn': [], 'typeProperties': {'errorCode': 'MASTER_TABLES_FAILED', 'message': expr(
                      f"@concat('PL_{c.src}_MASTER_ORCHESTRATOR: ', string(length(variables('Failed'))), ' table(s) failed, the others are loaded: ', "
                      "join(variables('Failed'), ' | '))")}}]}}]
    p = lambda v: {'type': 'String', 'defaultValue': v}
    params = {'RawRoot': p(c.raw)} | ({'LandingRoot': p(c.landing)} if c.method != 'structured' else {}) | {'MaxParallel': p('8')}
    # concurrency 1: a second run of this source (schedule + manual re-run) waits until the first has finished, so two runs never
    # write the same tables at the same time
    content = {'properties': {'activities': acts, 'parameters': params, 'concurrency': 1,
                              'variables': {'Run': {'type': 'String'}, 'Failed': {'type': 'Array', 'defaultValue': []}}}}
    if c.incremental:  # watermark of the incremental tables that reached the lakehouse (DPV1: SP_COMMON_UpdateWatermark)
        acts.insert(3, ingestion.watermark_step(sys.modules[__name__], c, s3_ok, ret('Execute RAW to Lakehouse', 'LoadedTables')))
        acts.append(fail('Update watermarks', 'MASTER_WATERMARK_FAILED', f'PL_{c.src}_MASTER_ORCHESTRATOR: data loaded but the watermark was not updated; the next run re-reads the same changes (safe).'))
        lv = lambda n: {'type': 'String', 'variableName': n, 'libraryName': 'VL_MAIN'}
        content['properties']['libraryVariables'] = {n: lv(n) for n in ingestion.libs(c, warehouse=True)}
    name = f'PL_{c.src}_MASTER_ORCHESTRATOR'
    folder = c.out('0-ORCHESTRATION', f'{name}.DataPipeline')
    platform(folder, 'DataPipeline', name, f'{c.src}: source => raw, then raw => dbo tables, same run folder.')
    write(os.path.join(folder, 'pipeline-content.json'), dump(content))
    import create_variable_library as cvl  # VL_MAIN follows the catalog profile (watermark table) of this build
    variables = cvl.build_variables(load_map(), 'sds', c.scope)
    _, kept = cvl.save_workspace_library('sds', c.scope, c.ws, variables)  # one VL_MAIN per workspace: other sources' variables are kept
    vl_note = ['## VL_MAIN shared by the workspace', '',
               f"- `{c.ws}/VL_MAIN` is one item for every source of the workspace. Names that differ per source carry it (`{vl_name(c.src, 'CATALOG_VIEW_NAME')}`, "
               f"`{vl_name(c.src, 'LH_CONN_ID')}`…), and each pipeline declares them under the same name.",
               *([f"- Also holds {len(kept)} variables of other sources or of earlier builds, kept and not used by {c.src}: " + ', '.join(f'`{k}`' for k in kept) + '.',
                  '- Remove a name only when no deployed pipeline uses it any more (for example the unprefixed `CATALOG_*` names once every source is republished).']
                 if kept else []), '']
    sched = legacy_schedule(c)
    srow = lambda s: f"| `{s['trigger']}` | {s['state']} | {s['frequency']} every {s['interval']} | {', '.join(s['days']) or '-'} | {', '.join(s['times']) or '-'} | {s['timezone'] or '-'} | {', '.join('`' + x + '`' for x in s['pipelines'])} |"
    write_note('sds', c.scope, 'S4-orchestration', '\n'.join([
        f'# S4 Orchestration and variable library: {c.src}', '',
        f'- **Items**: `{c.ws}/{c.src}/0-ORCHESTRATION/{name}`, and `{c.ws}/VL_MAIN`',
        f"- **Replaces (DPV1)**: {', '.join('`' + x + '`' for x in c.legacy['MASTER_ORCHESTRATOR']) or 'none'}, and the chaining of `PL_CLNDATA_*` inside `PL_RAWDATA_*`", '',
        '## Run order', '', '0. Set the run folder once; both children get it (`RunPartition`)', f'1. `{s2}`: catalog view => ' + ('raw parquet' if c.method == 'structured' else 'landing'),
        f'2. `{s3}`: only the tables that copied (`LoadedTables` returned by step 1) => `dbo` tables',
        *([f"   - then **Update watermarks**: `{vl_name(c.src, 'CATALOG_WATERMARK_TABLE_NAME')}` = start of this run (CET, as DPV1) for the incremental tables loaded in this run only; replaces `SP_COMMON_UpdateWatermark`"] if c.incremental else []),
        '3. **Any table failed**: the failed tables of both steps, with their errors, end the run as Failed; the other tables are loaded.',
        '4. A Fail activity names the child that did not run to the end.', '',
        '## Parallel loads and waiting', '',
        '- One Spark session per notebook run, whatever the number of tables; the tables run in a thread pool inside it.',
        '- `MaxParallel` (master parameter, default 8): tables loaded at the same time; the others wait in the queue. '
        'Start with the Spark pool cores ÷ 4; lower it when the source has a few very large tables, raise it (16–32) for many small ones. '
        'Set it per schedule or manual run.',
        *([] if c.incremental and not c.layout.get('delete_logs') else ['- Automatic: FAIR scheduling (one pool per table thread), largest tables first.']),
        f"- The master has concurrency 1: a second run of {c.src} waits until the first has finished. "
        f"Notebook timeout: `{ingestion.notebook_timeout(c)}` (`notebook_timeout` in `shared-platform.json`, or per project in `progress.json` `project_inputs`).",
        '- FLATTEN and the loader share one session (session tag) when *high concurrency for pipelines* is on in the workspace Spark settings: turn it on once.', '',
        '## Schedule (documented, not activated)', '',
        '| DPV1 trigger | State in DPV1 | Recurrence | Days | Time | Time zone | Started |', '| --- | --- | --- | --- | --- | --- | --- |',
        *([srow(s) for s in sched] or ['| none | - | - | - | - | - | - |']), '',
        f'- In Fabric: open `{name}` => Schedule, and enter the same recurrence. Leave it **off** until the data phase and the cut-over are agreed.',
        '- The DPV1 trigger also started pipelines that are dropped (owner decisions); the Fabric schedule starts only the master orchestrator.', '',
        *vl_note,
        '## Connections', '', '- `connections.md` (next to this page): each Fabric connection to create, its name per environment, type, gateway, DPV1 values, secret and VL_MAIN variable.', '',
        '## Alerts instead of mail wrappers', '',
        f'- On `{name}`: add an Activator job alert for **Failed** (and **Succeeded** if the owner wants it), sent to the source owner.',
        '- Use workspace monitoring for run history. No DPV1 mail or log child pipeline is migrated.', '',
        '## Hand-over to Data Product Migration', '',
        f'- `source-dataset-contract.json` / `.md` (project root) lists the Lakehouse, every table with its DPV1 access paths, the VL_MAIN names and the data products that read {c.src}.',
        '- Data Product Migration reads it to build its input Lakehouse (`build_input_lakehouse.py`) and to re-point T-SQL (D2).', '']))
    import connections  # which Fabric connections to create, with which name and values (from the DPV1 linked services)
    connections.sheet('sds', c.scope)
    import source_contract
    source_contract.publish(c.scope)
    return [name, 'VL_MAIN', 'connections.md', 'source-dataset-contract']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--id', required=True)
    ap.add_argument('--stage', choices=['S1', 'S2', 'S3', 'S4', 'all'], default='all')
    ap.add_argument('--parallel', action='store_true', help='allow a second project in progress (owner agreed)')
    a = ap.parse_args()
    c = Ctx(a.id)
    import track
    track.ensure_single_active(c.scope, 'sds', a.parallel)
    for st, fn in (('S1', build_s1), ('S2', build_s2), ('S3', build_s3), ('S4', build_s4)):
        if a.stage in (st, 'all'):
            items = fn(c)
            track_event(c.scope, 'sds', st, f"Built {', '.join('`' + i + '`' for i in items)} (build_source_dataset.py)")
            print(f"{c.scope} {st}: {', '.join(items)}")


if __name__ == '__main__':
    main()
