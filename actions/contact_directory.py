"""JARVIS-owned local contacts; Google readonly OAuth and Google CSV import.

Codex connectors are deliberately not a runtime dependency of this app.
"""
import csv
import hashlib
import json
import re
import secrets
import threading
import time
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

ROOT = Path(__file__).resolve().parent.parent
DIRECTORY = ROOT / 'memory' / 'contacts.user.json'
CLIENT = ROOT / 'config' / 'google_contacts_client.user.json'
TOKEN = ROOT / 'config' / 'google_contacts_token.user.json'
LOCK = threading.RLock()
_selected_csv = None
SCOPE = 'https://www.googleapis.com/auth/contacts.readonly'


def _read(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding='utf-8-sig'))


def _save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def import_contacts(contacts, source, *, complete=False, method=None):
    """Replace only this source after successful retrieval; keep duplicates distinct."""
    clean = []
    for index, person in enumerate(contacts):
        name = str(person.get('name', '')).strip()
        name = name or next(iter(person.get('phones') or person.get('emails') or []), '')
        if name:
            clean.append({'id': str(person.get('id') or f'{source}:{index}'), 'name': name,
                          'phones': list(person.get('phones', [])), 'emails': list(person.get('emails', [])),
                          'source': source})
    with LOCK:
        old = _read(DIRECTORY)
        old['contacts'] = [c for c in old.get('contacts', []) if c.get('source') != source] + clean
        old.setdefault('sources', {})[source] = {'count': len(clean), 'complete': complete,
                                                'updated_at': datetime.now(timezone.utc).isoformat()}
        if method:
            old['sources'][source]['method'] = method
        _save(DIRECTORY, old)
    return len(clean)


def resolve_saved_contact(query):
    with LOCK:
        people = _read(DIRECTORY).get('contacts', [])
    q = str(query).strip().casefold()
    matches = [c for c in people if c['name'].casefold() == q]
    if not matches:
        return None
    # Two different phone identities with the same name must not become one recipient.
    def identity(contact):
        # Strip display punctuation only. Never guess a country code or merge
        # different numbers just because their last digits happen to match.
        phones = contact.get('phones')
        values = [re.sub(r'[\s().-]', '', value) for value in phones] if phones else [v.casefold() for v in contact.get('emails', [])]
        return tuple(sorted(set(values or [contact['id']])))
    identities = {(c['name'].casefold(), identity(c)) for c in matches}
    if len(identities) > 1:
        return {'status': 'AMBIGUOUS_CONTACT', 'requires_clarification': True,
                'matches': [c['name'] for c in matches],
                'message': f'{query} naam ke multiple contacts hain. Exact WhatsApp naam ya number do.'}
    return {'status': 'RESOLVED', 'contact': matches[0]['name']}


def import_csv(path, *, expected_count=None, method=None):
    path = Path(path)
    if path.suffix.lower() != '.csv' or not path.is_file() or path.stat().st_size > 10_000_000:
        raise ValueError('Google Contacts ki CSV select karo (maximum 10 MB).')
    contacts = []
    def phone_column(key):
        return 'phone' in key and ('value' in key or key.endswith('number'))
    def email_column(key):
        return ('e-mail' in key or 'email' in key) and ('value' in key or key.endswith('address'))
    with path.open(encoding='utf-8-sig', newline='') as file:
        reader = csv.DictReader(file)
        fields = {(key or '').strip().casefold() for key in reader.fieldnames or []}
        if not (fields & {'name', 'first name', 'given name', 'family name', 'last name'}
                or any(phone_column(key) or email_column(key) for key in fields)):
            raise ValueError('Google Contacts CSV columns nahi mile; purani directory safe hai.')
        for index, row in enumerate(reader):
            if index >= 20_000:
                raise ValueError('Contact file bahut badi hai.')
            # Reject malformed rows before any directory write.
            if None in row or any(value is None for value in row.values()):
                raise ValueError('Contacts CSV row incomplete hai; purani directory safe hai.')
            row = {key.strip().casefold(): value.strip() for key, value in row.items()}
            name = row.get('name') or ' '.join(filter(None, [row.get('first name') or row.get('given name'),
                                                             row.get('middle name'), row.get('last name') or row.get('family name')]))
            phones = [v for k, v in row.items() if v and phone_column(k)]
            emails = [v for k, v in row.items() if v and email_column(k)]
            if name or phones or emails:
                contacts.append({'name': name, 'phones': phones, 'emails': emails})
    if expected_count is not None and len(contacts) != expected_count:
        raise ValueError('Google export count match nahi hua; purane contacts safe hain. Dobara sync karo.')
    # Commit the validated rows and full-export metadata in the same atomic write.
    return import_contacts(contacts, 'google_csv', complete=expected_count is not None, method=method)


