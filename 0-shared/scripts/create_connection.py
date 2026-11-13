"""Create the REST (Web) connection of a source dataset in Fabric through the REST API (connections are tenant objects, not Git items).

Reads the name and url from 3-build/build-notes/connections.md, resolves the on-premises data gateway by name, creates the
connection with Anonymous authentication and prints the id for VL_MAIN (<SRC>_REST_SERVICE_CONN_ID). Dry run unless --create.
An existing connection with the same name is reused (nothing is created twice). Sign-in: browser window (azure-identity).

  python 0-shared/scripts/create_connection.py --id EPTW --env DEV --gateway Gateway_Dev_On_Premises            # dry run
  python 0-shared/scripts/create_connection.py --id EPTW --env DEV --gateway Gateway_Dev_On_Premises --create
  python 0-shared/scripts/create_connection.py --list-types      # supported connection types of the tenant
"""
import argparse, json, os, re, sys, urllib.error, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, load_map, resolve_scope, notes_path
from resolve_catalog import API, token


def call(method, path, tok, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method,
                                 headers={'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as f:
            raw = f.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise SystemExit(f'Fabric API {e.code} on {method} {path}: {e.read().decode()[:600]}')


def paged(path, tok):
    out, sep = [], '&' if '?' in path else '?'
    url = path
    while url:
        r = call('GET', url, tok)
        out += r.get('value', [])
        t = r.get('continuationToken')
        url = f'{path}{sep}continuationToken={t}' if t else None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--id')
    ap.add_argument('--env', default='DEV', choices=('DEV', 'UAT', 'PRD'))
    ap.add_argument('--gateway', help='on-premises data gateway name')
    ap.add_argument('--url', help='override the url read from connections.md')
    ap.add_argument('--type', default='Web', help='Fabric connection type (see --list-types)')
    ap.add_argument('--create', action='store_true')
    ap.add_argument('--list-types', action='store_true')
    a = ap.parse_args()
    tok = token()
    if a.list_types:
        for t in paged('/connections/supportedConnectionTypes', tok):
            print(t.get('type'), [c.get('name') for c in t.get('creationMethods', [])])
        return
    if not a.id:
        raise SystemExit('--id is required')
    m = load_map()
    scope, _ = resolve_scope(m, 'sds', a.id)
    notes = open(notes_path('sds', scope, 'connections.md'), encoding='utf-8').read()
    name = f'CONN_{a.id.upper()}_REST_SERVICE_{a.env}'
    url = a.url or (re.search(r'\| Url \| `([^`]+)`', notes) or [None, None])[1]
    if not url:
        raise SystemExit('No url in connections.md: pass --url')
    existing = [c for c in paged('/connections', tok) if c.get('displayName') == name]
    if existing:
        print(f'{name} exists: {existing[0]["id"]} (nothing created)')
        return
    gw = None
    if a.gateway:
        gws = [g for g in paged('/gateways', tok) if g.get('displayName') == a.gateway]
        if not gws:
            raise SystemExit(f'Gateway "{a.gateway}" not found for this account.')
        gw = gws[0]['id']
    body = {
        'displayName': name,
        'connectivityType': 'OnPremisesGateway' if gw else 'ShareableCloud',
        'privacyLevel': 'Organizational',
        'connectionDetails': {'type': a.type, 'creationMethod': a.type,
                              'parameters': [{'dataType': 'Text', 'name': 'url', 'value': url}]},
        'credentialDetails': {'singleSignOnType': 'None', 'connectionEncryption': 'NotEncrypted', 'skipTestConnection': False,
                              'credentials': {'credentialType': 'Anonymous'}},
    }
    if gw:
        body['gatewayId'] = gw
    print(json.dumps(body, indent=1))
    if not a.create:
        print('Dry run: add --create to create it.')
        return
    r = call('POST', '/connections', tok, body)
    print(f'Created {name}: {r.get("id")}\nSet VL_MAIN {a.id.upper()}_REST_SERVICE_CONN_ID ({a.env}) = {r.get("id")}')


if __name__ == '__main__':
    main()
