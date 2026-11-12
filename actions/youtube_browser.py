"""Search actual video cards, compare available captions, verify media playback."""
import asyncio
import re
import time
from urllib.parse import parse_qs, quote_plus, urlsplit


def video_id(url):
    try:
        parts = urlsplit(str(url))
        host = (parts.hostname or '').lower()
        port = parts.port
    except ValueError:
        return None
    if parts.scheme != 'https' or parts.username or parts.password or port not in (None, 443):
        return None
    if host == 'youtu.be':
        value = parts.path.strip('/').split('/')[0]
    elif host in ('youtube.com', 'www.youtube.com', 'm.youtube.com'):
        value = parse_qs(parts.query).get('v', [''])[0] if parts.path == '/watch' else parts.path.split('/')[-1] if parts.path.startswith(('/embed/', '/shorts/', '/v/')) else ''
    else:
        return None
    return value if re.fullmatch(r'[A-Za-z0-9_-]{11}', value) else None


def expand_query(query):
    query = re.sub(r'थर्मो(?:डायनेमिक्स)?', 'thermodynamics', query)
    query = re.sub(r'केटीजी|गतिज सिद्धांत', 'kinetic theory of gases', query)
    query = re.sub(r'हिंग्लिश', 'Hinglish', query)
    query = re.sub(r'हिन्दी|हिंदी', 'Hindi', query)
    query = re.sub(r'\bthermo\b', 'thermodynamics', query, flags=re.I)
    query = re.sub(r'\bktg\b', 'kinetic theory of gases', query, flags=re.I)
    return query


def preferred_query(query):
    # User's saved preference is Hinglish; preserve explicit language overrides.
    if not re.search(r'\b(?:hindi|hinglish|english|tamil|bengali|telugu)\b', query, re.I):
        return expand_query(query) + ' Hindi Hinglish'
    return expand_query(query)


def parse_youtube_request(text):
    raw = text.strip()
    low = raw.casefold()
    if not re.search(r'\b(?:youtube|yt|video|videos|lecture|lectures)\b|वीडियो|यूट्यूब', low):
        return None
    if not re.search(r'\b(?:search|find|play|chala|chalao|dhund|dhoond|khol|kholo|open|recommend|best|bata|dikha|chahiye)\w*\b|चला|खोल|ढूंढ|ढूँढ|चाहिए|सर्च|सबसे अच्छा', low):
        return None
    if re.fullmatch(r'(?:open|khol|kholo)\s+(?:youtube|yt)|(?:youtube|yt)\s+(?:khol|kholo)(?:\s+do)?', low):
        return None  # Preserve opening the homepage.
    if re.fullmatch(r'(?:open|khol|kholo)\s+(?:https?://)?(?:www\.)?youtube\.com/?|(?:https?://)?(?:www\.)?youtube\.com/?\s+(?:khol|kholo)(?:\s+do)?', low):
        return None
    url = re.search(r'https://(?:www\.)?(?:youtube\.com|youtu\.be)/\S+', raw)
    if url and video_id(url[0].rstrip('.,')):
        return {'action': 'play', 'url': url[0].rstrip('.,'), 'query': raw}
    query = re.sub(r'\b(?:youtube|yt|videos?|lectures?|par|pe|on|for|search|find|play|chalao?|open|kholo?|dhund|dhoond|recommend|best|batao?|dikhao?|please|mujhe|mere|ki|ka|ke|karo?|do|chahiye)\b', ' ', raw, flags=re.I)
    query = re.sub(r'यूट्यूब|वीडियो|लेक्चर|ढूंढो?|ढूँढो?|चलाओ?|खोलो?|चाहिए|सर्च|सबसे अच्छा|(?:^|\s)(?:की|का|के|पर|पे|और|मुझे|कर|दो)(?=\s|$)', ' ', query)
    query = re.sub(r'\s+', ' ', query).strip(' .,:?!')
    if not query:
        return {'action': 'play', 'query': ''}
    action = 'recommend' if re.search(r'\b(?:best|recommend)\b|सबसे अच्छा', low) else 'play'
    if re.search(r'\b(?:sirf|only)\b.*\b(?:search|results)\b', low):
        action = 'search_only'
    return {'action': action, 'query': expand_query(query)}


