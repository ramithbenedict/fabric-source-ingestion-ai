"""Progress tracking and change log of a migration, per service offering and project (Fabric-AI-DEV-REPO format).

State: 4-migration-project-deliverables/<source-dataset|data-product>/<PROJECT>/0_progress_tracking/progress.json (never edit by hand).
Rendered on every call:
  <project>_tracking.md           one page: ID card, completion, stage status, gates, inputs, risks, then the change log (every activity)
  4-migration-project-deliverables/migration-portfolio.md   every project of both services: overview, stages per workflow, gates, risks,
                                                             change-log index
  4-migration-project-deliverables/migration-portfolio.md   all projects of both services

Usage (from the repository root; --service sds = Source Dataset, dp = Data Product):
  python -I 0-shared/scripts/track.py init   --service sds --project GEOS [--owner "<name>"]
  python -I 0-shared/scripts/track.py set    --service sds --project GEOS --stage S1 --status completed|in_progress|not_started|blocked [--note "<blocker>"]
  python -I 0-shared/scripts/track.py gate   --service sds --project GEOS --gate framing_approved --status completed [--evidence "<who / file>"]
  python -I 0-shared/scripts/track.py log    --service sds --project GEOS --stage S2 --type decision|issue|note|change --text "<what>"
  python -I 0-shared/scripts/track.py input  --service sds --project GEOS --item "<input received>"
  python -I 0-shared/scripts/track.py risk   --service sds --project GEOS --text "<risk>" | --close "<risk>"
  python -I 0-shared/scripts/track.py report [--service sds --project GEOS]
"""
import argparse, datetime, glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import paths, load_map, write, project_dir, SERVICE_DIR

STATUS = {'completed': '✅ completed', 'in_progress': '🟡 in progress', 'not_started': '⚪ not started', 'blocked': '⚠️ blocked', 'na': '⚫ n/a'}
LOGTYPE = {'completed': '✅ completed', 'started': '🟡 started', 'decision': '✔️ decision', 'issue': '⚠️ issue', 'note': 'ℹ️ note', 'change': '🔵 change', 'rollback': '❌ rollback'}
# What each status and activity type means: printed at the end of every tracking file
STATUS_MEANING = [
    ('✅ completed', 'Stage finished and its review passed, or gate met (evidence in the Evidence column).'),
    ('🟡 in progress', 'Started, not finished. The note says what is still pending.'),
    ('⚪ not started', 'Not started yet.'),
    ('⚠️ blocked', 'Cannot continue until an input, a decision or an ID arrives (the note names it). Also used to pause a project.'),
    ('⚫ n/a', 'Does not apply to this project.')]
LOGTYPE_MEANING = [
    ('🟡 started', 'A project or a stage began.'),
    ('✅ completed', 'A stage finished or a gate was met.'),
    ('✔️ decision', 'The owner or developer chose something that changes the scope or the design. Decisions on one object are also in `2-config/migration/scope-decisions.json`.'),
    ('⚠️ issue', 'A problem, missing input, risk or failed check. It stays open until a later decision or completed entry resolves it.'),
    ('🔵 change', 'A script or agent generated or changed files (build, re-generation, fix).'),
    ('ℹ️ note', 'Information recorded, such as an input received. No action needed.'),
    ('❌ rollback', 'An earlier change was undone.')]


def legend(log=True, status=True):
    L = []
    if status:
        L += ['', '## Status definitions', '', '| Status | Meaning |', '| --- | --- |'] + [f'| {k} | {v} |' for k, v in STATUS_MEANING]
    if log:
        L += ['', '## Activity types', '', '| Type | Meaning |', '| --- | --- |'] + [f'| {k} | {v} |' for k, v in LOGTYPE_MEANING]
    return L


