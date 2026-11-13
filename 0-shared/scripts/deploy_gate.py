"""Deployability checks shared by the review (S5, D6), deploy_publish.py and deploy_preflight.py.

What Fabric refuses at import or deployment and a build can know in advance:
  - import-time ids: a shortcut target (workspaceId, itemId) read from VL_MAIN must be a real GUID, not the zero placeholder or `<to set>`
    ("Either target workspace ID or artifact ID is not a valid GUID": LH_INP_SDS_RMA, 2026-10-30)
  - project closure: every schema a database project uses is created in it, every object it references is created in it or is an input view,
    every procedure a pipeline calls exists, and the Lakehouse is read only in the 1-input views (one place to re-point)
Nothing here writes. Rules: 3-workflows/wf-2-migration-source-dataset/deployment-design.md ("Standard rule: dependencies are in place before deployment").
"""
import collections, glob, json, os, re
from common import read_json, read_text, exists, walk_files

GUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
ZERO = '00000000-0000-0000-0000-000000000000'
TOKEN = re.compile(r'\$\(/\*\*/(\w+)/(\w+)\)')
strip_sql = lambda t: re.sub(r'--[^\n]*|/\*.*?\*/', '', t, flags=re.S)


def is_real_guid(v):
    return bool(v) and bool(GUID.match(str(v))) and str(v) != ZERO


def vl_values(vl_dir, env='DEV'):
    """{variable: value} of a VL_MAIN folder for one environment (the value set, else the default value in variables.json)."""
    if not exists(os.path.join(vl_dir, 'variables.json')):
        return {}
    out = {v['name']: v.get('value') for v in read_json(os.path.join(vl_dir, 'variables.json')).get('variables', [])}
    vs = os.path.join(vl_dir, 'valueSets', f'{env}.json')
    if exists(vs):
        out.update({o['name']: o.get('value') for o in read_json(vs).get('variableOverrides', [])})
    return out


def shortcut_variables(build_dir):
    """{(library, variable): [shortcut file]} for every $(/**/<library>/<variable>) token of the shortcuts.metadata.json files under build_dir."""
    found = collections.defaultdict(list)
    for f in walk_files(build_dir, names={'shortcuts.metadata.json'}):
        for lib, var in TOKEN.findall(read_text(f, 'replace')):
            found[(lib, var)].append(os.path.relpath(f, build_dir))
    return found


def unresolved_imports(build_dir, env='DEV'):
    """Variables a shortcut needs at import whose value in the environment is not a real GUID: [(variable, value, file)].
    The library is the VL_MAIN of the same workspace folder as the shortcut file."""
    bad = []
    for (lib, var), files in shortcut_variables(build_dir).items():
        for f in files:
            ws = f.split(os.sep)[0]
            vl = os.path.join(build_dir, ws, f'{lib}.VariableLibrary')
            v = vl_values(vl, env).get(var)
            if not is_real_guid(v):
                bad.append((var, v if v else 'missing', f))
                break
    return bad


def database_projects(build_dir):
    return [p for p in glob.glob(os.path.join(build_dir, 'database-projects', 'DPG-*')) if os.path.isdir(p)]


CLOSURE_FAILS = ('schemas', 'references', 'procedures', 'syntax', 'stub', 'precision', 'rowversion')  # closure() keys that fail the review and block the publish