def _terms(query):
    return set(re.findall(r'[a-z]{3,}', expand_query(query).lower())) - {'hindi', 'hinglish', 'english', 'video', 'videos', 'lecture', 'one', 'shot', 'best', 'and', 'complete', 'the', 'sirf', 'only', 'results'}


def rank_candidates(candidates, query):
    terms = _terms(query)
    scored = []
    for item in candidates:
        title_terms = set(re.findall(r'[a-z]{3,}', expand_query(item.get('title', '')).lower()))
        score = len(terms & title_terms)
        if not terms or score / len(terms) >= .4:
            scored.append({**item, 'relevance': score})
    return sorted(scored, key=lambda x: x['relevance'], reverse=True)


async def search_videos(query):
    from actions.browser_automation import browser_automation_engine as engine
    url = 'https://www.youtube.com/results?search_query=' + quote_plus(preferred_query(query)) + '&sp=EgIQAQ%3D%3D'
    page = await engine.get_or_open_page('youtube.com', url)
    # The reusable engine intentionally returns an existing tab without navigating it.
    await page.goto(url, wait_until='domcontentloaded', timeout=25000)
    cards = page.locator('ytd-video-renderer')
    await cards.first.wait_for(state='visible', timeout=18000)
    items, seen = [], set()
    for i in range(min(await cards.count(), 12)):
        card = cards.nth(i)
        link = card.locator('a#video-title').first
        href = await link.get_attribute('href') or ''
        full = 'https://www.youtube.com' + href if href.startswith('/') else href
        identifier = video_id(full)
        if not identifier or '/shorts/' in full or identifier in seen:
            continue
        seen.add(identifier)
        title = re.sub(r'\s+', ' ', await link.inner_text()).strip()
        channel = card.locator('ytd-channel-name').first
        channel_text = re.sub(r'\s+', ' ', await channel.inner_text()).strip() if await channel.count() else ''
        if title:
            items.append({'title': title, 'channel': channel_text,
                          'url': 'https://www.youtube.com/watch?v=' + identifier})
    return page, rank_candidates(items, query)


def playback_verified(before, after, expected, actual_url):
    return bool(video_id(actual_url) == expected and not after.get('ad') and not after.get('paused', True)
                and not after.get('ended', True) and after.get('ready', 0) >= 2
                and after.get('time', 0) > before.get('time', 0) + .1)


async def play_video(page, url):
    identifier = video_id(url)
    if not identifier:
        raise ValueError('Valid YouTube video link do.')
    await page.goto('https://www.youtube.com/watch?v=' + identifier, wait_until='domcontentloaded', timeout=25000)
    await page.locator('video').first.wait_for(state='visible', timeout=18000)
    await page.bring_to_front()
    read_media = """() => {const v=document.querySelector('video');return v ? {
      time:v.currentTime,paused:v.paused,ended:v.ended,ready:v.readyState,
      ad:!!document.querySelector('.html5-video-player.ad-showing')} : {paused:true};}"""
    first = await page.evaluate(read_media)
    deadline = time.monotonic() + 40
    started = False
    # Ads are not the requested lecture; let them finish or use the offered Skip.
    while time.monotonic() < deadline:
        if first.get('paused') and not started:
            button = page.locator('button.ytp-play-button').first
            if await button.count() and await button.is_visible():
                await button.click()
                started = True
        if first.get('ad'):
            skip = page.locator('button.ytp-skip-ad-button, button.ytp-ad-skip-button, button.ytp-ad-skip-button-modern').first
            if await skip.count() and await skip.is_visible():
                await skip.click()
        await asyncio.sleep(.8)
        current = await page.evaluate(read_media)
        if playback_verified(first, current, identifier, page.url):
            return True
        first = current
    return False


