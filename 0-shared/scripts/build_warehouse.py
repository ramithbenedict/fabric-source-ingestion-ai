"""Warehouse item of a data product (empty: the DACPAC fills it).
Writes 3-build/fabric-deployment/<workspace folder>/WH_DPG_<GROUP>.Warehouse/{.platform,WH_DPG_<GROUP>.sqlproj,xmla.json}
from 1-skills/skill-fabric-create-warehouse/template. Usage: python -I build_warehouse.py --id RMA --group RMA
"""
import argparse, json, os, sys, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, write, project_dir
import project_inputs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--id', required=True); ap.add_argument('--group', required=True)
    a = ap.parse_args()
    wf = project_inputs.load('dp', a.id).get('workspace_folder')
    if not wf:
        raise SystemExit('workspace missing: run project_inputs.py set first')
    name = f'WH_DPG_{a.group}'
    t = os.path.join(ROOT, '1-skills', 'skill-fabric-create-warehouse', 'template', 'WH_NAME.Warehouse')
    d = os.path.join(project_dir('dp', a.id, '3-build', 'fabric-deployment'), wf, f'{name}.Warehouse')
    sub = {'{{WH_NAME}}': name, '{{Dataset_Name}}': name, '{{DESCRIPTION}}': f'Warehouse of the {a.group} data product.',
           '{{LOGICAL_ID}}': str(uuid.uuid5(uuid.NAMESPACE_URL, name))}
    for f in ('.platform', 'WH_DPG_SERVICENOW.sqlproj', 'xmla.json'):
        s = open(os.path.join(t, f), encoding='utf-8').read()
        for k, v in sub.items():
            s = s.replace(k, v)
        write(os.path.join(d, f.replace('WH_DPG_SERVICENOW', name)), s)
    print(f'{name}.Warehouse => {d}')


if __name__ == '__main__':
    main()
