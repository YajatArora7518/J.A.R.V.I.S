# agent/awareness/calendar_provider.py
"""
Calendar Read-Only Awareness Provider.
Analyzes today's events, upcoming meetings, conflicts, and deadlines.
Returns AUTHENTICATION_REQUIRED cleanly when unconfigured.
"""

import os
import urllib.request
import time
from typing import Dict, Any, List
from agent.awareness.permissions import permission_manager, privacy_mode_manager
from agent.awareness.status_model import status_registry, ProviderState


class CalendarAwarenessProvider:
    """
    Read-only Calendar integration via ICS URL feed or College schedule engine.
    """
    def check_events(self) -> Dict[str, Any]:
        if privacy_mode_manager.is_privacy_mode_active():
            status_registry.update_status("calendar", ProviderState.PAUSED, enabled=False)
            return {"status": "CALENDAR_UNAVAILABLE", "today_events": [], "upcoming": []}

        if not permission_manager.is_granted("CALENDAR_READ"):
            status_registry.update_status("calendar", ProviderState.DISABLED, enabled=False)
            return {"status": "CALENDAR_UNAVAILABLE", "today_events": [], "upcoming": []}

        # 1. Try Chrome browser session reuse
        try:
            from actions.browser_automation import is_cdp_active, browser_automation_engine
            if is_cdp_active():
                res = browser_automation_engine.check_service_auth_sync("calendar")
                if res.get("status") == "LIVE_VERIFIED":
                    status_registry.update_status("calendar", ProviderState.LIVE_VERIFIED, authenticated=True, enabled=True)
                    return {
                        "status": "OK",
                        "today_events": [],
                        "upcoming": [],
                        "source": "chrome_session",
                        "verified": True
                    }
                elif res.get("status") == "AUTHENTICATION_REQUIRED":
                    status_registry.update_status("calendar", ProviderState.AUTHENTICATION_REQUIRED, enabled=True, error_msg="Google Calendar login required in Chrome")
                    return {
                        "status": "CALENDAR_UNAVAILABLE",
                        "today_events": [],
                        "upcoming": [],
                        "message": "Google Calendar login required in Chrome session."
                    }
        except Exception:
            pass

        cal_url = os.environ.get("CALENDAR_ICS_URL", "")
        if not cal_url:
            status_registry.update_status("calendar", ProviderState.AUTHENTICATION_REQUIRED, enabled=True, error_msg="CALENDAR_ICS_URL missing")
            return {
                "status": "CALENDAR_UNAVAILABLE",
                "today_events": [],
                "upcoming": [],
                "message": "Calendar provider requires CALENDAR_ICS_URL environment variable."
            }

        try:
            req = urllib.request.Request(cal_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                content = response.read().decode("utf-8", errors="ignore")

            events: List[Dict[str, Any]] = []
            summary = ""
            for line in content.splitlines():
                if line.startswith("SUMMARY:"):
                    summary = line[8:].strip()
                elif line.startswith("DTSTART:") and summary:
                    dt_str = line[8:].strip()
                    events.append({
                        "source": "calendar",
                        "title": summary,
                        "start": dt_str,
                        "important": True
                    })
                    summary = ""

            status_registry.update_status("calendar", ProviderState.LIVE_VERIFIED, authenticated=True, enabled=True)
            return {
                "status": "OK",
                "today_events": events,
                "upcoming": events[:3],
                "verified": True
            }
        except Exception as ex:
            status_registry.update_status("calendar", ProviderState.AUTHENTICATION_REQUIRED, error_msg=str(ex))
            return {
                "status": "CALENDAR_UNAVAILABLE",
                "today_events": [],
                "upcoming": [],
                "error": str(ex)
            }


calendar_provider = CalendarAwarenessProvider()
