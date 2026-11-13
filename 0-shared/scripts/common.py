"""Shared helpers: repository paths and the migration map."""
import json, os, re, sys

for _s in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252
    try:
        _s.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))


def paths():
    cfg = json.load(open(os.path.join(ROOT, '2-config', 'migration', 'paths.json'), encoding='utf-8'))
    resolve = lambda p: p if not p or os.path.isabs(p) else os.path.abspath(os.path.join(ROOT, p))
    return {k: resolve(v) for k, v in cfg.items() if not k.startswith('_')}


SERVICE_DIR = {'sds': 'source-dataset', 'dp': 'data-product'}


def project_dir(service, project, *parts):
    """4-migration-project-deliverables/<source-dataset|data-product>/<PROJECT>/<parts…>

    Inside a project: 0_progress_tracking/, 1-framing/, 2-legacy-code/, 3-build/<stage>/, 4-dacpac/ (data product), review/."""
    return os.path.join(paths()['deliverables_root'], SERVICE_DIR[service], project.lower(), *parts)  # repo folders are lowercase


def deploy_dir(service, project, *parts):
    """3-build/fabric-deployment/: the same layout as REPO-FABRIC-DEPLOYMENT (2-config/conventions/01-general/fabric-git-repo-structure.md):
    <WORKSPACE_FOLDER>/ (no environment suffix: VL_MAIN at the root, one folder per source with 0-ORCHESTRATION, 1-SOURCE_TO_RAW,
    2-RAW_TO_DELTA and the Lakehouse) and database-projects/DPG-<GROUP>/. Copy it to the deployment repository unchanged."""
    return project_dir(service, project, '3-build', 'fabric-deployment', *parts)


def notes_path(service, project, name):
    """3-build/build-notes/<name>: what each build stage did (merge logs, catalog view, table mapping). Not deployed."""
    return project_dir(service, project, '3-build', 'build-notes', name)


def work_path(service, project, *parts):
    """3-build/_work/: generated files that are neither deployed nor meant to be read (converted SQL, machine JSON). One folder, safe to ignore."""
    return project_dir(service, project, '3-build', '_work', *parts)


def load_map():
    p = os.path.join(paths()['hub_root'], 'migration-map.json')
    if not os.path.exists(p):
        raise SystemExit('migration-map.json not found: run  python -I 0-shared/scripts/refresh_hub.py  first')
    m = json.load(open(p, encoding='utf-8'))
    import project_inputs  # the workspace chosen at framing replaces the derived one
    return project_inputs.apply_to_map(m)


def resolve_scope(m, service, ident):
    """Service 'sds' takes a source name; 'dp' takes a project, master pipeline or DW/DM schema."""
    q = ident.strip().upper()
    coll = m['sds'] if service == 'sds' else m['dp']
    if q in coll:
        return q, 'name'
    if service == 'dp' and q in m['lookup']:
        return m['lookup'][q], ('schema ' if q.startswith(('DW_', 'DM_')) else 'master pipeline ') + q
    near = [k for k in coll if q in k]
    if len(near) == 1:
        return near[0], 'closest name'
    raise SystemExit(f'No {"source dataset" if service == "sds" else "data product"} matches "{ident}". '
                     f'Candidates: {", ".join(near[:10]) or "none"}. Check 5-migration-hub/dpv1-fabric-migration-hub.html.')


# VL_MAIN variables whose value differs per source. VL_MAIN is one item per workspace and a workspace can hold several sources
# (Platform-Hub: GEOS and CORNERSTONE), so these names always carry the source: <SRC>_CATALOG_VIEW_NAME, <SRC>_LH_CONN_ID…
# The same name is used in the expression, in the pipeline's libraryVariables block and in VL_MAIN.
SOURCE_VARS = ('CATALOG_VIEW_NAME', 'CATALOG_WATERMARK_TABLE_NAME', 'CATALOG_WAREHOUSE_NAME', 'CATALOG_WAREHOUSE_ID',
               'CATALOG_WAREHOUSE_SQL_ENDPOINT', 'CATALOG_WAREHOUSE_CONN_ID', 'CATALOG_WAREHOUSE_WORKSPACE_ID', 'LH_CONN_ID', 'LH_NAME')


# Warehouse parameters shared by every source that keeps its catalog view in the same common warehouse (project input catalog_warehouse,
# e.g. WH_CATALOG_COMMON): one set of CATALOG_WAREHOUSE_* values in VL_MAIN instead of one set per source.
COMMON_WH_VARS = ('CATALOG_WAREHOUSE_NAME', 'CATALOG_WAREHOUSE_ID', 'CATALOG_WAREHOUSE_SQL_ENDPOINT', 'CATALOG_WAREHOUSE_CONN_ID', 'CATALOG_WAREHOUSE_WORKSPACE_ID')


