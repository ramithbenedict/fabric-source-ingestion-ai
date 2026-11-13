"""wf-3 D2 (D-COPY): assemble the flat input of dacpac_retarget.py from the live-pool DDL and the converted DPV1 views and loaders.

Usage (after pool_read.py ddl and convert_serverless_sql.py):
  python -I 0-shared/scripts/d2_assemble_flat.py --id RMA --silver DW_RMA --gold DM_RMA --view-schema OUT_RMA --int INT_SILV_RMA --prc PRC_SILV_RMA --out-silver OUT_SILV_RMA

Writes 3-build/_work/d2-flat/:
  - tables of the silver and gold schemas from 2-legacy-code/database-extract (the live pool is the truth), with the K3 fixes of convert_serverless_sql.py
  - the OUT views of DPV1 as [<int>].[<table>] views (cleaned of the text left by the pipeline scripts)
  - SP_LOAD_<TABLE> as [<prc>].[SP_LOAD_<TABLE>]: TRUNCATE + INSERT into [<out-silver>].[<table>] from [<int>].[<table>]
Nothing is rewritten besides schema names and the Fabric type fixes.
"""
import argparse, collections, glob, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, write, project_dir
from convert_serverless_sql import k3_fix, build_input_layer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--id', required=True)
    ap.add_argument('--silver', required=True); ap.add_argument('--gold', required=True)
    ap.add_argument('--view-schema', required=True, help='schema of the DPV1 OUT views, e.g. OUT_RMA')
    ap.add_argument('--int', required=True); ap.add_argument('--prc', required=True); ap.add_argument('--out-silver', required=True)
    a = ap.parse_args()
    base = project_dir('dp', a.id)
    flat = os.path.join(base, '3-build', '_work', 'd2-flat')
    conv = os.path.join(base, '3-build', '_work', 'd2-converted-sql')
    ext = os.path.join(base, '2-legacy-code', 'database-extract')
    counts = collections.Counter()
    names = {}
    for sch in (a.silver, a.gold):
        for f in glob.glob(os.path.join(ext, sch.lower(), '*.table.sql')):
            obj = os.path.basename(f).split('.')[0]
            names[obj.lower()] = obj
            write(os.path.join(flat, sch.lower(), f'{obj}.sql'), k3_fix(open(f, encoding='utf-8').read(), counts))
    nview = nproc = 0
    for f in glob.glob(os.path.join(conv, f'{a.view_schema.lower()}.*.sql')):
        text = open(f, encoding='utf-8').read()
        m = re.search(r'CREATE\s+VIEW\s+\[?\w+\]?\.\[?(\w+)\]?', text, re.I)
        if not m:
            continue
        obj = names.get(m.group(1).lower(), m.group(1))
        body = text[m.start():]
        cut = re.search(r'^\s*(--|DROP\s+VIEW)', body, re.M)
        body = (body[:cut.start()] if cut else body).rstrip()
        wrap = re.search(r"'\s*;?\s*$", body)  # DPV1 created the view inside EXEC('...'): drop the closing quote and its semicolon (an odd number of quotes means one is the wrapper's)
        if wrap and body.count("'") % 2 == 1:
            body = body[:wrap.start()]
        body = body.rstrip()
        body = re.sub(r'CREATE\s+VIEW\s+\[?\w+\]?\.\[?\w+\]?', f'CREATE VIEW [{a.int}].[{obj}]', body, count=1, flags=re.I)
        write(os.path.join(flat, a.int.lower(), f'{obj}.sql'), f'-- VIEW {a.int}.{obj} (DPV1 OUT view {a.view_schema}.{obj})\n{body}\nGO\n')
        nview += 1
    for f in glob.glob(os.path.join(conv, '*.sp_load_*.sql')):
        text = open(f, encoding='utf-8').read()
        obj = re.search(r'SP_LOAD_(\w+)\]?', text, re.I).group(1)
        tbl = names.get(obj.lower(), obj)
        text = re.sub(r'CREATE\s+PROCEDURE\s+\[?\w+\]?\.\[?SP_LOAD_\w+\]?', f'CREATE PROCEDURE [{a.prc}].[SP_LOAD_{tbl.upper()}]', text, flags=re.I)
        text = re.sub(rf'(TRUNCATE TABLE|INSERT INTO)\s+\[\w+\]\.\[{obj}\]', rf'\1 [{a.out_silver}].[{tbl}]', text, flags=re.I)
        text = re.sub(rf'FROM\s+\[\w+\]\.\[{obj}\]', f'FROM [{a.int}].[{tbl}]', text, flags=re.I)
        write(os.path.join(flat, a.prc.lower(), f'SP_LOAD_{tbl.upper()}.sql'), text.rstrip() + '\nGO\n')
        nproc += 1
    ninp = build_input_layer(sorted(glob.glob(os.path.join(flat, '*', '*.sql'))), lambda s, t, lh, text: write(os.path.join(flat, f'inp_{s.lower()}', f'{t}.sql'), text))
    print(f'{a.id}: {ninp} input views [INP_<SRC>],')
    print(f'{a.id}: {len(names)} tables ({sum(counts.values())} K3 fixes), {nview} views, {nproc} loaders => {os.path.relpath(flat, ROOT)}')
    for k, v in counts.items():
        print(f'  {k}: {v}')


if __name__ == '__main__':
    main()
