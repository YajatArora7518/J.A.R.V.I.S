# agent/awareness/email_provider.py
"""
Email Read-Only Awareness Provider.
Analyzes unread messages via IMAP SSL if environment credentials are provided.
Returns AUTHENTICATION_REQUIRED cleanly when unconfigured.
"""

import os
import imaplib
import email
from email.header import decode_header
from typing import Dict, Any, List
from agent.awareness.permissions import permission_manager, privacy_mode_manager
from agent.awareness.status_model import status_registry, ProviderState


class EmailAwarenessProvider:
    """
    Read-only Email IMAP SSL integration.
    """
    def check_inbox(self) -> Dict[str, Any]:
        if privacy_mode_manager.is_privacy_mode_active():
            status_registry.update_status("email", ProviderState.PAUSED, enabled=False)
            return {"status": "EMAIL_UNAVAILABLE", "unread_count": 0, "important_emails": []}

        if not permission_manager.is_granted("EMAIL_READ"):
            status_registry.update_status("email", ProviderState.DISABLED, enabled=False)
            return {"status": "EMAIL_UNAVAILABLE", "unread_count": 0, "important_emails": []}

        # 1. Try Chrome browser session reuse
        try:
            from actions.browser_automation import is_cdp_active, browser_automation_engine
            if is_cdp_active():
                res = browser_automation_engine.check_service_auth_sync("gmail")
                if res.get("status") == "LIVE_VERIFIED":
                    status_registry.update_status("email", ProviderState.LIVE_VERIFIED, authenticated=True, enabled=True)
                    return {
                        "status": "OK",
                        "unread_count": 0,
                        "important_emails": [],
                        "source": "chrome_session",
                        "verified": True
                    }
                elif res.get("status") == "AUTHENTICATION_REQUIRED":
                    status_registry.update_status("email", ProviderState.AUTHENTICATION_REQUIRED, enabled=True, error_msg="Gmail login required in Chrome")
                    return {
                        "status": "EMAIL_UNAVAILABLE",
                        "unread_count": 0,
                        "important_emails": [],
                        "message": "Gmail login required in Chrome session."
                    }
        except Exception:
            pass

        user = os.environ.get("EMAIL_USER", "")
        passw = os.environ.get("EMAIL_PASS", "")
        server = os.environ.get("IMAP_SERVER", "imap.gmail.com")

        if not user or not passw:
            status_registry.update_status("email", ProviderState.AUTHENTICATION_REQUIRED, enabled=True, error_msg="EMAIL_USER / EMAIL_PASS missing")
            return {
                "status": "EMAIL_UNAVAILABLE",
                "unread_count": 0,
                "important_emails": [],
                "message": "Email provider requires EMAIL_USER and EMAIL_PASS environment variables."
            }

        try:
            mail = imaplib.IMAP4_SSL(server)
            mail.login(user, passw)
            mail.select("inbox")
            status, data = mail.search(None, "UNSEEN")
            unread_ids = data[0].split() if data and data[0] else []
            unread_count = len(unread_ids)

            important_list: List[Dict[str, Any]] = []
            for num in unread_ids[:5]:
                _, msg_data = mail.fetch(num, "(RFC822.HEADER)")
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        subject, encoding = decode_header(msg.get("Subject", ""))[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding or "utf-8", errors="ignore")
                        from_sender = msg.get("From", "")
                        important_list.append({
                            "source": "email",
                            "sender": from_sender,
                            "subject": subject,
                            "unread": True
                        })

            mail.logout()
            status_registry.update_status("email", ProviderState.LIVE_VERIFIED, authenticated=True, enabled=True)
            return {
                "status": "OK",
                "unread_count": unread_count,
                "important_emails": important_list,
                "verified": True
            }
        except Exception as ex:
            status_registry.update_status("email", ProviderState.AUTHENTICATION_REQUIRED, error_msg=str(ex))
            return {
                "status": "EMAIL_UNAVAILABLE",
                "unread_count": 0,
                "important_emails": [],
                "error": str(ex)
            }


email_provider = EmailAwarenessProvider()
