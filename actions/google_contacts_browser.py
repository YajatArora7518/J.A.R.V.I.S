"""Normal Google Contacts export for JARVIS users without their own OAuth client.

Uses the signed-in JARVIS browser. No cookies/tokens are read or copied.
"""
import re
import uuid
from pathlib import Path


async def _export_contacts():
    from actions.browser_automation import browser_automation_engine as engine
    from actions.contact_directory import import_csv
    url = 'https://contacts.google.com/?hl=en'
    page = await engine.get_or_open_page('contacts.google.com', url)
    await page.goto(url, wait_until='domcontentloaded', timeout=25000)
    if 'accounts.google.com' in page.url:
        return {'success': False, 'verified': False, 'status': 'GOOGLE_LOGIN_REQUIRED',
                'message': 'JARVIS browser mein Google Contacts login khula hai. Khud sign in kar lo; phir “sync Google contacts” bolo. Password chat mein mat bhejna.'}
    export = page.get_by_role('button', name=re.compile(r'^Export$|^निर्यात$')).first
    try:
        await export.wait_for(state='visible', timeout=12000)
    except Exception:
        if (await page.get_by_role('button', name=re.compile(r'^Sign in$')).count()
                or 'accounts.google.com' in page.url):
            return {'success': False, 'verified': False, 'status': 'GOOGLE_LOGIN_REQUIRED',
                    'message': 'JARVIS browser mein Google Contacts par khud sign in karo, phir “sync Google contacts” bolo.'}
        raise
    await export.click()
    dialog = page.get_by_role('dialog').filter(has_text=re.compile(r'Export|निर्यात')).first
    await dialog.wait_for(state='visible', timeout=8000)
    all_contacts = dialog.get_by_text(re.compile(r'^Contacts \(\d+\)$')).first
    if not await all_contacts.count():
        # Do not export a selected/filtered subset and report it as a full sync.
        return {'success': False, 'verified': False, 'status': 'EXPORT_SCOPE_REQUIRED',
                'message': 'Export window mein “Contacts (all contacts)” select karo; full-contact scope verify nahi hua. CSV download karke Attach → “import contacts” bhi kar sakte ho.'}
    scope_text = await all_contacts.inner_text()
    expected = int(re.search(r'\((\d+)\)', scope_text)[1])
    csv_format = dialog.get_by_role('radio', name=re.compile(r'Google CSV')).first
    await csv_format.click()
    async with page.expect_download(timeout=20000) as pending:
        await dialog.get_by_role('button', name=re.compile(r'^Export$|^निर्यात$')).click()
    download = await pending.value
    if await download.failure():
        raise RuntimeError('Google export download failed.')
    target = Path(__file__).resolve().parent.parent / 'scratch' / ('contacts_export_' + uuid.uuid4().hex + '.csv')
    target.parent.mkdir(exist_ok=True)
    await download.save_as(str(target))
    try:
        count = import_csv(target, expected_count=expected, method='google_contacts_browser_export')
    finally:
        target.unlink(missing_ok=True)  # Only this exact newly-created export copy.
    return {'success': True, 'verified': True, 'count': count, 'complete': count == expected,
            'message': f'{count} Google contacts JARVIS mein save ho gaye.' + ('' if count == expected else ' Export count match nahi hua; full sync confirm nahi hai.')}


def sync_contacts_in_browser():
    from actions.browser_automation import browser_automation_engine as engine
    try:
        result = engine.run(_export_contacts(), timeout=75)
    except ValueError as exc:
        result = {'success': False, 'verified': False, 'status': 'GOOGLE_EXPORT_INVALID',
                  'message': str(exc)}  # Local CSV validation messages contain no contact values.
    except Exception:
        result = {'success': False, 'verified': False, 'status': 'GOOGLE_EXPORT_UNAVAILABLE',
                  'message': 'Google Contacts export complete nahi hua. Login ya export controls verify nahi hue; purane contacts safe hain. Google CSV download karke Attach → “import contacts” use kar sakte ho.'}
    return {**result, 'authoritative_response': True}
