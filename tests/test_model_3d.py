"""Real container/server checks; no paid generation, browser launch or private upload."""
import json
import struct
import urllib.error
import urllib.request
from unittest.mock import patch

import pytest


def glb(document=None):
    document = document or {'asset': {'version': '2.0'}, 'scenes': [{'nodes': [0]}],
                            'nodes': [{'mesh': 0}], 'meshes': [{'primitives': []}]}
    body = json.dumps(document).encode()
    body += b' ' * (-len(body) % 4)
    return struct.pack('<4sIIII', b'glTF', 2, 20 + len(body), len(body), 0x4E4F534A) + body


@pytest.fixture
def studio(tmp_path, monkeypatch):
    import actions.model_3d as mod
    monkeypatch.setattr(mod, 'STORE', tmp_path / 'studio')
    monkeypatch.setattr(mod, '_server', None)
    monkeypatch.setattr(mod, '_opener', None)
    monkeypatch.setattr(mod, '_state', {'subject':'', 'prompt':'', 'references':[], 'models':[],
                                     'active':'', 'viewed':'', 'status':'EMPTY', 'error':''})
    yield mod
    if mod._server:
        mod._server.shutdown()
        mod._server.server_close()


@pytest.mark.parametrize('text,subject', [
    ('Virat Kohli ka 3d model banao', 'Virat Kohli'),
    ('make a realistic full body 3D model of Iron Man', 'Iron Man'),
    ('Tony Stark ka crazy 3d model bana de', 'Tony Stark'),
    ('ironman ka 3d model bna', 'ironman'),
    ('विराट कोहली का 3डी मॉडल बनाओ', 'विराट कोहली'),
])
def test_subject_and_model_intent(text, subject):
    from core.intent_router import classify_intent
    result = classify_intent(text)
    assert result['tool'] == 'model_3d' and result['subject'] == subject


@pytest.mark.parametrize('text', ['explain 3D geometry', 'what is a 3D model', 'open Discord',
                                  'send Divyansh a WhatsApp message saying create a 3D model'])
def test_other_commands_are_not_hijacked(text):
    from core.intent_router import classify_intent
    assert classify_intent(text).get('tool') != 'model_3d'


def test_import_path_preserved():
    from core.intent_router import classify_intent
    result = classify_intent('import "C:\\Models\\Full Iron Man.glb"')
    assert result['file_path'] == 'C:\\Models\\Full Iron Man.glb'


@pytest.mark.parametrize('corrupt', [b'fake image', glb()[:-1], b'XXXX' + glb()[4:],
                                    glb()[:4] + struct.pack('<I', 1) + glb()[8:]])
def test_not_a_glb_rejected(studio, corrupt):
    with pytest.raises(ValueError):
        studio.import_glb(corrupt, 'photo.glb')
    assert not studio.STORE.exists()


@pytest.mark.parametrize('resources', [
    {'images':[{'uri':'https://example.com/private'}]},
    {'buffers':[{'uri':'../../config/api_keys.json'}]},
    {'images':[{'uri':'data:text/html,ignored'}]},
    {'extensionsUsed':['KHR_draco_mesh_compression']},
])
def test_external_and_unsupported_resources_rejected(studio, resources):
    document = json.loads(glb()[20:])
    document.update(resources)
    with pytest.raises(ValueError):
        studio.validate_glb(glb(document))


def test_import_is_content_addressed_and_persistent(studio):
    first = studio.import_glb(glb(), '../../whatever.glb')
    second = studio.import_glb(glb(), 'renamed.glb')
    assert first['id'] == second['id'] and first['name'] == 'whatever.glb'
    assert len(studio._state['models']) == 1
    assert studio._state['status'] == 'IMPORTED' and not studio._state['viewed']
    assert (studio.STORE / (first['id'] + '.glb')).read_bytes() == glb()
    assert json.loads((studio.STORE / 'studio.json').read_text())['active'] == first['id']


def request(studio, path, data=None, token=True, headers=None):
    url = studio.studio_url()
    request_headers = {'X-Studio-Token':studio._server.studio_token} if token else {}
    request_headers.update(headers or {})
    body = data if isinstance(data, bytes) else json.dumps(data).encode() if data is not None else None
    return urllib.request.urlopen(urllib.request.Request(url + path, data=body, headers=request_headers), timeout=4)


def test_server_only_exposes_curated_assets(studio):
    entry = studio.import_glb(glb(), 'example.glb')
    with request(studio, '') as response:
        assert b'__STUDIO_TOKEN__' not in response.read()
    with request(studio, 'three/build/three.module.js') as response:
        assert response.headers['Content-Type'] == 'text/javascript'
    with request(studio, 'models/' + entry['id'] + '.glb') as response:
        assert response.read() == glb()
    for path in ['three/../../../../config/api_keys.json', 'config/api_keys.json', 'api/state']:
        with pytest.raises(urllib.error.HTTPError) as caught:
            request(studio, path, token=False)
        assert caught.value.code == 404


