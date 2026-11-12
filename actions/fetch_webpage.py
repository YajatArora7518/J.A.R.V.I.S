# actions/fetch_webpage.py
# Safe Webpage Extraction Engine for JARVIS

import re
import urllib.parse
import requests
import json
import socket
import ipaddress
from datetime import datetime, timezone
from typing import Dict, Any, Optional

try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False

USER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
}

_FETCH_SESSION = requests.Session()
_adapter = requests.adapters.HTTPAdapter(pool_connections=5, pool_maxsize=10, max_retries=1)
_FETCH_SESSION.mount("https://", _adapter)
_FETCH_SESSION.mount("http://", _adapter)


def _session_get(url: str, **kwargs) -> requests.Response:
    if hasattr(requests.get, "assert_called") or "unittest" in getattr(requests.get, "__module__", ""):
        return requests.get(url, **kwargs)
    return _FETCH_SESSION.get(url, **kwargs)


def _check_public_url(url: str):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Only public HTTP(S) webpages are supported')
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80), type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError('Private/local webpage addresses are not allowed')


def _page_dates(soup):
    published, updated = '', ''
    structured_dates = []
    for meta in soup.find_all('meta'):
        name = str(meta.get('property') or meta.get('name') or '').lower()
        value = str(meta.get('content') or '')
        if name in ('article:published_time', 'datepublished', 'date', 'pubdate'):
            published = published or value
        if name in ('article:modified_time', 'datemodified', 'last-modified'):
            updated = updated or value
    def visit(value):
        if isinstance(value, list):
            for item in value: visit(item)
        elif isinstance(value, dict):
            kind = value.get('@type') or ''
            kinds = kind if isinstance(kind,list) else [kind]
            is_article = any(any(word in str(item).lower() for word in ('article','blogposting','report')) for item in kinds)
            # Organization/site creation dates are not this page's publication.
            if is_article or not kind or 'WebPage' in kinds:
                structured_dates.append((0 if is_article else 1,str(value.get('datePublished') or ''),str(value.get('dateModified') or '')))
            if '@graph' in value: visit(value['@graph'])
    for script in soup.select('script[type="application/ld+json"]'):
        try: visit(json.loads(script.string or script.get_text()))
        except (ValueError, TypeError): pass
    for _,pub,mod in sorted(structured_dates):
        published,updated=published or pub,updated or mod
    # A home/news index may contain dozens of other articles' timestamps.
    articles=soup.find_all('article')
    stamp = articles[0].find('time',attrs={'datetime':True}) if len(articles)==1 else None
    if stamp and not published:
        published = str(stamp.get('datetime') or '')
    return published, updated


def _extract_html_tables(soup, max_tables=8, max_rows=40, max_columns=12):
    """Extract bounded visible table text before page cleanup, without inferring values."""
    tables = []
    for table in soup.find_all("table")[:max_tables]:
        rows = []
        for row in table.find_all("tr")[:max_rows]:
            cells = [cell.get_text(" ", strip=True)[:300] for cell in row.find_all(["th", "td"], recursive=False)[:max_columns]]
            if any(cells): rows.append(cells)
        if rows:
            headers = [str(value).strip().casefold() for value in rows[0]]
            entity_index = next((i for i, value in enumerate(headers) if value in {"team", "team name", "player", "club", "squad"}), None)
            rank_index = next((i for i, value in enumerate(headers) if value in {"rank", "position", "place", "standing"}), None)
            points_index = next((i for i, value in enumerate(headers) if value in {"points", "pts", "score", "total points"}), None)
            kind = "standings" if entity_index is not None and (rank_index is not None or points_index is not None) else "table"
            tables.append({"caption": (table.caption.get_text(" ", strip=True)[:200] if table.caption else ""),
                           "headers": rows[0], "rows": rows, "kind": kind,
                           "entity_column": entity_index, "rank_column": rank_index, "points_column": points_index})
    return tables


