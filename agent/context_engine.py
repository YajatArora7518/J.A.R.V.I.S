# agent/context_engine.py
"""
Normalized Context Engine & Unified Context Analyzer for JARVIS.
Normalizes awareness provider outputs into a concise, lightweight ContextObject.
"""

import time
from typing import Dict, Any, List
from agent.awareness.permissions import privacy_mode_manager, permission_manager
from agent.awareness.camera_provider import camera_provider
from agent.awareness.screen_provider import screen_provider
from agent.awareness.whatsapp_provider import whatsapp_provider
from agent.awareness.email_provider import email_provider
from agent.awareness.calendar_provider import calendar_provider
from agent.awareness.instagram_provider import instagram_provider


class ContextEngine:
    """
    Normalizes feed outputs from all providers into a single lightweight ContextObject.
    """
    def get_current_context(self) -> Dict[str, Any]:
        if privacy_mode_manager.is_privacy_mode_active():
            return {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "active_window": "",
                "activity": "PRIVACY_MODE_ACTIVE",
                "screen_context": "SCREEN_UNAVAILABLE",
                "camera_presence": "CAMERA_UNAVAILABLE",
                "calendar": [],
                "unread_messages": 0,
                "important_notifications": []
            }

        sc = screen_provider.classify_context()
        cc = camera_provider.sample_context()
        wa = whatsapp_provider.check_unread()
        em = email_provider.check_inbox()
        cal = calendar_provider.check_events()
        insta = instagram_provider.check_activity()

        notifications: List[str] = []
        if wa.get("unread_count", 0) > 0:
            notifications.append(f"WhatsApp: {wa['unread_count']} unread message(s)")
        if em.get("unread_count", 0) > 0:
            notifications.append(f"Email: {em['unread_count']} unread message(s)")

        return {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "active_window": sc.get("active_window", ""),
            "activity": sc.get("category", "UNKNOWN"),
            "screen_context": sc,
            "camera_context": cc,
            "whatsapp_context": wa,
            "gmail_context": em,
            "calendar_context": cal,
            "instagram_context": insta,
            "calendar": cal.get("today_events", []),
            "unread_messages": wa.get("unread_count", 0) + em.get("unread_count", 0),
            "important_notifications": notifications,
            "provider_statuses": {
                "camera": cc.get("status", "CAMERA_UNAVAILABLE"),
                "screen": sc.get("status", "SCREEN_UNAVAILABLE"),
                "whatsapp": wa.get("status", "WHATSAPP_UNAVAILABLE"),
                "email": em.get("status", "EMAIL_UNAVAILABLE"),
                "calendar": cal.get("status", "CALENDAR_UNAVAILABLE"),
                "instagram": insta.get("status", "INSTAGRAM_UNAVAILABLE"),
            }
        }


class UnifiedContextAnalyzer:
    """
    Combines authorized provider feeds into concise, privacy-safe human summaries.
    """
    def summarize(self, context: Dict[str, Any]) -> str:
        if privacy_mode_manager.is_privacy_mode_active():
            return "Privacy mode active. Awareness paused."

        items: List[str] = []
        notifs = context.get("important_notifications", [])
        for n in notifs:
            items.append(n)

        cal = context.get("calendar", [])
        if cal:
            items.append(f"Calendar: {len(cal)} event(s) scheduled today")

        if not items:
            return "All clear, Boss. No urgent alerts."

        lines = ["Boss, here is your summary:"]
        for idx, it in enumerate(items, 1):
            lines.append(f"{idx}. {it}")

        return "\n".join(lines)


context_engine = ContextEngine()
unified_analyzer = UnifiedContextAnalyzer()
