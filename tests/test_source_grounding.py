"""Quoted page/pixel evidence, not search snippets or remembered claims."""
import asyncio
import json
import threading
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock, patch
import pytest


def page(content, age=0):
    return {'success':True,'url':'https://www.icc-cricket.com/news/fixture', 'domain':'icc-cricket.com',
            'title':'Virat Kohli ODI centuries','content':content,
            'published_at':(datetime.now(timezone.utc)-timedelta(days=age)).isoformat(), 'updated_at':''}


def search_data():
    return {'success':True,'live_search':True,'retrieved_at':'now','query':'Virat Kohli ODI centuries',
            'results':[{'title':'Kohli ODI centuries','url':'https://www.icc-cricket.com/news/fixture','source':'icc-cricket.com'}]}


def model_claim(text, quote, source=1):
    return {'success':True,'text':json.dumps({'supported':True,'claims':[{'text':text,'quote':quote,'source':source}]})}


def audit_ok():
    return {'success':True,'text':json.dumps({'conflict':False,'checks':[{'id':0,'supported':True}]})}


def test_current_stat_requires_page_evidence_and_accepts_ordinal_number():
    from actions.web_research import answer_from_pages
    quote='Virat Kohli brought up his 55th ODI century in the match.'
    brain=MagicMock()
    brain.generate_response.side_effect=[model_claim('Virat Kohli ke 55 ODI centuries hain.',quote),audit_ok()]
    with patch('actions.web_research.fetch_webpage',return_value=page(quote)),patch('core.ai_multitier_engine.get_ai_engine',return_value=brain):
        result=answer_from_pages('Virat Kohli total ODI centuries',search_data(),current=True)
    assert result['verified'] and result['authoritative_response']
    assert '55' in result['message'] and 'icc-cricket.com' in result['message']
    assert 'http' not in result['spoken_message']
    assert brain.generate_response.call_args.kwargs['record_history'] is False


@pytest.mark.parametrize('passage_id',[1,99,True])
def test_research_selects_only_actual_integer_source_passages(passage_id):
    from actions.web_research import answer_from_pages
    quote='Virat Kohli brought up his 55th ODI century in the match.'
    brain=MagicMock()
    brain.generate_response.side_effect=[{'success':True,'text':json.dumps({'supported':True,'claims':[{'text':'Kohli ke 55 ODI centuries hain.','source':1,'passage':passage_id}]})},audit_ok()]
    with patch('actions.web_research.fetch_webpage',return_value=page(quote)),patch('core.ai_multitier_engine.get_ai_engine',return_value=brain):
        result=answer_from_pages('Virat Kohli total ODI centuries',search_data(),current=True)
    assert result['verified'] is (type(passage_id) is int and passage_id==1)
    if result['verified']:assert result['data']['claims'][0]['quote']==quote


@pytest.mark.parametrize('ids',[[1],[True],[99],[1,2]])
def test_provider_single_passage_list_cannot_expand_or_invent_evidence(ids):
    from actions.web_research import answer_from_pages
    quote='Virat Kohli brought up his 55th ODI century in the match.'
    brain=MagicMock()
    brain.generate_response.side_effect=[{'success':True,'text':json.dumps({'supported':True,'claims':[{'text':'Kohli ke 55 ODI centuries hain.','source':1,'passages':ids}]})},audit_ok()]
    with patch('actions.web_research.fetch_webpage',return_value=page(quote)),patch('core.ai_multitier_engine.get_ai_engine',return_value=brain):
        result=answer_from_pages('Virat Kohli total ODI centuries',search_data(),current=True)
    assert result['verified'] is (len(ids)==1 and type(ids[0]) is int and ids[0]==1)