def closure(build_dir):
    """Findings of every database project under build_dir and the pipelines next to it: {key: [messages]}. Empty lists = fine."""
    res = collections.defaultdict(list)
    for dbp in database_projects(build_dir):
        created, schemas, used = {}, set(), collections.Counter()
        lakehouse_reads = collections.defaultdict(set)
        files = [f for f in walk_files(dbp, exts=('.sql',))]
        for f in files:
            t = re.sub(r'\$\((\w+)\)', r'\1', strip_sql(read_text(f, 'replace')))  # a SQLCMD variable stands for its name: [$(LH_X)] reads as [LH_X]
            rel = os.path.relpath(f, dbp)
            if re.sub(r"''", '', t).count("'") % 2:  # a quote that is never closed: SQL46030 at build (left over from a DPV1 EXEC('...') wrapper)
                res['syntax'].append(f'{os.path.basename(dbp)}: unbalanced single quote in {rel}')
            if re.search(r'\b(?:datetime2|datetimeoffset|time)\s*\(\s*7\s*\)', t, re.I):  # Msg 24597 at deploy: Fabric Warehouse allows precision 0 to 6
                res['precision'].append(f'{os.path.basename(dbp)}: time precision 7 (Fabric allows 0 to 6) in {rel}')
            if re.search(r'\bRowVersion\]?\s+(?:AS\s+)?\[?datetime', t, re.I):  # error 241 at load: a rowversion is binary in the Lakehouse
                res['rowversion'].append(f'{os.path.basename(dbp)}: RowVersion typed or cast as a date in {rel} (a rowversion is binary: varbinary(8))')
            schemas |= {m.group(1).lower() for m in re.finditer(r'CREATE\s+SCHEMA\s+\[?(\w+)\]?', t, re.I)}
            for m in re.finditer(r'CREATE\s+(?:OR\s+ALTER\s+)?(TABLE|VIEW|PROC(?:EDURE)?|FUNCTION)\s+\[?(\w+)\]?\.\[?(\w+)\]?', t, re.I):
                created[(m.group(2).lower(), m.group(3).lower())] = rel
            for m in re.finditer(r'\b(?:FROM|JOIN|INTO|UPDATE|TABLE)\s+(?:\[?(\w+)\]?\.)?\[?(\w+)\]?\.\[?(\w+)\]?(?:\.\[?(\w+)\]?)?', t, re.I):
                parts = tuple(x.lower() for x in m.groups() if x)
                if len(parts) == 3 and parts[0].startswith('lh_'):
                    lakehouse_reads[rel].add('.'.join(parts))
                elif len(parts) == 2:
                    used[(parts, rel)] += 1
        name = os.path.basename(dbp)
        missing_schemas = sorted({p[0] for (p, _), _n in used.items()} - schemas)
        if missing_schemas:
            res['schemas'].append(f"{name}: schema(s) used but not created in the project: {', '.join(missing_schemas)}")
        unres = sorted({(p, rel) for (p, rel), _ in used.items() if p not in created and p[0] in schemas})
        if unres:
            res['references'].append(f"{name}: {len(unres)} reference(s) to an object the project does not create, e.g. {unres[0][0][0]}.{unres[0][0][1]} in {unres[0][1]}")
        outside = sorted(r for r in lakehouse_reads if '1-input' not in r.replace('\\', '/'))
        if outside:
            res['input_layer'].append(f"{name}: the Lakehouse is read outside 1-input in {len(outside)} file(s), e.g. {outside[0]} (read it in [INP_<SRC>] views only)")
        if lakehouse_reads and not any('1-input' in r.replace('\\', '/') for r in lakehouse_reads):
            res['input_layer'].append(f'{name}: no 1-input view layer over LH_INP_SDS_<SRC> (convention database-project-structure.md)')
    for dbp in database_projects(build_dir):  # every column the code reads from an input table is in the stub table of its EXT-LH project (else SQL71501 at build)
        code = [f for f in walk_files(dbp, exts=('.sql',)) if '1-input' not in f.replace('\\', '/')]
        for (inp, table), cols in sorted(input_refs(code).items()):
            stub = os.path.join(build_dir, 'database-projects', 'EXT-LH-' + inp.replace('inp_', 'INP-SDS-', 1).upper().replace('_', '-'), 'dbo', 'Tables', f'{table}.sql')
            if exists(stub):
                have = {c.lower() for c in re.findall(r'^\s*\[(\w+)\]\s', read_text(stub, 'replace'), re.M)}
                lack = [c for c in cols if c.lower() not in have]
                if lack:
                    res['stub'].append(f"{os.path.basename(dbp)}: columns read from [{inp.upper()}].[{table}] but not in its EXT-LH stub: {', '.join(lack[:6])}")
    procs = set()
    for p in database_projects(build_dir):
        for f in walk_files(p, exts=('.sql',)):
            procs |= {(m.group(1).lower(), m.group(2).lower()) for m in re.finditer(r'CREATE\s+(?:OR\s+ALTER\s+)?PROC(?:EDURE)?\s+\[?(\w+)\]?\.\[?(\w+)\]?', strip_sql(read_text(f, 'replace')), re.I)}
    for pf in walk_files(build_dir, names={'pipeline-content.json'}):
        try:
            doc = json.loads(read_text(pf, 'replace'))
        except ValueError:
            continue
        def walk(o):
            if isinstance(o, dict):
                if o.get('type') == 'SqlServerStoredProcedure':
                    n = (o.get('typeProperties') or {}).get('storedProcedureName') or ''
                    k = tuple(x.strip('[]').lower() for x in n.split('.'))
                    if len(k) == 2 and k not in procs and database_projects(build_dir):
                        res['procedures'].append(f"{os.path.basename(os.path.dirname(pf))}: calls {n}, which no database project creates")
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(doc)
    return dict(res)


