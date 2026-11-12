"""JARVIS-owned GLB studio. Website generation is separate from verified import.

No API keys or billable submissions: prepare a prompt/reference search, then
import the website's downloaded, self-contained GLB. Existing Three.js renders it.
"""
import hashlib
import json
import re
import secrets
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote_plus, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / 'data' / 'model_studio'
MAX_BYTES = 100 * 1024 * 1024
MESHY_URL = 'https://www.meshy.ai/workspace'
TRIPO_URL = 'https://studio.tripo3d.ai/'
_lock = threading.RLock()
_server = None
_opener = None
_state = {'subject': '', 'prompt': '', 'references': [], 'models': [], 'active': '',
          'status': 'EMPTY', 'viewed': '', 'error': ''}
# These require additional decoders, which the installed viewer does not bundle.
_UNSUPPORTED = {'KHR_draco_mesh_compression', 'KHR_texture_basisu', 'EXT_meshopt_compression'}


def parse_model_request(text):
    raw = text.strip()
    if re.match(r'^(?:explain|how\b|what\b|why\b|kaise\b|समझाओ|कैसे)', raw, re.I):
        return None
    if not re.search(r'\b3[ -]?d\b|थ्रीडी|3डी|\.glb\b', raw, re.I):
        return None
    path = re.fullmatch(r'(?:import|open|load)\s+(?:3[ -]?d\s+model\s+)?["\']?(.+\.glb)["\']?', raw, re.I)
    if path:
        return {'action': 'import', 'file_path': path[1]}
    if re.fullmatch(r'(?:open|show|resume|kholo?|dikhao?)\s+(?:the\s+)?3[ -]?d\s+(?:studio|viewer|model)(?:\s+(?:karo|kar|do))?|3[ -]?d\s+(?:studio|viewer|model)\s+(?:kholo?|dikhao?)', raw, re.I):
        return {'action': 'open'}
    if not re.search(r'\b(?:create|make|generate|build|bana|banao|banana|banado|bna|bnao|bnado|chahiye)\b|बना|चाहिए', raw, re.I):
        return None
    subject = re.sub(r'\b3[ -]?d\b|थ्रीडी|3डी', ' ', raw, flags=re.I)
    subject = re.sub(r'\b(?:create|make|generate|build|bana|banao|banana|banado|bna|bnao|bnado|model|models|a|an|the|of|for|ka|ki|ke|ko|mujhe|mera|mere|please|pls|chahiye|kar|karo|do|de|full|body|realistic|professional|crazy|ekdum|360|view)\b|बनाओ|बना|मॉडल|चाहिए|का|की|मुझे', ' ', subject, flags=re.I)
    subject = re.sub(r'\s+', ' ', subject).strip(' .,?!:')
    return {'action': 'prepare', 'subject': subject}


def model_prompt(subject):
    return (f'Create a detailed full-body 3D model of {subject}. Entire subject visible, '
            'front-facing neutral pose, correct proportions, clean silhouette, realistic '
            'materials and PBR textures, detailed face and clothing where applicable. '
            'One complete subject; no cropped head or feet, no pedestal, no background. '
            'Use the chosen reference image for appearance. Export self-contained GLB '
            'with embedded textures. For a human character, use a rig-ready neutral pose; '
            'include rig and animation only if supported.')


def _reference_links(value):
    """Keep malformed search/saved entries from interrupting model loading."""
    references = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        url = str(item.get('url', ''))[:2000]
        try:
            parsed = urlsplit(url)
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
                continue
        except ValueError:
            continue
        references.append({'url': url, 'title': str(item.get('title', ''))[:300]})
        if len(references) == 5:
            break
    return references


