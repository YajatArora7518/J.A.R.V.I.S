# actions/app_first_routing.py
# Intelligent Application & Web Routing Engine for JARVIS (Native Desktop First + Disambiguation)

import logging
from typing import Dict, Any, Optional

from actions.app_registry import resolve_app, is_app_installed

logger = logging.getLogger("JARVIS.AppFirstRouting")


def resolve_app_or_web_target(target_name: str) -> Dict[str, Any]:
    """
    Intelligent routing priority:
    1. EXPLICIT MODE: User explicitly said 'web' or 'app/desktop' -> Directly select mode.
    2. NATIVE ONLY: Only native app installed -> launch native.
    3. WEB ONLY: Native app not installed & web URL exists -> web fallback.
    4. BOTH AVAILABLE & AMBIGUOUS -> Returns AMBIGUOUS_NATIVE_AND_WEB to trigger conversational prompt.
    """
    raw_name = (target_name or "").strip()
    lower_name = raw_name.lower()

    explicit_web = any(w in lower_name for w in ["web", "browser", "chrome", "edge", "online"])
    explicit_app = any(w in lower_name for w in ["app", "desktop", "native", "software"])

    # Clean target name for registry lookup
    clean_name = lower_name
    for w in ["web", "browser", "chrome", "edge", "online", "app", "desktop", "native", "software", "kholo", "khol", "open", "launch"]:
        clean_name = clean_name.replace(w, "").strip()

    app_info = resolve_app(clean_name or raw_name)
    if not app_info:
        return {
            "status": "UNKNOWN_APP",
            "app_canonical": raw_name,
            "launch_mode": "web" if explicit_web else "native",
            "message": f"Unknown application '{raw_name}'."
        }

    app_canonical = app_info.get("name", raw_name)
    has_native = is_app_installed(clean_name or raw_name) or app_info.get("installed", False)
    has_web = bool(app_info.get("web_url"))

    # Explicit instruction wins
    if explicit_app and has_native:
        return {
            "status": "EXPLICIT_NATIVE",
            "app_canonical": app_canonical,
            "launch_mode": "native",
            "app_info": app_info
        }

    if explicit_web and has_web:
        return {
            "status": "EXPLICIT_WEB",
            "app_canonical": app_canonical,
            "launch_mode": "web",
            "web_url": app_info.get("web_url"),
            "app_info": app_info
        }

    # Opening an installed app is unambiguous; use its web version if absent.
    if has_native:
        return {
            "status": "NATIVE_AVAILABLE",
            "app_canonical": app_canonical,
            "launch_mode": "native",
            "app_info": app_info
        }

    if has_web and not explicit_app:
        return {"status": "WEB_AVAILABLE", "app_canonical": app_canonical,
                "launch_mode": "web", "web_url": app_info["web_url"], "app_info": app_info}
    return {
        "status": "APP_NOT_FOUND",
        "app_canonical": app_canonical,
        "launch_mode": "none",
        "message": f"Application '{app_canonical}' is not installed on this system."
    }