ENV_SUFFIX = re.compile(r'[_-](DEV|UAT|PRD|PROD|TST|TEST)$', re.I)
ENVS = ('DEV', 'UAT', 'PRD')


def cicd(build_dir):
    """What the promotion DEV => UAT => PRD needs and a build can know (DPV2: fabric-git-repo-structure.md, ci-cd-dacpac/, ci-cd/profiles/).
    Returns {'fail': [...], 'warn': [...]}: fail = the same build would not deploy to another environment; warn = a value only known after the first sync."""
    fail, warn = [], []
    skip = {'database-projects', 'ci-cd', 'ci-cd-dacpac'}
    folders = [d for d in os.listdir(build_dir) if os.path.isdir(os.path.join(build_dir, d)) and d not in skip] if os.path.isdir(build_dir) else []
    for d in folders:
        if ENV_SUFFIX.search(d):
            fail.append(f'workspace folder {d} carries an environment suffix: the same folder is promoted to every environment (use {ENV_SUFFIX.sub("", d)})')
    for d in folders:
        vl = os.path.join(build_dir, d, 'VL_MAIN.VariableLibrary')
        if not exists(os.path.join(vl, 'variables.json')):
            continue
        sp = os.path.join(vl, 'settings.json')
        order = read_json(sp).get('valueSetsOrder', []) if exists(sp) else []
        if any(e not in order for e in ENVS):  # the deploy (fabric-cicd) makes the value set named like the environment the active one
            fail.append(f'{d}/VL_MAIN settings.json: valueSetsOrder must list {", ".join(ENVS)} (the deployment activates the value set of the target environment)')
        dev = vl_values(vl, 'DEV')
        for env in ENVS[1:]:
            vals = vl_values(vl, env)
            same = [n for n, v in vals.items() if re.search(r'_(WORKSPACE_ID|CONN_ID|SQL_ENDPOINT|ID)$', n) and v and v == dev.get(n) and str(v) != ZERO and '<' not in str(v)]
            if same:  # UAT or PRD would read the DEV item: a value copied from DEV
                fail.append(f'{d}/VL_MAIN {env} value set holds the DEV value of {", ".join(same[:4])}{" ..." if len(same) > 4 else ""}: give the {env} one (create_variable_library.py --env {env} --set NAME=VALUE)')
    for dbp in database_projects(build_dir):
        name = os.path.basename(dbp)
        proj = read_text(os.path.join(dbp, f'{name}.sqlproj'), 'replace') if exists(os.path.join(dbp, f'{name}.sqlproj')) else ''
        lakes = set()
        for f in walk_files(dbp, exts=('.sql',)):
            lakes |= set(re.findall(r'\[\$\((LH_\w+)\)\]\.\[dbo\]', read_text(f, 'replace')))
        raw = set()
        for f in walk_files(dbp, exts=('.sql',)):
            raw |= set(re.findall(r'(?<![\w$(])\[(LH_\w+)\]\.\[?dbo\]?\.', read_text(f, 'replace')))
        if raw:
            fail.append(f'{name}: reads {", ".join(sorted(raw))} by a fixed name: use the SQLCMD variable [$(LH_...)] so the environment can set it')
        for lh in sorted(lakes):
            ext = 'EXT-' + lh.replace('_', '-')
            if f'{ext}.sqlproj' not in proj or f'<SqlCmdVariable Include="{lh}">' not in proj or not exists(os.path.join(build_dir, 'database-projects', ext, f'{ext}.sqlproj')):
                fail.append(f'{name}: {lh} has no {ext} project reference and SQLCMD variable (the DACPAC build cannot resolve [{lh}].[dbo].*)')
        pl = os.path.join(build_dir, 'ci-cd-dacpac', f'pipeline-{name.lower()}.yml')
        if not exists(pl):
            fail.append(f'{name}: no ci-cd-dacpac/pipeline-{name.lower()}.yml (nothing builds or publishes the DACPAC)')
        else:
            y = read_text(pl, 'replace')
            y = ' '.join(l for l in y.splitlines() if not l.lstrip().startswith('#'))  # comments do not pass variables
            if f"projectName: '{name}'" not in y:
                fail.append(f'pipeline-{name.lower()}.yml: projectName is not {name}')
            declared = set(re.findall(r'<SqlCmdVariable Include="(\w+)"', proj))
            passed = set(re.findall(r'/v:(\w+)=', y))
            if passed - declared:
                fail.append(f'pipeline-{name.lower()}.yml passes {", ".join(sorted(passed - declared))} which {name}.sqlproj does not declare')
            if declared - passed:
                fail.append(f'pipeline-{name.lower()}.yml does not pass {", ".join(sorted(declared - passed))} (declared in {name}.sqlproj)')
            for n, v in sorted(set(re.findall(r'/v:(\w+)=(\S+)', y))):
                if '<' in v:
                    warn.append(f'SQLCMD variable {n} of the DACPAC pipeline has no value yet (a DPV1 project variable: give it per environment, build_cicd.py)')
            for env in ENVS:
                m = re.search(rf'{env}:\s*targetServer: \'([^\']*)\'', y)
                if not m or '<' in m.group(1):
                    warn.append(f'{env}: targetServer of the DACPAC pipeline (SQL endpoint of the warehouse in the {env} workspace)')
        for env in ENVS:
            prof = os.path.join(build_dir, 'ci-cd', 'profiles')
            hit = [p for p in glob.glob(os.path.join(prof, f'*_{env.lower()}.yaml'))]
            ours = [p for p in hit if any(f"repositoryDirectory: '{d}'" in read_text(p, 'replace') for d in folders)]
            if not ours:
                fail.append(f'no ci-cd/profiles/<workspace>_{env.lower()}.yaml for {", ".join(folders) or "the workspace folder"} (nothing can deploy it to {env})')
            else:
                t = read_text(ours[0], 'replace')
                if f"environmentName: '{env}'" not in t or re.search(r"workspaceId: '[^']*<", t) or f"branchName: '{env.lower()}'" not in t:
                    warn.append(f'{env}: profile {os.path.basename(ours[0])} needs the workspace id of the {env} workspace (and environmentName / branchName {env.lower()})')
    return {'fail': fail, 'warn': warn}


