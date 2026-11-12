"""Regression cases for real bugs; no account writes or desktop actions."""
import json
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


@pytest.fixture
def directory(tmp_path, monkeypatch):
    import actions.contact_directory as module
    monkeypatch.setattr(module, 'DIRECTORY', tmp_path / 'contacts.json')
    return module


@pytest.fixture
def study(monkeypatch):
    import core.study_documents as module
    monkeypatch.setattr(module, '_attachment', None)
    return module


@pytest.mark.parametrize('contents', ['topic,count\n', '', 'topic,count\nthermo,5\n'])
def test_invalid_csv_preserves_existing_directory(directory, tmp_path, contents):
    directory.import_contacts([{'name':'Keep', 'phones':['123']}], 'google_csv')
    before = directory.DIRECTORY.read_bytes()
    file = tmp_path / 'wrong.csv'
    file.write_text(contents)
    with pytest.raises(ValueError):
        directory.import_csv(file)
    assert directory.DIRECTORY.read_bytes() == before


def test_google_contact_without_name_keeps_phone(directory, tmp_path):
    file = tmp_path / 'contacts.csv'
    file.write_text('Name,Phone 1 - Value\n,+919000000001\n')
    assert directory.import_csv(file) == 1
    assert directory.resolve_saved_contact('+919000000001')['status'] == 'RESOLVED'


def test_incomplete_export_preserves_existing_directory(directory, tmp_path):
    directory.import_contacts([{'name':'Keep'}], 'google_csv')
    before = directory.DIRECTORY.read_bytes()
    file = tmp_path / 'contacts.csv'
    file.write_text('Name,Phone 1 - Value\nNew,123\n')
    with pytest.raises(ValueError):
        directory.import_csv(file, expected_count=2)
    assert directory.DIRECTORY.read_bytes() == before


def test_valid_export_commits_contacts_and_scope_together(directory, tmp_path):
    file = tmp_path / 'contacts.csv'
    file.write_text('Name,Phone 1 - Value\nNew,123\n')
    assert directory.import_csv(file, expected_count=1, method='google_contacts_browser_export') == 1
    data = json.loads(directory.DIRECTORY.read_text())
    assert data['sources']['google_csv']['complete'] is True
    assert data['sources']['google_csv']['method'] == 'google_contacts_browser_export'


def test_full_document_with_whitespace_is_not_marked_partial(study, tmp_path):
    file = tmp_path / 'study.txt'
    file.write_text('\n  Thermodynamics\nHeat and work\n\n')
    assert study.extract_document(file)['partial'] is False


def test_specific_question_does_not_replace_whole_document_plan(study, tmp_path):
    file = tmp_path / 'study.txt'
    file.write_text('Thermodynamics\nKTG\n')
    overview = [{'title':'Thermodynamics','unit':1,'quote':'Thermodynamics','explanation':'Heat and work'},
                {'title':'KTG','unit':1,'quote':'KTG','explanation':'Gas particles'}]
    with patch.object(study, 'analyze_document', side_effect=[overview, overview[:1]]) as analyze:
        study.study_document({'file_path':str(file)})
        study.study_document({'query':'Explain thermodynamics only'})
        result = study.study_document({'action':'plan'})
    assert [t['title'] for t in result['topics']] == ['Thermodynamics','KTG']
    assert analyze.call_count == 2


@pytest.mark.parametrize(('text','action'), [
    ('इस PDF के टॉपिक्स समझाओ', 'analyze'),
    ('इसका प्लान बनाओ', 'plan'),
    ('इसके टॉपिक्स के वीडियो ढूंढो', 'resources'),
])
def test_hindi_document_followup_uses_shared_attachment(study, text, action):
    study._attachment = {'name':'study.pdf'}
    request = study.attachment_request(text)
    assert request and request['action'] == action


@pytest.mark.parametrize('text', ['थर्मो और केटीजी की हिंग्लिश वीडियो चला', 'thermo ki video chala do'])
def test_spoken_video_request_preserves_both_academic_topics(text):
    from actions.youtube_browser import parse_youtube_request
    request = parse_youtube_request(text)
    assert request and 'thermodynamics' in request['query']
    if 'केटीजी' in text:
        assert 'kinetic theory of gases' in request['query']
    assert not any(word in request['query'] for word in ('चला','की','और'))


@pytest.mark.parametrize('url', ['https://[invalid/watch?v=JAvi2K_DbbI',
                               'https://youtube.com:444/watch?v=JAvi2K_DbbI'])
