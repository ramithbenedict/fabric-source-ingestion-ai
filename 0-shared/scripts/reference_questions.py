"""Key reference questions of framing: what the developer must confirm so the source dataset and the data product map correctly.

Usage (from the repository root):
  python -I 0-shared/scripts/reference_questions.py show   --service dp  --id GAIA        # the questions with evidence and status
  python -I 0-shared/scripts/reference_questions.py answer --service dp  --id GAIA --q Q22 --text "Build it from the DPV1 code"
  python -I 0-shared/scripts/reference_questions.py status --service dp  --id GAIA        # open required questions (exit 2 when some are open)

frame_scope.py writes 1-framing/04-key-reference-questions.md with this. Questions: 2-config/migration/framing-questions.json. The evidence is read
from DPV1, the migration map and the deployment repository; answers are kept in 1-framing/analysis/reference-answers.json and survive a re-run.
Every required question answered => gate reference_questions_answered (data product). For a source dataset an open required question is a review warning.
"""
import argparse, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, paths, load_map, resolve_scope, write, project_dir, read_json, exists
import classify_scenarios as cs

ITEM_SUFFIX = ('.Lakehouse', '.Warehouse', '.DataPipeline', '.Notebook', '.Report', '.SemanticModel', '.VariableLibrary')


def questions():
    return read_json(os.path.join(ROOT, '2-config', 'migration', 'framing-questions.json'))['questions']


def tok_rx(scope):
    return re.compile(r'(?<![A-Za-z])' + r'[_\- ]?'.join(re.escape(x) for x in re.split(r'[_\- ]', scope)) + r'(?![A-Za-z])', re.I)


def dpv1_texts(kinds=('notebook', 'pipeline', 'sqlscript')):
    for kind in kinds:
        d = os.path.join(paths()['dpv1_export_root'], kind)
        for f in sorted(os.listdir(d)):
            if f.endswith('.json'):
                try:
                    yield kind, f[:-5], open(os.path.join(d, f), encoding='utf-8-sig', errors='replace').read()
                except OSError:
                    pass


def fabric_items(repo, scope):
    """Items of the deployment repository whose name contains the scope (up to three levels deep)."""
    if not repo or not os.path.isdir(repo):
        return None
    rx, out = tok_rx(scope), []
    for root, dirs, _ in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules')]
        depth = os.path.relpath(root, repo).count(os.sep)
        if depth > 3:
            dirs[:] = []
        for d in list(dirs):
            if rx.search(d) and (d.endswith(ITEM_SUFFIX) or d.startswith(('DPG-', 'DP_', 'WH_', 'LH_')) or depth <= 1):
                out.append(os.path.relpath(os.path.join(root, d), repo).replace(os.sep, '/'))
    return sorted(set(out))[:14]


def triggers_of(S):
    out = []
    for n in S['triggers']:
        j = (cs.dpv1('trigger', n) or {}).get('properties', {})
        r = (j.get('typeProperties') or {}).get('recurrence') or {}
        sch = r.get('schedule') or {}
        out.append(f"{n} ({j.get('runtimeState', '?')}, {r.get('frequency', '?')} every {r.get('interval', '?')}{', hours ' + ','.join(map(str, sch['hours'])) if sch.get('hours') else ''})")
    return out