def validate_glb(data):
    """Validate container and block network/file resource fetches before rendering."""
    if not 20 <= len(data) <= MAX_BYTES:
        raise ValueError('GLB 100 MB se chhoti aur valid honi chahiye.')
    magic, version, length = struct.unpack_from('<4sII', data)
    if magic != b'glTF' or version != 2 or length != len(data):
        raise ValueError('Valid GLB version 2 file chahiye; renamed photo nahi chalegi.')
    offset, document, chunks = 12, None, []
    while offset < length:
        if offset + 8 > length:
            raise ValueError('GLB chunk header incomplete hai.')
        size, kind = struct.unpack_from('<II', data, offset)
        offset += 8
        if size % 4 or offset + size > length:
            raise ValueError('GLB chunk incomplete hai.')
        chunks.append(kind)
        if len(chunks) == 1:
            if kind != 0x4E4F534A:
                raise ValueError('GLB ka first chunk JSON hona chahiye.')
            try:
                document = json.loads(data[offset:offset + size].decode('utf-8'))
            except (UnicodeError, ValueError) as exc:
                raise ValueError('GLB metadata invalid hai.') from exc
        offset += size
    if not isinstance(document, dict) or not isinstance(document.get('asset'), dict) or document['asset'].get('version') != '2.0':
        raise ValueError('glTF 2.0 metadata missing hai.')
    if not document.get('meshes') or not document.get('scenes'):
        raise ValueError('Is file mein renderable 3D mesh/scene nahi hai.')
    if not all(isinstance(document.get(key, []), list) for key in ('buffers', 'images', 'extensionsUsed', 'meshes', 'scenes', 'animations', 'materials')):
        raise ValueError('GLB metadata lists invalid hain.')
    for item in document.get('buffers', []) + document.get('images', []):
        if not isinstance(item, dict) or 'uri' in item:
            raise ValueError('Textures/buffers GLB mein embed karke export karo; external files supported nahi hain.')
    if not all(isinstance(extension, str) for extension in document.get('extensionsUsed', [])):
        raise ValueError('GLB extension names invalid hain.')
    unsupported = _UNSUPPORTED.intersection(document.get('extensionsUsed', []))
    if unsupported:
        raise ValueError('Uncompressed GLB export karo; is file ko additional decoder chahiye: ' + ', '.join(sorted(unsupported)))
    return {'meshes': len(document['meshes']), 'animations': len(document.get('animations', [])),
            'materials': len(document.get('materials', [])), 'bytes': len(data)}


def _save_state():
    STORE.mkdir(parents=True, exist_ok=True)
    target = STORE / 'studio.json'
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps({k: v for k, v in _state.items() if k != 'viewed'}, ensure_ascii=False), encoding='utf-8')
    temporary.replace(target)


def import_glb(data, name):
    details = validate_glb(data)
    model_id = hashlib.sha256(data).hexdigest()
    # User filename is display text, never a server filesystem path.
    label = Path(str(name).replace('\\', '/')).name[:160] or 'model.glb'
    with _lock:
        STORE.mkdir(parents=True, exist_ok=True)
        target = STORE / (model_id + '.glb')
        if not target.exists():
            temporary = target.with_suffix('.tmp')
            temporary.write_bytes(data)
            temporary.replace(target)
        entry = {'id': model_id, 'name': label, **details}
        _state['models'] = ([entry] + [m for m in _state['models'] if m['id'] != model_id])[:20]
        _state.update(active=model_id, status='IMPORTED', viewed='', error='')
        _save_state()
        return entry


def register_viewer_opener(callback):
    global _opener
    _opener = callback