WORKFLOWS = {
    'wf-1-framing': [('F1', 'Capture the request'), ('F2', 'Scope analysis'), ('F3', 'Target design'), ('F4', 'Migration plan and approval')],
    'wf-2-migration-source-dataset': [('S1', 'Catalog view and Lakehouse'), ('S2', 'Source to landing and RAW'), ('S3', 'RAW to Lakehouse tables'),
                                      ('S4', 'Orchestration and variable library'), ('S5', 'Gap review and readiness')],
    'wf-3-migration-data-product': [('D1', 'Extract legacy code'), ('D2', 'Translate to Fabric T-SQL'), ('D3', 'Database project, Warehouse, input Lakehouse'),
                                    ('D4', 'Pipelines and variable library'), ('D5', 'Equivalence tests'), ('D6', 'Gap review and readiness')],
    'wf-4-migration-dacpac': [('K1', 'Get dedicated-pool source'), ('K2', 'Retarget to Fabric Warehouse'), ('K3', 'Fix unsupported T-SQL'), ('K4', 'Build and compare')],
}
SERVICE_WF = {'sds': ['wf-1-framing', 'wf-2-migration-source-dataset'], 'dp': ['wf-1-framing', 'wf-3-migration-data-product', 'wf-4-migration-dacpac']}
GATES = {
    'sds': [('framing_approved', 'Framing approved by the owner'), ('name_check_resolved', 'Name check: no "not included" object left'),
            ('catalog_rows_match', 'Catalog view rows = DPV1 catalog script'), ('vl_main_complete', 'VL_MAIN: no `<to set>` value for DEV'),
            ('gap_review_passed', 'Gap review: no ❌ finding left')],
    'dp': [('framing_approved', 'Framing approved by the owner'), ('name_check_resolved', 'Name check: no "not included" object left'),
           ('reference_questions_answered', 'Key reference questions answered (04-key-reference-questions.md)'),
           ('sources_available', 'Every input source dataset exists in Fabric'), ('lint_zero_blocking', 'T-SQL lint: 0 blocking findings'),
           ('build_succeeds', 'Database project builds'), ('vl_main_complete', 'VL_MAIN: no `<to set>` value for DEV'), ('gap_review_passed', 'Gap review: no ❌ finding left')],
}
SVC_LABEL = {'sds': 'Source dataset', 'dp': 'Data product'}
today = lambda: f'{datetime.date.today():%Y-%m-%d}'
now = lambda: f'{datetime.datetime.now():%Y-%m-%d %H:%M}'


def folder(project, service):
    return project_dir(service, project, '0_progress_tracking')


def load(project, service):
    p = os.path.join(folder(project, service), 'progress.json')
    if not os.path.exists(p):
        raise SystemExit(f'No tracking for {SVC_LABEL[service]} {project}: run  track.py init --service {service} --project {project}')
    st = json.load(open(p, encoding='utf-8'))
    return st if 'stages' in st else init(project, service, quiet=True)  # only the framing inputs saved so far


def save(st):
    st['last_update'] = today()
    write(os.path.join(folder(st['project'], st['service']), 'progress.json'), json.dumps(st, indent=1, ensure_ascii=False) + '\n')
    render(st)
    portfolio()


def stage_keys(st):
    return [sid for wf in SERVICE_WF[st['service']] for sid, _ in WORKFLOWS[wf]]


def completion(st):
    keys = [k for k in stage_keys(st) if st['stages'].get(k, {}).get('status') != 'na']
    return round(100 * sum(1 for k in keys if st['stages'].get(k, {}).get('status') == 'completed') / len(keys)) if keys else 0


def current(st):
    return next((k for k in stage_keys(st) if st['stages'].get(k, {}).get('status', 'not_started') not in ('completed', 'na')), 'done')


def open_gates(st):
    return sum(1 for gid, _ in GATES[st['service']] if st['gates'].get(gid, {}).get('status') != 'completed')