def evidence(service, scope, S, m, scen, pin):
    """Evidence text per evidence key, from the code and the repositories. Empty string = nothing found."""
    ev, rx = {}, tok_rx(scope)
    owned = {r['v1'] for s in ('sds', 'dp') for X in m[s].values() for r in X['rows']}
    mine = {r['v1'] for X in (m['sds'].get(scope), m['dp'].get(scope)) if X for r in X['rows']}  # both services of the project
    repo = (pin or {}).get('deployment_repo')
    items = fabric_items(repo, scope)
    ev['names'] = (f"workspace {S['ws']}; " + (f"Lakehouse {S['lakehouse']}, folder {S['folder']}" if service == 'sds' else f"warehouse {S['warehouse']}, project {S['dbproject']}, group {S['group']}"))
    ev['existing_items'] = ('deployment repo not set yet' if items is None else ('; '.join(items) if items else 'none found in the deployment repo'))
    ev['orphans'] = ', '.join(scen.get('orphans', [])[:8]) + (' ...' if len(scen.get('orphans', [])) > 8 else '') if scen.get('orphans') else ''
    ev['triggers'] = '; '.join(triggers_of(S)) or 'no trigger in the scope'
    entry = set(S.get('entry', [])) | set(S.get('masters', []))
    mon = sorted({f'{k}/{n}' for k, n, t in dpv1_texts(('sqlscript', 'notebook')) if n not in mine and any(e in t for e in entry)})[:6] if entry else []
    ev['monitoring'] = ', '.join(mon) if mon else 'no other config mentions the entry pipelines'
    pat = re.compile(r'(?i)\b(?:spot|inp|dw|dm|out)_' + re.escape(scope.replace('-', '_')) + r'\b')
    readers = sorted({f'{k}/{n}' for k, n, t in dpv1_texts() if n not in mine and pat.search(t.replace('\\n', ' '))})[:8]
    cons = [x for x in (S.get('read_by_products') or [])] + [c.get('dp') for c in (S.get('consumers') or [])]
    ev['readers'] = '; '.join(filter(None, [('data products: ' + ', '.join(str(c) for c in cons if c)) if any(cons) else '', ('also read by: ' + ', '.join(readers)) if readers else ''])) or 'no reader found in DPV1 (reports are not in the export)'
    if service == 'sds':
        types = scen['evidence'].get('connectors', [])
        secrets = sorted({x for k, n, t in dpv1_texts(('pipeline',)) if n in mine for x in re.findall(r'secrets/([A-Za-z0-9\-_]+)', t)})
        ev['connections'] = f"linked services: {', '.join(S['linked_services']) or 'none'}; types: {', '.join(types) or 'none'}; Key Vault secrets: {', '.join(secrets) or 'none found'}"
        ev['load_mode'] = f"scenario {scen['scenario']}" + ('; catalog flags exist but DPV1 never reads them: it loads in full' if 'M-FLAGS-UNUSED' in scen['modifiers'] else '')
        used = set()
        for dpn, D in m['dp'].items():
            if scope in D['upstream']:
                txt = '\n'.join(t for k, n, t in dpv1_texts() if n in {r['v1'] for r in D['rows']}).lower()
                used |= {c['table'].lower() for c in S['catalog'] if re.search(r'(?<![a-z0-9_])' + re.escape(c['table'].lower()) + r'(?:_vw)?(?![a-z0-9_])', txt)}
        unused = sorted(c['table'] for c in S['catalog'] if c['table'].lower() not in used)
        has_dp = any(scope in D['upstream'] for D in m['dp'].values())
        ev['tables_unused'] = (f"{len(S['catalog'])} catalog tables; not read by any data product: {', '.join(unused[:10])}{' ...' if len(unused) > 10 else ''}" if has_dp and unused else
                               (f"{len(S['catalog'])} catalog tables, all read by a data product" if has_dp else f"{len(S['catalog'])} catalog tables; no data product reads this source"))
        ev['extra_inputs'] = ('; '.join(f"{x}" for x in scen['modifiers'] if x in ('M-MIXED', 'M-EXCEL', 'M-SHAREPOINT-GRAPH')) + ' (see the DP code of the products that read it for the table names)') if 'M-MIXED' in scen['modifiers'] else ''
        ev['rest_incremental'] = 'REST source with a watermark in the request' if 'M-REST-INCREMENTAL' in scen['modifiers'] else ''
        ev['volume'] = f"{S['identified'].get('Catalog table', 0)} tables; sizes are not in the DPV1 export"
    else:
        import source_contract
        _, srcs = source_contract.show(scope)
        ev['sources'] = '; '.join(f"{x['source']}: " + ('not migrated (no contract)' if not x['contract'] else f"contract {'ready' if x['ready'] else 'not finished'}, {len(x['tables_used'])}/{x['tables_total']} tables used") for x in srcs) or 'no source dataset'
        sql = cs.sql_of(S).lower()
        refs = sorted({f'{a}.{b}' for a, b in re.findall(r'\b(inp_[a-z0-9_]+|spot_[a-z0-9_]+)\.\[?(?:dbo\.)?\[?([a-z0-9_]+)', sql) if b not in ('sp_create_spot_view', 'sp_meta_create_inp_view')})
        by = {}
        for r in refs:
            by.setdefault(r.split('.')[0], []).append(r.split('.')[1])
        known = {c['table'].lower() for u in S['upstream'] for c in m['sds'].get(u, {}).get('catalog', [])}
        notcat = sorted({t for ts in by.values() for t in ts if re.sub(r'_vw$', '', t) not in known})
        ev['tables_read'] = '; '.join(f"{k}: {len(v)} objects" for k, v in sorted(by.items())) + (f"; not in a source catalog: {', '.join(notcat[:10])}{' ...' if len(notcat) > 10 else ''}" if notcat else '')
        e = scen['evidence']
        ev['dacpac'] = f"code source {scen['dacpac_source']}: {e['procs_called']} procedures called, {e['procs_defined']} defined in the repo, {e['pool_table_ddl']} table DDL statements" + (f"; missing: {', '.join(e['procs_missing'][:4])}" if e['procs_missing'] else '')
        ev['modeling'] = f"scenario {scen['scenario']}: {e['ldw_views'] + e['ldw_view_procs']} LDW objects, {e['out_objects']} OUT objects, {e['notebooks']} notebooks, {e['dataflows']} dataflows" + ('; surrogate keys by DENSE_RANK' if re.search(r'dense_rank', sql) else '') + ('; case-insensitive collation in code' if re.search(r'collate\s+\w*_ci_', sql) else '')
        ev['spot_copy_back'] = 'a copy-back to SPOT exists' if 'M-SPOT-COPY-BACK' in scen['modifiers'] else 'no copy-back found'
        ev['security'] = f"{len(re.findall(r'create security policy|create user|grant ', sql))} permission statements; {len(re.findall(r'ad_group|adgroup|security_level', sql))} references to groups or security levels in code"
        ev['sequencing'] = f"upstream pipelines in DPV1: {', '.join(S.get('upstream_steps', [])[:4]) or 'none'}; triggers: {', '.join(S['triggers']) or 'none'}"
        ev['baseline'] = 'DPV1 dedicated pool linked service: ' + (', '.join(l for l in S['linked_services'] if 'pool' in l.lower()) or 'none found')
    return ev


