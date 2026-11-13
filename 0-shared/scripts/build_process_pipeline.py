"""wf-3 D4: the pipelines of a data product (pattern of the deployed products: PL_MDM_DATA_QUALITY_MASTER calls PL_MDM_DATA_QUALITY).

  PL_<GROUP>_PROCESS_DATA_PRODUCT   child: one Stored Procedure activity per load procedure of the database project (SP_LOAD_* / SP_TRAN_* / SP_PRC_*).
                                    Dimensions in parallel, facts after all dimensions (d2-load-order.json, written by convert_serverless_sql.py), retry 2.
  PL_<GROUP>_MASTER_ORCHESTRATOR    master: sets MASTER_PIPELINE_EXECUTION_ID and EXECUTION_DATE, runs the child and waits, fails with a clear message.
                                    No trigger: the schedule is an owner decision (framing Q04), and the product runs after its source datasets (Q26).

Usage (after dacpac_retarget.py and create_variable_library.py):
  python -I 0-shared/scripts/build_process_pipeline.py --id RMA --group RMA [--folder ORCHESTRATION] [--no-master]

Writes 3-build/fabric-deployment/<workspace folder>/<folder>/<pipeline>.DataPipeline/{.platform,pipeline-content.json}. The warehouse is read through VL_MAIN
(WH_DPG_<G>_ID, _SQL_ENDPOINT, _CONN_ID); the workspace is @pipeline().DataFactory. The master calls the child by its logicalId (same workspace folder).
"""
import argparse, glob, json, os, re, sys, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, write, project_dir, read_json, exists

SCHEMA = 'https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json'
EXPR = lambda v: {'value': v, 'type': 'Expression'}


