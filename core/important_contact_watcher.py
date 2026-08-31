# core/important_contact_watcher.py
# High-Priority Contact Message Watcher & Deduplication Engine for JARVIS

import json
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

logger = logging.getLogger("JARVIS.ImportantContactWatcher")

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "important_contacts.json"

DEFAULT_IMPORTANT_CONTACTS = ["Papa", "Mom", "Family", "Dad"]


class ImportantContactWatcher:
    """Manages high-priority contact alerts with read-aloud confirmation and deduplication."""

    def __init__(self):
        self.important_contacts: List[str] = self._load_contacts()
        self.seen_messages: Set[str] = set()

    def _load_contacts(self) -> List[str]:
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("important_contacts", DEFAULT_IMPORTANT_CONTACTS)
            except Exception as e:
                logger.warning(f"Failed to load important contacts: {e}")
        return DEFAULT_IMPORTANT_CONTACTS.copy()

    def _save_contacts(self) -> None:
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump({"important_contacts": self.important_contacts}, f, indent=4)
        except Exception as e:
            logger.warning(f"Failed to save important contacts: {e}")

    def add_important_contact(self, name: str) -> Dict[str, Any]:
        c_name = name.strip()
        if c_name and c_name not in self.important_contacts:
            self.important_contacts.append(c_name)
            self._save_contacts()
            return {"success": True, "message": f"'{c_name}' added to important contacts.", "contacts": self.important_contacts}
        return {"success": True, "message": f"'{c_name}' is already in important contacts.", "contacts": self.important_contacts}

    def remove_important_contact(self, name: str) -> Dict[str, Any]:
        c_name = name.strip()
        if c_name in self.important_contacts:
            self.important_contacts.remove(c_name)
            self._save_contacts()
            return {"success": True, "message": f"'{c_name}' removed from important contacts.", "contacts": self.important_contacts}
        return {"success": False, "message": f"'{c_name}' was not found in important contacts.", "contacts": self.important_contacts}

    def is_important_contact(self, contact_name: str) -> bool:
        c_lower = (contact_name or "").strip().lower()
        return any(imp.lower() in c_lower or c_lower in imp.lower() for imp in self.important_contacts)

    def process_incoming_message(self, platform: str, contact: str, message_text: str, timestamp: str = "") -> Optional[Dict[str, Any]]:
        """
        Evaluates incoming message for important contact alert & deduplication.
        Returns prompt dictionary if genuine new message from important contact.
        """
        if not self.is_important_contact(contact):
            return None

        # Compute deduplication hash (platform, contact, message_text)
        msg_sig = f"{platform.lower()}:{contact.lower()}:{message_text.strip()}:{timestamp}"
        msg_hash = hashlib.sha256(msg_sig.encode("utf-8")).hexdigest()

        if msg_hash in self.seen_messages:
            logger.debug(f"[Watcher] Duplicate message suppressed for {contact}: {message_text[:20]}...")
            return None

        self.seen_messages.add(msg_hash)
        logger.info(f"[Watcher] Important contact message detected from '{contact}': {message_text}")

        prompt_str = f"Boss, {contact} ka message aaya hai. Padhun?"
        return {
            "platform": platform,
            "contact": contact,
            "message_text": message_text,
            "prompt": prompt_str,
            "requires_approval": True,
            "status": "IMPORTANT_MESSAGE_ALERT"
        }


default_important_watcher = ImportantContactWatcher()