def test_import_requires_same_origin_and_secret(studio):
    for token, origin in [(False, None), (True, 'https://evil.example')]:
        with pytest.raises(urllib.error.HTTPError) as caught:
            request(studio, 'api/import', glb(), token=token, headers={'Origin':origin} if origin else {})
        assert caught.value.code == 403
    with request(studio, 'api/import', glb(), headers={'X-File-Name':'test.glb'}) as response:
        entry = json.load(response)
    with request(studio, 'api/viewed', {'id':'wrong'}) as response:
        result = json.load(response)
        assert result['success'] and not result['verified']
    assert studio._state['status'] == 'IMPORTED'
    with request(studio, 'api/viewed', {'id':entry['id']}) as response:
        assert json.load(response)['verified']
    assert studio._state['viewed'] == entry['id'] and studio._state['status'] == 'READY'


def test_prepare_never_claims_generated_model(studio):
    with patch('actions.web_search.web_search_structured', return_value={'results':[]}), patch.object(studio, '_open_viewer', return_value=True):
        result = studio.model_3d({'action':'prepare', 'subject':'Virat Kohli'})
    assert result['success'] and not result['verified']
    assert result['status'] == 'AWAITING_WEBSITE_GLB'
    assert 'Abhi model generate nahi hua' in result['message']
    assert not studio._state['models']
    assert 'Try free on Tripo' in result['message'] and 'Paid plan mat lena' in result['message']


def test_free_generator_uses_allowed_site_only(studio):
    with patch('actions.chrome_profile.open_url_in_yajat_chrome', return_value={'success': True}) as opened:
        with request(studio, 'api/open-site', {'site': 'tripo'}) as response:
            assert json.load(response)['success']
        opened.assert_called_once_with(studio.TRIPO_URL)
        with pytest.raises(urllib.error.HTTPError):
            request(studio, 'api/open-site', {'site': 'https://evil.example'})
        assert opened.call_count == 1


@pytest.mark.parametrize('contents', ['[]', '{"models":null}', '{"models":[],"references":null}'])
def test_bad_saved_metadata_does_not_break_studio(studio, contents):
    studio.STORE.mkdir(parents=True)
    (studio.STORE / 'studio.json').write_text(contents)
    with request(studio, 'api/state') as response:
        assert json.load(response)['references'] == []


def test_bad_reference_links_are_skipped(studio):
    results = [None, {'url':'https://['}, {'url':'javascript:alert(1)'},
               {'url':'https://user:secret@example.com/'}, {'url':'https://example.com/ok','title':'Reference'}]
    with patch('actions.web_search.web_search_structured', return_value={'results':results}), patch.object(studio, '_open_viewer', return_value=True):
        assert studio.model_3d({'action':'prepare','subject':'Iron Man'})['success']
    assert studio._state['references'] == [results[-1]]


@pytest.mark.parametrize('outcome', ['superseded', 'error'])
def test_import_never_verifies_other_model_or_failed_renderer(studio, tmp_path, outcome):
    file = tmp_path / 'first.glb'
    file.write_bytes(glb())
    def open_viewer(_url):
        if outcome == 'superseded':
            studio._state.update(active='b' * 64, viewed='b' * 64, status='READY')
        else:
            with request(studio, 'api/viewed', {'id':studio._state['active']}):
                pass
            with request(studio, 'api/error', {'id':studio._state['active'], 'error':'WebGL context lost'}):
                pass
            assert studio._state['viewed'] == ''
        return True
    with patch.object(studio, '_open_viewer', side_effect=open_viewer):
        result = studio.model_3d({'action':'import','file_path':str(file)})
    assert result['success'] and not result['verified']
    assert result['status'] == ('IMPORTED_SUPERSEDED' if outcome == 'superseded' else 'RENDER_FAILED')


def test_glb_attachment_goes_to_studio_and_preserves_document_flow(tmp_path):
    from core.study_documents import handle_attachment_command
    target = str(tmp_path / 'model.glb')
    with patch('actions.model_3d.model_3d', return_value={'success':True}) as execute:
        result = handle_attachment_command('[FILE_UPLOADED] ' + json.dumps({'path':target}))
    assert result['success']
    execute.assert_called_once_with({'action':'import','file_path':target})


@pytest.mark.parametrize('source',['voice','chat'])
def test_both_input_paths_dispatch_same_tool(source):
    from core.command_pipeline import process_user_command
    from core.tool_registry import ToolResult
    output = ToolResult(success=True, tool='model_3d', message='Awaiting GLB',
                        data={'authoritative_response':True}, verification={'verified':False})
    with patch('core.command_pipeline.default_tool_registry.execute_tool', return_value=output) as execute:
        result = process_user_command('Tony Stark ka 3d model banao', source=source)
    assert result['success'] and not result['verified']
    assert execute.call_args.args[0] == 'model_3d'
    assert execute.call_args.args[1]['subject'] == 'Tony Stark'
