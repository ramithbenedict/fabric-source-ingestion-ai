"""Flag Synapse Dedicated SQL Pool / serverless T-SQL that Fabric Warehouse does not accept. The code stays T-SQL;
this only lists what to fix (rules follow 1-skills/skill-tsql-dedicated-to-fabric and skill-sql-generation).

Usage: python -I 0-shared/scripts/tsql_fabric_lint.py <folder or .sql file> [--report <file.md>]
Exit code 1 when blocking findings remain, so it can gate a build.
"""
import argparse, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import write

# (rule id, severity, regex, fix)
RULES = [
    ('DISTRIBUTION', 'block', r'DISTRIBUTION\s*=\s*\w+', 'Remove the WITH (DISTRIBUTION …) option: Fabric distributes data automatically.'),
    ('HEAP_CCI', 'block', r'\bHEAP\b|CLUSTERED\s+COLUMNSTORE\s+INDEX', 'Remove HEAP / CLUSTERED COLUMNSTORE INDEX table options.'),
    ('INDEX', 'block', r'CREATE\s+(UNIQUE\s+)?(NON)?CLUSTERED\s+INDEX|\bCLUSTERED\s+INDEX\s*\(', 'Remove index definitions (not supported in Fabric Warehouse).'),
    ('PARTITION', 'block', r'\bPARTITION\s*\(', 'Remove table partitioning.'),
    ('EXTERNAL', 'block', r'CREATE\s+EXTERNAL\s+(TABLE|DATA\s+SOURCE|FILE\s+FORMAT)', 'Replace with a Lakehouse table read by three-part name (LH_INP_SDS_<SRC>.dbo.<table>).'),
    ('CETAS', 'block', r'CREATE\s+EXTERNAL\s+TABLE\s+[\w\[\]\.]+\s+WITH\s*\([^)]*LOCATION', 'CETAS export is not needed: the table or view itself is the output.'),
    ('OPENROWSET', 'block', r'OPENROWSET\s*\(\s*BULK', 'Read the Lakehouse table instead of files in ADLS.'),
    ('RENAME_OBJECT', 'block', r'\bRENAME\s+OBJECT\b', 'Use sp_rename or truncate + insert.'),
    ('NVARCHAR', 'fix', r'\bN(VAR)?CHAR\]?\s*\(', 'Use VARCHAR / CHAR (UTF-8 collation).'),
    ('DATETIME', 'fix', r'\b(SMALL)?DATETIME\b(?!2|OFFSET)\]?', 'Use DATETIME2(6).'),
    ('TIME_PRECISION', 'fix', r'\b(DATETIME2|DATETIMEOFFSET|TIME)\s*\(\s*7\s*\)', 'Use precision 6 at most (Fabric Warehouse: 0 to 6).'),
    ('MONEY', 'fix', r'\b(SMALL)?MONEY\b\]?', 'Use DECIMAL(19,4).'),
    ('TINYINT', 'fix', r'\bTINYINT\b\]?', 'Use SMALLINT.'),
    ('IDENTITY', 'check', r'\bIDENTITY\s*\(', 'Check the Fabric Warehouse IDENTITY rules in skill-sql-generation; otherwise use ROW_NUMBER() + max key.'),
    ('DYNAMIC_SQL', 'check', r'sp_executesql|EXEC\s*\(\s*@', 'Dynamic SQL: confirm every generated statement is Fabric-compatible.'),
    ('TEMP_TABLE', 'check', r'(?<![\w@])#\w+', 'Session temp tables are supported; prefer a CTE when used once.'),
    ('SERVERLESS_DB', 'check', r'\bUSE\s+\[?\w+\]?', 'USE is not needed in a database project; remove it.'),
]


def lint_text(text):
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        code = line.split('--', 1)[0]
        for rid, sev, rx, fix in RULES:
            if re.search(rx, code, re.I):
                out.append((i, rid, sev, fix, line.strip()[:120]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('path')
    ap.add_argument('--report')
    a = ap.parse_args()
    files = [a.path] if a.path.lower().endswith('.sql') else [os.path.join(d, f) for d, _, fs in os.walk(a.path) for f in fs if f.lower().endswith('.sql')]
    findings = {f: lint_text(open(f, encoding='utf-8', errors='replace').read()) for f in sorted(files)}
    sev = lambda s: sum(1 for v in findings.values() for x in v if x[2] == s)
    L = [f'# T-SQL Fabric lint · {a.path}', '', f'- Files: {len(files)} · blocking: {sev("block")} · fix: {sev("fix")} · check: {sev("check")}', '',
         '| File | Line | Rule | Severity | Fix | Code |', '|---|---|---|---|---|---|']
    for f, v in findings.items():
        rel = os.path.relpath(f, a.path if os.path.isdir(a.path) else os.path.dirname(a.path))
        L += [f'| `{rel}` | {i} | {r} | {s} | {fx} | `{c.replace("|", "/")}` |' for i, r, s, fx, c in v]
    report = '\n'.join(L) + '\n'
    if a.report:
        write(a.report, report)
    print(f'{len(files)} files · blocking {sev("block")} · fix {sev("fix")} · check {sev("check")}' + (f' → {a.report}' if a.report else ''))
    sys.exit(1 if sev('block') else 0)


if __name__ == '__main__':
    main()
