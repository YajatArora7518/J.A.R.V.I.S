"""Meaning, query translation and bounded source recovery, without real actions."""
import json
from unittest.mock import MagicMock, patch
import pytest
from tests.test_source_grounding import page,search_data,model_claim,audit_ok


@pytest.mark.parametrize('failure',['format','contradiction','missing_check','boolean_id','unavailable','invalid_json'])
def test_matching_number_and_quote_alone_cannot_verify_a_claim(failure):
    from actions.web_research import answer_from_pages
    quote='Virat Kohli scored 55 centuries in Test cricket.'
    check=audit_ok()
    if failure=='format':check['text']=json.dumps({'conflict':False,'checks':[{'id':0,'supported':False}]})
    if failure=='contradiction':check['text']=json.dumps({'conflict':True,'checks':[{'id':0,'supported':True}]})
    if failure=='missing_check':check['text']=json.dumps({'conflict':False,'checks':[]})
    if failure=='boolean_id':check['text']=json.dumps({'conflict':False,'checks':[{'id':False,'supported':True}]})
    if failure=='unavailable':check={'success':False}
    if failure=='invalid_json':check={'success':True,'text':'yes seems right'}
    brain=MagicMock()
    brain.generate_response.side_effect=[model_claim('Kohli ke 55 ODI centuries hain.',quote),check]
    with patch('actions.web_research.fetch_webpage',return_value=page(quote)),patch('core.ai_multitier_engine.get_ai_engine',return_value=brain):
        result=answer_from_pages('Virat Kohli ODI centuries',search_data(),current=True)
    assert not result['verified'] and not result['success']
    assert brain.generate_response.call_count==2
    assert brain.generate_response.call_args.kwargs['temperature']==0.0
    assert brain.generate_response.call_args.kwargs['record_history'] is False


@pytest.mark.parametrize('query',['Virat Kohli ODI centuries','Virat Kohli ODI centuries 55','Virat Kohli ODI centuries 2026',None])
def test_query_translation_preserves_question_without_inventing_answer_or_date(query):
    from actions.web_search import _prepare_search_query
    brain=MagicMock()
    brain.generate_response.return_value={'success':True,'text':json.dumps({'query':query})}
    with patch('core.ai_multitier_engine.get_ai_engine',return_value=brain):
        result=_prepare_search_query('विराट कोहली के ODI में कितने शतक हैं')
    assert result==query if query=='Virat Kohli ODI centuries' else 'शतक' in result
    assert brain.generate_response.call_args.kwargs['record_history'] is False


def test_ordinary_abbreviations_expand_without_model_call():
    from actions.web_search import _prepare_search_query
    with patch('core.ai_multitier_engine.get_ai_engine') as brain:
        assert _prepare_search_query('ind vs nz T20 squad October 2026')=='India vs New Zealand T20 squad October 2026'
    brain.assert_not_called()


def test_rewritten_search_uses_original_hindi_question_for_answer():
    from actions.web_search import web_search_tool
    data={**search_data(),'provider':'fixture'}
    with patch('actions.web_search._prepare_search_query',return_value='Virat Kohli ODI centuries'),patch('actions.web_search.web_search_structured',return_value=data),patch('actions.web_search.fetch_webpage',return_value={'links':[]}),patch('actions.web_research.answer_from_pages',return_value={'success':True}) as answer:
        web_search_tool({'query':'विराट कोहली के ODI में कितने शतक हैं'})
    assert answer.call_args.args[0]=='विराट कोहली के ODI में कितने शतक हैं'
    assert answer.call_args.args[1]['evidence_query']=='Virat Kohli ODI centuries'
    assert answer.call_args.kwargs['current'] is True


def test_historical_stat_is_searched_without_claiming_it_is_today():
    from actions.web_search import _requires_fresh_sources
    assert not _requires_fresh_sources('Virat Kohli ODI centuries in 2023')
    assert _requires_fresh_sources('Virat Kohli ODI centuries now compared to 2023')


def test_failed_answer_gets_one_refined_search_without_guessing_fact():
    from actions.web_search import web_search_tool
    first={'success':True,'results':[{'url':'https://example.org/old','source':'example.org'}]}
    retry={'success':True,'results':[{'url':'https://example.org/current','source':'example.org'}]}
    with patch('actions.web_search.web_search_structured',side_effect=[first,retry]) as search,patch('actions.web_research.answer_from_pages',side_effect=[{'success':False,'message':'Unverified'},{'success':True,'message':'Checked'}]) as answer:
        result=web_search_tool({'query':'latest telescope discovery'})
    assert result['message']=='Checked' and search.call_count==2 and answer.call_count==2
    assert answer.call_args.args[1]['results'][0]['url'].endswith('/current')
    assert 'official source' in search.call_args.args[0]


def test_recovery_stops_after_one_retry():
    from actions.web_search import web_search_tool
    data={'success':True,'results':[{'url':'https://example.org/old','source':'example.org'}]}
    with patch('actions.web_search.web_search_structured',return_value=data) as search,patch('actions.web_research.answer_from_pages',return_value={'success':False,'message':'Unverified'}) as answer:
        result=web_search_tool({'query':'latest telescope discovery'})
    assert not result['success'] and search.call_count==2 and answer.call_count==2


def test_explicit_source_url_is_read_and_not_replaced_by_guessed_url():
    from actions.web_search import web_search_tool
    data={'success':False,'results':[]}
    with patch('actions.web_search.web_search_structured',return_value=data),patch('actions.web_research.answer_from_pages',return_value={'success':True}) as answer:
        web_search_tool({'query':'Check https://example.org/article and explain this announcement'})
    assert answer.call_args.args[1]['results'][0]['url']=='https://example.org/article'


def test_homepage_story_date_and_site_creation_are_not_page_publication():
    from bs4 import BeautifulSoup
    from actions.fetch_webpage import _page_dates
    soup=BeautifulSoup('<script type="application/ld+json">{"@type":"WebSite","datePublished":"2000-01-01"}</script><main><h1>Home</h1><time datetime="2026-10-02">Other news</time></main>','html.parser')
    assert _page_dates(soup)==('','')


def test_article_schema_date_wins_over_organization_schema():
    from bs4 import BeautifulSoup
    from actions.fetch_webpage import _page_dates
    soup=BeautifulSoup('<script type="application/ld+json">{"@graph":[{"@type":"Organization","datePublished":"1990-01-01"},{"@type":"NewsArticle","datePublished":"2026-10-06"}]}</script>','html.parser')
    assert _page_dates(soup)[0]=='2026-10-06'