def select_csv(path):
    global _selected_csv
    with LOCK:
        _selected_csv = None  # A failed new selection must not reuse the old CSV.
    file = Path(path).resolve(strict=True)
    if not file.is_file() or file.suffix.lower() != '.csv':
        raise ValueError('Contacts CSV select karo.')
    stat = file.stat()
    with LOCK:
        _selected_csv = (str(file), stat.st_mtime_ns, stat.st_size)


def _selected_csv_path():
    with LOCK:
        selected = _selected_csv
    if not selected:
        raise ValueError('Google Contacts se Export → Google CSV download karke JARVIS ke Attach se select karo; phir “import contacts” bolo.')
    path, stamp, size = selected
    file = Path(path)
    if not file.exists() or (file.stat().st_mtime_ns, file.stat().st_size) != (stamp, size):
        raise ValueError('CSV badal gayi hai; dobara attach karo.')
    return path


def _credentials():
    config = _read(CLIENT).get('installed', {})
    if not config.get('client_id') or not config.get('client_secret'):
        raise ValueError('Google sync ka setup baaki hai: apne Desktop OAuth client ki JSON config/google_contacts_client.user.json mein rakho. Bina setup ke Attach se Google Contacts CSV import kar sakte ho.')
    return config


def _store_token(token):
    # Windows account-bound encryption; never save refresh tokens as plaintext.
    import win32crypt
    encrypted = win32crypt.CryptProtectData(json.dumps(token).encode(), 'JARVIS Google contacts', None, None, None, 0)[1]
    _save(TOKEN, {'dpapi': encrypted.hex()})


def _load_token():
    if not TOKEN.exists():
        return {}
    import win32crypt
    return json.loads(win32crypt.CryptUnprotectData(bytes.fromhex(_read(TOKEN)['dpapi']), None, None, None, 0)[1])


def connect_google():
    import base64
    import requests
    client = _credentials()
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    result = {}
    class Callback(BaseHTTPRequestHandler):
        def do_GET(self):
            parts = urlsplit(self.path)
            values = parse_qs(parts.query)
            valid = parts.path == '/callback' and values.get('state') == [state]
            if valid:
                result.update(code=values.get('code', [''])[0], error=values.get('error', [''])[0], received=True)
            self.send_response(200 if valid else 400)
            self.end_headers()
            self.wfile.write(b'JARVIS: return to the app.' if valid else b'Invalid authorization callback.')
        def log_message(self, *args):
            pass  # The authorization code must never enter a log.
    with HTTPServer(('127.0.0.1', 0), Callback) as server:
        server.timeout = 1
        redirect = f'http://127.0.0.1:{server.server_port}/callback'
        url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode({
            'client_id': client['client_id'], 'redirect_uri': redirect, 'response_type': 'code',
            'scope': SCOPE, 'state': state, 'code_challenge': challenge, 'code_challenge_method': 'S256',
            'access_type': 'offline', 'prompt': 'consent'})
        if not webbrowser.open(url):
            raise RuntimeError('Google login window nahi khuli.')
        deadline = time.monotonic() + 150
        while not result.get('received') and time.monotonic() < deadline:
            server.handle_request()
    if not result.get('code'):
        raise RuntimeError('Google login approve nahi hua; contacts change nahi kiye.')
    response = requests.post('https://oauth2.googleapis.com/token', data={
        'client_id': client['client_id'], 'client_secret': client['client_secret'],
        'code': result['code'], 'code_verifier': verifier, 'redirect_uri': redirect,
        'grant_type': 'authorization_code'}, timeout=20)
    if not response.ok:
        raise RuntimeError('Google authorization complete nahi hua.')
    _store_token(response.json())
    return sync_google()


