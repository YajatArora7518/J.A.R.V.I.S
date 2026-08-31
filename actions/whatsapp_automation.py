# actions/whatsapp_automation.py
# Dedicated WhatsApp Web Automation Service for JARVIS (Chrome Profile "Yajat")

import os
import re
import json
import time
import asyncio
import logging
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

from actions.chrome_profile import open_url_in_yajat_chrome, resolve_chrome_profile
from actions.browser_automation import browser_automation_engine, is_cdp_active, ensure_cdp_chrome, check_cdp_health

logger = logging.getLogger("JARVIS.WhatsApp")

WHATSAPP_URL = "https://web.whatsapp.com/"

# ════════════════════════════════════════════
# WHATSAPP STATE MACHINE CONSTANTS
# ════════════════════════════════════════════
STATE_IDLE = "IDLE"
STATE_WHATSAPP_READY = "WHATSAPP_READY"
STATE_LOGIN_REQUIRED = "LOGIN_REQUIRED"
STATE_CDP_UNAVAILABLE = "CDP_UNAVAILABLE"
STATE_CONTACT_RESOLVING = "CONTACT_RESOLVING"
STATE_AMBIGUOUS_CONTACT = "AMBIGUOUS_CONTACT"
STATE_CONTACT_NOT_FOUND = "CONTACT_NOT_FOUND"
STATE_CHAT_OPENING = "CHAT_OPENING"
STATE_CHAT_OPENED = "CHAT_OPENED"
STATE_CALL_BUTTON_FOUND = "CALL_BUTTON_FOUND"
STATE_CALL_INITIATING = "CALL_INITIATING"
STATE_CALL_ACTIVE = "CALL_ACTIVE"
STATE_CALL_ENDED = "CALL_ENDED"
STATE_CALL_FAILED = "CALL_FAILED"
STATE_CALL_UNAVAILABLE = "CALL_UNAVAILABLE"
STATE_VIDEO_CALL_INITIATING = "VIDEO_CALL_INITIATING"
STATE_VIDEO_CALL_ACTIVE = "VIDEO_CALL_ACTIVE"
STATE_VIDEO_CALL_FAILED = "VIDEO_CALL_FAILED"
STATE_VIDEO_CALL_UNAVAILABLE = "VIDEO_CALL_UNAVAILABLE"
STATE_SENT_VERIFIED = "SENT_VERIFIED"
STATE_SENT_UNVERIFIED = "SENT_UNVERIFIED"

def _log_wa(msg: str):
    logger.info(f"[WHATSAPP] {msg}")

def _get_base_dir() -> Path:
    import sys
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = _get_base_dir()
CONFIG_DIR = BASE_DIR / "config"
AUTOREPLY_CONFIG_PATH = CONFIG_DIR / "whatsapp_autoreply.json"
AUTOREPLY_STATE_PATH = CONFIG_DIR / "whatsapp_autoreply_state.json"

# Standard contact database for resolution
KNOWN_CONTACTS = [
    {"name": "Rahul Sharma", "phone": "+919876543210"},
    {"name": "Rahul Mehta", "phone": "+919876543211"},
    {"name": "Rahul Kumar", "phone": "+919876543212"},
    {"name": "Priya Patel", "phone": "+919876543213"},
    {"name": "Krish", "phone": "+919876543214"},
    {"name": "Stark Industries", "phone": "+18005550199"},
]


# ════════════════════════════════════════════
# AUTO-REPLY PERSISTENT CONFIG & STATE
# ════════════════════════════════════════════
def load_autoreply_config() -> Dict[str, Any]:
    if AUTOREPLY_CONFIG_PATH.exists():
        try:
            return json.loads(AUTOREPLY_CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "enabled": False,
        "allowed_contacts": [],
        "template": "Hello! I am currently away. JARVIS received your message and will notify my owner.",
        "rate_limit_minutes": 5
    }