def _open_viewer(url):
    if _opener:
        return bool(_opener(url))
    from actions.chrome_profile import open_url_in_yajat_chrome
    return bool(open_url_in_yajat_chrome(url).get('success'))


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def _reply(self, value, status=200, mime='application/json'):
        body = json.dumps(value, ensure_ascii=False).encode() if mime == 'application/json' else value
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; connect-src 'self'; worker-src blob:; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _allowed_host(self):
        return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

    def do_GET(self):
        if not self._allowed_host():
            return self._reply({'error': 'Invalid host'}, 403)
        parts = urlsplit(self.path)
        path = unquote(parts.path)
        if path == '/':
            html = (ROOT / 'assets' / 'model_3d_viewer.html').read_text(encoding='utf-8')
            return self._reply(html.replace('__STUDIO_TOKEN__', self.server.studio_token).encode(), mime='text/html; charset=utf-8')
        if self.headers.get('X-Studio-Token') == self.server.studio_token and path == '/api/state':
            with _lock:
                return self._reply(_state)
        if re.fullmatch(r'/models/[a-f0-9]{64}\.glb', path):
            with _lock:
                known = {m['id'] for m in _state['models']}
            if path[8:-4] in known:
                file = STORE / path.rsplit('/', 1)[1]
                if file.is_file():
                    return self._reply(file.read_bytes(), mime='model/gltf-binary')
        if path.startswith('/three/'):
            vendor = (ROOT / 'assets' / 'three' / 'node_modules' / 'three').resolve()
            file = (vendor / path[7:]).resolve()
            if file.is_relative_to(vendor) and file.suffix == '.js' and file.is_file():
                return self._reply(file.read_bytes(), mime='text/javascript')
        self._reply({'error': 'Not found'}, 404)

    def do_POST(self):
        origin = f'http://127.0.0.1:{self.server.server_port}'
        if (not self._allowed_host() or self.headers.get('Origin') not in (None, origin)
                or self.headers.get('X-Studio-Token') != self.server.studio_token):
            return self._reply({'error': 'Request denied'}, 403)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= (MAX_BYTES if self.path == '/api/import' else 8192):
                return self._reply({'error': 'Invalid request size'}, 413)
            self.connection.settimeout(20)
            data = self.rfile.read(length)
            if len(data) != length:
                raise ValueError('Upload incomplete hai.')
            if self.path == '/api/import':
                return self._reply(import_glb(data, unquote(self.headers.get('X-File-Name', 'model.glb'))))
            payload = json.loads(data)
            if not isinstance(payload, dict):
                raise ValueError('JSON object required')
            with _lock:
                if self.path == '/api/select':
                    model_id = payload.get('id')
                    if model_id not in {m['id'] for m in _state['models']}:
                        raise ValueError('Saved model missing hai.')
                    _state.update(active=model_id, viewed='', status='IMPORTED', error='')
                    _save_state()
                elif self.path == '/api/viewed':
                    accepted = bool(_state['active']) and payload.get('id') == _state['active']
                    if accepted:
                        _state.update(viewed=payload['id'], status='READY', error='')
                    return self._reply({'success': True, 'verified': accepted})
                elif self.path == '/api/error':
                    if payload.get('id') == _state['active']:
                        _state.update(viewed='', status='RENDER_FAILED', error=str(payload.get('error', 'Model load failed'))[:300])
                elif self.path == '/api/open-site':
                    site = payload.get('site')
                    url = {'meshy': MESHY_URL, 'tripo': TRIPO_URL}.get(site)
                    if site == 'references':
                        url = 'https://www.google.com/search?tbm=isch&q=' + quote_plus(_state['subject'] + ' full body reference photo')
                    if not url:
                        raise ValueError('Unknown website')
                    from actions.chrome_profile import open_url_in_yajat_chrome
                    result = open_url_in_yajat_chrome(url)
                    return self._reply({'success': bool(result.get('success'))})
                else:
                    return self._reply({'error': 'Not found'}, 404)
            self._reply({'success': True})
        except (ValueError, TypeError, KeyError, OSError, struct.error) as exc:
            self._reply({'error': str(exc)}, 400)


def studio_url():
    global _server
    with _lock:
        if _server is None:
            saved = STORE / 'studio.json'
            if saved.is_file():
                try:
                    state = json.loads(saved.read_text(encoding='utf-8'))
                    if not isinstance(state, dict) or not isinstance(state.get('models', []), list):
                        raise ValueError('Invalid saved studio state')
                    models = [m for m in state.get('models', []) if isinstance(m, dict)
                              and re.fullmatch('[a-f0-9]{64}', str(m.get('id', '')))
                              and (STORE / (m['id'] + '.glb')).is_file()][:20]
                    _state.update(subject=str(state.get('subject', ''))[:200], prompt=str(state.get('prompt', ''))[:2000],
                                  models=models, active=state.get('active') if state.get('active') in {m['id'] for m in models} else '',
                                  references=_reference_links(state.get('references', [])))
                except (ValueError, TypeError, OSError):
                    pass
            _server = ThreadingHTTPServer(('127.0.0.1', 0), _Handler)
            _server.daemon_threads = True
            _server.studio_token = secrets.token_urlsafe(32)
            threading.Thread(target=_server.serve_forever, name='JARVIS-3D-Studio', daemon=True).start()
        return f'http://127.0.0.1:{_server.server_port}/'