def test_malformed_or_nonstandard_video_urls_are_rejected_without_crash(url):
    from actions.youtube_browser import video_id
    assert video_id(url) is None


def test_document_stops_extracting_pages_when_preview_is_full(study, tmp_path):
    file = tmp_path / 'study.pdf'
    file.write_bytes(b'fixture')
    pages = [MagicMock() for _ in range(30)]
    for page in pages:
        page.extract_text.return_value = 'Heat and work\n' * 1000
    pdf = MagicMock()
    pdf.__enter__.return_value.pages = pages
    with patch('pdfplumber.open', return_value=pdf):
        result = study.extract_document(file)
    assert result['partial'] and result['total_units'] == 30
    assert sum(len(u['text']) for u in result['units']) <= study.MAX_CHARS
    assert sum(page.extract_text.call_count for page in pages) == 5


def test_failed_csv_selection_never_reimports_previous_file(directory, tmp_path, monkeypatch):
    monkeypatch.setattr(directory, '_selected_csv', None)
    file = tmp_path / 'first.csv'
    file.write_text('Name\nOld\n')
    directory.select_csv(file)
    with pytest.raises(OSError):
        directory.select_csv(tmp_path / 'missing.csv')
    with pytest.raises(ValueError):
        directory._selected_csv_path()


def test_contacts_remain_readable_during_network_sync(directory, tmp_path, monkeypatch):
    directory.import_contacts([{'name':'Mumma'}], 'manual')
    client = tmp_path / 'client.json'
    client.write_text('{}')
    monkeypatch.setattr(directory, 'CLIENT', client)
    started, release = threading.Event(), threading.Event()
    def slow_sync():
        started.set()
        release.wait(2)
        return 1
    with patch.object(directory, 'sync_google', side_effect=slow_sync), ThreadPoolExecutor(2) as pool:
        sync = pool.submit(directory.contact_directory, {'action':'sync'})
        assert started.wait(1)
        try:
            lookup = pool.submit(directory.resolve_saved_contact, 'Mumma')
            assert lookup.result(timeout=.5)['contact'] == 'Mumma'
        finally:
            release.set()
        assert sync.result(timeout=1)['success']


def test_browser_initialization_failure_is_immediate_and_closes_unsubmitted_task():
    from actions.browser_automation import BrowserAutomationEngine
    engine = BrowserAutomationEngine()
    task = asyncio.sleep(0)
    with patch.object(engine, '_init', new=AsyncMock(side_effect=RuntimeError('fixture failure'))):
        with pytest.raises(RuntimeError, match='initialize'):
            engine.run(task, timeout=.1)
    assert task.cr_frame is None
    assert engine._ready.is_set()


def test_search_cache_is_bounded_and_result_mutations_are_isolated():
    from actions.web_search import _QueryCache
    cache = _QueryCache()
    for i in range(300):
        cache.set(f'thermodynamics concept {i}', {'results':[{'title':'Heat'}]})
    assert len(cache._cache) <= 128
    value = cache.get('thermodynamics concept 299')
    value['results'][0]['title'] = 'Unexpected mutation'
    assert cache.get('thermodynamics concept 299')['results'][0]['title'] == 'Heat'


def test_browser_search_looks_past_irrelevant_early_results():
    from actions.browser_search import _search
    page = MagicMock()
    page.url = 'https://www.google.com/search'
    page.goto = AsyncMock()
    headings = MagicMock()
    headings.first.wait_for = AsyncMock()
    headings.count = AsyncMock(return_value=4)
    titles = ['Buy garden tools','Learn cooking','Travel guide','Thermodynamics kinetic theory of gases']
    entries = []
    for i, title in enumerate(titles):
        entry = MagicMock()
        entry.inner_text = AsyncMock(return_value=title)
        entry.locator.return_value.get_attribute = AsyncMock(return_value=f'https://example.edu/{i}')
        entries.append(entry)
    headings.nth.side_effect = lambda i: entries[i]
    body = MagicMock()
    body.inner_text = AsyncMock(return_value='Search results')
    page.locator.side_effect = lambda selector: body if selector == 'body' else headings
    with patch('actions.browser_automation.browser_automation_engine.get_or_open_page', new=AsyncMock(return_value=page)):
        result = asyncio.run(_search('thermodynamics kinetic theory of gases',3))
    assert len(result) == 1 and result[0]['url'] == 'https://example.edu/3'


