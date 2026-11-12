"""Read and operate the installed WhatsApp WebView, never a browser substitute.

An existing app-owned loopback connection may be used. Otherwise the app
is read locally with Windows OCR. No debug ports or registry values are added.
"""
import asyncio
import json
import os
import re
import subprocess
import time
import urllib.request
import urllib.parse
from pathlib import Path

PORT = 9223
ENDPOINT = f"http://127.0.0.1:{PORT}"


def failed(message, status="ACTION_UNAVAILABLE"):
    return {"success": False, "verified": False, "status": status, "message": message,
            "execution_target": "WINDOWS_INSTALLED_WHATSAPP_DESKTOP"}


def desktop_connection_ready():
    import psutil
    owned = False
    for proc in psutil.process_iter(["name", "cmdline"]):
        try:
            args = proc.info.get("cmdline") or []
            if (proc.info.get("name", "").lower() == "msedgewebview2.exe"
                    and "--webview-exe-name=WhatsApp.Root.exe" in args
                    and f"--remote-debugging-port={PORT}" in args):
                owned = True
                break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if not owned:
        return False
    try:
        with urllib.request.urlopen(ENDPOINT + "/json/version", timeout=1) as response:
            return response.status == 200
    except Exception:
        return False


async def unique(page, selectors):
    for selector in selectors:
        loc = page.locator(selector).filter(visible=True)
        if await loc.count() == 1:
            return loc
    return None


async def open_chat(page, recipient):
    if not recipient.strip():
        return failed("Exact WhatsApp contact name do.", "RECIPIENT_REQUIRED")
    header = page.locator('#main header, [data-testid="conversation-header"]').get_by_text(recipient, exact=True).filter(visible=True)
    if await header.count() == 1:
        return None
    search = await unique(page, ['#side input[aria-label="Search or start a new chat"]',
                                '#side input[placeholder="Search or start a new chat"]',
                                '#side [contenteditable="true"][role="textbox"]',
                                '[contenteditable="true"][aria-label="Search input textbox"]',
                                '[contenteditable="true"][data-tab="3"]'])
    if search is None:
        return failed("WhatsApp search box nahi mila. Login/app check karo.", "SEARCH_UNAVAILABLE")
    await search.fill(recipient)
    match = page.locator('#pane-side span[title]').filter(has_text=re.compile(rf"^{re.escape(recipient)}$", re.I)).filter(visible=True)
    try:
        await match.first.wait_for(state="visible", timeout=5000)
    except Exception:
        return failed(f"WhatsApp contact '{recipient}' nahi mila.", "RECIPIENT_NOT_RESOLVED")
    if await match.count() != 1:
        return failed("Multiple contacts mile. Exact unique contact name do.", "AMBIGUOUS_RECIPIENT")
    await match.click()
    try:
        await header.wait_for(state="visible", timeout=5000)
    except Exception:
        return failed("Selected chat ka recipient verify nahi hua; message/call nahi kiya.", "RECIPIENT_UNVERIFIED")
    return None


async def execute_desktop_page(page, action, recipient="", message="", limit=5):
    if await page.locator('#side').count() == 0:
        return failed("WhatsApp desktop login/loading complete nahi hai.", "LOGIN_REQUIRED")
    if action in ("send", "read", "open_chat", "voice_call", "video_call") and recipient:
        error = await open_chat(page, recipient)
        if error:
            return error
    if action in ("send", "voice_call", "video_call") and not recipient:
        return failed("Exact contact name do.", "RECIPIENT_REQUIRED")
    if action == "open_chat":
        return {"success": True, "verified": True, "message": f"{recipient} ki WhatsApp chat khol di."}
    rows = page.locator('#main .message-in .selectable-text, #main .message-out .selectable-text, [data-testid="conversation-panel-messages"] .message-in .selectable-text, [data-testid="conversation-panel-messages"] .message-out .selectable-text')
    if action == "read":
        texts = [s.strip() for s in await rows.all_text_contents() if s.strip()][-max(1, min(int(limit), 20)):]
        if not texts:
            return failed("Current WhatsApp chat mein readable messages nahi mile.", "NO_VISIBLE_MESSAGES")
        return {"success": True, "verified": True, "status": "VISIBLE_MESSAGES_READ", "messages": texts, "message": "\n".join(texts)}
    if action == "send":
        if not message.strip():
            return failed("Message text do.", "MESSAGE_REQUIRED")
        composer = await unique(page, ['[data-testid="conversation-compose-box-input"][contenteditable="true"]', '#main footer [contenteditable="true"][role="textbox"]'])
        if composer is None:
            return failed("WhatsApp composer nahi mila.", "COMPOSER_NOT_FOUND")
        if (await composer.inner_text()).strip():
            return failed("WhatsApp chat mein unsent draft hai; use overwrite nahi kiya.", "EXISTING_DRAFT")
        outgoing = page.locator('#main .message-out, [data-testid="conversation-panel-messages"] .message-out').filter(has=page.locator('.selectable-text').filter(has_text=re.compile(rf"^{re.escape(message)}$")))
        before = await outgoing.count()
        await composer.fill(message)
        await composer.press("Enter")  # At most one send attempt; never retry on uncertainty.
        for _ in range(20):
            if await outgoing.count() > before:
                last = outgoing.last
                if await last.locator('[data-icon="msg-error"]').count():
                    return failed("WhatsApp ne send error dikhaya. Automatically dobara nahi bheja.", "SEND_ERROR")
                ticks = last.locator('[data-icon="msg-check"], [data-icon="msg-dblcheck"], [data-icon="msg-dblcheck-ack"]')
                if await ticks.count():
                    return {"success": True, "verified": True, "status": "SENT_UI_VERIFIED", "message": f"{recipient} ko WhatsApp par message bhej diya; sent tick verify hua."}
            await asyncio.sleep(0.25)
        return failed("Message submit hua, sent tick verify nahi hua. Automatically dobara nahi bheja.", "SEND_UNVERIFIED")
    if action in ("voice_call", "video_call", "answer", "decline", "end_call"):
        names = {"voice_call": r"^(Voice call|Audio call|Start voice call)$", "video_call": r"^(Video call|Start video call)$",
                 "answer": r"^(Accept|Answer|Accept call|Answer call)$",
                 "decline": r"^(Decline|Decline call|Reject call)$", "end_call": r"^(End call|Hang up)$"}
        button = page.get_by_role("button", name=re.compile(names[action], re.I)).filter(visible=True)
        if await button.count() != 1:
            return failed("WhatsApp call control available nahi hai.", "CALL_CONTROL_UNAVAILABLE")
        await button.click()
        end_button = page.get_by_role("button", name=re.compile(r"^(End call|Hang up)$", re.I)).filter(visible=True)
        for _ in range(12):
            if action in ("decline", "end_call"):
                if await button.count() == 0 and await end_button.count() == 0:
                    return {"success": True, "verified": True, "status": "CALL_ENDED", "message": "WhatsApp call end ho gayi."}
            elif await end_button.count() == 1 and (action != "answer" or await button.count() == 0):
                return {"success": True, "verified": True, "status": "CALL_UI_ACTIVE", "message": "WhatsApp call controls active hain. Dusre person ka connected hona confirm nahi hai."}
            await asyncio.sleep(0.25)
        return failed("Call action attempt hua, call state verify nahi hui.", "CALL_UNVERIFIED")
    return failed("Unsupported WhatsApp action.", "UNSUPPORTED")