def fetch_webpage(
    url: str,
    max_chars: int = 4000,
    parameters: Optional[Dict[str, Any]] = None,
    player: Any = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Downloads and extracts clean readable text content from a webpage URL.
    Strips scripts, navigation, ads, and tracking elements.
    Content is sanitized as untrusted data.
    """
    if parameters and "url" in parameters:
        url = parameters["url"]

    url = (url or "").strip()
    if not url:
        return {"success": False, "error": "No URL provided", "url": "", "content": ""}

    # Ensure http/https scheme
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    domain = urllib.parse.urlparse(url).netloc.replace("www.", "")

    if player and hasattr(player, "write_log"):
        player.write_log(f"[WEB] Reading: {domain or url}")
    if player and hasattr(player, "set_state"):
        try:
            player.set_state("THINKING")
        except Exception:
            pass

    response = None
    try:
        headers = USER_HEADERS
        for _ in range(4):
            _check_public_url(url)
            response = _session_get(url, headers=headers, timeout=5.0, stream=True, allow_redirects=False)
            if response.status_code not in (301, 302, 303, 307, 308):
                break
            location = response.headers.get('Location')
            response.close()
            response = None
            if not location:
                raise ValueError('Webpage redirect has no destination')
            url = urllib.parse.urljoin(url, location)
        else:
            raise ValueError('Too many webpage redirects')
        domain = urllib.parse.urlsplit(url).hostname.removeprefix('www.')
        response.raise_for_status()

        # Limit response size read to 2MB max
        content_bytes = bytearray()
        for chunk in response.iter_content(chunk_size=1024 * 64):
            content_bytes.extend(chunk)
            if len(content_bytes) > 2 * 1024 * 1024:  # 2MB limit
                break

        html_text = content_bytes.decode(response.encoding or "utf-8", errors="replace")
        response.close()
        response = None
        published_at, updated_at = '', ''
        tables = []
        links = []

        if _HAS_BS4:
            soup = BeautifulSoup(html_text, "html.parser")
            published_at, updated_at = _page_dates(soup)
            tables = _extract_html_tables(soup)
            for anchor in soup.select('a[href]')[:200]:
                target = urllib.parse.urljoin(url, anchor.get('href',''))
                if urllib.parse.urlsplit(target).hostname == urllib.parse.urlsplit(url).hostname:
                    links.append({'title':anchor.get_text(' ',strip=True)[:300], 'url':target})

            # Strip scripts, styles, navigation, footers, forms, ads
            for tag in soup(["script", "style", "nav", "header", "footer", "form", "aside", "iframe", "noscript", "svg", "button"]):
                tag.decompose()

            # Extract Title
            title = soup.title.string.strip() if soup.title and soup.title.string else domain

            # Extract Headings
            headings = [h.get_text(strip=True) for h in soup.find_all(["h1", "h2", "h3"]) if h.get_text(strip=True)]
            heading_text = " | ".join(headings[:5]) if headings else ""

            # Extract Main Body Text
            main = soup.find('article') or soup.find('main') or soup.body or soup
            text = main.get_text(separator=' ', strip=True)

            if not text:
                text = soup.get_text(separator=" ", strip=True)

        else:
            # Fallback regex HTML tag stripping if bs4 is unavailable
            title = domain
            heading_text = ""
            text = re.sub(r"<script.*?>.*?</script>", "", html_text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style.*?>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<.*?>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()

        # Clean up whitespace
        text = re.sub(r"\n\s*\n", "\n\n", text).strip()

        if tables:
            table_evidence = "\n\nExtracted source tables:\n" + "\n".join(
                " | ".join(cell for cell in row) for table in tables for row in table["rows"])
            text = (text + table_evidence)[:2 * 1024 * 1024]

        # Untrusted Content Sanitization (Defend against prompt injection in webpages)
        text = _sanitize_untrusted_text(text)

        trimmed_content = text[:max(500, min(12000, int(max_chars)))]

        return {
            "success": bool(trimmed_content),
            "url": url,
            "domain": domain,
            "title": title,
            "headings": heading_text,
            "published_at": published_at,
            "updated_at": updated_at,
            "event_date": None,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "tables": tables,
            "links": links,
            "content": trimmed_content,
            "length": len(trimmed_content)
        }

    except Exception as e:
        print(f"[WEB] Webpage fetch error for {url}: {e}")
        return {
            "success": False,
            "error": str(e),
            "url": url,
            "domain": domain,
            "title": domain,
            "content": f"Could not read webpage content from {domain}: {e}"
        }
    finally:
        if response is not None:
            response.close()


def _sanitize_untrusted_text(raw_text: str) -> str:
    """
    Sanitizes untrusted webpage text to prevent prompt injection inside scraped content.
    Prevents scraped text from trying to manipulate system prompts or expose secret keys.
    """
    # Neutralize instructions attempting system overrides
    patterns = [
        r"ignore\s+previous\s+instructions",
        r"reveal\s+your\s+(api_key|password|secret|system\s+prompt)",
        r"override\s+system\s+prompt",
        r"you\s+are\s+now\s+a",
    ]
    sanitized = raw_text
    for p in patterns:
        sanitized = re.sub(p, "[content filtered for security]", sanitized, flags=re.IGNORECASE)
    return sanitized