def save_autoreply_config(config: Dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    AUTOREPLY_CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")

def load_autoreply_state() -> Dict[str, Any]:
    if AUTOREPLY_STATE_PATH.exists():
        try:
            return json.loads(AUTOREPLY_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "processed_ids": [],
        "last_replied": {}
    }

def save_autoreply_state(state: Dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # Limit stored processed IDs to 200 items to prevent unbounded growth
    if len(state.get("processed_ids", [])) > 200:
        state["processed_ids"] = state["processed_ids"][-200:]
    AUTOREPLY_STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ════════════════════════════════════════════
# NATURAL LANGUAGE COMMAND PARSER (ENGLISH & HINGLISH)
# ════════════════════════════════════════════
def parse_whatsapp_command(text: str) -> Dict[str, str]:
    """
    Parses natural language WhatsApp message & call instructions in English & Hinglish.
    Examples:
    - "Send Rahul a WhatsApp message saying I'll be late" -> contact="Rahul", message="I'll be late"
    - "WhatsApp Rahul and tell him I'm coming" -> contact="Rahul", message="I'm coming"
    - "Message Mom on WhatsApp" -> contact="Mom", message=""
    - "Rahul ko WhatsApp pe message karo ki main 10 minute late hoon" -> contact="Rahul", message="main 10 minute late hoon"
    - "Call Rahul on WhatsApp" -> contact="Rahul", message=""
    - "WhatsApp pe mummy ko call karo" -> contact="mummy", message=""
    """
    if not text:
        return {"contact": "", "message": ""}

    t = text.strip()

    # 1. English patterns
    m = re.search(r"send\s+([a-zA-Z0-9_\s]+?)\s+a\s+whatsapp\s+message\s+(?:saying|that)\s+(.+)", t, re.IGNORECASE)
    if m:
        return {"contact": m.group(1).strip(), "message": m.group(2).strip()}

    m = re.search(r"whatsapp\s+([a-zA-Z0-9_\s]+?)\s+and\s+tell\s+(?:him|her|them)\s+(.+)", t, re.IGNORECASE)
    if m:
        return {"contact": m.group(1).strip(), "message": m.group(2).strip()}

    m = re.search(r"message\s+([a-zA-Z0-9_\s]+?)\s+on\s+whatsapp\s+(?:saying|that|telling)?\s*(.*)", t, re.IGNORECASE)
    if m:
        return {"contact": m.group(1).strip(), "message": m.group(2).strip()}

    m = re.search(r"whatsapp\s+([a-zA-Z0-9_\s]+?)\s+(?:saying|that|telling)\s+(.+)", t, re.IGNORECASE)
    if m:
        return {"contact": m.group(1).strip(), "message": m.group(2).strip()}

    # 2. Hinglish patterns
    m = re.search(r"([a-zA-Z0-9_\s]+?)\s+ko\s+whatsapp\s+(?:pe|par)\s+message\s+(?:karo|bhejo|kar do)\s+(?:ki\s+)?(.+)", t, re.IGNORECASE)
    if m:
        return {"contact": m.group(1).strip(), "message": m.group(2).strip()}

    m = re.search(r"([a-zA-Z0-9_\s]+?)\s+ko\s+(?:message|msg)\s+(?:karo|bhej|bhejo)\s*[:\s]*\s*(.+)", t, re.IGNORECASE)
    if m:
        return {"contact": m.group(1).strip(), "message": m.group(2).strip()}

    m = re.search(r"([a-zA-Z0-9_\s]+?)\s+ko\s+whatsapp\s+(?:kar do|karo)", t, re.IGNORECASE)
    if m:
        return {"contact": m.group(1).strip(), "message": ""}

    # 3. Call patterns
    m = re.search(r"whatsapp\s+(?:pe|par)\s+([a-zA-Z0-9_\s]+?)\s+ko\s+call\b", t, re.IGNORECASE)
    if m:
        return {"contact": m.group(1).strip(), "message": ""}

    m = re.search(r"([a-zA-Z0-9_\s]+?)\s+ko\s+whatsapp\s+call\b", t, re.IGNORECASE)
    if m:
        return {"contact": m.group(1).strip(), "message": ""}

    m = re.search(r"(?:call|start a whatsapp call with)\s+([a-zA-Z0-9_\s]+?)(?:\s+on\s+whatsapp|\s+call|$)", t, re.IGNORECASE)
    if m:
        return {"contact": m.group(1).strip(), "message": ""}

    return {"contact": "", "message": ""}


# ════════════════════════════════════════════
# CONTACT RESOLUTION
# ════════════════════════════════════════════
def resolve_contact(query: str) -> Dict[str, Any]:
    """
    Resolves contact query safely.
    If 1 exact match exists -> exact.
    If multiple matches exist -> ambiguous (asks user to clarify).
    """
    if not query or not query.strip():
        return {"success": False, "status": "CONTACT_NOT_FOUND", "message": "No contact query specified.", "verified": False}

    q_lower = query.strip().lower()
    matches = [c for c in KNOWN_CONTACTS if q_lower in c["name"].lower()]

    if len(matches) == 1:
        return {"success": True, "status": "exact", "contact": matches[0]}
    elif len(matches) > 1:
        names = [c["name"] for c in matches]
        return {
            "success": False,
            "status": "AMBIGUOUS_CONTACT",
            "matches": names,
            "message": f"I found multiple '{query}' contacts: {', '.join(names)}. Which one would you like to choose?",
            "requires_clarification": True,
            "verified": False
        }

    return {"success": True, "status": "exact", "contact": {"name": query.strip(), "phone": ""}}



def whatsapp_open() -> Dict[str, Any]:
    """Opens or brings WhatsApp Web to front in Yajat Chrome profile."""
    return open_url_in_yajat_chrome(WHATSAPP_URL)


# ════════════════════════════════════════════
# COMPONENT 1: SEND MESSAGE & DOM VERIFICATION
# ════════════════════════════════════════════
async def _async_whatsapp_send(recipient: str, message: str, force_send: bool = False) -> Dict[str, Any]:
    """Async CDP-based WhatsApp message send with strict DOM delivery verification."""
    resolution = resolve_contact(recipient)
    if resolution.get("status") in ["ambiguous", "AMBIGUOUS_CONTACT"] or resolution.get("requires_clarification"):
        return {
            "success": False,
            "action": "whatsapp_send",
            "platform": "whatsapp",
            "status": "AMBIGUOUS_CONTACT",
            "message": resolution["message"],
            "requires_clarification": True,
            "matches": resolution.get("matches", []),
            "verified": False
        }

    if not resolution.get("success") and resolution.get("status") == "CONTACT_NOT_FOUND":
        return {
            "success": False,
            "action": "whatsapp_send",
            "platform": "whatsapp",
            "status": "CONTACT_NOT_FOUND",
            "message": resolution["message"],
            "verified": False
        }

    target_contact = resolution["contact"]["name"]
    _log_wa("Session detected")
    _log_wa(f"Contact resolved: {target_contact}")

    if not force_send:
        return {
            "success": False,
            "action": "whatsapp_send",
            "platform": "whatsapp",
            "status": "CONFIRMATION_REQUIRED",
            "contact": target_contact,
            "message_text": message,
            "message": f"WhatsApp message ready for {target_contact}: '{message}'. Should I send it?",
            "requires_confirmation": True,
            "verified": False
        }

    try:
        page = await browser_automation_engine.get_or_open_page("web.whatsapp.com", WHATSAPP_URL)
        await asyncio.sleep(1.5)

        # Check for QR Code / Login Required State
        login_qr = await page.query_selector('canvas[aria-label*="Scan"], div[data-ref], div._ak96, div[data-testid="qrcode"]')
        if login_qr:
            _log_wa("LOGIN_REQUIRED — QR screen detected")
            return {
                "success": False,
                "action": "whatsapp_send",
                "platform": "whatsapp",
                "state": STATE_LOGIN_REQUIRED,
                "status": STATE_LOGIN_REQUIRED,
                "contact": target_contact,
                "message": "Boss, WhatsApp Web is not logged in. Please scan the QR code in Chrome first.",
                "verified": False,
                "error": "Login required"
            }

        # 1. Search contact in WhatsApp Web UI
        search_selectors = [
            '#side div[contenteditable="true"]',
            'div[contenteditable="true"][data-tab="3"]',
            'div[contenteditable="true"][aria-label*="Search"]',
            'div[title*="Search"]',
            'div._ai4g',
            'p.selectable-text'
        ]

        found_search = False
        for sel in search_selectors:
            try:
                el = await page.wait_for_selector(sel, timeout=3000, state="visible")
                if el:
                    await el.click()
                    await page.fill(sel, "")
                    await page.type(sel, target_contact, delay=30)
                    await asyncio.sleep(1.0)
                    found_search = True
                    break
            except Exception:
                continue

        if not found_search:
            _log_wa("Search input not found in DOM")
            return {
                "success": False,
                "action": "whatsapp_send",
                "platform": "whatsapp",
                "state": STATE_CONTACT_NOT_FOUND,
                "status": "SEARCH_INPUT_NOT_FOUND",
                "contact": target_contact,
                "message": f"Could not find search box on WhatsApp Web to locate '{target_contact}'.",
                "verified": False,
                "error": "WhatsApp search input not found in DOM"
            }

        # Select matching contact item from list or press Enter
        contact_clicked = False
        try:
            items = await page.query_selector_all('#side div[role="listitem"], #side div[role="row"]')
            for item in items[:8]:
                txt = await item.inner_text()
                if target_contact.lower() in txt.lower():
                    await item.click()
                    contact_clicked = True
                    await asyncio.sleep(1.0)
                    break
        except Exception:
            pass

        if not contact_clicked:
            await page.keyboard.press("Enter")
            await asyncio.sleep(1.0)

        # Confirm active chat panel (#main) loaded
        main_chat = await page.query_selector('#main')
        if not main_chat:
            _log_wa(f"Could not open conversation with {target_contact}")
            return {
                "success": False,
                "action": "whatsapp_send",
                "platform": "whatsapp",
                "state": STATE_CONTACT_NOT_FOUND,
                "status": "CONTACT_NOT_FOUND",
                "contact": target_contact,
                "message": f"Boss, I couldn't open conversation with '{target_contact}' on WhatsApp Web.",
                "verified": False,
                "error": "Contact chat not opened"
            }

        _log_wa("Chat opened")

        # 2. Locate message input box & compose message (Unicode, Emojis, Multiline support)
        input_selectors = [
            '#main footer div[contenteditable="true"]',
            'div[contenteditable="true"][data-tab="10"]',
            'footer div[contenteditable="true"]',
            'div[contenteditable="true"][aria-label*="Type a message"]',
            'p.selectable-text.copyable-text'
        ]

        sent_attempted = False
        for sel in input_selectors:
            try:
                el = await page.wait_for_selector(sel, timeout=3000, state="visible")
                if el:
                    _log_wa("Message composer located")
                    await el.click()
                    # Insert text via Playwright keyboard insert_text to preserve exact formatting & emojis
                    await page.keyboard.insert_text(message)
                    await asyncio.sleep(0.3)
                    await page.keyboard.press("Enter")
                    sent_attempted = True
                    _log_wa("Message sent")
                    await asyncio.sleep(1.2)
                    break
            except Exception:
                continue

        if not sent_attempted:
            # Fallback: click send icon button
            try:
                send_btn = await page.query_selector('#main footer span[data-icon="send"], #main footer button[aria-label*="Send"]')
                if send_btn:
                    await send_btn.click()
                    sent_attempted = True
                    _log_wa("Message sent")
                    await asyncio.sleep(1.2)
            except Exception:
                pass

        if not sent_attempted:
            _log_wa("Message input not found in DOM")
            return {
                "success": False,
                "action": "whatsapp_send",
                "platform": "whatsapp",
                "state": STATE_CHAT_OPENED,
                "status": "INPUT_NOT_FOUND",
                "contact": target_contact,
                "message": f"Could not locate message input box in WhatsApp Web for '{target_contact}'.",
                "verified": False,
                "error": "Message input not found"
            }

        # 3. Strict DOM Delivery Verification: Inspect #main for sent bubble containing message
        try:
            sent_bubbles = await page.query_selector_all('#main div.message-out, #main div._akbu, #main span.selectable-text, #main div.copyable-text')
            verified_in_dom = False
            for bubble in sent_bubbles[-6:]:
                b_text = await bubble.inner_text()
                if message in b_text or (len(message) > 4 and message[:8] in b_text):
                    verified_in_dom = True
                    break

            if verified_in_dom:
                _log_wa("Message delivery verified")
                return {
                    "success": True,
                    "action": "whatsapp_send",
                    "platform": "whatsapp",
                    "state": STATE_SENT_VERIFIED,
                    "status": "SENT_VERIFIED",
                    "contact": target_contact,
                    "message_text": message,
                    "message": f"Done, Boss. I sent the message to {target_contact}.",
                    "verified": True
                }
            else:
                return {
                    "success": False,
                    "action": "whatsapp_send",
                    "platform": "whatsapp",
                    "status": "SENT_UNVERIFIED",
                    "contact": target_contact,
                    "message_text": message,
                    "message": f"Boss, I attempted to send the message to {target_contact}, but I couldn't verify that WhatsApp delivered it.",
                    "verified": False,
                    "error": "DOM send verification unconfirmed"
                }
        except Exception:
            return {
                "success": False,
                "action": "whatsapp_send",
                "platform": "whatsapp",
                "status": "SENT_UNVERIFIED",
                "contact": target_contact,
                "message_text": message,
                "message": f"Boss, I attempted to send the message to {target_contact}, but I couldn't verify that WhatsApp delivered it.",
                "verified": False,
                "error": "Verification query exception"
            }

    except Exception as e:
        logger.error(f"CDP WhatsApp send failed: {e}")
        return {
            "success": False,
            "action": "whatsapp_send",
            "platform": "whatsapp",
            "status": "AUTOMATION_ERROR",
            "contact": target_contact,
            "message": f"WhatsApp send failed due to browser automation error: {e}",
            "verified": False,
            "error": str(e)
        }


def whatsapp_send_message(recipient: str, message: str, force_send: bool = False) -> Dict[str, Any]:
    """Public wrapper for WhatsApp message sending."""
    resolution = resolve_contact(recipient)
    if resolution.get("status") in ["ambiguous", "AMBIGUOUS_CONTACT"] or resolution.get("requires_clarification"):
        return {
            "success": False,
            "action": "whatsapp_send",
            "platform": "whatsapp",
            "status": "AMBIGUOUS_CONTACT",
            "message": resolution["message"],
            "requires_clarification": True,
            "matches": resolution.get("matches", []),
            "verified": False
        }

    contact_name = resolution["contact"]["name"]

    if not force_send:
        return {
            "success": False,
            "action": "whatsapp_send",
            "platform": "whatsapp",
            "status": "CONFIRMATION_REQUIRED",
            "contact": contact_name,
            "message_text": message,
            "message": f"WhatsApp message ready for {contact_name}: '{message}'. Should I send it?",
            "requires_confirmation": True,
            "verified": False
        }

    from actions.windows_whatsapp_desktop_executor import send_windows_whatsapp_desktop_message
    res = send_windows_whatsapp_desktop_message(recipient=contact_name, message=message)
    assert res.get("execution_target") == "WINDOWS_INSTALLED_WHATSAPP_DESKTOP", "CRITICAL: WhatsApp message execution target must be WINDOWS_INSTALLED_WHATSAPP_DESKTOP!"
    return res


# ════════════════════════════════════════════
# COMPONENT 2 & 3: RECEIVE, UNREAD & READ ALOUD
# ════════════════════════════════════════════
async def _async_whatsapp_read(recipient: Optional[str] = None, limit: int = 5, unread_only: bool = False) -> Dict[str, Any]:
    """CDP-based WhatsApp message reading from DOM with outgoing message filtering."""
    try:
        page = await browser_automation_engine.get_or_open_page("web.whatsapp.com", WHATSAPP_URL)
        await asyncio.sleep(1.5)

        # 1. If recipient is specified, navigate/open that chat
        if recipient:
            resolution = resolve_contact(recipient)
            target_contact = resolution["contact"]["name"] if resolution.get("contact") else recipient

            search_selectors = [
                '#side div[contenteditable="true"]',
                'div[contenteditable="true"][data-tab="3"]',
                'div[contenteditable="true"][aria-label*="Search"]',
                'div[title*="Search"]',
                'p.selectable-text'
            ]
            for sel in search_selectors:
                try:
                    el = await page.wait_for_selector(sel, timeout=2000, state="visible")
                    if el:
                        await el.click()
                        await page.fill(sel, "")
                        await page.type(sel, target_contact, delay=20)
                        await asyncio.sleep(1.0)
                        await page.keyboard.press("Enter")
                        await asyncio.sleep(1.2)
                        break
                except Exception:
                    continue

            # Read messages in current #main chat pane
            msg_elements = await page.query_selector_all('#main div.message-in, #main div.message-out, #main div._akbu')
            extracted_messages = []

            for el in msg_elements[-limit:]:
                try:
                    cls_name = await el.get_attribute("class") or ""
                    # Filter direction: message-out vs message-in
                    direction = "outgoing" if "message-out" in cls_name else "incoming"

                    t_el = await el.query_selector("span.selectable-text, div.copyable-text, span._ao3e")
                    text = (await t_el.inner_text()).strip() if t_el else (await el.inner_text()).strip()

                    tm_el = await el.query_selector('div[data-pre-plain-text], span[dir="auto"], span.x1rg5ohf')
                    timestamp = "Recent"

                    if text:
                        extracted_messages.append({
                            "sender": target_contact if direction == "incoming" else "JARVIS",
                            "text": text[:300],
                            "timestamp": timestamp,
                            "direction": direction,
                            "unread": False
                        })
                except Exception:
                    continue

            # Filter outgoing messages when user asks for incoming messages
            incoming_only = [m for m in extracted_messages if m["direction"] == "incoming"]
            active_msgs = incoming_only if incoming_only else extracted_messages

            if active_msgs:
                last_m = active_msgs[-1]
                return {
                    "success": True,
                    "action": "whatsapp_read",
                    "platform": "whatsapp",
                    "status": "MESSAGES_READ",
                    "contact": target_contact,
                    "messages": active_msgs,
                    "last_message": last_m["text"],
                    "message": f"Latest message from {target_contact}: '{last_m['text']}'.",
                    "verified": True
                }
            else:
                return {
                    "success": True,
                    "action": "whatsapp_read",
                    "platform": "whatsapp",
                    "status": "NO_MESSAGES",
                    "contact": target_contact,
                    "messages": [],
                    "message": f"No messages found for {target_contact}.",
                    "verified": True
                }

        # 2. Extract recent chats from chat list
        chats: List[Dict[str, Any]] = []
        elements = await page.query_selector_all('#side div[role="listitem"]')
        unread_detectable = False
        for el in elements[:limit]:
            try:
                text = await el.inner_text()
                lines = [line.strip() for line in text.split("\n") if line.strip()]
                if lines:
                    name = lines[0]
                    msg_preview = lines[1] if len(lines) > 1 else ""
                    time_str = lines[2] if len(lines) > 2 else ""

                    unread_badge = await el.query_selector('span[aria-label*="unread"], span._ao3e, span[data-icon="unread-count"]')
                    has_unread = unread_badge is not None
                    if unread_badge:
                        unread_detectable = True

                    chats.append({
                        "contact": name,
                        "last_message": msg_preview,
                        "time": time_str,
                        "direction": "incoming",
                        "unread": has_unread
                    })
            except Exception:
                continue

        if unread_only:
            chats = [c for c in chats if c.get("unread")]

        summary_items = [f"• {c['contact']}: '{c['last_message']}'" for c in chats[:4]]
        summary_str = "\n".join(summary_items) if summary_items else "No unread messages."
        msg = f"Recent WhatsApp chats:\n{summary_str}"

        return {
            "success": True,
            "action": "whatsapp_read",
            "platform": "whatsapp",
            "status": "SUCCESS" if unread_detectable else "UNREAD_STATUS_UNAVAILABLE",
            "unread_count": len([c for c in chats if c.get("unread")]),
            "chats": chats,
            "message": msg,
            "verified": True
        }

    except Exception as e:
        logger.error(f"CDP WhatsApp read failed: {e}")
        return {
            "success": False,
            "action": "whatsapp_read",
            "platform": "whatsapp",
            "status": "AUTOMATION_ERROR",
            "message": f"WhatsApp read failed: {e}",
            "verified": False,
            "error": str(e)
        }


def whatsapp_read_messages(recipient: Optional[str] = None, limit: int = 5, unread_only: bool = False) -> Dict[str, Any]:
    """Public wrapper for WhatsApp message reading."""
    try:
        if is_cdp_active():
            return browser_automation_engine.run(_async_whatsapp_read(recipient, limit, unread_only))
    except Exception as e:
        logger.warning(f"CDP WhatsApp read failed: {e}")

    open_url_in_yajat_chrome(WHATSAPP_URL)
    return {
        "success": False,
        "action": "whatsapp_read",
        "platform": "whatsapp",
        "status": "CDP_UNAVAILABLE",
        "message": "WhatsApp Web opened in Yajat Chrome. Message reading requires active CDP session.",
        "verified": False,
        "error": "CDP unavailable — cannot read DOM"
    }


# ════════════════════════════════════════════
# COMPONENT 4: REPLY
# ════════════════════════════════════════════
def whatsapp_reply(recipient: str, message: str) -> Dict[str, Any]:
    """Replies to recipient's latest message with delivery verification."""
    res = whatsapp_send_message(recipient=recipient, message=message, force_send=True)
    res["action"] = "whatsapp_reply"
    return res


# ════════════════════════════════════════════
# COMPONENT 5: SAFE PERSISTENT AUTO-REPLY
# ════════════════════════════════════════════
def whatsapp_set_auto_reply(enabled: bool = True, contact: Optional[str] = None, template: Optional[str] = None) -> Dict[str, Any]:
    """Configures persistent auto-reply settings with contact opt-in safety."""
    cfg = load_autoreply_config()
    cfg["enabled"] = bool(enabled)

    if contact:
        res = resolve_contact(contact)
        c_name = res["contact"]["name"] if res.get("contact") else contact
        if c_name not in cfg["allowed_contacts"]:
            cfg["allowed_contacts"].append(c_name)

    if template:
        cfg["template"] = template.strip()

    save_autoreply_config(cfg)
    status_str = "ENABLED" if cfg["enabled"] else "DISABLED"
    contacts_str = ", ".join(cfg["allowed_contacts"]) if cfg["allowed_contacts"] else "All allowed"

    return {
        "success": True,
        "action": "whatsapp_auto_reply",
        "status": "CONFIGURED",
        "enabled": cfg["enabled"],
        "allowed_contacts": cfg["allowed_contacts"],
        "message": f"WhatsApp Auto-Reply set to {status_str} for: [{contacts_str}].",
        "verified": True
    }


def whatsapp_check_auto_reply() -> Dict[str, Any]:
    """
    Checks incoming WhatsApp messages and applies strict Loop-Protected Auto-Reply:
    1. Must be explicitly enabled (defaults to DISABLED).
    2. Only for allowed contacts.
    3. Ignores outgoing messages & JARVIS's own auto-replies.
    4. Enforces 5-minute per-contact rate limit.
    5. Deduplicates message IDs/fingerprints.
    6. Fails closed if sender/direction is uncertain.
    """
    cfg = load_autoreply_config()
    if not cfg.get("enabled"):
        return {"success": True, "status": "DISABLED", "replied": False, "reason": "Auto-reply is disabled."}

    allowed = cfg.get("allowed_contacts", [])
    if not allowed:
        return {"success": True, "status": "NO_ALLOWED_CONTACTS", "replied": False, "reason": "No contacts configured for auto-reply."}

    read_res = whatsapp_read_messages(limit=5, unread_only=True)
    if not read_res.get("success") or not read_res.get("chats"):
        return {"success": True, "status": "NO_UNREAD", "replied": False, "reason": "No unread messages found."}

    state = load_autoreply_state()
    processed = set(state.get("processed_ids", []))
    last_replied = state.get("last_replied", {})
    now = time.time()
    rate_limit_sec = float(cfg.get("rate_limit_minutes", 5)) * 60.0

    replied_list = []

    for chat in read_res.get("chats", []):
        contact_name = chat.get("contact", "")
        last_msg = chat.get("last_message", "")

        # Fail closed: uncertain identity
        if not contact_name:
            continue

        # Protection 1: Allowed contacts check
        if not any(a.lower() in contact_name.lower() for a in allowed):
            continue

        # Protection 2: Direction check (ignore outgoing & JARVIS's own messages)
        if chat.get("direction") == "outgoing" or "[Auto-Reply]" in last_msg or "JARVIS" in contact_name:
            continue

        # Protection 3: Fingerprint deduplication
        msg_id = f"{contact_name}_{last_msg}_{chat.get('time', '')}"
        if msg_id in processed:
            continue

        # Protection 4: 5-minute rate limit check
        last_t = float(last_replied.get(contact_name, 0.0))
        if now - last_t < rate_limit_sec:
            continue

        # Generate & Send Auto-Reply
        reply_text = f"[Auto-Reply] {cfg.get('template')}"
        send_res = whatsapp_reply(recipient=contact_name, message=reply_text)

        if send_res.get("success"):
            processed.add(msg_id)
            last_replied[contact_name] = now
            replied_list.append(contact_name)

    state["processed_ids"] = list(processed)
    state["last_replied"] = last_replied
    save_autoreply_state(state)

    if replied_list:
        return {
            "success": True,
            "status": "REPLIED",
            "replied": True,
            "contacts": replied_list,
            "message": f"Auto-replied to: {', '.join(replied_list)}.",
            "verified": True
        }

    return {"success": True, "status": "NO_ELIGIBLE_MESSAGES", "replied": False, "reason": "No eligible messages for auto-reply."}


# ════════════════════════════════════════════
# OPEN CHAT & SEARCH CONTACT ACTIONS
# ════════════════════════════════════════════
async def _async_whatsapp_open_chat_cdp(recipient: str) -> Dict[str, Any]:
    """CDP-based opening of a specific WhatsApp Web contact chat."""
    resolution = resolve_contact(recipient)
    if resolution.get("status") in ["ambiguous", "AMBIGUOUS_CONTACT"] or resolution.get("requires_clarification"):
        return {
            "success": False,
            "action": "whatsapp_open_chat",
            "platform": "whatsapp",
            "status": "AMBIGUOUS_CONTACT",
            "message": resolution["message"],
            "requires_clarification": True,
            "matches": resolution.get("matches", []),
            "verified": False
        }

    if not resolution.get("success") and resolution.get("status") == "CONTACT_NOT_FOUND":
        return {
            "success": False,
            "action": "whatsapp_open_chat",
            "platform": "whatsapp",
            "status": "CONTACT_NOT_FOUND",
            "message": resolution["message"],
            "verified": False
        }

    target_contact = resolution["contact"]["name"]

    try:
        page = await browser_automation_engine.get_or_open_page("web.whatsapp.com", WHATSAPP_URL)
        await asyncio.sleep(1.5)

        # Search & open chat in side panel
        search_selectors = [
            '#side div[contenteditable="true"]',
            'div[contenteditable="true"][data-tab="3"]',
            'div[contenteditable="true"][aria-label*="Search"]',
            'p.selectable-text'
        ]
        opened = False
        for sel in search_selectors:
            try:
                el = await page.wait_for_selector(sel, timeout=2000, state="visible")
                if el:
                    await el.click()
                    await page.fill(sel, "")
                    await page.type(sel, target_contact, delay=20)
                    await asyncio.sleep(1.0)
                    await page.keyboard.press("Enter")
                    await asyncio.sleep(1.2)
                    opened = True
                    break
            except Exception:
                continue

        # Verify #main header text contains target contact name
        header_el = await page.query_selector('#main header')
        if header_el:
            header_text = (await header_el.inner_text()) or ""
            if target_contact.lower() in header_text.lower() or (len(target_contact) > 3 and target_contact.split()[0].lower() in header_text.lower()):
                return {
                    "success": True,
                    "action": "whatsapp_open_chat",
                    "platform": "whatsapp",
                    "status": "CHAT_OPENED",
                    "contact": target_contact,
                    "message": f"Opened WhatsApp chat with '{target_contact}'.",
                    "verified": True
                }

        if opened:
            return {
                "success": True,
                "action": "whatsapp_open_chat",
                "platform": "whatsapp",
                "status": "CHAT_OPENED",
                "contact": target_contact,
                "message": f"Opened WhatsApp chat with '{target_contact}'.",
                "verified": True
            }

        return {
            "success": False,
            "action": "whatsapp_open_chat",
            "platform": "whatsapp",
            "status": "CONTACT_NOT_FOUND",
            "contact": target_contact,
            "message": f"Could not find or open chat with '{target_contact}' on WhatsApp Web.",
            "verified": False
        }
    except Exception as e:
        logger.error(f"CDP WhatsApp open chat failed: {e}")
        return {
            "success": False,
            "action": "whatsapp_open_chat",
            "platform": "whatsapp",
            "status": "AUTOMATION_ERROR",
            "contact": target_contact,
            "message": f"Failed to open chat with '{target_contact}': {e}",
            "verified": False,
            "error": str(e)
        }


def whatsapp_open_chat(recipient: str) -> Dict[str, Any]:
    """Public wrapper for WhatsApp open chat action."""
    resolution = resolve_contact(recipient)
    if resolution.get("status") in ["ambiguous", "AMBIGUOUS_CONTACT"] or resolution.get("requires_clarification"):
        return {
            "success": False,
            "action": "whatsapp_open_chat",
            "platform": "whatsapp",
            "state": STATE_AMBIGUOUS_CONTACT,
            "status": "AMBIGUOUS_CONTACT",
            "message": resolution["message"],
            "requires_clarification": True,
            "matches": resolution.get("matches", []),
            "verified": False
        }

    target_contact = resolution["contact"]["name"]

    health = check_cdp_health()
    if not health.get("ready"):
        return {
            "success": False,
            "action": "whatsapp_open_chat",
            "platform": "whatsapp",
            "state": STATE_CDP_UNAVAILABLE,
            "status": health.get("status", "CDP_UNAVAILABLE"),
            "contact": target_contact,
            "message": f"Cannot open WhatsApp chat automatically: {health.get('message')}",
            "verified": False,
            "error": health.get("message")
        }

    try:
        return browser_automation_engine.run(_async_whatsapp_open_chat_cdp(recipient))
    except Exception as e:
        logger.warning(f"CDP WhatsApp open chat failed: {e}")
        return {
            "success": False,
            "action": "whatsapp_open_chat",
            "platform": "whatsapp",
            "state": STATE_CDP_UNAVAILABLE,
            "status": "CDP_UNAVAILABLE",
            "contact": target_contact,
            "message": f"Could not open WhatsApp chat with '{target_contact}': {e}",
            "verified": False,
            "error": str(e)
        }


def whatsapp_search_contact(query: str) -> Dict[str, Any]:
    """Public contact search tool for WhatsApp."""
    return resolve_contact(query)


# ════════════════════════════════════════════
# CALL, VIDEO CALL & END CALL
# ════════════════════════════════════════════
async def _async_whatsapp_call_cdp(recipient: str, call_type: str = "voice") -> Dict[str, Any]:
    """Async CDP-based WhatsApp Web call controller with state machine & DOM call verification."""
    _log_wa("Session detected")
    _log_wa(f"Contact resolving: {recipient}")
    resolution = resolve_contact(recipient)
    if resolution.get("status") in ["ambiguous", "AMBIGUOUS_CONTACT"] or resolution.get("requires_clarification"):
        _log_wa(f"AMBIGUOUS_CONTACT: {recipient}")
        return {
            "success": False,
            "action": "whatsapp_call",
            "platform": "whatsapp",
            "state": STATE_AMBIGUOUS_CONTACT,
            "status": STATE_AMBIGUOUS_CONTACT,
            "message": resolution["message"],
            "requires_clarification": True,
            "matches": resolution.get("matches", []),
            "verified": False
        }

    target_contact = resolution["contact"]["name"] if resolution.get("contact") else recipient
    _log_wa(f"Contact resolved: {target_contact}")

    page = await browser_automation_engine.get_or_open_page("web.whatsapp.com", WHATSAPP_URL)
    await asyncio.sleep(1.5)

    login_qr = await page.query_selector('canvas[aria-label*="Scan"], div[data-ref], div._ak96, div[data-testid="qrcode"]')
    if login_qr:
        _log_wa("LOGIN_REQUIRED — QR screen detected")
        return {
            "success": False,
            "action": "whatsapp_call",
            "platform": "whatsapp",
            "state": STATE_LOGIN_REQUIRED,
            "status": STATE_LOGIN_REQUIRED,
            "contact": target_contact,
            "message": "Boss, WhatsApp Web is not logged in. Please scan the QR code in Chrome first.",
            "verified": False,
            "error": "Login required"
        }

    # 1. Open chat pane for recipient
    _log_wa(f"Chat opening for {target_contact}")
    search_selectors = [
        '#side div[contenteditable="true"]',
        'div[contenteditable="true"][aria-label*="Search"]',
        'p.selectable-text'
    ]
    chat_opened = False
    for sel in search_selectors:
        try:
            el = await page.wait_for_selector(sel, timeout=2000, state="visible")
            if el:
                await el.click()
                await page.fill(sel, "")
                await page.type(sel, target_contact, delay=20)
                await asyncio.sleep(1.0)
                await page.keyboard.press("Enter")
                await asyncio.sleep(1.2)
                chat_opened = True
                break
        except Exception:
            continue

    if chat_opened:
        _log_wa("Chat opened")

    # 2. Inspect #main header for call buttons
    header_selectors = [
        '#main header button[aria-label*="Voice call"]',
        '#main header button[aria-label*="Start voice call"]',
        '#main header button[title*="Voice call"]',
        '#main header button[aria-label*="Video call"]',
        '#main header button[aria-label*="Start video call"]',
        '#main header button[title*="Video call"]',
        '#main header span[data-icon="phone"]',
        '#main header span[data-icon="call"]',
        '#main header span[data-icon="video-call"]',
        '#main header span[data-icon="video"]'
    ]

    call_btn = None
    target_pattern = "video" if call_type == "video" else "voice"
    for sel in header_selectors:
        try:
            if target_pattern in sel.lower() or ("phone" in sel and call_type != "video") or ("video" in sel and call_type == "video"):
                btn = await page.query_selector(sel)
                if btn:
                    call_btn = btn
                    break
        except Exception:
            continue

    if call_btn:
        _log_wa(f"{call_type.capitalize()} call button located")
        _log_wa(f"{call_type.capitalize()} call initiating")
        await call_btn.click()
        await asyncio.sleep(1.5)

        # 3. Call State Verification: Inspect DOM for active call interface
        call_verified = False
        call_ui_selectors = [
            'div[aria-label*="Call"]',
            'button[aria-label*="End call"]',
            'span[data-icon="call-end"]',
            'span[data-icon="phone-down"]',
            'div[data-testid="call-container"]',
            'div._aizc',
            'div._aizh'
        ]
        for sel in call_ui_selectors:
            try:
                c_el = await page.query_selector(sel)
                if c_el:
                    call_verified = True
                    break
            except Exception:
                continue

        if not call_verified:
            try:
                body_text = await page.inner_text("body")
                if any(w in body_text.lower() for w in ["calling...", "ringing...", "calling", "00:0", "end call"]):
                    call_verified = True
            except Exception:
                pass

        if call_verified:
            _log_wa(f"{call_type.capitalize()} call ACTIVE")
            active_state = STATE_VIDEO_CALL_ACTIVE if call_type == "video" else STATE_CALL_ACTIVE
            return {
                "success": True,
                "action": "whatsapp_call",
                "platform": "whatsapp",
                "contact": target_contact,
                "call_type": call_type,
                "state": active_state,
                "status": "CALL_INITIATED",
                "message": f"WhatsApp {call_type} call initiated to {target_contact}.",
                "verified": True
            }
        else:
            fail_state = STATE_VIDEO_CALL_FAILED if call_type == "video" else STATE_CALL_FAILED
            _log_wa(f"{call_type.capitalize()} call FAILED (DOM unconfirmed)")
            return {
                "success": False,
                "action": "whatsapp_call",
                "platform": "whatsapp",
                "contact": target_contact,
                "call_type": call_type,
                "state": fail_state,
                "status": "CALL_UNVERIFIED",
                "message": f"Call button clicked for {target_contact}, but WhatsApp Web call interface could not be confirmed in the DOM.",
                "verified": False,
                "error": "Call interface unconfirmed in DOM"
            }

    unavail_state = STATE_VIDEO_CALL_UNAVAILABLE if call_type == "video" else STATE_CALL_UNAVAILABLE
    _log_wa(f"{unavail_state}")
    _log_wa(f"Reason: {call_type.capitalize()} call controls unexposed in WhatsApp Web browser tab")
    return {
        "success": False,
        "action": "whatsapp_call",
        "platform": "whatsapp",
        "contact": target_contact,
        "call_type": call_type,
        "state": unavail_state,
        "status": unavail_state,
        "message": f"WhatsApp Web opened for {target_contact}, but {call_type} call controls are unexposed in this browser tab. Download WhatsApp Desktop for native calling.",
        "verified": False,
        "error": f"{call_type.capitalize()} call DOM button unavailable in browser tab"
    }


def whatsapp_make_call(recipient: str, call_type: str = "voice", confirm_call: bool = False) -> Dict[str, Any]:
    """Initiates WhatsApp voice or video call with confirmation safety."""
    resolution = resolve_contact(recipient)
    if resolution.get("status") in ["ambiguous", "AMBIGUOUS_CONTACT"] or resolution.get("requires_clarification"):
        return {
            "success": False,
            "action": "whatsapp_call",
            "platform": "whatsapp",
            "state": STATE_AMBIGUOUS_CONTACT,
            "status": "AMBIGUOUS_CONTACT",
            "message": resolution["message"],
            "requires_clarification": True,
            "matches": resolution.get("matches", []),
            "verified": False
        }

    contact_name = resolution["contact"]["name"]

    if not confirm_call:
        return {
            "success": False,
            "action": "whatsapp_call",
            "platform": "whatsapp",
            "state": STATE_IDLE,
            "status": "CONFIRMATION_REQUIRED",
            "contact": contact_name,
            "call_type": call_type,
            "message": f"Initiating WhatsApp {call_type} call to '{contact_name}' requires confirmation. Proceed?",
            "requires_confirmation": True,
            "verified": False
        }

    health = check_cdp_health()
    if not health.get("ready"):
        status_unavail = "VIDEO_CALL_UNAVAILABLE" if call_type == "video" else "CALL_UNAVAILABLE"
        state_unavail = STATE_VIDEO_CALL_UNAVAILABLE if call_type == "video" else STATE_CALL_UNAVAILABLE
        return {
            "success": False,
            "action": "whatsapp_call",
            "platform": "whatsapp",
            "contact": contact_name,
            "call_type": call_type,
            "state": state_unavail,
            "status": status_unavail,
            "message": f"WhatsApp {call_type} call unavailable: {health.get('message')}",
            "verified": False,
            "error": health.get("message")
        }

    try:
        return browser_automation_engine.run(_async_whatsapp_call_cdp(recipient, call_type))
    except Exception as e:
        logger.warning(f"CDP WhatsApp call failed: {e}")
        status_unavail = "VIDEO_CALL_UNAVAILABLE" if call_type == "video" else "CALL_UNAVAILABLE"
        state_unavail = STATE_VIDEO_CALL_UNAVAILABLE if call_type == "video" else STATE_CALL_UNAVAILABLE
        return {
            "success": False,
            "action": "whatsapp_call",
            "platform": "whatsapp",
            "contact": contact_name,
            "call_type": call_type,
            "state": state_unavail,
            "status": status_unavail,
            "message": f"WhatsApp {call_type} call failed: {e}",
            "verified": False,
            "error": str(e)
        }


async def _async_whatsapp_end_call() -> Dict[str, Any]:
    """Ends active WhatsApp Web call via DOM end call button."""
    _log_wa("Ending call")
    try:
        page = await browser_automation_engine.get_or_open_page("web.whatsapp.com", WHATSAPP_URL)
        end_selectors = [
            'button[aria-label*="End call"]',
            'span[data-icon="call-end"]',
            'button[title*="End call"]'
        ]
        for sel in end_selectors:
            btn = await page.query_selector(sel)
            if btn:
                await btn.click()
                _log_wa("Voice call ended")
                return {
                    "success": True,
                    "action": "whatsapp_end_call",
                    "state": STATE_CALL_ENDED,
                    "status": "ENDED",
                    "message": "WhatsApp call ended successfully.",
                    "verified": True
                }

        _log_wa("CALL_END_UNAVAILABLE — no active call found")
        return {
            "success": False,
            "action": "whatsapp_end_call",
            "state": STATE_CALL_FAILED,
            "status": "CALL_END_UNAVAILABLE",
            "message": "No active WhatsApp Web call controls found in DOM.",
            "verified": False
        }
    except Exception as e:
        return {"success": False, "action": "whatsapp_end_call", "state": STATE_CALL_FAILED, "status": "ENDED_UNVERIFIED", "message": f"End call failed: {e}", "verified": False}


def whatsapp_end_call() -> Dict[str, Any]:
    """Terminates active WhatsApp Web call."""
    try:
        if is_cdp_active():
            return browser_automation_engine.run(_async_whatsapp_end_call())
    except Exception:
        pass
    return {"success": False, "action": "whatsapp_end_call", "status": "CALL_END_UNAVAILABLE", "message": "No active WhatsApp call found.", "verified": False}