def browser_call_fallback(action, recipient=""):
    """Use only an already signed-in WhatsApp Web session, never a QR flow.

    This fallback is allowed only when native controls were unavailable before
    any call attempt. It must not duplicate an uncertain native call.
    """
    from actions.browser_automation import browser_automation_engine
    auth = browser_automation_engine.check_service_auth_sync("whatsapp")
    if not auth.get("authenticated"):
        return failed("Native call controls unavailable; WhatsApp Web mein bhi signed-in call session nahi mila.", "CALL_CONTROL_UNAVAILABLE")
    async def run():
        page = await browser_automation_engine.get_or_open_page("web.whatsapp.com", "https://web.whatsapp.com/")
        result = await execute_desktop_page(page, action, recipient)
        result["execution_target"] = "SIGNED_IN_WHATSAPP_WEB_CALL_FALLBACK"
        return result
    try:
        return browser_automation_engine.run(run(), timeout=25)
    except Exception as exc:
        return failed(f"WhatsApp Web call state verify nahi hui: {type(exc).__name__}", "CALL_UNVERIFIED")


def desktop_action(action, recipient="", message="", limit=5):
    if not desktop_connection_ready():
        from actions.whatsapp_desktop_accessibility import CALL_ACTIONS, execute_accessible_call
        if action in CALL_ACTIONS:
            result = execute_accessible_call(action, recipient)
            if result.get("status") != "ACCESSIBILITY_CONTROL_UNAVAILABLE":
                result["execution_target"] = "WINDOWS_INSTALLED_WHATSAPP_DESKTOP"
                return result
            from actions.whatsapp_desktop_icons import execute_icon_call
            result = execute_icon_call(action, recipient)
            if result.get("status") != "ICON_CONTROL_UNAVAILABLE":
                result["execution_target"] = "WINDOWS_INSTALLED_WHATSAPP_DESKTOP"
                return result
            return browser_call_fallback(action, recipient)
        from actions.whatsapp_desktop_visual import execute_visual
        result = execute_visual(action, recipient, message, limit)
        result["execution_target"] = "WINDOWS_INSTALLED_WHATSAPP_DESKTOP"
        return result
    from actions.browser_automation import browser_automation_engine
    async def run():
        from playwright.async_api import async_playwright
        async with async_playwright() as playwright:
            browser = await playwright.chromium.connect_over_cdp(ENDPOINT, timeout=5000)
            try:
                pages = [p for c in browser.contexts for p in c.pages if urllib.parse.urlparse(p.url).hostname == "web.whatsapp.com"]
                if len(pages) != 1:
                    return failed("Installed WhatsApp chat page exact match nahi mila.", "DESKTOP_PAGE_UNAVAILABLE")
                return await execute_desktop_page(pages[0], action, recipient, message, limit)
            finally:
                await browser.close()  # Disconnects CDP, leaves the installed app running.
    try:
        result = browser_automation_engine.run(run(), timeout=35)
        result["execution_target"] = "WINDOWS_INSTALLED_WHATSAPP_DESKTOP"
        return result
    except Exception as exc:
        return failed(f"WhatsApp desktop action complete nahi hui: {str(exc)[:150]}")