SQL_WORDS = {'where', 'inner', 'left', 'right', 'outer', 'full', 'cross', 'join', 'on', 'union', 'group', 'order', 'having', 'with', 'select', 'from', 'set', 'into', 'values',
             'using', 'when', 'and', 'or', 'go', 'as', 'by', 'all', 'except', 'intersect', 'option', 'pivot', 'unpivot', 'tablesample'}


def input_refs(files):
    """Columns the code reads from each input table: {(inp schema, table): [column]} (lower-case keys, the case of the first use). A stub table of the
    EXT-LH project must hold every such column or the build fails with SQL71501 (unresolved reference): a view over [INP_X].[t] may read source columns
    the DW table of the same name does not have. Looks at alias.column and [INP_X].[t].column in every file."""
    refs = {}
    for f in files:
        t = re.sub(r'--[^\n]*|/\*.*?\*/', '', open(f, encoding='utf-8-sig', errors='replace').read(), flags=re.S)
        alias = {}
        for m in re.finditer(r'\[?(INP_\w+?)\]?\s*\.\s*\[?(\w+)\]?(?!\s*\.)(?:\s+(?:AS\s+)?\[?(\w+)\]?)?', t, re.I):
            key = (m.group(1).lower(), m.group(2).lower())
            refs.setdefault(key, {})
            names = {m.group(2).lower()}
            if m.group(3) and m.group(3).lower() not in SQL_WORDS:
                names.add(m.group(3).lower())
            for n in names:
                alias.setdefault(n, set()).add(key)
        for m in re.finditer(r'\[?(INP_\w+?)\]?\s*\.\s*\[?(\w+)\]?\s*\.\s*\[?(\w+)\]?', t, re.I):
            refs.setdefault((m.group(1).lower(), m.group(2).lower()), {}).setdefault(m.group(3).lower(), m.group(3))
        for n, keys in alias.items():
            for m in re.finditer(r'(?<![\w\]\.])\[?' + re.escape(n) + r'\]?\s*\.\s*\[?(\w+)\]?', t, re.I):
                for key in keys:
                    refs[key].setdefault(m.group(1).lower(), m.group(1))
    return {k: list(v.values()) for k, v in refs.items()}