def test_same_contact_phone_format_from_two_sources_is_not_ambiguous(directory):
    directory.import_contacts([{'name':'Mumma','phones':['+91 90000-00001']}], 'google_seed')
    directory.import_contacts([{'name':'Mumma','phones':['+919000000001']}], 'google_csv')
    assert directory.resolve_saved_contact('Mumma')['status'] == 'RESOLVED'


def test_uploading_csv_clears_previous_document_context(study, directory, tmp_path, monkeypatch):
    monkeypatch.setattr(directory, '_selected_csv', None)
    study._attachment = {'name':'old.pdf'}
    file = tmp_path / 'contacts.csv'
    file.write_text('Name\nMumma\n')
    result = study.handle_attachment_command('[FILE_UPLOADED] ' + json.dumps({'path':str(file)}))
    assert result['success'] and study._attachment is None


def test_ai_unavailable_keeps_real_extracted_text(study, tmp_path):
    file = tmp_path / 'study.txt'
    file.write_text('Thermodynamics\nHeat and work')
    brain = MagicMock()
    brain.generate_response.side_effect = RuntimeError('provider unavailable')
    with patch('core.ai_multitier_engine.get_ai_engine', return_value=brain):
        result = study.study_document({'file_path':str(file)})
    assert result['success'] and result['status'] == 'TEXT_EXTRACTED'
    assert not result['analysis_verified']
    assert result['topics'][0]['title'] == 'Thermodynamics'


def test_expired_cache_entries_are_cleaned_on_new_queries():
    from actions.web_search import _QueryCache
    cache = _QueryCache(ttl_seconds=5)
    with patch('actions.web_search.time.monotonic', return_value=10):
        cache.set('heat concepts', {'results':[]})
    with patch('actions.web_search.time.monotonic', return_value=20):
        cache.set('gas concepts', {'results':[]})
    assert 'heat concepts' not in cache._cache


def test_cached_live_command_restores_state_without_executing_again():
    from main import JarvisLive
    from types import SimpleNamespace
    live = JarvisLive.__new__(JarvisLive)
    live.ui = MagicMock()
    live.ui.muted = False
    live._is_speaking = False
    live.tts_engine = None
    live._command_in_progress = False
    live._turn_command_results = {'calculate 2 * 3': {'success':True,'verified':True,'message':'6'}}
    fc = SimpleNamespace(name='assistant_command',args={'query':'calculate 2 * 3'},id='fixture')
    with patch('core.command_pipeline.process_user_command') as execute:
        result = asyncio.run(live._execute_tool(fc))
    execute.assert_not_called()
    assert result.response['message'] == '6'
    assert live.ui.set_state.call_args.args == ('LISTENING',)


@pytest.mark.parametrize('row', ['New\n','New,123,extra\n'])
def test_malformed_csv_rows_do_not_replace_contacts(directory, tmp_path, row):
    directory.import_contacts([{'name':'Keep'}], 'google_csv')
    before = directory.DIRECTORY.read_bytes()
    file = tmp_path / 'contacts.csv'
    file.write_text('Name,Phone 1 - Value\n' + row)
    with pytest.raises(ValueError):
        directory.import_csv(file)
    assert directory.DIRECTORY.read_bytes() == before


def test_document_changed_during_extraction_is_rejected(study, tmp_path):
    file = tmp_path / 'study.pdf'
    file.write_bytes(b'original fixture')
    page = MagicMock()
    def changed():
        file.write_bytes(b'changed larger fixture')
        return 'Heat and work'
    page.extract_text.side_effect = changed
    pdf = MagicMock()
    pdf.__enter__.return_value.pages = [page]
    with patch('pdfplumber.open', return_value=pdf), pytest.raises(ValueError, match='badal'):
        study.extract_document(file)


def test_concurrent_browser_requests_share_one_initialized_loop():
    from actions.browser_automation import BrowserAutomationEngine
    engine = BrowserAutomationEngine()
    async def initialize():
        await asyncio.sleep(.02)
    try:
        with patch.object(engine, '_init', new=AsyncMock(side_effect=initialize)) as init, ThreadPoolExecutor(2) as pool:
            jobs = [pool.submit(engine.run, asyncio.sleep(0, result=i), 2) for i in range(2)]
            assert [job.result(timeout=3) for job in jobs] == [0,1]
        assert init.await_count == 1
    finally:
        if engine._loop and engine._loop.is_running():
            engine._loop.call_soon_threadsafe(engine._loop.stop)
        if engine._thread:
            engine._thread.join(timeout=2)
        if engine._loop and not engine._loop.is_running() and not engine._loop.is_closed():
            engine._loop.close()
