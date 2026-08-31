# actions/telegram_automation.py
# Dedicated Telegram Web Automation Service for JARVIS (Chrome Profile "Yajat")

import asyncio
import logging
from typing import Dict, Any, Optional
from actions.chrome_profile import open_url_in_yajat_chrome
from actions.browser_automation import browser_automation_engine, is_cdp_active

logger = logging.getLogger("JARVIS.Telegram")

TELEGRAM_URL = "https://web.telegram.org/"

KNOWN_CONTACTS = [
    {"name": "Rahul Sharma", "handle": "@rahul_sharma"},
    {"name": "Rahul Mehta", "handle": "@rahul_mehta"},
    {"name": "Krish", "handle": "@krish_dev"},
    {"name": "Priya Patel", "handle": "@priya_p"},
]


def resolve_telegram_contact(query: str) -> Dict[str, Any]:
    """Resolves Telegram contact with ambiguity handling."""
    if not query:
        return {"status": "not_found", "message": "No contact specified."}

    q_lower = query.strip().lower()
    matches = [c for c in KNOWN_CONTACTS if q_lower in c["name"].lower() or q_lower in c["handle"].lower()]

    if len(matches) == 1:
        return {"status": "exact", "contact": matches[0]}
    elif len(matches) > 1:
        names = [c["name"] for c in matches]
        return {
            "status": "ambiguous",
            "matches": names,
            "message": f"Multiple Telegram contacts matched '{query}': {', '.join(names)}. Which one?",
            "requires_clarification": True
        }

    return {"status": "exact", "contact": {"name": query.strip(), "handle": ""}}


def telegram_open() -> Dict[str, Any]:
    """Opens Telegram Web in Yajat Chrome profile."""
    return open_url_in_yajat_chrome(TELEGRAM_URL)


def telegram_send_message(recipient: str, message: str, force_send: bool = False) -> Dict[str, Any]:
    """Sends message via Telegram Web with confirmation safety."""
    resolution = resolve_telegram_contact(recipient)
    if resolution["status"] == "ambiguous":
        return {
            "success": False,
            "action": "telegram_send",
            "platform": "telegram",
            "message": resolution["message"],
            "requires_clarification": True,
            "matches": resolution["matches"],
            "verified": False
        }

    target_name = resolution["contact"]["name"]
    if not force_send:
        return {
            "success": False,
            "action": "telegram_send",
            "platform": "telegram",
            "contact": target_name,
            "message_text": message,
            "message": f"Telegram message ready for {target_name}: '{message}'. Should I send it?",
            "requires_confirmation": True,
            "verified": False
        }

    # Open Telegram Web — honest about what we can and can't do
    open_res = open_url_in_yajat_chrome(TELEGRAM_URL)
    if not open_res.get("success"):
        return {
            "success": False,
            "action": "telegram_send",
            "platform": "telegram",
            "contact": target_name,
            "message": f"Could not open Telegram Web: {open_res.get('message')}",
            "verified": False,
            "error": open_res.get("message")
        }

    return {
        "success": False,
        "action": "telegram_send",
        "platform": "telegram",
        "contact": target_name,
        "message_text": message,
        "message": f"Telegram Web opened for {target_name} in Yajat Chrome. Message NOT sent automatically — CDP automation required for DOM interaction.",
        "verified": False,
        "error": "CDP unavailable — manual send required"
    }