def paths_of(service, scope):
    d = project_dir(service, scope, '1-framing')
    return os.path.join(d, '04-key-reference-questions.md'), os.path.join(d, 'analysis', 'reference-answers.json')


def load_answers(service, scope):
    p = paths_of(service, scope)[1]
    return read_json(p) if exists(p) else {}


def applies(q, service, scen):
    return service in q['services'] and (not q.get('when') or any(x in scen['modifiers'] for x in q['when']))


def rows(service, scope, S, m, scen, pin):
    ev = evidence(service, scope, S, m, scen, pin)
    ans = load_answers(service, scope)
    out = []
    for q in questions():
        if not applies(q, service, scen):
            continue
        e = ev.get(q['evidence'], '')
        a = ans.get(q['id'], {}).get('answer', '')
        auto = (not a) and q['evidence'] == 'orphans' and not e
        out.append({**q, 'evidence_text': e, 'answer': a or ('none found' if auto else ''), 'status': 'answered' if (a or auto) else 'open'})
    return out


def write_page(service, scope, S, m, pin, scen=None):
    scen = scen or cs.classify(m, scope)[service][scope]
    R = rows(service, scope, S, m, scen, pin)
    cell = lambda t: re.sub(r'\s+', ' ', str(t or '')).replace('|', '/').strip() or '-'
    openr = [r for r in R if r['status'] == 'open' and r['required']]
    L = [f'# Key reference questions: {scope}', '',
         f"Generated by `reference_questions.py` from DPV1, the migration map and the deployment repository ({len(R)} questions, {len(openr)} required still open). Do not edit: record answers with "
         f"`python -I 0-shared/scripts/reference_questions.py answer --service {service} --id {scope} --q <ID> --text \"<answer>\"` (kept in `analysis/reference-answers.json`).", '',
         f"Scenario: `{scen['scenario']}`" + (f", modifiers {', '.join('`' + x + '`' for x in scen['modifiers'])}" if scen['modifiers'] else '') + ' (what each means: the scenario catalog of the workflow).', '',
         '| ID | Question | Evidence | Options | Status | Answer |', '| --- | --- | --- | --- | --- | --- |']
    grp = None
    for r in R:
        if r['group'] != grp:
            grp = r['group']
            L.append(f'| | **{grp}** | | | | |')
        L.append(f"| {r['id']}{' *' if r['required'] else ''} | {cell(r['question'])} | {cell(r['evidence_text'])} | {cell('; '.join(r['options']))} | {'✅ answered' if r['status'] == 'answered' else '⚪ open'} | {cell(r['answer'])} |")
    L += ['', '`*` required: for a data product the gate `reference_questions_answered` waits for it; for a source dataset an open one is a review warning.']
    write(paths_of(service, scope)[0], '\n'.join(L) + '\n')
    return R


