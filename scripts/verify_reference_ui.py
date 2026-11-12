"""Render the real local UI with fixture content and a send-free test bridge."""
import asyncio
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import json
from pathlib import Path
import sys
from threading import Thread

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from playwright.async_api import async_playwright
from actions.chrome_profile import get_chrome_executable


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


async def verify():
    output = ROOT / 'scratch' / 'reference_ui_20261006'
    output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT / 'assets')))
    Thread(target=server.serve_forever, daemon=True).start()
    report = {'mode': 'real HTML/Three.js; fixture text; no real actions', 'checks': []}
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(executable_path=get_chrome_executable(), headless=True)
            try:
                page = await browser.new_page(viewport={'width': 1440, 'height': 900}, device_scale_factor=1)
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                await page.goto(f'http://127.0.0.1:{server.server_port}/jarvis_holographic_ui.html')
                await page.wait_for_function('window._jarvis3dReady && window.JARVIS3DCore')
                await page.evaluate(r'''() => {
                    window.fixtureCommands=[];
                    window.pyBridge={sendCommand:(cmd)=>fixtureCommands.push(cmd)};
                    JARVIS3DCore.setTasks([{title:'Review landing page',assignee:'Design team',priority:'HIGH'},
                        {title:'Prepare launch checklist',priority:'MEDIUM'}]);
                    JARVIS3DCore.appendChat('You','Landing page ka plan banao aur flaws bhi batao.');
                    JARVIS3DCore.appendChat('JARVIS','Pehle audience aur offer clear karte hain. Main risk: headline benefit nahi batati.\n\n1. Clear headline\n2. Ek primary action\n3. Mobile par readable layout');
                    JARVIS3DCore.setResponse('Haan, bolo. Main sun raha hoon.');
                    JARVIS3DCore.setState('LISTENING');
                }''')
                await page.get_by_role('button', name='Open WhatsApp', exact=True).click()
                assert await page.evaluate('fixtureCommands.length') == 1
                assert 'Open WhatsApp' in await page.evaluate('fixtureCommands[0]')
                await page.get_by_role('button', name='Controls', exact=True).click()
                report['render_budget'] = await page.evaluate('''async () => {
                    const samples={pixelRatio:JARVIS3DCore.getRenderStats().pixelRatio};
                    for (const state of ['LISTENING','SPEAKING']) {
                        JARVIS3DCore.setState(state);
                        const start=JARVIS3DCore.getRenderStats().frames;
                        const time=performance.now();
                        await new Promise(resolve=>setTimeout(resolve,1000));
                        samples[state]={frames:JARVIS3DCore.getRenderStats().frames-start,elapsedMs:performance.now()-time};
                    }
                    JARVIS3DCore.setState('LISTENING');
                    return samples;
                }''')
                assert await page.locator('.col-right').is_visible()
                await page.get_by_role('button', name='Controls', exact=True).click()
                for width, height in [(1440, 900), (1100, 700)]:
                    await page.set_viewport_size({'width': width, 'height': height})
                    await page.wait_for_timeout(600)
                    filename = f'jarvis_{width}x{height}.png'
                    await page.screenshot(path=str(output / filename))
                    boxes = await page.evaluate('''() => Object.fromEntries(['cmd-input','chat-input','task-board'].map(id=>{
                        let b=document.getElementById(id).getBoundingClientRect();
                        return [id,{x:b.x,y:b.y,width:b.width,height:b.height,inside:b.bottom<=innerHeight&&b.right<=innerWidth&&b.x>=0}];
                    }))''')
                    report['checks'].append({'viewport': [width,height], 'screenshot': filename, 'controls':boxes})
                report['page_errors'] = errors
                report['verified'] = not errors and report['render_budget']['pixelRatio'] <= 1.5 and all(item['inside'] for check in report['checks'] for item in check['controls'].values())
            finally:
                await browser.close()
    finally:
        server.shutdown()
        server.server_close()
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    return report['verified']


if __name__ == '__main__':
    sys.exit(0 if asyncio.run(verify()) else 1)