async def _async_telegram_read_cdp(recipient: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
    """Internal async CDP Telegram DOM message reader using Playwright CDP."""
    page = await browser_automation_engine.get_or_open_page("telegram", TELEGRAM_URL)
    await page.wait_for_timeout(2000)

    # Optional: Select recipient if specified
    if recipient:
        res = resolve_telegram_contact(recipient)
        target_name = res["contact"]["name"] if res.get("contact") else recipient
        search_el = await browser_automation_engine.find_element(
            page,
            selectors=[".input-search input", "#telegram-search-input", "input[type='search']", "input[placeholder*='Search']"],
            timeout=2.0
        )
        if search_el:
            await search_el.fill(target_name)
            await page.wait_for_timeout(1000)
            chat_item = await browser_automation_engine.find_element(
                page,
                selectors=[f".chatlist-chat:has-text('{target_name}')", f".ListItem:has-text('{target_name}')", f"text='{target_name}'"],
                timeout=2.0
            )
            if chat_item:
                await chat_item.click()
                await page.wait_for_timeout(1500)

    msg_elements = await page.query_selector_all(".message, .Message, [data-message-id]")
    results = []

    for el in msg_elements[-limit:]:
        try:
            t_el = await el.query_selector(".message-content, .text-content, .content, .text")
            text = (await t_el.inner_text()).strip() if t_el else (await el.inner_text()).strip()

            s_el = await el.query_selector(".peer-title, .author-name, .sender-title, .name")
            sender = (await s_el.inner_text()).strip() if s_el else "Contact"

            tm_el = await el.query_selector(".message-time, .time, time")
            timestamp = (await tm_el.inner_text()).strip() if tm_el else "Just now"

            if text:
                results.append({
                    "sender": sender,
                    "text": text[:250],
                    "timestamp": timestamp
                })
        except Exception:
            continue

    if results:
        return {
            "success": True,
            "action": "telegram_read",
            "platform": "telegram",
            "recipient": recipient or "Active Chat",
            "messages": results,
            "message": f"Successfully extracted {len(results)} Telegram messages via CDP.",
            "verified": True
        }
    else:
        return {
            "success": False,
            "action": "telegram_read",
            "platform": "telegram",
            "recipient": recipient or "Active Chat",
            "messages": [],
            "message": "Telegram Web opened via CDP, but no active messages were found in current viewport.",
            "verified": False,
            "error": "No message DOM elements found"
        }


def telegram_read_messages(recipient: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
    """Reads Telegram messages — leverages Playwright CDP when available."""
    try:
        if is_cdp_active():
            res = browser_automation_engine.run(_async_telegram_read_cdp(recipient, limit), timeout=30)
            if res and isinstance(res, dict) and res.get("success"):
                return res
    except Exception as e:
        logger.warning(f"CDP Telegram read failed: {e}")

    # Fallback when CDP is unavailable or DOM parsing yields zero elements
    open_url_in_yajat_chrome(TELEGRAM_URL)
    return {
        "success": False,
        "action": "telegram_read",
        "platform": "telegram",
        "message": "Telegram Web opened in Yajat Chrome, but automatic message reading was unavailable. Please check manually.",
        "verified": False,
        "error": "CDP unavailable or DOM unreadable"
    }


def telegram_make_call(recipient: str, confirm_call: bool = False) -> Dict[str, Any]:
    """Telegram call initiation with confirmation safety."""
    resolution = resolve_telegram_contact(recipient)
    if resolution["status"] == "ambiguous":
        return {
            "success": False,
            "action": "telegram_call",
            "platform": "telegram",
            "message": resolution["message"],
            "requires_clarification": True,
            "matches": resolution["matches"],
            "verified": False
        }

    contact_name = resolution["contact"]["name"]
    if not confirm_call:
        return {
            "success": False,
            "action": "telegram_call",
            "platform": "telegram",
            "contact": contact_name,
            "message": f"Telegram call to '{contact_name}' requires confirmation. Proceed?",
            "requires_confirmation": True,
            "verified": False
        }

    open_res = open_url_in_yajat_chrome(TELEGRAM_URL)
    if not open_res.get("success"):
        return {
            "success": False,
            "action": "telegram_call",
            "platform": "telegram",
            "contact": contact_name,
            "message": f"Could not open Telegram Web: {open_res.get('message')}",
            "verified": False,
            "error": open_res.get("message")
        }

    return {
        "success": False,
        "action": "telegram_call",
        "platform": "telegram",
        "contact": contact_name,
        "message": f"Telegram Web opened for {contact_name}. Call requires CDP automation — please initiate manually.",
        "verified": False,
        "error": "CDP unavailable — manual action needed"
    }
