"""Connection setup sheet of a scope: which Fabric connections to create, with which name and values, and where their ids go.

Written by build_source_dataset.py S4 to 3-build/build-notes/connections.md: the list someone works through to create the connections.
Every value comes from the DPV1 linked service (the export holds one environment: confirm UAT and PRD with the owner).
Secrets are never copied: the sheet names the Key Vault secret DPV1 used.

Usage (from the repository root):
  python -I 0-shared/scripts/connections.py --service sds --id GEOS
"""
import argparse, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, load_map, resolve_scope, write, write_note, notes_path, read_json, catalog_warehouse, vl_name

ENVS = ('DEV', 'UAT', 'PRD')
# DPV1 linked service type => Fabric connection type, the fields to fill in, and the Fabric authentication to use
FABRIC = {
    'Oracle': ('Oracle database', ['host', 'port', 'service_name'], 'Basic (user name and password)'),
    'SqlServer': ('SQL Server database', ['server', 'database'], 'Basic or Windows'),
    'AzureSqlDatabase': ('Azure SQL database', ['server', 'database'], 'Service principal or Basic (the DPV1 managed identity does not exist in Fabric)'),
    'AzurePostgreSql': ('Azure Database for PostgreSQL', ['server', 'database'], 'Basic'),
    'PostgreSql': ('PostgreSQL database', ['server', 'database'], 'Basic'),
    'MySql': ('MySQL database', ['server', 'database'], 'Basic'),
    'AmazonRedshift': ('Amazon Redshift', ['server', 'database'], 'Basic'),
    'RestService': ('Web v2 (REST)', ['url'], 'as DPV1 (Basic, OAuth2 or anonymous)'),
    'HttpServer': ('Web v2 (HTTP)', ['url'], 'as DPV1'),
    'Sftp': ('SFTP', ['host', 'port'], 'Basic or SSH public key, as DPV1'),
    'FtpServer': ('FTP', ['host', 'port'], 'Basic'),
    'FileServer': ('File system', ['host'], 'Windows'),
    'AzureBlobStorage': ('Azure Blob Storage', ['url'], 'Service principal or account key'),
    'AzureFileStorage': ('Azure Files', ['url'], 'Account key'),
    'AmazonS3': ('Amazon S3', ['url'], 'Access key'),
    'OracleCloudStorage': ('Oracle Cloud Storage', ['url'], 'Access key'),
    'SharePointOnlineList': ('SharePoint Online list', ['url'], 'Service principal or OAuth2'),
}


def values_of(ls):
    """Connection fields from the DPV1 linked service details (Oracle descriptors are split into host, port and service)."""
    d = dict(ls.get('details') or {})
    out = {}
    srv = d.get('server') or d.get('host') or ''
    m = re.search(r'HOST\s*=\s*([^)\s]+).*?PORT\s*=\s*(\d+).*?(?:SERVICE_NAME|SID)\s*=\s*([^)\s]+)', srv, re.I | re.S)
    if m:
        out.update(host=m.group(1), port=m.group(2), service_name=m.group(3))
    else:
        for k in ('host', 'server'):
            if d.get(k):
                out[k] = d[k]
        if d.get('port'):
            out['port'] = d['port']
    for k in ('database', 'url', 'baseUrl'):
        if d.get(k):
            out['url' if k == 'baseUrl' else k] = d[k]
    if 'connectionString' in d and not d['connectionString'].lstrip().startswith('{'):
        for part in d['connectionString'].split(';'):
            if '=' in part:
                k, v = part.split('=', 1)
                k = k.strip().lower()
                if k in ('data source', 'server', 'host'):
                    out.setdefault('server', v.strip())
                elif k in ('initial catalog', 'database'):
                    out.setdefault('database', v.strip())
    user = d.get('username') or d.get('userName') or d.get('user')
    return out, d.get('authenticationType', ''), user


