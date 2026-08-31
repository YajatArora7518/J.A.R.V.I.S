# actions/web_registry.py
# Scalable Web & Social Media Registry for JARVIS (Strict Yajat Chrome Profile)

import re
import urllib.parse
from typing import Dict, Any, Optional

from actions.chrome_profile import open_url_in_chrome_profile, resolve_chrome_profile

# Canonical dictionary mapping supported platforms & web services to their official URLs
KNOWN_WEBSITES: Dict[str, str] = {
    # Special Communication / Chat Web Apps
    "whatsapp": "https://web.whatsapp.com/",
    "whatsapp web": "https://web.whatsapp.com/",
    "whats app": "https://web.whatsapp.com/",
    "telegram": "https://web.telegram.org/",
    "telegram web": "https://web.telegram.org/",
    
    # Social Media Platforms
    "instagram": "https://www.instagram.com/",
    "insta": "https://www.instagram.com/",
    "facebook": "https://www.facebook.com/",
    "fb": "https://www.facebook.com/",
    "twitter": "https://x.com/",
    "x": "https://x.com/",
    "youtube": "https://www.youtube.com/",
    "yt": "https://www.youtube.com/",
    "reddit": "https://www.reddit.com/",
    "discord": "https://discord.com/app",
    "linkedin": "https://www.linkedin.com/",
    "pinterest": "https://www.pinterest.com/",
    "snapchat": "https://web.snapchat.com/",
    "snap": "https://web.snapchat.com/",
    "spotify": "https://open.spotify.com/",
    
    # Developer & Workspace Services
    "github": "https://github.com/",
    "gmail": "https://mail.google.com/",
    "google drive": "https://drive.google.com/",
    "drive": "https://drive.google.com/",
    "google docs": "https://docs.google.com/",
    "docs": "https://docs.google.com/",
    "google maps": "https://maps.google.com/",
    "maps": "https://maps.google.com/",
    "google": "https://www.google.com/",
}


def resolve_website_url(raw_input: str) -> Optional[Dict[str, str]]:
    """
    Resolves input text into a canonical web service record or safe HTTP/HTTPS URL.
    Returns dict with 'name', 'url', and 'category' if valid, or None.
    """
    if not raw_input:
        return None

    cleaned = raw_input.strip().lower()
    
    # Remove common prefixes like 'open ', 'visit ', 'go to ', 'kholo', 'open karo'
    prefixes = [r"^open\s+", r"^visit\s+", r"^go\s+to\s+", r"^launch\s+"]
    suffixes = [r"\s+kholo$", r"\s+khol$", r"\s+open\s+karo$", r"\s+karo$", r"\s+app$"]

    query = cleaned
    for p in prefixes:
        query = re.sub(p, "", query).strip()
    for s in suffixes:
        query = re.sub(s, "", query).strip()

    # 1. Exact match in KNOWN_WEBSITES
    if query in KNOWN_WEBSITES:
        url = KNOWN_WEBSITES[query]
        name = query.title()
        return {"name": name, "url": url, "category": "social_web" if "instagram" in query or "youtube" in query or "reddit" in query else "known_website"}

    # 2. Check if input is a valid domain (e.g. example.com, github.com)
    domain_match = re.search(r"\b([a-zA-Z0-9\-]+\.(com|org|net|io|ai|gov|edu|in|co|app))\b", cleaned)
    if domain_match:
        domain = domain_match.group(1)
        url = f"https://{domain}"
        return {"name": domain, "url": url, "category": "generic_website"}

    # 3. Direct URL (http:// or https://)
    url_match = re.search(r"https?://[^\s]+", cleaned)
    if url_match:
        url = url_match.group(0)
        return {"name": "Web Destination", "url": url, "category": "generic_website"}

    return None


def open_website_in_yajat_profile(target_query_or_url: str) -> Dict[str, Any]:
    """
    Opens any requested website or social media platform strictly inside Chrome profile 'Yajat'.
    Enforces normal mode, no incognito, no guest mode, no Edge, no desktop fallbacks.
    """
    resolved = resolve_website_url(target_query_or_url)
    if not resolved:
        # Fallback to direct URL normalization if safely formatted
        clean_target = target_query_or_url.strip()
        if not clean_target.startswith("http"):
            clean_target = f"https://{clean_target}"
        resolved = {"name": target_query_or_url, "url": clean_target, "category": "generic_website"}

    target_url = resolved["url"]
    display_name = resolved["name"]

    res = open_url_in_chrome_profile(profile_name="Yajat", url=target_url)
    if not res.get("success"):
        return {
            "success": False,
            "action": "open_website",
            "service": display_name,
            "message": res.get("message", "Yajat Chrome profile was not found."),
            "verified": False
        }

    return {
        "success": True,
        "action": "open_website",
        "service": display_name,
        "url": target_url,
        "category": resolved.get("category", "website"),
        "message": f"Opening {display_name} in your Yajat Chrome profile.",
        "verified": True
    }
