# actions/notification_engine.py
# Universal Notification Aggregator & Importance Classifier Engine for JARVIS
# Collects notifications across Android, Windows, and Browser sessions and filters important alerts.

import re
import time
import logging
import hashlib
import threading
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

logger = logging.getLogger("JARVIS.NotificationEngine")


@dataclass
class UniversalNotification:
    id: str
    service_id: str  # "whatsapp", "discord", "instagram", "sms", "phone", etc.
    service_name: str
    sender: str
    title: str
    message: str
    timestamp: float = field(default_factory=time.time)
    platform: str = "windows"  # "windows", "android", "chrome_web"
    priority: str = "MEDIUM"  # "HIGH", "MEDIUM", "LOW"
    is_read: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "service_id": self.service_id,
            "service_name": self.service_name,
            "sender": self.sender,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp,
            "platform": self.platform,
            "priority": self.priority,
            "is_read": self.is_read,
        }


class ImportanceFilter:
    """
    Classifies incoming notifications into HIGH, MEDIUM, or LOW priority.
    Prioritizes direct messages, missed calls, mentions, and urgent replies.
    Deprioritizes ads, recommendations, and system alerts.
    """

    HIGH_PATTERNS = [
        r"\b(missed call|call from|calling|urgent|emergency|help|asap|important)\b",
        r"\b(direct message|dm|sent you a message|mentioned you|replied to you)\b",
        r"\b(otp|verification code|security code)\b"
    ]

    LOW_PATTERNS = [
        r"\b(sale|discount|off|promo|advertisement|update available|news|recommendation|trending)\b",
        r"\b(suggested for you|people you may know|new feature|sponsored)\b"
    ]

    @classmethod
    def classify(cls, service_id: str, sender: str, title: str, message: str) -> str:
        full_text = f"{service_id} {sender} {title} {message}".lower()

        # Check for High Priority
        for pat in cls.HIGH_PATTERNS:
            if re.search(pat, full_text):
                return "HIGH"

        # Check for Low Priority
        for pat in cls.LOW_PATTERNS:
            if re.search(pat, full_text):
                return "LOW"

        # Direct messages on personal chat platforms are default HIGH
        if service_id in ["whatsapp", "sms", "phone", "telegram", "signal"]:
            return "HIGH"
        elif service_id in ["discord", "instagram", "facebook_messenger"]:
            return "MEDIUM"

        return "LOW"


class NotificationAggregator:
    """
    Aggregates notifications from Android, Windows desktop, and Chrome sessions.
    Deduplicates notifications and exposes clean importance-filtered summaries.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NotificationAggregator, cls).__new__(cls)
            cls._instance._notifications: List[UniversalNotification] = []
            cls._instance._lock = threading.RLock()
            cls._instance._initialized = True
        return cls._instance

    def add_notification(self, service_id: str, service_name: str, sender: str, title: str, message: str, platform: str = "windows") -> UniversalNotification:
        priority = ImportanceFilter.classify(service_id, sender, title, message)
        digest = hashlib.sha256(f"{service_id}\0{sender}\0{title}\0{message}\0{platform}".encode()).hexdigest()
        notif_id = digest
        
        notif = UniversalNotification(
            id=notif_id,
            service_id=service_id,
            service_name=service_name,
            sender=sender,
            title=title,
            message=message,
            platform=platform,
            priority=priority,
            is_read=False
        )
        with self._lock:
            for existing in self._notifications:
                if existing.id == digest and time.time() - existing.timestamp < 600:
                    return existing
            self._notifications[:] = [item for item in self._notifications if time.time() - item.timestamp < 86400][-199:]
            self._notifications.append(notif)
        logger.info(f"[NotificationEngine] Aggregated notification: [{priority}] {service_name} from '{sender}': {message[:30]}")
        return notif

    def fetch_recent_notifications(self, min_priority: str = "MEDIUM") -> List[UniversalNotification]:
        """Collects active notifications from system & browser."""
        # Visible chat messages are not evidence of unread notifications.
        # Only explicit captured events belong in this aggregator.
        priority_levels = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        min_level = priority_levels.get(min_priority.upper(), 2)

        with self._lock:
            return [n for n in self._notifications if not n.is_read and time.time() - n.timestamp < 86400 and priority_levels.get(n.priority, 1) >= min_level]

    def get_summary(self, only_important: bool = True) -> Dict[str, Any]:
        notifs = self.fetch_recent_notifications(min_priority="MEDIUM" if only_important else "LOW")
        
        if not notifs:
            return {
                "success": False,
                "verified": False,
                "status": "NOTIFICATION_SOURCE_UNAVAILABLE",
                "count": 0,
                "message": "Live notifications ka access connected nahi hai. WhatsApp ki visible chat padhne ki command de sakte ho.",
                "notifications": []
            }

        high_count = sum(1 for n in notifs if n.priority == "HIGH")
        items_by_service: Dict[str, List[str]] = {}
        for n in notifs:
            items_by_service.setdefault(n.service_name, []).append(f"{n.sender}: {n.message}")

        summary_parts = []
        for s_name, msgs in items_by_service.items():
            summary_parts.append(f"{len(msgs)} on {s_name} ({', '.join(msgs[:2])})")

        msg_str = f"Boss, you have {len(notifs)} important notifications: " + "; ".join(summary_parts) + "."
        return {
            "success": True,
            "verified": True,
            "count": len(notifs),
            "high_priority_count": high_count,
            "message": msg_str,
            "source": "captured_events",
            "notifications": [n.to_dict() for n in notifs]
        }


# Global Instance
notification_aggregator = NotificationAggregator()


def read_aggregated_notifications(only_important: bool = True) -> Dict[str, Any]:
    """Public tool handler for reading notifications."""
    return notification_aggregator.get_summary(only_important=only_important)