@pytest.mark.parametrize('failure',['old_page','no_date','future_date','missing_quote','invented_number','wrong_source','historical_milestone','unreadable','unsupported','invalid_json'])
def test_current_claim_cannot_be_verified_from_stale_or_mismatched_evidence(failure):
    from actions.web_research import answer_from_pages
    quote='Virat Kohli brought up his 55th ODI century in the match.'
    evidence=page(quote, age=90 if failure=='old_page' else 0)
    answer=model_claim('Virat Kohli ke 55 ODI centuries hain.',quote)
    if failure=='no_date':evidence['published_at']=''
    if failure=='future_date':evidence['published_at']=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
    if failure=='missing_quote':answer=model_claim('Virat Kohli ke 55 ODI centuries hain.','Virat Kohli scored a century in a different game.')
    if failure=='invented_number':answer=model_claim('Virat Kohli ke 50 ODI centuries hain.',quote)
    if failure=='wrong_source':answer=model_claim('Virat Kohli ke 55 ODI centuries hain.',quote,9)
    if failure=='historical_milestone':
        quote='Virat Kohli scored his 50th ODI century in November 2023.'
        evidence['content']=quote
        answer=model_claim('Virat Kohli ke 50 ODI centuries hain.',quote)
    if failure=='unreadable':evidence={'success':False}
    if failure=='unsupported':answer={'success':True,'text':'{"supported":false,"claims":[]}'}
    if failure=='invalid_json':answer={'success':True,'text':'Kohli has 50 centuries.'}
    brain=MagicMock()
    brain.generate_response.return_value=answer
    with patch('actions.web_research.fetch_webpage',return_value=evidence),patch('core.ai_multitier_engine.get_ai_engine',return_value=brain):
        result=answer_from_pages('Virat Kohli total ODI centuries',search_data(),current=True)
    assert not result['success'] and not result['verified'] and result['authoritative_response']
    assert 'guess nahi' in result['message']
    if failure in {'old_page','no_date','future_date','unreadable'}:brain.generate_response.assert_not_called()


def test_compound_search_rejects_generic_india_pages():
    from actions.web_search_providers import _relevant_results
    generic={'title':'India Wikipedia','url':'https://en.wikipedia.org/wiki/India','snippet':'India is a South Asian country'}
    actual={'title':'India and India A squads for New Zealand tour announced','url':'https://www.bcci.tv/news/article/fixture','snippet':'India T20I cricket squad'}
    assert _relevant_results('India vs New Zealand cricket squad announcement latest news',[generic,actual])==[actual]


def test_fresh_official_index_is_checked_even_when_search_contains_old_official_article():
    from actions.web_search import web_search_tool
    old={'success':True,'results':[{'url':'https://www.bcci.tv/news/article/old','source':'bcci.tv'}]}
    fresh='https://www.bcci.tv/news/article/india-new-zealand-squad'
    index={'retrieved_at':'now','links':[{'title':'India New Zealand squad announced','url':fresh}]}
    with patch('actions.web_search.web_search_structured',return_value=old),patch('actions.web_search.fetch_webpage',return_value=index) as fetch,patch('actions.web_research.answer_from_pages',return_value={'success':True}) as answer:
        web_search_tool({'query':'India vs New Zealand T20 squad'})
    fetch.assert_called_once()
    assert answer.call_args.args[1]['results'][0]['url']==fresh


@pytest.mark.parametrize('text',['Virat Kohli total ODI centuries','Virat Kohli ke kitne shatak hain','विराट कोहली के कितने शतक हैं','India vs NZ T20 squad','एक बार मेरी स्क्रीन देखियो उसको एनालाइज करो'])
def test_exact_user_stat_and_hindi_screen_requests_reach_tools(text):
    from core.intent_router import classify_intent
    assert classify_intent(text)['tool'] == ('screen_process' if 'स्क्रीन' in text else 'web_search')


def test_page_extracts_publication_separately_from_retrieval_and_keeps_tables():
    from actions.fetch_webpage import fetch_webpage
    response=MagicMock(status_code=200,encoding='utf-8')
    response.iter_content.return_value=[b'<html><head><script type="application/ld+json">{"datePublished":"2026-10-06T10:00:00Z"}</script></head><body><main><h1>Squad announced</h1><table><tr><td>Shreyas Iyer</td><td>Captain</td></tr></table><a href="/news/squad">Squad article</a></main></body></html>']
    with patch('actions.fetch_webpage._check_public_url'),patch('actions.fetch_webpage._session_get',return_value=response):
        data=fetch_webpage('https://example.org/news')
    assert data['published_at']=='2026-10-06T10:00:00Z'
    assert data['retrieved_at'] != data['published_at']
    assert 'Shreyas Iyer Captain' in data['content']
    assert data['links'][0]['url']=='https://example.org/news/squad'


