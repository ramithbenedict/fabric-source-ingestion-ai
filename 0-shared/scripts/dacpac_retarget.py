"""wf-4-migration-dacpac: retarget a Synapse Dedicated SQL Pool database project to a Fabric Warehouse database project.
The code stays T-SQL. Objects are copied into the DPG-<GROUP> folder convention; nothing is rewritten silently.

Input, one of:
  --sqlproj <folder>   an existing dedicated-pool SQL database project (.sqlproj + .sql files)
  --flat <folder>      .sql files, e.g. from  SqlPackage /Action:Extract /p:ExtractTarget=Flat  of the dedicated pool,
                       or 2-legacy-code/embedded-sql produced by extract_scope_code.py

Usage:
  python -I 0-shared/scripts/dacpac_retarget.py --flat <folder> --group GAIABI --product gaia --project GAIA [--schemas dw_gaia,dm_gaia] [--schema-map dw_gaia=OUT_SILV_GAIA,dm_gaia=OUT_GOLD_GAIA]

--schema-map renames schemas to the layer convention (DW => silver OUT_SILV_<P>, DM => gold OUT_GOLD_<P>; 2-config/conventions/05-data-products/database-project-structure.md):
every `[old]` and `old.` reference in the code is rewritten and 00-global/schemas/schemas.sql creates the new schemas.

Writes 4-migration-project-deliverables/data-product/<PROJECT>/3-build/fabric-deployment/database-projects/DPG-<GROUP>/ (reports in 4-dacpac/) (SDK-style .sqlproj for Fabric Warehouse) and lint-report.md.
"""
import argparse, json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, paths, write, track_event, project_dir, deploy_dir, walk_files, read_json

FABRIC_DSP = 'Microsoft.Data.Tools.Schema.Sql.SqlDwUnifiedDatabaseSchemaProvider'
# Same shape as REPO-FABRIC-DEPLOYMENT/database-projects/_TEMPLATE (DPV2): the DACPAC is built by the Azure DevOps pipeline (ci-cd-dacpac), not locally.
SQLPROJ = """<?xml version="1.0" encoding="utf-8"?>
<Project DefaultTargets="Build">
  <Sdk Name="Microsoft.Build.Sql" Version="2.2.0" />
  <PropertyGroup>
    <Name>{name}</Name>
    <ProjectGuid>{{{guid}}}</ProjectGuid>
    <DSP>{dsp}</DSP>
    <ModelCollation>1033, CI</ModelCollation>{suppress}
  </PropertyGroup>

  <ItemGroup>
    <PackageReference Include="Microsoft.SqlServer.Dacpacs.FabricDw" Version="170.0.4" />
  </ItemGroup>
{refs}
  <ItemGroup>
    <None Include="{name}.publish.xml" />
  </ItemGroup>

  <Target Name="BeforeBuild">
    <Delete Files="$(BaseIntermediateOutputPath)\\project.assets.json" />
  </Target>
</Project>
"""
PUBLISH = """<?xml version="1.0" encoding="utf-8"?>
<Project ToolsVersion="Current" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <PropertyGroup>
    <TargetDatabaseName>{wh}</TargetDatabaseName>
    <AllowIncompatiblePlatform>True</AllowIncompatiblePlatform>
    <BlockOnPossibleDataLoss>True</BlockOnPossibleDataLoss>
    <DropObjectsNotInSource>False</DropObjectsNotInSource>
  </PropertyGroup>
</Project>
"""
NUGET = """<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources>
    <add key="nuget.org" value="https://api.nuget.org/v3/index.json" />
  </packageSources>
</configuration>
"""
KIND = re.compile(r'CREATE\s+(?:OR\s+ALTER\s+)?(PROC(?:EDURE)?|VIEW|TABLE|FUNCTION|SCHEMA|EXTERNAL\s+TABLE)\s+\[?(\w+)\]?(?:\.\[?(\w+)\]?)?', re.I)