def pipeline_files(d, name, description, content):
    write(os.path.join(d, 'pipeline-content.json'), json.dumps(content, indent=2) + '\n')
    write(os.path.join(d, '.platform'), json.dumps({'$schema': SCHEMA, 'metadata': {'type': 'DataPipeline', 'displayName': name, 'description': description},
                                                    'config': {'version': '2.0', 'logicalId': str(uuid.uuid5(uuid.NAMESPACE_URL, name))}}, indent=2) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--id', required=True); ap.add_argument('--group', required=True); ap.add_argument('--folder', default='ORCHESTRATION')
    ap.add_argument('--no-master', action='store_true', help='only the process pipeline')
    a = ap.parse_args()
    g = a.group.upper()
    base = project_dir('dp', a.id, '3-build', 'fabric-deployment')
    procs = []
    for f in sorted(glob.glob(os.path.join(base, 'database-projects', f'DPG-{g}', '*', '3-processing', 'stored_procedures', '*.sql'))):
        m = re.search(r'CREATE\s+PROCEDURE\s+\[(\w+)\]\.\[(\w+)\]', open(f, encoding='utf-8').read(), re.I)
        if m:
            procs.append(f'{m.group(1)}.{m.group(2)}')
    if not procs:
        raise SystemExit(f'{a.id}: no stored procedures under database-projects/DPG-{g}/*/3-processing: run dacpac_retarget.py first (K2); a pipeline without activities would deploy and do nothing.')
    order_p = project_dir('dp', a.id, '3-build', '_work', 'd2-load-order.json')
    facts = set()
    if exists(order_p):  # dimensions first, then facts: the fact loaders look up the dimension keys
        for b in read_json(order_p).get('batches', []):
            if b['name'] == 'facts':
                facts = {p.split('.')[-1].strip('[]').upper() for p in b['procedures']}
    wh = f'WH_DPG_{g}'
    conn = {'name': str(uuid.uuid5(uuid.NAMESPACE_URL, f'{wh}-conn')).replace('-', '_'), 'properties': {'annotations': [], 'type': 'DataWarehouse', 'typeProperties': {
        'endpoint': f'@pipeline().libraryVariables.{wh}_SQL_ENDPOINT', 'artifactId': f'@pipeline().libraryVariables.{wh}_ID', 'workspaceId': '@pipeline().DataFactory'},
        'externalReferences': {'connection': f'@pipeline().libraryVariables.{wh}_CONN_ID'}}}
    dims = [p for p in procs if p.split('.')[1].upper() not in facts]
    acts = []
    for p in procs:
        dep = [{'activity': d.split('.')[1], 'dependencyConditions': ['Succeeded']} for d in dims] if p.split('.')[1].upper() in facts else []
        acts.append({'name': p.split('.')[1], 'type': 'SqlServerStoredProcedure', 'dependsOn': dep,
                     'policy': {'timeout': '0.02:00:00', 'retry': 2, 'retryIntervalInSeconds': 30, 'secureInput': False, 'secureOutput': False},
                     'typeProperties': {'storedProcedureName': p}, 'connectionSettings': conn})
    libs = {v: {'type': 'String', 'variableName': v, 'libraryName': 'VL_MAIN'} for v in (f'{wh}_ID', f'{wh}_SQL_ENDPOINT', f'{wh}_CONN_ID')}
    child, master = f'PL_{g}_PROCESS_DATA_PRODUCT', f'PL_{g}_MASTER_ORCHESTRATOR'
    ws = __import__('project_inputs').load('dp', a.id).get('workspace_folder') or f'DP_DPG_{g}'
    folder = os.path.join(base, ws, a.folder)
    params = {'MASTER_PIPELINE_EXECUTION_ID': {'type': 'String', 'defaultValue': ''}, 'EXECUTION_DATE': {'type': 'String', 'defaultValue': ''}}
    pipeline_files(os.path.join(folder, f'{child}.DataPipeline'), child,
                   f'{g}: loads the tables of {wh} ({len(dims)} in parallel' + (f', then {len(facts)} facts' if facts else '') + '), one Stored Procedure activity each.',
                   {'properties': {'activities': acts, 'parameters': params, 'libraryVariables': libs}})
    print(f'{child}: {len(acts)} procedure activities ({len(dims)} dimensions in parallel, {len(facts)} facts after them) => {os.path.relpath(os.path.join(folder, child + ".DataPipeline"), ROOT)}')
    if a.no_master:
        return
    child_id = str(uuid.uuid5(uuid.NAMESPACE_URL, child))
    macts = [{'name': 'Set_MASTER_PIPELINE_EXECUTION_ID', 'type': 'SetVariable', 'dependsOn': [], 'policy': {'secureOutput': False, 'secureInput': False},
              'typeProperties': {'variableName': 'MASTER_PIPELINE_EXECUTION_ID', 'value': EXPR('@pipeline().RunId')}},
             {'name': 'Set_EXECUTION_DATE', 'type': 'SetVariable', 'dependsOn': [], 'policy': {'secureOutput': False, 'secureInput': False},
              'typeProperties': {'variableName': 'EXECUTION_DATE', 'value': EXPR("@formatDateTime(utcnow(), 'yyyy-MM-dd')")}},
             {'name': f'Run_{child}', 'type': 'ExecutePipeline', 'policy': {'secureInput': False},
              'dependsOn': [{'activity': 'Set_MASTER_PIPELINE_EXECUTION_ID', 'dependencyConditions': ['Succeeded']}, {'activity': 'Set_EXECUTION_DATE', 'dependencyConditions': ['Succeeded']}],
              'description': f'Runs {child} and waits for it. Run it after the source datasets {", ".join(read_json(project_dir("dp", a.id, "0_progress_tracking", "progress.json")).get("inputs", [])[:0]) or "of this product"} have finished (framing Q26).',
              'typeProperties': {'pipeline': {'referenceName': child_id, 'type': 'PipelineReference'}, 'waitOnCompletion': True,
                                 'parameters': {'MASTER_PIPELINE_EXECUTION_ID': EXPR("@variables('MASTER_PIPELINE_EXECUTION_ID')"), 'EXECUTION_DATE': EXPR("@variables('EXECUTION_DATE')")}}},
             {'name': f'Fail {child}', 'type': 'Fail', 'dependsOn': [{'activity': f'Run_{child}', 'dependencyConditions': ['Failed']}],
              'typeProperties': {'errorCode': 'PROCESS_DATA_PRODUCT_FAILED', 'message': f'{master} stopped: {child} did not run to the end. Open its run.'}}]
    pipeline_files(os.path.join(folder, f'{master}.DataPipeline'), master,
                   f'{g}: master of the data product. Sets a run id and date and runs {child}. No trigger (the schedule is an owner decision); run it after the source datasets.',
                   {'properties': {'activities': macts, 'variables': {'MASTER_PIPELINE_EXECUTION_ID': {'type': 'String'}, 'EXECUTION_DATE': {'type': 'String'}}}})
    print(f'{master}: sets a run id and date, runs {child}, fails with a message => {os.path.relpath(os.path.join(folder, master + ".DataPipeline"), ROOT)}')


if __name__ == '__main__':
    main()