def test_private_redirect_is_never_fetched():
    from actions.fetch_webpage import fetch_webpage
    response=MagicMock(status_code=302,headers={'Location':'http://127.0.0.1/secret'})
    with patch('actions.fetch_webpage._check_public_url',side_effect=[None,ValueError('private')]),patch('actions.fetch_webpage._session_get',return_value=response) as get:
        data=fetch_webpage('https://example.org')
    assert not data['success']
    get.assert_called_once()


def test_live_voice_does_not_rewrite_verified_research_into_old_stat():
    from tests.test_runtime_glitches import live_fixture, packet, run_packets
    live=live_fixture()
    live._voice_conversation_active=True
    verified={'success':True,'verified':True,'authoritative_response':True,'message':'Kohli ke 55 ODI centuries. Source ICC.', 'spoken_message':'Kohli ke 55 ODI centuries.'}
    live._execute_tool=AsyncMock(return_value=SimpleNamespace(response=verified))
    packets=[packet(text='Virat Kohli total ODI centuries',tool=SimpleNamespace(name='assistant_command',id='fixture',args={})),packet(output='Kohli ke 50 centuries hain.',data=b'stale-voice',complete=True)]
    run_packets(live,packets)
    assert live.audio_in_queue.empty()
    live.speak.assert_called_once_with(verified['spoken_message'])
    assert not any('50 centuries' in str(call) for call in live.ui.write_log.call_args_list)


@pytest.mark.parametrize('tool_name',['screen_process','web_search'])
def test_direct_vision_and_research_tools_preserve_approved_reply(tool_name):
    from tests.test_runtime_glitches import live_fixture, packet, run_packets
    live=live_fixture()
    live._voice_conversation_active=True
    query='Jarvis screen dekh' if tool_name=='screen_process' else 'Virat Kohli total ODI centuries'
    safe={'success':True,'verified':True,'authoritative_response':True,'message':'Verified visible fact.','spoken_message':'Verified visible fact.'}
    live._execute_tool=AsyncMock(return_value=SimpleNamespace(response=safe))
    run_packets(live,[packet(text=query,tool=SimpleNamespace(name=tool_name,id='fixture',args={})),packet(output='Old false fact.',data=b'wrong',complete=True)])
    assert live.audio_in_queue.empty()
    live.speak.assert_called_once_with(safe['spoken_message'])
    live._dispatch_voice_to_pipeline.assert_not_called()


def test_registered_direct_vision_result_keeps_grounding_metadata():
    from tests.test_runtime_glitches import live_fixture
    from main import JarvisLive
    from core.tool_registry import ToolResult
    live=live_fixture()
    tool_result=ToolResult(success=True,tool='screen_process',message='Visible announcement.',data={'authoritative_response':True,'spoken_message':'Announcement visible hai.'},verification={'verified':True})
    with patch('main.default_tool_registry.get_tool',return_value=MagicMock()),patch('main.default_tool_registry.execute_tool',return_value=tool_result):
        response=asyncio.run(JarvisLive._execute_tool(live,SimpleNamespace(name='screen_process',id='fixture',args={}))).response
    assert response['authoritative_response'] and response['message']=='Visible announcement.'
    assert response['spoken_message']=='Announcement visible hai.'


def vision_fixture(claim='BCCI ne squad announce kar di hai.', quote='India and India A squads for New Zealand tour announced', view='webpage'):
    return SimpleNamespace(text=json.dumps({'view':view,'readable':True,'claims':[{'text':claim,'quote':quote}]}))


def test_screen_observation_uses_fresh_pixels_and_independent_ocr_for_each_question():
    from actions.screen_processor import analyze_screen_vision
    quote='India and India A squads for New Zealand tour announced'
    client=MagicMock()
    client.models.generate_content.return_value=vision_fixture()
    with patch('actions.screen_processor._capture_target',side_effect=[(b'frame-one','BCCI Chrome'),(b'frame-two','BCCI Chrome')]) as capture,patch('actions.screen_processor._capture_text',return_value=quote),patch('actions.screen_processor._get_cached_genai_client',return_value=client),patch('core.ai_policy.is_cloud_ai_allowed',return_value=True),patch('core.ai_policy.assert_cloud_ai_allowed'):
        first=analyze_screen_vision('screen dekh squad announce hui?')
        second=analyze_screen_vision('screen dekh kya likha hai?')
    assert first['verified'] and second['verified'] and first['capture_id']!=second['capture_id']
    assert capture.call_count==2 and client.models.generate_content.call_count==2
    assert first['confidence'] is None