def place(kind, schema, product):
    """Folder in the DPG-<GROUP> convention (2-config/conventions/05-data-products/database-project-structure.md)."""
    k = kind.upper()
    if k == 'SCHEMA':
        return '00-global/schemas'
    if k.startswith('EXTERNAL'):
        return f'01-silver-{product}/1-input'
    if k == 'VIEW' and (schema or '').lower().startswith('inp_'):  # the input layer: the one place that reads the Lakehouse
        return f'01-silver-{product}/1-input/views'
    gold = re.match(r'^(dm|gsp|spbi|rpt)', schema or '', re.I)
    layer = f'02-gold-{product}' if gold else f'01-silver-{product}'  # silver gets the lower number, gold follows (as DPG-ECV)
    if k == 'TABLE':
        return f'{layer}/4-output/tables'
    if k == 'VIEW':
        return f'{layer}/4-output/views' if gold else f'{layer}/2-intermediate/views'
    return f'{layer}/3-processing/stored_procedures'


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument('--sqlproj'); src.add_argument('--flat')
    ap.add_argument('--group', required=True, help='data product group, e.g. GAIABI')
    ap.add_argument('--product', required=True, help='data product name used in folder names, e.g. gaia')
    ap.add_argument('--project', required=True, help='project folder under 4-migration-project-deliverables/data-product')
    ap.add_argument('--schemas', default='', help='comma-separated schemas to keep (default: all)')
    ap.add_argument('--schema-map', default='', help='old=NEW pairs, e.g. dw_rma=OUT_SILV_RMA,dm_rma=OUT_GOLD_RMA')
    ap.add_argument('--gold-views', action='store_true', help='gold tables that mirror a silver table (same columns) become views over it, no copy')
    ap.add_argument('--parallel', action='store_true', help='allow a second project in progress (owner agreed)')
    a = ap.parse_args()
    folder = a.sqlproj or a.flat
    keep = {s.strip().lower() for s in a.schemas.split(',') if s.strip()}
    smap = {k.strip().lower(): v.strip() for k, v in (p.split('=', 1) for p in a.schema_map.split(',') if '=' in p)}

    def remap(text):
        for old, new in smap.items():
            text = re.sub(rf'(?<![\w\]])(\[?){re.escape(old)}(\]?)(?=\.)', lambda m: f'[{new}]' if m.group(1) else new, text, flags=re.I)
            text = re.sub(rf'\[{re.escape(old)}\]', f'[{new}]', text, flags=re.I)
        return text

    import track
    track.ensure_single_active(a.project, 'dp', a.parallel)
    import source_contract
    source_contract.require_sources(a.project)
    name = f'DPG-{a.group}'
    out = deploy_dir('dp', a.project, 'database-projects', name)  # reports stay in 4-dacpac/
    if os.path.isdir(out):
        shutil.rmtree(out)
    old_dsp = ''
    if a.sqlproj:
        proj = next((os.path.join(folder, f) for f in os.listdir(folder) if f.endswith('.sqlproj')), None)
        if proj:
            m = re.search(r'<DSP>(.*?)</DSP>', open(proj, encoding='utf-8-sig').read())
            old_dsp = m.group(1) if m else ''
    moved, skipped, silver_tbl, gold_tbl = [], [], {}, []
    cols_of = lambda t: [m.group(1).lower() for m in re.finditer(r'^\s*\[(\w+)\]\s', t, re.M)]
    cols_cased = lambda t: [m.group(1) for m in re.finditer(r'^\s*\[(\w+)\]\s', t, re.M)]  # the case the code uses: the stub of the Lakehouse table keeps it (no SQL71558 warning)
    for d, _, fs in os.walk(folder):
        for f in fs:
            if not f.lower().endswith('.sql'):
                continue
            text = open(os.path.join(d, f), encoding='utf-8-sig', errors='replace').read()
            code = re.sub(r'/\*.*?\*/', '', re.sub(r'--[^\n]*', '', text), flags=re.S)  # ignore comments
            m = KIND.search(code)
            if not m:
                skipped.append((f, 'no CREATE statement (script or post-deployment)')); continue
            kind, schema, obj = m.group(1), m.group(2), m.group(3)
            if kind.upper() != 'SCHEMA' and keep and (schema or '').lower() not in keep:
                skipped.append((f, f'schema {schema} not in scope')); continue
            new_schema = smap.get((schema or '').lower(), schema)
            text = re.sub(r'^\s*USE\s+\[?\w+\]?\s*;?\s*$', '', text, flags=re.I | re.M)
            if kind.upper() == 'TABLE':
                text = re.sub(r'CONSTRAINT \[PK_[^\]]+\]', f'CONSTRAINT [PK_{new_schema}_{obj}]', text)  # a dot in a constraint name is not valid after the rename
                if re.match(r'^(dm|gsp|spbi|rpt)', schema or '', re.I):
                    if a.gold_views:
                        gold_tbl.append((f, schema, new_schema, obj, text)); continue
                else:
                    silver_tbl[obj.lower()] = (new_schema, cols_of(text), cols_cased(text))
            target = os.path.join(out, place(kind, schema, a.product), f"{obj or schema}.sql")
            write(target, remap(text).strip() + '\n')
            moved.append((f, os.path.relpath(target, out)))
    for f, schema, new_schema, obj, text in gold_tbl:
        s = silver_tbl.get(obj.lower())
        if s and s[1] == cols_of(text):  # same columns as the silver table: gold is a view over silver
            target = os.path.join(out, place('VIEW', schema, a.product), f'{obj}.sql')
            body = ',\n'.join(f'    [{c}]' for c in re.findall(r'^\s*\[(\w+)\]\s', text, re.M))
            write(target, f'-- VIEW {new_schema}.{obj}: gold over silver (DPV1 table {schema}.{obj} had the same columns)\nCREATE VIEW [{new_schema}].[{obj}]\nAS\nSELECT\n{body}\nFROM [{s[0]}].[{obj}];\nGO\n')
        else:
            target = os.path.join(out, place('TABLE', schema, a.product), f'{obj}.sql')
            write(target, remap(text).strip() + '\n')
        moved.append((f, os.path.relpath(target, out)))
    if smap:
        write(os.path.join(out, '00-global', 'schemas', 'schemas.sql'), '\n'.join(f'CREATE SCHEMA [{n}];\nGO\n' for n in list(smap.values()) + sorted(s.upper() for s in keep if s not in smap)))
    # every schema an object uses is created in the project (a missing one fails the deployment)
    import deploy_gate
    used, made = set(), set()
    for f in walk_files(out, exts=('.sql',)):
        t = deploy_gate.strip_sql(open(f, encoding='utf-8-sig', errors='replace').read())
        made |= {m.group(1).lower() for m in re.finditer(r'CREATE\s+SCHEMA\s+\[?(\w+)\]?', t, re.I)}
        used |= {m.group(1).upper() for m in re.finditer(r'CREATE\s+(?:OR\s+ALTER\s+)?(?:TABLE|VIEW|PROC(?:EDURE)?|FUNCTION)\s+\[?(\w+)\]?\.', t, re.I)}
    extra = sorted(s for s in used if s.lower() not in made and s.lower() != 'dbo')
    if extra:
        sp = os.path.join(out, '00-global', 'schemas', 'schemas.sql')
        old = open(sp, encoding='utf-8').read() if os.path.exists(sp) else ''
        add = '\n'.join(f'CREATE SCHEMA [{x}];\nGO\n' for x in extra)
        write(sp, (old.rstrip('\n') + '\n' if old else '') + add)
    import uuid
    # the input views read the Lakehouse as [$(LH_...)]: each Lakehouse is an EXT-LH project reference + a SQLCMD variable (as DPG-OPA, DPG-MDM-DATA-QUALITY),
    # so the DACPAC builds and the same project deploys to DEV, UAT and PRD (the pipeline passes /v:LH_...=<name>)
    lakes = {}
    for f in walk_files(out, exts=('.sql',)):
        for lh, tbl in re.findall(r'\[\$\((LH_\w+)\)\]\.\[dbo\]\.\[(\w+)\]', open(f, encoding='utf-8-sig', errors='replace').read()):
            lakes.setdefault(lh, set()).add(tbl)
    refs, ext_names = '', []
    for lh, tbls in sorted(lakes.items()):
        ext = 'EXT-' + lh.replace('_', '-')
        ext_names.append(ext)
        extdir = deploy_dir('dp', a.project, 'database-projects', ext)
        if os.path.isdir(extdir):
            shutil.rmtree(extdir)
        used = deploy_gate.input_refs([f for f in walk_files(out, exts=('.sql',)) if '1-input' not in f.replace('\\', '/')])
        inp = 'inp_' + lh.lower().replace('lh_inp_sds_', '').replace('lh_sds_', '')
        for t in sorted(tbls):
            cols = list((silver_tbl.get(t.lower()) or (None, ["id"], ["id"]))[2])  # the stub only lets the views resolve: the columns of the silver table of that name ...
            have = {c.lower() for c in cols}
            cols += [c for c in used.get((inp, t.lower()), []) if c.lower() not in have]  # ... plus every column the code reads from the input table (the DW table may be a computed output with other columns)
            write(os.path.join(extdir, 'dbo', 'Tables', f'{t}.sql'), f'CREATE TABLE [dbo].[{t}] (\n' + ',\n'.join(f'    [{c}] varchar(4000) NULL' for c in cols) + '\n);\n')
        write(os.path.join(extdir, f'{ext}.sqlproj'), SQLPROJ.format(name=ext, dsp=FABRIC_DSP, guid=str(uuid.uuid5(uuid.NAMESPACE_URL, ext)).upper(), suppress='', refs='').replace(f'  <ItemGroup>\n    <None Include="{ext}.publish.xml" />\n  </ItemGroup>\n', ''))
        write(os.path.join(extdir, 'NuGet.config'), NUGET)
        refs += (f'\n  <!-- External reference: input Lakehouse {lh}, resolves the [{lh}].[dbo].* references of the input views -->\n'
                 f'  <ItemGroup>\n    <ProjectReference Include="..\\{ext}\\{ext}.sqlproj">\n      <DatabaseSqlCmdVariable>{lh}</DatabaseSqlCmdVariable>\n    </ProjectReference>\n  </ItemGroup>\n'
                 f'  <ItemGroup>\n    <SqlCmdVariable Include="{lh}">\n      <DefaultValue>{lh}</DefaultValue>\n    </SqlCmdVariable>\n  </ItemGroup>\n')
    # a DPV1 project that already has a DACPAC: its SQLCMD variables (declared in the sqlproj, valued per environment in its publish profiles) and every $(VAR) the code uses
    # are carried over, never dropped: they are declared here, passed per environment by the pipeline (build_cicd.py) and listed for the owner
    carried, per_env = {}, {}
    if a.sqlproj:
        for pf in walk_files(folder, exts=('.sqlproj',)):
            for n, dv in re.findall(r'<SqlCmdVariable Include="(\w+)">\s*(?:<DefaultValue>(.*?)</DefaultValue>)?', open(pf, encoding='utf-8-sig').read(), re.S):
                carried[n] = dv.strip()
        for pf in walk_files(folder, exts=('.xml',)):
            env = next((e for k, e in (('dev', 'DEV'), ('uat', 'UAT'), ('prd', 'PRD'), ('prod', 'PRD')) if k in os.path.basename(pf).lower()), None)
            if env and pf.lower().endswith('.publish.xml'):
                for n, v in re.findall(r'<SqlCmdVariable Include="(\w+)">\s*<Value>(.*?)</Value>', open(pf, encoding='utf-8-sig').read(), re.S):
                    per_env.setdefault(env, {})[n] = v.strip()
    for f in walk_files(out, exts=('.sql',)):
        for n in re.findall(r'\$\((\w+)\)', open(f, encoding='utf-8-sig', errors='replace').read()):
            if not n.startswith('LH_'):
                carried.setdefault(n, '')
    for n, dv in sorted(carried.items()):
        if f'<SqlCmdVariable Include="{n}">' in refs:
            continue
        refs +=f'  <ItemGroup>\n    <SqlCmdVariable Include="{n}">\n      <DefaultValue>{dv}</DefaultValue>\n    </SqlCmdVariable>\n  </ItemGroup>\n'
    if carried or per_env:
        import project_inputs
        pdoc = read_json(project_inputs.path('dp', a.project))
        pi = pdoc.setdefault('project_inputs', {})
        for env, vals in per_env.items():
            pi.setdefault('sqlcmd_values', {}).setdefault(env, {}).update({k: v for k, v in vals.items() if k in carried})
        write(project_inputs.path('dp', a.project), json.dumps(pdoc, indent=1, ensure_ascii=False) + '\n')
    suppress = ('\n    <!-- Suppress SQL71561 / 71563 / 71501 / 71502: cross-database views over a Lakehouse (resolved at runtime) -->\n    <SuppressTSqlWarnings>71561;71563;71501;71502</SuppressTSqlWarnings>' if lakes else '')
    write(os.path.join(out, f'{name}.sqlproj'), SQLPROJ.format(name=name, dsp=FABRIC_DSP, guid=str(uuid.uuid5(uuid.NAMESPACE_URL, name)).upper(), suppress=suppress, refs=refs))
    write(os.path.join(out, f'{name}.publish.xml'), PUBLISH.format(wh=f'WH_DPG_{a.group}'))
    write(os.path.join(out, 'NuGet.config'), NUGET)
    rep = project_dir('dp', a.project, '4-dacpac', 'retarget-report.md')
    write(rep, '\n'.join([f'# {name} · DACPAC retarget', '', f'- Source: `{folder}`' + (f' (DSP was `{old_dsp}`)' if old_dsp else ''), f'- Target DSP: `{FABRIC_DSP}`',
                          f'- Objects placed: {len(moved)} · skipped: {len(skipped)}', '', '## Placed', '', '| Source file | Target |', '|---|---|',
                          *[f'| `{s}` | `{t}` |' for s, t in moved], '', '## Skipped', '', *([f'- `{s}`: {why}' for s, why in skipped] or ['- None']), '',
                          *([f'## SQLCMD variables carried over from the DPV1 project', '', *[f'- `{n}` (default `{dv or "none"}`): value per environment through build_cicd.py (progress.json `sqlcmd_values`)' for n, dv in sorted(carried.items()) if not n.startswith('LH_')], ''] if any(not n.startswith('LH_') for n in carried) else []),
                          'Next: run the lint (D2 / K3), fix every blocking finding in T-SQL. The DACPAC is built by the Azure DevOps pipeline (ci-cd-dacpac, .NET 8); no local build needed.', '']))
    lint = project_dir('dp', a.project, '4-dacpac', 'lint-report.md')
    import subprocess
    r = subprocess.run([sys.executable, '-I', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tsql_fabric_lint.py'), out, '--report', lint], capture_output=True, text=True, encoding='utf-8')
    blocking = 0 if r.returncode == 0 else int((re.search(r'blocking (\d+)', r.stdout) or [0, 0])[1])
    track_event(a.project, 'dp', 'K2', f'{name} retargeted to Fabric Warehouse: {len(moved)} objects placed, {len(skipped)} skipped; lint {r.stdout.strip()}',
                gate='lint_zero_blocking', gate_ok=blocking == 0, evidence=f'{blocking} blocking findings (4-dacpac/lint-report.md)')
    for stage, done, note in (('K1', True, 'source: DPV1 code and the live pool (2-legacy-code)'), ('K2', True, f'{len(moved)} objects placed in {name}'), ('K3', blocking == 0, f'{blocking} blocking findings')):
        try:  # the K stages follow what ran: the retarget is K1 + K2, the lint K3 (K4, the build, is the Azure DevOps DACPAC pipeline)
            track.set_status(a.project, 'dp', stage, 'completed' if done else 'in_progress', note)
        except Exception:
            pass
    print(f'{name}: {len(moved)} objects placed, {len(skipped)} skipped => {os.path.relpath(out, ROOT)}')
    print('lint: ' + r.stdout.strip())


if __name__ == '__main__':
    main()
