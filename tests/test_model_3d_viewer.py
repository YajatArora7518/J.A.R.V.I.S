"""Isolated Chrome exercises the real Three.js canvas; no user browser/profile."""
from pathlib import Path
import pytest


@pytest.fixture
def studio(tmp_path, monkeypatch):
    import actions.model_3d as mod
    monkeypatch.setattr(mod, 'STORE', tmp_path / 'studio')
    monkeypatch.setattr(mod, '_server', None)
    monkeypatch.setattr(mod, '_state', {'subject':'', 'prompt':'', 'references':[], 'models':[],
                                     'active':'', 'viewed':'', 'status':'EMPTY', 'error':''})
    yield mod
    if mod._server:
        mod._server.shutdown()
        mod._server.server_close()


def test_real_mesh_orbit_movement_materials_and_animation(studio, tmp_path):
    from playwright.sync_api import sync_playwright, expect
    sample = Path(__file__).resolve().parents[1] / 'assets/model_samples/RobotExpressive_sample.glb'
    assert sample.is_file(), 'Official CC0 test model missing'
    url = studio.studio_url()
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='chrome', headless=True)
        page = browser.new_page(viewport={'width':1200,'height':800})
        page.add_init_script("""window.meshDraws=0;
            for(const type of [WebGLRenderingContext,WebGL2RenderingContext]){
                const original=type.prototype.drawElements;
                type.prototype.drawElements=function(...args){window.meshDraws++;return original.apply(this,args);};
            }""")
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.goto(url)
        assert page.locator('#status').inner_text() == 'READY TO IMPORT'
        page.locator('#file').set_input_files(str(sample))
        expect(page.locator('#status')).to_have_text('READY · REAL 3D MODEL', timeout=20000)
        assert studio._state['viewed'] == studio._state['active']
        assert '14 animations' in page.locator('#stats').inner_text()
        assert page.locator('#model-label').inner_text() == 'GLB · RobotExpressive_sample.glb'
        assert page.locator('#tripo').inner_text() == 'Try free on Tripo ↗'
        # A stationary model should stop GPU draw calls once damping settles.
        page.wait_for_timeout(1200)
        draws = page.evaluate('window.meshDraws')
        assert draws > 0, 'Instrumentation must observe real mesh drawing'
        page.wait_for_timeout(400)
        assert page.evaluate('window.meshDraws') == draws
        before = page.locator('#canvas').screenshot()
        canvas = page.locator('#canvas').bounding_box()
        x, y = canvas['x'] + canvas['width'] * .5, canvas['y'] + canvas['height'] * .5
        page.mouse.move(x,y)
        page.mouse.down()
        page.mouse.move(x+160,y+50,steps=16)
        page.mouse.up()
        page.wait_for_timeout(300)
        rotated = page.locator('#canvas').screenshot()
        assert rotated != before, 'Cursor drag must change the actual mesh view'
        page.mouse.move(x,y)
        page.mouse.wheel(0,-250)
        page.wait_for_timeout(300)
        zoomed = page.locator('#canvas').screenshot()
        assert zoomed != rotated
        page.locator('[data-axis=y][data-step="1"]').click()
        page.wait_for_timeout(150)
        assert page.locator('#canvas').screenshot() != zoomed
        page.locator('#holo').click()
        page.wait_for_timeout(150)
        hologram = page.locator('#canvas').screenshot()
        page.locator('#real').click()
        page.wait_for_timeout(150)
        assert page.locator('#canvas').screenshot() != hologram
        page.locator('#animation').select_option(label='Walking')
        assert page.locator('#play').inner_text() == 'Pause animation'
        animation_before = page.locator('#canvas').screenshot()
        page.wait_for_timeout(400)
        assert page.locator('#canvas').screenshot() != animation_before
        page.locator('#play').click()
        assert page.locator('#play').inner_text() == 'Play animation'
        page.locator('#reset').click()
        page.locator('#rotate').click()
        assert page.locator('#rotate').inner_text() == 'Stop rotation'
        page.locator('#reset').click()
        assert page.locator('#rotate').inner_text() == 'Auto rotate'
        page.screenshot(path=str(tmp_path / '3d-studio.png'))
        assert not errors, errors
        # A new subject must not relabel the previous sample as a generated person.
        with studio._lock:
            studio._state.update(subject='Virat Kohli', active='', viewed='', status='AWAITING_WEBSITE_GLB',
                                 references=[{'title':'A full-body reference source with a long description ' * 3,
                                              'url':f'https://example.com/reference/{i}'} for i in range(5)] + [None, {'url':'broken URL'}])
        expect(page.locator('#status')).to_have_text('AWAITING WEBSITE GLB', timeout=6000)
        assert page.locator('#empty').is_visible() and page.locator('#reset').is_disabled()
        assert page.locator('#model-label').inner_text() == ''
        # Long reference lists scroll in the sidebar, never grow the 3D canvas.
        bounds = page.locator('#canvas').bounding_box()
        assert bounds['y'] + bounds['height'] <= page.viewport_size['height']
        assert page.locator('#tools').bounding_box()['y'] < page.viewport_size['height']
        # Bad reference entries must not prevent a subsequent actual model import.
        page.locator('#file').set_input_files(str(sample))
        expect(page.locator('#status')).to_have_text('READY · REAL 3D MODEL', timeout=20000)
        assert studio._state['viewed'] == studio._state['active']
        assert page.locator('#subject').inner_text() == 'Virat Kohli'
        assert page.locator('#model-label').inner_text() == 'GLB · RobotExpressive_sample.glb'
        assert not errors, errors
        browser.close()