def sync_google():
    import requests
    client, token = _credentials(), _load_token()
    if not token.get('refresh_token'):
        raise ValueError('Pehle "connect Google contacts" bolo aur Google login approve karo.')
    response = requests.post('https://oauth2.googleapis.com/token', data={
        'client_id': client['client_id'], 'client_secret': client['client_secret'],
        'refresh_token': token['refresh_token'], 'grant_type': 'refresh_token'}, timeout=20)
    if not response.ok:
        raise RuntimeError('Google login expire/deny hua; reconnect karo. Purane contacts safe hain.')
    access = response.json()['access_token']
    people, page, seen = [], '', set()
    for _ in range(100):
        params = {'personFields': 'names,phoneNumbers,emailAddresses', 'pageSize': 1000}
        if page:
            params['pageToken'] = page
        response = requests.get('https://people.googleapis.com/v1/people/me/connections', params=params,
                                headers={'Authorization': 'Bearer ' + access}, timeout=25)
        if not response.ok:
            raise RuntimeError('Google contacts fetch fail hua; purane contacts safe hain.')
        data = response.json()
        for person in data.get('connections', []):
            names = person.get('names', [])
            people.append({'id': person['resourceName'], 'name': names[0].get('displayName', '') if names else '',
                           'phones': [n['value'] for n in person.get('phoneNumbers', [])],
                           'emails': [e['value'] for e in person.get('emailAddresses', [])]})
        page = data.get('nextPageToken', '')
        if not page:
            return import_contacts(people, 'google_oauth', complete=True)
        if page in seen:
            break
        seen.add(page)
    raise RuntimeError('Google pagination incomplete; purane contacts safe hain.')


def contact_directory(parameters, **kwargs):
    action = parameters.get('action', 'status')
    try:
        if action in ('connect', 'sync') and not CLIENT.exists():
            from actions.google_contacts_browser import sync_contacts_in_browser
            return sync_contacts_in_browser()
        if action in ('connect', 'sync', 'import'):
            # Network/OAuth can take minutes. Only the final atomic save needs
            # the directory lock; local recipient lookups must remain available.
            count = connect_google() if action == 'connect' else sync_google() if action == 'sync' else import_csv(parameters.get('file_path') or _selected_csv_path())
            return {'success': True, 'verified': True, 'authoritative_response': True,
                    'message': f'{count} contacts JARVIS mein save ho gaye.', 'count': count}
        data = _read(DIRECTORY)
        count = len(data.get('contacts', []))
        return {'success': True, 'verified': True, 'authoritative_response': True,
                'message': f'JARVIS mein {count} saved contacts hain. ' + ('Google API login saved hai.' if TOKEN.exists() else 'Google sync ke liye “sync Google contacts” bolo; JARVIS browser ka login use hoga.'),
                'count': count, 'sources': data.get('sources', {})}
    except Exception as exc:
        # Avoid HTTP response bodies, URLs with OAuth codes, or tokens in diagnostics.
        message = str(exc) if isinstance(exc, (ValueError, RuntimeError)) else 'Contacts update nahi hua; purane contacts safe hain.'
        return {'success': False, 'verified': False, 'authoritative_response': True, 'message': message}