def model_3d(parameters=None, player=None, **kwargs):
    args = {**(parameters or {}), **kwargs}
    action = args.get('action', 'open')
    try:
        url = studio_url()
        if action == 'prepare':
            subject = str(args.get('subject', '')).strip()[:200]
            if not subject:
                return {'success': False, 'verified': False, 'authoritative_response': True,
                        'message': 'Kis cheez ka 3D model banaun, bhai? Naam bata do.'}
            from actions.web_search import web_search_structured
            result = web_search_structured(subject + ' full body reference photo', num_results=5, force_refresh=True)
            refs = _reference_links(result.get('results', []))
            with _lock:
                _state.update(subject=subject, prompt=model_prompt(subject), references=refs,
                              active='', viewed='', status='AWAITING_WEBSITE_GLB', error='')
                _save_state()
        elif action == 'import':
            file = Path(str(args.get('file_path', '')).strip('"\''))
            if file.suffix.lower() != '.glb' or not file.is_file():
                raise ValueError('Downloaded .glb file attach karo ya uska exact path do.')
            with file.open('rb') as stream:
                imported = import_glb(stream.read(MAX_BYTES + 1), file.name)
        elif action != 'open':
            raise ValueError('Action open, prepare ya import honi chahiye.')
        opened = _open_viewer(url)
        if not opened:
            raise ValueError('3D studio window load nahi hui; dobara “open 3D studio” bolo.')
        if action == 'import':
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                with _lock:
                    replaced = _state['active'] != imported['id']
                    viewed = _state['viewed'] == imported['id']
                    failed = _state['status'] == 'RENDER_FAILED'
                if viewed or failed or replaced:
                    break
                time.sleep(.1)
            with _lock:
                ready = _state['active'] == imported['id'] == _state['viewed'] and _state['status'] == 'READY'
                import_status = _state['status'] if _state['active'] == imported['id'] else 'IMPORTED_SUPERSEDED'
                message = 'Asli 3D model load ho gaya, bhai. Mouse se 360° ghumao, wheel se zoom, aur arrows se move karo.' if ready else 'GLB save ho gayi, lekin 3D render abhi verify nahi hua. Studio mein loading/error check karo.'
                if import_status == 'RENDER_FAILED':
                    message = 'GLB save hui, lekin render fail hua: ' + _state['error']
                elif import_status == 'IMPORTED_SUPERSEDED':
                    message = 'GLB library mein save hui, bhai. Studio mein ab doosra model selected hai; is file ka view verify nahi hua.'
            return {'success': True, 'verified': ready, 'status': import_status,
                    'message': message, 'viewer_url': url, 'authoritative_response': True}
        message = (f'{subject} ka 3D workspace ready hai, bhai. Prompt aur reference links diye hain. “Try free on Tripo” se website khol; H2.5 aur free GLB export pehle check kar, phir model banao aur import karo. Paid plan mat lena. Abhi model generate nahi hua.'
                   if action == 'prepare' else '3D studio khul gaya, bhai. Apni GLB import karo; drag se 360° view milega.')
        return {'success': True, 'verified': False, 'status': 'AWAITING_WEBSITE_GLB' if action == 'prepare' else 'VIEWER_OPEN',
                'message': message, 'viewer_url': url, 'authoritative_response': True}
    except (ValueError, TypeError, OSError, struct.error) as exc:
        return {'success': False, 'verified': False, 'status': 'MODEL_ERROR', 'message': str(exc), 'authoritative_response': True}