def render(st):
    """<project>_tracking.md: status first, then the full change log, on one page."""
    p, svc, f = st['project'], st['service'], folder(st['project'], st['service'])
    low = p.lower()
    cur = current(st)
    L = [f'# Tracking: {p} ({SVC_LABEL[svc]})', '', f"Last update: {st['last_update']}", '',
         'Sections: [ID card](#project-id-card) · [Stages](#workflow-and-stage-status) · [Gates](#mandatory-gates) · [Inputs](#inputs-received) · '
         '[Risks](#open-risks--blockers) · [Change log](#change-log) · [Definitions](#status-definitions)', '', '## Project ID Card']
    L += [f'- **{k}**: {v}' for k, v in st['card'].items()]
    L += [f"- **Created on**: {st['created']}", f"- **Last updated**: {st['last_update']}", '', '## Workflow and Stage Status', f'- **Completion**: {completion(st)}%',
          f"- **Current stage**: {cur if cur != 'done' else '✅ all stages completed'}", '',
          '| # | Workflow | Stage Name | Status | Notes |', '| --- | --- | --- | --- | --- |']
    for wf in SERVICE_WF[svc]:
        for sid, name in WORKFLOWS[wf]:
            s_ = st['stages'].get(sid, {})
            stat = s_.get('status', 'not_started')
            L.append(f"| {sid} | `{wf}` | {name} | {STATUS[stat]} | {s_.get('note', '') if stat in ('in_progress', 'blocked') else ''} |")
    L += ['', '## Mandatory Gates', '', '| Gate | Status | Evidence |', '| --- | --- | --- |']
    L += [f"| {gname} | {STATUS[st['gates'].get(gid, {}).get('status', 'not_started')]} | {st['gates'].get(gid, {}).get('evidence', '')} |" for gid, gname in GATES[svc]]
    pin = st.get('project_inputs') or {}
    L += ['', '## Inputs Received', ''] + ([f'- [x] {k.replace("_", " ").capitalize()}: `{v}`' for k, v in pin.items() if v] + [f'- [x] {i}' for i in st['inputs']] or ['- [ ] None yet'])
    L += ['', '## Open Risks / Blockers', ''] + ([f'- ⚠️ {r}' for r in st['risks']] or ['- None identified yet'])
    L += ['', '## Change Log', '', 'Chronological order: the first activity is at the top.', '',
          '| # | Date | Workflow | Stage | Type | Activity |', '| --- | --- | --- | --- | --- | --- |']
    L += [f"| {i} | {e['at']} | {e.get('workflow') or '-'} | {e.get('stage') or '-'} | {LOGTYPE.get(e['type'], e['type'])} | {e['text']} |" for i, e in enumerate(st['log'], 1)]
    write(os.path.join(f, f'{low}_tracking.md'), '\n'.join(L + legend()) + '\n')
    for old in (f'{low}_progress_tracking.md', f'{low}_change_log.md', 'project-inputs.json'):  # former layout
        if os.path.exists(os.path.join(f, old)):
            os.remove(os.path.join(f, old))


ICON = {k: v.split(' ')[0] for k, v in STATUS.items()}


def service_section(svc, sdir, states):
    """Section of the portfolio for one service: overview, stages per workflow, gates, risks, change-log index."""
    label = SVC_LABEL[svc]
    link = lambda p, anchor='': f'[{p}]({sdir}/{p.lower()}/0_progress_tracking/{p.lower()}_tracking.md{anchor})'
    P = [f'## {label} Migration', '', '| Project | Completion | Current stage | Open gates | Risks | Last update |', '| --- | --- | --- | --- | --- | --- |']
    P += [f"| {link(p)} | {completion(st)}% | {'✅ done' if current(st) == 'done' else current(st)} | {open_gates(st)} | {len(st['risks'])} | {st['last_update']} |"
          for p, st in states] or ['| - | - | - | - | - | - |']
    for wf in SERVICE_WF[svc]:
        stages = WORKFLOWS[wf]
        P += ['', f'### `{wf}`', '', '| Project | ' + ' | '.join(f'{sid} {name}' for sid, name in stages) + ' |', '| --- |' + ' :---: |' * len(stages)]
        P += [f'| {p} | ' + ' | '.join(ICON[st['stages'].get(sid, {}).get('status', 'not_started')] for sid, _ in stages) + ' |' for p, st in states] or \
             ['| - |' + ' - |' * len(stages)]
    P += ['', '### Mandatory gates', '', '| Project | ' + ' | '.join(g for g, _ in GATES[svc]) + ' |', '| --- |' + ' :---: |' * len(GATES[svc])]
    P += [f'| {p} | ' + ' | '.join(ICON[st['gates'].get(g, {}).get('status', 'not_started')] for g, _ in GATES[svc]) + ' |' for p, st in states] or \
         ['| - |' + ' - |' * len(GATES[svc])]
    P += ['', '### Open risks', ''] + ([f'- ⚠️ **{p}**: {r}' for p, st in states for r in st['risks']] or ['- None'])
    P += ['', '### Change log index', '', 'One row per project; the full history is in the change log of its tracking page.', '',
          '| Project | Started | Last activity | Activities | Decisions | Open issues | Last change |', '| --- | --- | --- | --- | --- | --- | --- |']
    for p, st in sorted(states, key=lambda x: x[1]['log'][0]['at'] if x[1]['log'] else ''):
        lg = st['log']
        last = lg[-1] if lg else {'at': '-', 'text': '-'}
        P.append(f"| {link(p, '#change-log')} | {lg[0]['at'] if lg else '-'} | {last['at']} | {len(lg)} | {sum(e['type'] == 'decision' for e in lg)} | "
                 f"{len(st['risks'])} | {last['text'][:90]}{'…' if len(last['text']) > 90 else ''} |")
    if not states:
        P.append('| - | - | - | - | - | - | - |')
    return P