def open_required(service, scope):
    """Required questions without an answer, read from the generated page and the answers file (no recomputation)."""
    page = paths_of(service, scope)[0]
    if not exists(page):
        return None
    txt = open(page, encoding='utf-8').read()
    return [m.group(1) for m in re.finditer(r'^\| (Q\d+) \* \|.*\| ⚪ open \|', txt, re.M)]


def sync_gate(service, scope):
    """Data product: gate reference_questions_answered follows the page (completed when no required question is open)."""
    if service != 'dp':
        return
    import track
    left = open_required(service, scope)
    if left is None:
        return
    st = track.load(scope, service)
    if st['gates'].get('reference_questions_answered', {}).get('status') == 'completed' and left:
        pass  # a reopened question reopens the gate below
    st['gates']['reference_questions_answered'] = {'status': 'completed' if not left else 'in_progress',
                                                    'evidence': '04-key-reference-questions.md: all required answered' if not left else f"{len(left)} required open: {', '.join(left)}"}
    track.save(st)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=['show', 'answer', 'status'])
    ap.add_argument('--service', choices=['sds', 'dp'], required=True)
    ap.add_argument('--id', required=True)
    ap.add_argument('--q')
    ap.add_argument('--text')
    a = ap.parse_args()
    m = load_map()
    scope, _ = resolve_scope(m, a.service, a.id)
    S = m[a.service][scope]
    import project_inputs
    pin = project_inputs.load(a.service, scope)
    if a.action == 'answer':
        if not (a.q and a.text):
            sys.exit('answer needs --q and --text')
        ids = {q['id'] for q in questions()}
        if a.q not in ids:
            sys.exit(f'unknown question {a.q}; known: {", ".join(sorted(ids))}')
        ans = load_answers(a.service, scope)
        ans[a.q] = {'answer': a.text}
        write(paths_of(a.service, scope)[1], json.dumps(ans, indent=1, ensure_ascii=False, sort_keys=True) + '\n')
    R = write_page(a.service, scope, S, m, pin)
    sync_gate(a.service, scope)
    left = [r['id'] for r in R if r['status'] == 'open' and r['required']]
    if a.action == 'show':
        for r in R:
            print(f"{r['id']}{'*' if r['required'] else ' '} [{r['status']}] {r['question']}\n      evidence: {r['evidence_text'] or '-'}\n      options: {' | '.join(r['options'])}" + (f"\n      answer: {r['answer']}" if r['answer'] else ''))
    print(f"{scope}: {len(R)} questions, {len(left)} required open{': ' + ', '.join(left) if left else ''}")
    sys.exit(2 if (a.action == 'status' and left) else 0)


if __name__ == '__main__':
    main()
