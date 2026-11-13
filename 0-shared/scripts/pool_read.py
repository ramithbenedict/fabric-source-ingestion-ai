"""Read-only access to the DPV1 dedicated SQL pool (see 2-config/migration/dedicated-pool-access.md).

Signs in through a browser window (azure-identity); no password, no token stored. Only SELECT / WITH statements run.

Usage:
  python -I 0-shared/scripts/pool_read.py query "SELECT ..."                       # print rows (tab separated)
  python -I 0-shared/scripts/pool_read.py ddl --schemas STG_RMA,DW_RMA,DM_RMA --out <folder>   # DDL of tables, views, procedures, functions
"""
import argparse, json, os, re, struct, subprocess, sys

SERVER = 'azswne08weuatsynapse01.sql.azuresynapse.net'
DATABASE = 'AZSQLPNE08WEUAT'
READ_ONLY = re.compile(r'^\s*(select|with)\b', re.I)
WRITE = re.compile(r'\b(insert|update|delete|merge|drop|alter|create|truncate|exec|execute|grant|revoke|into)\b', re.I)


def connect():
    import pyodbc
    try:
        import truststore; truststore.inject_into_ssl()   # use the Windows certificate store (corporate TLS inspection)
    except ImportError:
        pass
    from azure.identity import InteractiveBrowserCredential
    tok = InteractiveBrowserCredential(login_hint='gbadhani_azr@technip.onmicrosoft.com').get_token('https://database.windows.net/.default').token
    raw = tok.encode('utf-16-le')
    return pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={SERVER};DATABASE={DATABASE};Encrypt=yes',
                          attrs_before={1256: struct.pack(f'<I{len(raw)}s', len(raw), raw)}, autocommit=True)


def select(cn, sql, *params):
    if not READ_ONLY.match(sql) or WRITE.search(re.sub(r"'[^']*'", "''", sql)):
        sys.exit('Refused: only read-only SELECT statements are allowed on the dedicated pool.')
    cur = cn.cursor()
    cur.execute(sql, *params)
    return cur.fetchall()


def type_sql(r):
    t = r.type_name.lower()
    if t in ('varchar', 'char', 'varbinary', 'binary'):
        return f'{t}({"max" if r.max_length == -1 else r.max_length})'
    if t in ('nvarchar', 'nchar'):
        return f'{t}({"max" if r.max_length == -1 else r.max_length // 2})'
    if t in ('decimal', 'numeric'):
        return f'{t}({r.precision},{r.scale})'
    if t in ('datetime2', 'time', 'datetimeoffset'):
        return f'{t}({r.scale})'
    return t


def ddl(cn, schemas, out):
    os.makedirs(out, exist_ok=True)
    ins = ','.join('?' * len(schemas))
    objs = select(cn, f"SELECT s.name sch, o.name obj, RTRIM(o.type) typ, o.object_id oid FROM sys.objects o JOIN sys.schemas s ON s.schema_id=o.schema_id "
                      f"WHERE s.name IN ({ins}) AND o.type IN ('U','V','P','FN','IF','TF') ORDER BY s.name, o.name", *schemas)
    cols = select(cn, f"SELECT c.object_id oid, c.column_id, c.name, t.name type_name, c.max_length, c.precision, c.scale, c.is_nullable, c.is_identity, "
                      f"CAST(ic.seed_value AS bigint) seed_value, CAST(ic.increment_value AS bigint) increment_value, c.collation_name FROM sys.columns c JOIN sys.types t ON t.user_type_id=c.user_type_id "
                      f"LEFT JOIN sys.identity_columns ic ON ic.object_id=c.object_id AND ic.column_id=c.column_id "
                      f"JOIN sys.objects o ON o.object_id=c.object_id JOIN sys.schemas s ON s.schema_id=o.schema_id WHERE s.name IN ({ins}) ORDER BY c.object_id, c.column_id", *schemas)
    pks = select(cn, f"SELECT i.object_id oid, i.name, kc.column_id, ic.key_ordinal FROM sys.indexes i JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id "
                     f"JOIN sys.columns kc ON kc.object_id=ic.object_id AND kc.column_id=ic.column_id JOIN sys.objects o ON o.object_id=i.object_id JOIN sys.schemas s ON s.schema_id=o.schema_id "
                     f"WHERE i.is_primary_key=1 AND s.name IN ({ins})", *schemas)
    mods = {r.oid: r.definition for r in select(cn, f"SELECT m.object_id oid, m.definition FROM sys.sql_modules m JOIN sys.objects o ON o.object_id=m.object_id "
                                                    f"JOIN sys.schemas s ON s.schema_id=o.schema_id WHERE s.name IN ({ins})", *schemas)}
    colname = {(c.oid, c.column_id): c.name for c in cols}
    index = []
    for o in objs:
        if o.typ == 'U':
            lines = []
            for c in (c for c in cols if c.oid == o.oid):
                idt = f' IDENTITY({int(c.seed_value)},{int(c.increment_value)})' if c.is_identity else ''
                lines.append(f'    [{c.name}] {type_sql(c)}{idt} {"NULL" if c.is_nullable else "NOT NULL"}')
            pk = sorted((p for p in pks if p.oid == o.oid), key=lambda p: p.key_ordinal)
            if pk:
                lines.append(f'    CONSTRAINT [{pk[0].name}] PRIMARY KEY NONCLUSTERED ({", ".join("[" + colname[(o.oid, p.column_id)] + "]" for p in pk)}) NOT ENFORCED')
            text = f'CREATE TABLE [{o.sch}].[{o.obj}] (\n' + ',\n'.join(lines) + '\n);\n'
        else:
            text = (mods.get(o.oid) or '').strip() + '\nGO\n'
        kind = {'U': 'table', 'V': 'view', 'P': 'procedure'}.get(o.typ, 'function')
        path = os.path.join(out, o.sch.lower(), f'{o.obj}.{kind}.sql')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(f'-- {kind.upper()} {o.sch}.{o.obj} (read from the dedicated pool, read-only)\n' + text)
        index.append({'schema': o.sch, 'object': o.obj, 'kind': kind, 'file': os.path.relpath(path, out), 'columns': sum(1 for c in cols if c.oid == o.oid)})
    with open(os.path.join(out, 'pool-extract-index.json'), 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=1)
    by = {}
    for i in index:
        by[(i['schema'], i['kind'])] = by.get((i['schema'], i['kind']), 0) + 1
    for k, v in sorted(by.items()):
        print(f'{k[0]:10} {k[1]:10} {v}')


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    q = sub.add_parser('query'); q.add_argument('sql')
    d = sub.add_parser('ddl'); d.add_argument('--schemas', required=True); d.add_argument('--out', required=True)
    a = ap.parse_args()
    cn = connect()
    if a.cmd == 'query':
        for r in select(cn, a.sql):
            print('\t'.join(str(x) for x in r))
    else:
        ddl(cn, [s.strip() for s in a.schemas.split(',') if s.strip()], a.out)


if __name__ == '__main__':
    main()