def portfolio():
    """4-migration-project-deliverables/migration-portfolio.md: every project of both services on one page."""
    root = paths()['deliverables_root']
    L = ['# Migration Portfolio', '', f'Last update: {today()}', '',
         'Every project of both service offerings. Generated by `track.py` from each project\'s `progress.json`; do not edit. '
         'Each project has one tracking page (status and change log).', '', '[Source Dataset Migration](#source-dataset-migration) · [Data Product Migration](#data-product-migration)', '']
    for svc, sdir in SERVICE_DIR.items():
        base = os.path.join(root, sdir)
        states = []
        for p in sorted(os.listdir(base)) if os.path.isdir(base) else []:
            j = os.path.join(base, p, '0_progress_tracking', 'progress.json')
            if os.path.exists(j):
                st = json.load(open(j, encoding='utf-8'))
                if 'stages' in st:
                    states.append((st['project'], st))  # folder name is lowercase, the project name keeps its case
        L += service_section(svc, sdir, states) + ['']
        for old in ('progress_tracking.md', 'change_log.md'):  # former per-service pages
            if os.path.exists(os.path.join(base, old)):
                os.remove(os.path.join(base, old))
    try:  # keep the status column of 5-migration-hub/migration-scope-index.md current
        from refresh_hub import write_index
        write_index(paths()['hub_root'], load_map())
    except SystemExit:
        pass  # no migration map yet: refresh_hub.py writes the index
    from common import write_if_changed
    write_if_changed(os.path.join(root, 'migration-portfolio.md'), '\n'.join(L + legend()) + '\n')


def wf_of(sid):
    return next((wf for wf, st in WORKFLOWS.items() if any(s == sid for s, _ in st)), '')


def add_log(st, typ, text, stage=None):
    same = next((e for e in reversed(st['log'][-6:]) if e['type'] == typ and e['text'] == text and e.get('stage') == stage), None)
    if same and typ in ('change', 'issue', 'note'):
        st['log'].remove(same)
    st['log'].append({'at': now(), 'type': typ, 'text': text, 'stage': stage, 'workflow': wf_of(stage) if stage else ''})


def init(project, service, owner=None, quiet=False):
    p = os.path.join(folder(project, service), 'progress.json')
    st = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None
    if st is None or 'stages' not in st:  # new, or only the framing inputs saved so far
        pin = (st or {}).get('project_inputs')
        st = {'project': project, 'service': service, 'created': today(), 'stages': {}, 'gates': {}, 'inputs': [], 'risks': [], 'log': [], 'card': {}}
        if pin:
            st['project_inputs'] = pin
        add_log(st, 'started', f'{SVC_LABEL[service]} migration started')
    m = load_map()
    card = st['card']
    card['Project name'] = project
    card['Service offering'] = SVC_LABEL[service]
    if service == 'sds' and project in m['sds']:
        S = m['sds'][project]
        card['Domain'] = S['domain'] + ('' if S['domain_confirmed'] else ' (to confirm)')
        card['Target'] = f"`{S['ws']}` / `{S['lakehouse']}`"
        card['Source systems'] = ', '.join(sorted({m['objects']['linkedService'].get(n, {}).get('type', '?') for n in S['linked_services']
                                                  if m['objects']['linkedService'].get(n, {}).get('type') not in ('AzureBlobFS', 'AzureSqlDW', 'AzureKeyVault', 'AzureSqlDatabase')})) or 'TBD'
        card['Ingestion'] = 'Directly from the source: databases => Files/raw (parquet) => tables; APIs and files => Files/landing (as delivered) => Files/raw (parquet) => tables. No shortcut.'
    if service == 'dp' and project in m['dp']:
        D = m['dp'][project]
        card['Data product group'] = D['group'] + ('' if D['group_confirmed'] else ' (to confirm)')
        card['Target'] = f"`{D['ws']}` / `{D['warehouse']}` / `{D['dbproject']}`"
        card['Input source datasets'] = ', '.join(D['upstream']) or 'none'
    proj = next((x for x in m['projects'] if x['scope'] == project), {})
    det = proj.get('detected') or {}
    card['Complexity (repo)'] = f"{det.get('complexity', 'n/a')} ({det.get('objects', 0)} objects)"
    card['Register'] = ', '.join(f"{r['project']} ({r['complexity']})" for r in proj.get('register', [])) or 'not registered'
    card['Owner'] = owner or card.get('Owner', 'TBD')
    if not quiet:
        save(st)
    return st