def review_candidates(candidates, query):
    from actions.youtube_video import _get_transcript
    from core.study_documents import analyze_document
    reviewed = []
    for item in candidates[:2]:
        text = _get_transcript(video_id(item['url']))
        if text and len(text) > 60000:
            # Sample throughout a long lecture instead of judging it by its introduction.
            step = (len(text) - 5000) // 11
            text = '\n'.join(text[i * step:i * step + 5000] for i in range(12))
        text = text or ''
        terms = _terms(query)
        found = sorted(t for t in terms if re.search(r'\b' + re.escape(t) + r'\b', text.lower()))
        concepts = analyze_document({'units': [{'id': 1, 'text': text}]},
            f'Query: {query}. In caption samples mein is query se related kaunse concepts actually explain huye hain? Sirf text se proven concepts batao; whole video quality ya full coverage claim mat karo.') if text else []
        reviewed.append({**item, 'review_basis': 'captions' if text else 'title_only',
                         'caption_topic_matches': found, 'caption_chars_reviewed': len(text),
                         'verified_concepts': concepts,
                         'caption_review_scope': 'bounded samples; whole lecture not watched'})
    return sorted(reviewed, key=lambda x: (len(x['verified_concepts']), bool(x['caption_topic_matches']), x['relevance']), reverse=True)


async def _execute(parameters):
    action = parameters.get('action', 'play')
    query = str(parameters.get('query', '')).strip()
    url = str(parameters.get('url', '')).strip()
    from actions.browser_automation import browser_automation_engine as engine
    if url:
        if not video_id(url):
            raise ValueError('Valid YouTube video link do.')
        page = await engine.get_or_open_page('youtube.com', url)
        candidates = [{'title': 'YouTube video', 'url': url, 'channel': ''}]
    elif query:
        page, candidates = await search_videos(query)
    else:
        raise ValueError('Kis topic ka video chalaun? Topic bata do.')
    if not candidates:
        return {'success': False, 'verified': False, 'message': 'Relevant video result nahi mila. Query thodi clear karo.', 'status': 'NO_RELEVANT_VIDEO'}
    if action == 'recommend':
        candidates = await asyncio.to_thread(review_candidates, candidates, query)
    if action == 'search_only':
        lines = [f"{i+1}. {c['title']} — {c['channel']}\n{c['url']}" for i, c in enumerate(candidates[:3])]
        return {'success': True, 'verified': True, 'message': '\n'.join(lines), 'videos': candidates[:3], 'status': 'RESULTS_FOUND'}
    selected = candidates[0]
    playing = await play_video(page, selected['url'])
    msg = f"{selected['title']} — {selected['channel']}\n{selected['url']}\n"
    msg += 'Video chal raha hai.' if playing else 'Video page khula hai, lekin playback confirm nahi hua—player par login, ad ya autoplay block ho sakta hai.'
    if action == 'recommend':
        basis = selected.get('review_basis')
        msg += '\nCaptions ke limited samples aur query relevance compare ki; poora lecture watch nahi kiya.' if basis == 'captions' else '\nCaptions nahi mile; selection title ki relevance par hai. Full coverage ya best hone ka claim verify nahi kar saka.'
        concepts = selected.get('verified_concepts', [])
        if concepts:
            msg += '\nCaption evidence mein ye concepts mile: ' + ', '.join(c['title'] for c in concepts[:5]) + '.'
        msg += '\nTere exact syllabus se match karke hi bata sakta hoon ki kitna cover hoga; syllabus/PDF attach kar dena.'
        msg += '\nLecture ke baad 10 questions khud solve karo; jo topic atke usko dobara dekho.'
        for candidate in candidates[1:3]:
            msg += f"\nAlternative: {candidate['title']}\n{candidate['url']}"
    return {'success': playing, 'verified': playing, 'message': msg, 'videos': candidates[:3],
            'status': 'PLAYING' if playing else 'PLAYBACK_UNVERIFIED', 'selected_url': selected['url']}


def youtube_browser(parameters, **kwargs):
    from actions.browser_automation import browser_automation_engine as engine
    try:
        result = engine.run(_execute(parameters), timeout=110)
    except Exception as exc:
        message = str(exc) if isinstance(exc, ValueError) else 'YouTube search/playback complete nahi hua. Login, network ya page layout check karna padega; playing ka claim nahi kar raha.'
        result = {'success': False, 'verified': False, 'message': message, 'status': 'YOUTUBE_FAILED'}
    return {**result, 'authoritative_response': True}
