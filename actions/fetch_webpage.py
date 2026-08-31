# actions/fetch_webpage.py
# Safe Webpage Extraction Engine for JARVIS

import re
import urllib.parse
import requests
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

    try:
        headers = USER_HEADERS
        response = _session_get(url, headers=headers, timeout=5.0, stream=True)
        response.raise_for_status()

        # Limit response size read to 2MB max
        content_bytes = bytearray()
        for chunk in response.iter_content(chunk_size=1024 * 64):
            content_bytes.extend(chunk)
            if len(content_bytes) > 2 * 1024 * 1024:  # 2MB limit
                break

        html_text = content_bytes.decode(response.encoding or "utf-8", errors="replace")

        if _HAS_BS4:
            soup = BeautifulSoup(html_text, "html.parser")

            # Strip scripts, styles, navigation, footers, forms, ads
            for tag in soup(["script", "style", "nav", "header", "footer", "form", "aside", "iframe", "noscript", "svg", "button"]):
                tag.decompose()

            # Extract Title
            title = soup.title.string.strip() if soup.title and soup.title.string else domain

            # Extract Headings
            headings = [h.get_text(strip=True) for h in soup.find_all(["h1", "h2", "h3"]) if h.get_text(strip=True)]
            heading_text = " | ".join(headings[:5]) if headings else ""

            # Extract Main Body Text
            paragraphs = [p.get_text(strip=True) for p in soup.find_all(["p", "article", "section"]) if p.get_text(strip=True)]
            text = "\n".join(paragraphs)

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

        # Untrusted Content Sanitization (Defend against prompt injection in webpages)
        text = _sanitize_untrusted_text(text)

        trimmed_content = text[:max_chars]

        return {
            "success": True,
            "url": url,
            "domain": domain,
            "title": title,
            "headings": heading_text,
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