def sheet(service, scope):
    m = load_map()
    S = (m['sds'] if service == 'sds' else m['dp'])[scope]
    O = m['objects']
    sp = read_json(os.path.join(ROOT, '2-config', 'migration', 'shared-platform.json'))
    env = read_json(os.path.join(ROOT, '2-config', 'migration', 'environment-values.json'))['values']
    conns = []
    for r in S['rows']:
        if r['v1t'] == 'Linked service' and r['v2t'] == 'Connection':
            ls = O['linkedService'].get(r['v1'], {})
            name = r['v2'].split(' (')[0]
            base = re.sub(r'^CONN_|_<ENV>$', '', name)
            ftype, fields, auth = FABRIC.get(ls.get('type'), (ls.get('type', '?'), [], 'as DPV1'))
            vals, dpv1_auth, user = values_of(ls)
            conns.append({'dpv1': r['v1'], 'dpv1_type': ls.get('type', '?'), 'name': name, 'var': f'{base}_CONN_ID', 'name_var': f'{base}_CONN_NAME',
                          'type': ftype, 'fields': fields, 'values': vals, 'auth': auth, 'dpv1_auth': dpv1_auth, 'user': user,
                          'secrets': ls.get('kv_secrets', []), 'gateway': ls.get('runtime') == 'SelfHostedIntegrationRuntime'})
    L = [f'# Fabric connections to create: {scope}', '',
         'Create each connection in Fabric (Settings => Manage connections and gateways => New), with the name and values below, then put its id in VL_MAIN.',
         'Values come from the DPV1 linked service, which the export holds for one environment only: confirm UAT and PRD with the source owner.',
         'Passwords are never in this repository: take them from the Key Vault secret DPV1 used.', '']
    for c in conns:
        L += [f"## {c['name'].replace('<ENV>', 'DEV')} (UAT, PRD: same name with `_UAT`, `_PRD`)", '',
              '| Setting | Value |', '| --- | --- |',
              f"| Connection name | `{c['name'].replace('<ENV>', 'DEV')}` / `{c['name'].replace('<ENV>', 'UAT')}` / `{c['name'].replace('<ENV>', 'PRD')}` |",
              f"| Connection type | {c['type']} |",
              f"| Gateway | {'**on-premises data gateway required** (DPV1 used a self-hosted integration runtime)' if c['gateway'] else 'none (cloud connection)'} |"]
        for f in c['fields'] or sorted(c['values']):
            L.append(f"| {f.replace('_', ' ').capitalize()} | `{c['values'].get(f, '<to confirm>')}` (DPV1 export) |")
        extra = sorted(k for k in c['values'] if k not in c['fields'])
        L += [f"| {k.capitalize()} | `{c['values'][k]}` (DPV1 export) |" for k in extra]
        L += [f"| Authentication | {c['auth']}; DPV1 used `{c['dpv1_auth'] or 'see linked service'}`" + (f", user `{c['user']}`" if c['user'] else '') + ' |',
              f"| Secret | {', '.join('Key Vault `' + s + '`' for s in c['secrets']) or 'none in DPV1'} |",
              f"| Replaces (DPV1) | linked service `{c['dpv1']}` ({c['dpv1_type']}) |",
              f"| VL_MAIN | `{c['var']}` = connection id (DEV / UAT / PRD); `{c['name_var']}` = connection name |", '']
    if service == 'sds':
        import ingestion
        from common import project_dir
        for c in conns:
            h = ingestion.dpv1_auth_headers(S, project_dir('sds', scope), c['dpv1'], c['dpv1_type'])
            if h:
                L += [f"## Key Vault connection (API key header of {c['dpv1']})", '',
                      'A Fabric REST connection cannot carry a header. The pipeline reads the secret with a Web activity and sends it as an additional header in every REST Copy.', '',
                      '| Setting | Value |', '| --- | --- |', '| Connection type | Web v2 (Web) to the Key Vault, authentication Organizational account or Service principal (token audience `https://vault.azure.net`) |',
                      f"| Url | {' / '.join('`' + v + '`' for v in h['vaults']) or '`<vault url>`'} (DPV1 pipeline, per environment: DEV / UAT / PRD) |",
                      f"| Secret(s) | {', '.join('`' + v['secret'] + '` (header `' + k + '`)' for k, v in h['headers'].items())}, read as `secrets/<name>?api-version={h['api_version']}` |",
                      '| Access | the identity of the connection needs `get` on the secrets of the vault |',
                      f"| VL_MAIN | `{ingestion.keyvault_var(S['folder'])}` = connection id (DEV / UAT / PRD) |", '']
        wh = catalog_warehouse(sp, S['folder'])
        n = lambda base: vl_name(S['folder'], base)
        lh_id = env.get('LH_CONN_ID', {})
        L += ['## Lakehouse and warehouse connections (Fabric items)', '',
              '| Connection | Type | Used by | VL_MAIN | Known value |', '| --- | --- | --- | --- | --- |',
              f"| Lakehouse `{S['lakehouse']}` | Lakehouse (OAuth2 or workspace identity) | Copy sinks, the raw to table Copy | `{n('LH_CONN_ID')}` | {lh_id.get('DEV') or 'none: create one connection per environment and reuse it for every source'} |",
              f"| Warehouse `{wh}` | Warehouse (OAuth2 or workspace identity) | catalog Lookup, watermark Script | `{n('CATALOG_WAREHOUSE_CONN_ID')}` | create after the warehouse exists |", '',
              'Both are required in the pipeline files: without the connection reference, Fabric\'s Git import fails with "Object reference not set".', '',
              '## Item ids to fill in VL_MAIN after the first sync', '',
              f"- `LH_SDS_{S['folder']}_ID`: item id of `{S['lakehouse']}`",
              f"- `{n('CATALOG_WAREHOUSE_ID')}` and `{n('CATALOG_WAREHOUSE_SQL_ENDPOINT')}`: item id and SQL connection string of `{wh}`", '']
    path = notes_path(service, scope, 'connections.md')
    write(path, '\n'.join(L))
    for old in ('S4-connections.md',):
        if os.path.exists(notes_path(service, scope, old)):
            os.remove(notes_path(service, scope, old))
    return path, conns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--service', choices=['sds', 'dp'], required=True)
    ap.add_argument('--id', required=True)
    a = ap.parse_args()
    scope, _ = resolve_scope(load_map(), a.service, a.id)
    path, conns = sheet(a.service, scope)
    print(f"{scope}: {len(conns)} source connection(s) => {os.path.relpath(path, ROOT)}")


if __name__ == '__main__':
    main()