def project_catalog_warehouse(source):
    """Common catalog warehouse chosen for a source dataset during framing (progress.json project_inputs.catalog_warehouse), or ''."""
    if not source:
        return ''
    p = project_dir('sds', source, '0_progress_tracking', 'progress.json')
    return read_json(p).get('project_inputs', {}).get('catalog_warehouse', '') if exists(p) else ''


def project_catalog_workspace(source):
    """Workspace chosen in framing for the catalog warehouse when it is not the target workspace of the source (project_inputs.catalog_workspace), or ''."""
    if not source:
        return ''
    p = project_dir('sds', source, '0_progress_tracking', 'progress.json')
    return read_json(p).get('project_inputs', {}).get('catalog_workspace', '') if exists(p) else ''


def catalog_remote(sp, source):
    """True when the catalog warehouse is in another workspace than the source's own (shared workspace or a workspace chosen in framing):
    the pipelines then read its workspace id from VL_MAIN."""
    return sp.get('catalog_warehouse_location') == 'shared' or bool(project_catalog_workspace(source))


def vl_name(source, base):
    """VL_MAIN name of a variable for one source: GEOS + CATALOG_VIEW_NAME => GEOS_CATALOG_VIEW_NAME; other names unchanged.
    The warehouse parameters of a source in a common catalog warehouse are the plain CATALOG_WAREHOUSE_* (shared by every source)."""
    if base in COMMON_WH_VARS and project_catalog_warehouse(source):
        return base
    return f"{source.upper().replace('-', '_')}_{base}" if base in SOURCE_VARS else base


def one_sync_findings(text):
    """What would make Fabric's Git import fail on a pipeline-content.json ("Failed to discover dependencies: Object reference not set"),
    as a list of messages. Used by the review (S5) and by deploy_publish.py, which refuses to publish a pipeline with findings.
    Rules: 3-workflows/wf-2-migration-source-dataset/deployment-design.md"""
    bad = []
    if '__VL_MAIN.' in text:
        bad.append('deploy token __VL_MAIN.<NAME>__ (only fabric-cicd replaces it; a Git sync fails with "Object reference not set")')
    try:
        doc = json.loads(text.lstrip('﻿'))
    except ValueError:
        return bad + ['invalid JSON']

    def walk(o):
        if isinstance(o, dict):
            if o.get('type') in ('Lakehouse', 'DataWarehouse') and isinstance(o.get('typeProperties'), dict):
                tp = o['typeProperties']
                for k in ('artifactId', 'workspaceId') + (('endpoint',) if o['type'] == 'DataWarehouse' else ()):
                    v = str(tp.get(k, ''))
                    if not v.startswith('@'):
                        bad.append(f"{o['type']} {k} = '{v or 'missing'}': use a VL_MAIN expression (workspaceId: @pipeline().DataFactory)")
                if not str(o.get('externalReferences', {}).get('connection', '')).startswith('@'):  # RMA, 2026-10-27 (B59)
                    bad.append(f"{o['type']} without externalReferences.connection: use @pipeline().libraryVariables.<SRC>_LH_CONN_ID / <SRC>_CATALOG_WAREHOUSE_CONN_ID")
            if isinstance(o.get('linkedService'), dict) and o['linkedService'].get('properties', {}).get('type') in ('Lakehouse', 'DataWarehouse'):
                bad.append('linkedService block for a Lakehouse / Warehouse: use connectionSettings (skill-fabric-create-pipeline)')
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(doc)
    return bad


def catalog_warehouse(sp, source=None):
    """Name of the catalog warehouse of a source: WH_CATALOG_<SOURCE> in the source's own workspace for now, the common one once shared.
    Without a source, the pattern (for pages that describe every source). A common warehouse chosen in framing wins."""
    if project_catalog_warehouse(source):
        return project_catalog_warehouse(source)
    if sp.get('catalog_warehouse_location') == 'shared':
        return sp['catalog_warehouse']
    pattern = sp.get('catalog_warehouse_pattern', 'WH_CATALOG_{SOURCE}')
    return pattern.format(SOURCE=source.upper().replace('-', '_')) if source else pattern.replace('{SOURCE}', '<SOURCE>')


NOTE_ORDER = ['S1-catalog-view', 'S1-lakehouse', 'S2-source-to-raw', 'S3-raw-to-tables', 'S4-orchestration', 'hand-over',
              'D1-legacy-code', 'D2-translation', 'D3-table-mapping', 'D4-pipelines', 'D5-equivalence']