def active_projects():
    """Projects of both services with a stage in progress (a paused project is set to blocked, so it does not count)."""
    out = []
    for svc, sdir in SERVICE_DIR.items():
        for j in sorted(glob.glob(os.path.join(paths()['deliverables_root'], sdir, '*', '0_progress_tracking', 'progress.json'))):
            st = json.load(open(j, encoding='utf-8'))
            if any(s.get('status') == 'in_progress' for s in st.get('stages', {}).values()):
                out.append((svc, st['project']))
    return out


def ensure_single_active(project, service, allow=False):
    """One project migration at a time: stop when another project is in progress, unless explicitly allowed."""
    others = [(s, p) for s, p in active_projects() if (s, p) != (service, project)]
    if others and not allow:
        who = ', '.join(f'{SVC_LABEL[s].lower()} {p}' for s, p in others)
        raise SystemExit(f'One project migration at a time: {who} is in progress. Finish it, or pause it first:\n'
                         f'  python -I 0-shared/scripts/track.py set --service <sds|dp> --project <PROJECT> --stage <ID> --status blocked --note "paused"\n'
                         f'Use --parallel only when the owner agreed to run two projects at once.')


def set_status(project, service, stage, status, note=None):
    st = load(project, service)
    st['stages'][stage] = {'status': status, 'note': note or '', 'at': now()}
    add_log(st, {'completed': 'completed', 'in_progress': 'started', 'blocked': 'issue'}.get(status, 'change'),
            f"{dict(WORKFLOWS[wf_of(stage)])[stage]}: {STATUS[status]}" + (f' - {note}' if note else ''), stage)
    save(st)


def set_gate(project, service, gate, status='completed', evidence=''):
    st = load(project, service)
    st['gates'][gate] = {'status': status, 'evidence': evidence}
    add_log(st, 'completed' if status == 'completed' else 'issue', f"Gate {gate}: {STATUS[status]}" + (f' ({evidence})' if evidence else ''))
    save(st)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=['init', 'set', 'gate', 'log', 'input', 'risk', 'report'])
    ap.add_argument('--service', choices=['sds', 'dp']); ap.add_argument('--project'); ap.add_argument('--owner')
    ap.add_argument('--stage'); ap.add_argument('--status', choices=list(STATUS)); ap.add_argument('--note')
    ap.add_argument('--gate'); ap.add_argument('--evidence'); ap.add_argument('--type', choices=list(LOGTYPE)); ap.add_argument('--text')
    ap.add_argument('--item'); ap.add_argument('--close')
    a = ap.parse_args()
    if a.action == 'report':
        portfolio()
        if a.project and a.service:
            st = load(a.project, a.service); render(st)
            print(f"{SVC_LABEL[a.service]} {a.project}: {completion(st)}% · current {current(st)} · open gates {open_gates(st)}")
        print('portfolio: ' + os.path.join(paths()['deliverables_root'], 'migration-portfolio.md'))
        return
    if not (a.service and a.project):
        sys.exit('--service and --project are required')
    if a.action == 'init':
        init(a.project, a.service, a.owner); print(f'{SVC_LABEL[a.service]} {a.project}: tracking ready'); return
    if a.action == 'set':
        set_status(a.project, a.service, a.stage, a.status, a.note)
    elif a.action == 'gate':
        set_gate(a.project, a.service, a.gate, a.status or 'completed', a.evidence or '')
    else:
        st = load(a.project, a.service)
        if a.action == 'log':
            add_log(st, a.type or 'note', a.text, a.stage)
        elif a.action == 'input' and a.item not in st['inputs']:
            st['inputs'].append(a.item); add_log(st, 'note', f'Input received: {a.item}')
        elif a.action == 'risk':
            if a.close:
                st['risks'] = [r for r in st['risks'] if r != a.close]; add_log(st, 'completed', f'Risk closed: {a.close}')
            else:
                st['risks'].append(a.text); add_log(st, 'issue', f'Risk opened: {a.text}')
        save(st)
    st = load(a.project, a.service)
    print(f"{SVC_LABEL[a.service]} {a.project}: {completion(st)}% · current stage {current(st)}")


if __name__ == '__main__':
    main()