def test_screen_accepts_independent_ocr_glyph_confusions_and_format_labels():
    from actions.screen_processor import analyze_screen_vision
    response=SimpleNamespace(text=json.dumps({'view':'webpage','readable':True,'claims':[
        {'text':'Captain Shreyas Iyer hain.','quote':"India's T20I Squad: Shreyas Iyer [C]"},
        {'text':'Bhuvneshwar Kumar T20I squad mein hain.','quote':'Bhuvneshwar Kumar, Varun Chakaravarthy, Kuldeep Yadav'}]}))
    client=MagicMock()
    client.models.generate_content.return_value=response
    ocr="India's T201 Squad: Shreyas lyer Abhishek Sharma Bhuvneshwar Kumar, Varun Chakaravarthy, Kuldeep Yadav"
    with patch('actions.screen_processor._capture_target',return_value=(b'fixture','BCCI Chrome')),patch('actions.screen_processor._capture_text',return_value=ocr),patch('actions.screen_processor._get_cached_genai_client',return_value=client),patch('core.ai_policy.is_cloud_ai_allowed',return_value=True),patch('core.ai_policy.assert_cloud_ai_allowed'):
        result=analyze_screen_vision('captain kaun aur Bhuvi shamil hai?')
    assert result['verified'] and 'Bhuvneshwar' in result['message']


@pytest.mark.parametrize('failure',['assistant_target','fake_quote','added_denial','invented_number','no_ocr','plain_response'])
def test_screen_cannot_claim_facts_from_its_own_chat_or_unreadable_pixels(failure):
    from actions.screen_processor import analyze_screen_vision
    quote='India and India A squads for New Zealand tour announced October 6 2026'
    response=vision_fixture(quote=quote)
    title='J.A.R.V.I.S — Futuristic AI Command Center' if failure=='assistant_target' else 'BCCI Chrome'
    if failure=='fake_quote':response=vision_fixture(quote='BCCI has not announced any squad for New Zealand')
    if failure=='added_denial':response=vision_fixture(claim='Squad announce nahi hui.',quote='India and India A squads for New Zealand tour not announced October 6 2026')
    if failure=='invented_number':response=vision_fixture(claim='BCCI ne 2023 mein announce kiya.',quote=quote)
    if failure=='plain_response':response=SimpleNamespace(text='BCCI has not announced anything.')
    client=MagicMock()
    client.models.generate_content.return_value=response
    with patch('actions.screen_processor._capture_target',return_value=(b'fixture',title)),patch('actions.screen_processor._capture_text',return_value='' if failure=='no_ocr' else quote),patch('actions.screen_processor._get_cached_genai_client',return_value=client),patch('core.ai_policy.is_cloud_ai_allowed',return_value=True),patch('core.ai_policy.assert_cloud_ai_allowed'):
        result=analyze_screen_vision('screen dekh squad bata')
    assert not result['success'] and not result['verified']
    if failure=='assistant_target':client.models.generate_content.assert_not_called()


@pytest.mark.parametrize('capture_fails',[False,True])
def test_ui_hides_itself_for_capture_and_restores_even_after_failure(capture_fails):
    from ui import MainWindow
    request={'event':threading.Event()}
    window=MagicMock()
    window.isActiveWindow.return_value=window.isVisible.return_value=True
    window.isMaximized.return_value=True
    with patch('ui.QTimer.singleShot',side_effect=lambda delay,fn:fn()),patch('pygetwindow.getActiveWindow',return_value=SimpleNamespace(title='BCCI Chrome')),patch('actions.screen_processor._capture_screenshot',side_effect=RuntimeError('fixture capture error') if capture_fails else None,return_value=b'fixture'):
        MainWindow._capture_analysis_frame(window,request)
    window.hide.assert_called_once()
    window.showMaximized.assert_called_once()
    assert request['event'].is_set()
    assert bool(request.get('error')) is capture_fails