def write_section(path, key, text, title, intro):
    """Replace (or add) one section of a page made of sections; sections stay in stage order."""
    old = read_text(path, 'replace') if exists(path) else ''
    found = dict(re.findall(r'<!-- note: ([\w-]+) -->\n(.*?)<!-- /note -->\n', old, re.S))
    found[key] = '\n'.join(('#' + l if l.startswith('#') else l) for l in text.strip('\n').split('\n')) + '\n'  # its title becomes a section
    keys = sorted(found, key=lambda k: (NOTE_ORDER.index(k) if k in NOTE_ORDER else len(NOTE_ORDER), k))
    anchor = lambda k: re.sub(r'[^a-z0-9 -]', '', found[k].split('\n')[0].lstrip('#').strip().lower()).replace(' ', '-')
    head = [title, '', intro, '', ' · '.join(f'[{k}](#{anchor(k)})' for k in keys), '']
    write(path, '\n'.join(head + [f'<!-- note: {k} -->\n{found[k]}<!-- /note -->' for k in keys]) + '\n')
    return path


def write_note(service, project, key, text, details=None):
    """One stage note as a section of 3-build/build-notes/build-notes.md: what the stage built, kept and changed (short).
    Long reference tables go to the same section of 3-build/analysis/build-details.md (details). A former <key>.md is removed."""
    path = write_section(notes_path(service, project, 'build-notes.md'), key, text, f'# Build notes: {project}',
                         'What each build stage generated and what changed. Long reference tables, when a stage writes them: `../analysis/build-details.md`. '
                         'Sections are rewritten when their stage runs again.')
    if details:
        write_section(project_dir(service, project, '3-build', 'analysis', 'build-details.md'), key, details, f'# Build details: {project}',
                      'Reference tables behind `../build-notes/build-notes.md`, one section per stage. Generated; do not edit.')
    stale = notes_path(service, project, f'{key}.md')
    if exists(stale):
        os.remove(lp(stale))
    return path


def track_event(project, service, stage, text, typ='change', gate=None, gate_ok=None, evidence=''):
    """Log a script activity in the project's change log (and optionally a gate), if tracking exists."""
    import track
    p = project_dir(service, project, '0_progress_tracking', 'progress.json')
    if not os.path.exists(p) or 'stages' not in read_json(p):  # no tracking yet (framing inputs only)
        return
    st = track.load(project, service)
    track.add_log(st, typ, text, stage)
    if gate:
        st['gates'][gate] = {'status': 'completed' if gate_ok else 'in_progress', 'evidence': evidence}
    track.save(st)


def lp(path):
    """Long-path safe form on Windows: the deployment-repository layout inside the project folder can pass 260 characters."""
    path = os.path.abspath(path)
    return '\\\\?\\' + path if os.name == 'nt' and len(path) >= 240 and not path.startswith('\\\\?\\') else path


def unlp(path):
    return path[4:] if path.startswith('\\\\?\\') else path


def read_text(path, errors='strict'):
    with open(lp(path), encoding='utf-8-sig', errors=errors) as f:
        return f.read()


def read_json(path):
    return json.loads(read_text(path).lstrip('﻿'))  # Fabric writes some files with a BOM


def exists(path):
    return os.path.exists(lp(path))


def walk_files(root, names=None, exts=None):
    """All files under root (long-path safe), optionally filtered by exact file name or by extension."""
    for d, _, files in os.walk(lp(root)):
        for f in files:
            if (names is None or f in names) and (exts is None or f.lower().endswith(exts)):
                yield unlp(os.path.join(d, f))


VOLATILE = re.compile(r'"generated_at":\s*"[^"]*"|^Last update: .*$|^# Migration hub refresh · .*$|\*\*Hub and index generated\*\*: [0-9: -]+', re.M)


def write_if_changed(path, text):
    """Write a generated file only when something other than its timestamps changed, so a refresh with nothing new
    leaves Git clean. Returns True when the file was written."""
    if path.endswith('.md'):  # same conversion as write(), so the comparison sees what would be written
        text = text.replace('→', '=>').replace('—', '-')
    if exists(path):
        old = read_text(path, 'replace')
        if VOLATILE.sub('', old.replace('\r\n', '\n')) == VOLATILE.sub('', text.replace('\r\n', '\n')):
            return False
    write(path, text)
    return True


def write(path, text):
    if path.endswith('.md'):  # Fabric-AI-DEV-REPO markdown convention: '=>' not '→', '-' not '—'
        text = text.replace('→', '=>').replace('—', '-')
    os.makedirs(lp(os.path.dirname(path)), exist_ok=True)
    for attempt in range(5):  # Windows refuses a write while another program (editor, Git, sync tool) briefly holds the file
        try:
            with open(lp(path), 'w', encoding='utf-8', newline='\n') as f:
                f.write(text)
            return
        except OSError as exc:
            if attempt == 4 or exc.errno not in (13, 22):
                raise
            import time
            time.sleep(0.5 * (attempt + 1))
