"""Explicit Discord/Instagram commands and verified browser chat actions."""
import asyncio
import re


def parse_social_command(query: str, include_whatsapp: bool = False) -> dict | None:
    from core.intent_router import normalize_command_prefix
    query = normalize_command_prefix(query)
    platforms = r"discord|instagram|insta|ig|whatsapp|whastapp|whtsapp|whatsap" if include_whatsapp else r"discord|instagram|insta|ig"
    match = re.search(rf"\b({platforms})\b", query, re.I)
    if not match:
        return None
    platform = ('whatsapp' if match[1].lower() in ('whatsapp', 'whastapp', 'whtsapp', 'whatsap')
                else 'discord' if match[1].lower() == 'discord' else 'instagram')
    before = re.sub(r"\b(?:pe|par|on|via)\s*$", "", query[:match.start()], flags=re.I)
    after = re.sub(r"^\s*(?:p|pe|par)\b", "", query[match.end():], flags=re.I)
    text = (before + " " + after).strip()
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r'^(?:open|khol(?:o)?|open\s+kar(?:o)?)\s+(?:and|aur|then)\s+', '', text, flags=re.I)
    chat = re.match(r"^(.+?)\s+(?:ki|ka)\s+chat\s+(?:khol(?:o)?|open\s+kar(?:o)?)(?:\s+(?:do|de))?$|^(?:open|show)\s+(?:the\s+)?chat\s+(?:with|for)\s+(.+)$", text, re.I)
    if chat:
        return {"platform": platform, "action": "open_chat", "recipient": (chat[1] or chat[2]).strip()}
    patterns = [
        r"^send\s+(?P<recipient>.+?)\s+a\s+message\s+(?:saying|that)\s+(?P<message>.+)$",
        r"^(?P<recipient>.+?)\s+and\s+tell\s+(?:him|her|them)\s+(?P<message>.+)$",
        r'''^(?:send|message)\s+(?:(?:a|the)\s+)?(?:message\s+)?['"](?P<message>.+)['"]\s+to\s+(?P<recipient>.+)$''',
        r"^send\s+(?:a\s+)?(?:message|msg|ms|msf)\s+(?:of\s+)?(?P<message>.+?)\s+to\s+(?P<recipient>.+)$",
        r"^send\s+(?:ms|msg)\s+(?:to|tu)\s+(?P<recipient>.+?)\s+of\s+(?P<message>.+)$",
        r'^(?:send|dm|message)\s+(?:to\s+)?(?P<recipient>.+?)\s+"(?P<message>.+)"$',
        r'^(?:send|message)\s+"(?P<message>.+)"\s+to\s+(?P<recipient>.+)$',
        r"^(?:send|dm|message|msg)\s+(?:a\s+)?(?:message\s+)?(?:to\s+)?(?P<recipient>.+?)\s+(?:saying|say|that|:|with message)\s*(?P<message>.+)$",
        r"^(?P<recipient>.+?)\s+ko\s+(?:message|msg|dm)\s+(?:bhej(?:o)?|kar(?:o)?|kr)(?:\s+(?:do|de))?\s*[:,-]?\s+(?P<message>.+)$",
        r"^(?P<recipient>.+?)\s+ko\s+(?:bol\s+de|bol(?:o)?|bolna)\s+(?P<message>.+)$",
        r"^(?P<recipient>.+?)\s+ko\s+(?P<message>.+?)\s+(?:bhej(?:o)?|send\s+kar(?:o)?)(?:\s+(?:do|de))?$",
    ]
    for pattern in patterns:
        m = re.match(pattern, text, re.I)
        if m:
            return {"platform": platform, "action": "send", "recipient": m["recipient"].strip(), "message_text": m["message"].strip().strip('"')}
    send_only = re.match(r'^(?:send\s+(?:a\s+)?(?:message|msg)\s+to\s+(.+)|(.+?)\s+ko\s+(?:message|msg)\s+(?:bhej(?:o)?|bhj|kar(?:o)?|kr)(?:\s+(?:do|de))?)$', text, re.I)
    if send_only:
        return {'platform': platform, 'action': 'send', 'recipient': (send_only[1] or send_only[2]).strip(), 'message_text': ''}
    if re.search(r"\b(send|bhej(?:o)?|dm)\b|\b(?:message|msg)\s+(?:kar|karo)\b", text, re.I):
        return {"platform": platform, "action": "send", "recipient": "", "message_text": ""}
    if re.search(r"\b(read|padho?|padh|messages?|msg|unread)\b", text, re.I):
        m = re.match(r"^(.+?)\s+(?:ke|ki|ka)\s+(?:messages?|msg)\b", text, re.I)
        english = re.match(r"^(?:read|show)(?:\s+me)?\s+(?:the\s+)?messages?\s+from\s+(.+)$", text, re.I)
        return {"platform": platform, "action": "read", "recipient": m[1].strip() if m else english[1].strip() if english else ""}
    if re.search(r"\b(call|calling)\b", text, re.I):
        action = "answer" if re.search(r"\b(answer|receive|utha|uthao|pick)\b", text, re.I) else "end_call" if re.search(r"\b(end|hang|kaat|cut|disconnect)\b", text, re.I) else "call"
        m = re.match(r"^(.+?)\s+ko\s+(?:video\s+)?call\b|^call\s+(.+?)(?:\s+(?:karo|kar|laga))?$", text, re.I)
        return {"platform": platform, "action": action, "recipient": (m[1] or m[2]).strip() if m and action == "call" else "", "call_type": "video" if "video" in text.lower() else "voice"}
    return None


def _failed(message: str, status: str = "ACTION_UNAVAILABLE") -> dict:
    return {"success": False, "verified": False, "status": status, "message": message}


async def _visible_unique(page, selectors):
    for selector in selectors:
        items = page.locator(selector).filter(visible=True)
        if await items.count() == 1:
            return items
    return None


async def _open_chat(page, platform: str, recipient: str) -> dict | None:
    """Only select an exact, unique name. Never pick the first fuzzy search hit."""
    if not recipient:
        return None  # Reading the currently visible chat is explicitly supported.
    name = recipient.lstrip("@").strip()
    current_chat = r"/channels/@me/\d+" if platform == "discord" else r"/direct/t/"
    heading = page.get_by_role("heading", name=re.compile(rf"^\s*@?{re.escape(name)}\s*$", re.I)).filter(visible=True)
    if re.search(current_chat, page.url) and await heading.count() == 1:
        return None
    if platform == "discord":
        links = page.locator('a[href^="/channels/@me/"]').filter(has_text=re.compile(rf"^\s*{re.escape(name)}\s*$", re.I))
        if await links.count() != 1:
            return _failed(f"Discord DM '{recipient}' ko exact match nahi mila. Chat ek baar kholkar phir command do.", "RECIPIENT_NOT_RESOLVED")
        await links.click(timeout=5000)
        await page.wait_for_url(re.compile(r"/channels/@me/\d+"), timeout=5000)
    else:
        await page.goto("https://www.instagram.com/direct/new/", wait_until="domcontentloaded")
        search = await _visible_unique(page, ['input[name="queryBox"]', 'input[placeholder="Search..."]', 'input[placeholder="Search"]'])
        if search is None:
            return _failed("Instagram recipient search available nahi hai. Controlled browser mein sign in karo.", "LOGIN_REQUIRED")
        await search.fill(name)
        exact = page.get_by_text(name, exact=True).filter(visible=True)
        try:
            await exact.first.wait_for(state="visible", timeout=5000)
        except Exception:
            return _failed(f"Instagram handle '@{name}' nahi mila.", "RECIPIENT_NOT_RESOLVED")
        if await exact.count() != 1:
            return _failed("Multiple recipient matches hain. Exact Instagram username do.", "AMBIGUOUS_RECIPIENT")
        await exact.click()
        chat = page.get_by_role("button", name=re.compile(r"^(Chat|Next)$", re.I)).filter(visible=True)
        if await chat.count() != 1:
            return _failed("Instagram chat selection confirm nahi hui.", "RECIPIENT_NOT_RESOLVED")
        await chat.click()
        await page.wait_for_url(re.compile(r"/direct/t/"), timeout=5000)
    return None


async def execute_social_chat(page, platform: str, action: str, recipient: str = "", message_text: str = "", call_type: str = "voice") -> dict:
    """Operate one signed-in page. Sending is attempted at most once."""
    if any(part in page.url.lower() for part in ("/login", "/accounts/login")):
        return _failed(f"{platform.title()} mein sign in karna baaki hai.", "LOGIN_REQUIRED")
    if action in ("send", "call", "open_chat") and not recipient:
        return _failed("Exact recipient/username batao.", "RECIPIENT_REQUIRED")
    if action == "send" and not message_text.strip():
        return _failed("Kya message bhejna hai?", "MESSAGE_REQUIRED")
    if action in ("send", "read", "call", "open_chat"):
        error = await _open_chat(page, platform, recipient)
        if error:
            return error
    # A logged-in homepage is not evidence of an active conversation.
    chat_url = r"/channels/@me/\d+" if platform == "discord" else r"/direct/t/"
    if action in ("send", "read", "call", "open_chat") and not re.search(chat_url, page.url):
        return _failed("Chat pehle khol do ya exact recipient do.", "CHAT_NOT_OPEN")
    if action == "open_chat":
        return {"success": True, "verified": True, "status": "CHAT_OPEN_VERIFIED", "message": f"{recipient} ki {platform.title()} chat khol di."}
    messages = page.locator('[id^="message-content-"]' if platform == "discord" else 'div[role="row"]')
    if action == "read":
        texts = [t.strip() for t in await messages.all_text_contents() if t.strip()][-10:]
        if not texts:
            return _failed("Visible chat mein readable messages nahi mile.", "NO_VISIBLE_MESSAGES")
        return {"success": True, "verified": True, "status": "VISIBLE_MESSAGES_READ", "messages": texts, "message": "\n".join(texts)}
    if action == "send":
        composer = await _visible_unique(page, ['div[role="textbox"][contenteditable="true"]', 'textarea[placeholder="Message..."]', 'textarea[placeholder="Message"]'])
        if composer is None:
            return _failed("Message box nahi mila. Chat/login check karo.", "COMPOSER_NOT_FOUND")
        # Protect a user's existing unsent draft.
        draft = await composer.input_value() if await composer.evaluate("el => el.tagName === 'TEXTAREA'") else await composer.inner_text()
        if draft.strip():
            return _failed("Chat mein unsent draft hai. Use clear/send karke phir command do.", "EXISTING_DRAFT")
        exact_messages = (messages.filter(has_text=re.compile(rf"^{re.escape(message_text)}$")) if platform == "discord"
                          else page.get_by_text(message_text, exact=True).filter(visible=True))
        before = await exact_messages.count()
        await composer.fill(message_text)
        await composer.press("Enter")
        for _ in range(12):
            if await exact_messages.count() > before:
                return {"success": True, "verified": True, "status": "SUBMITTED_UI_VERIFIED", "message": f"{recipient} ki {platform.title()} chat mein message appear ho gaya. Delivery/read status confirm nahi hai."}
            await asyncio.sleep(0.25)
        return _failed("Send attempt ho gaya, lekin chat mein message verify nahi hua. Dobara automatically send nahi kiya.", "SEND_UNVERIFIED")
    if action in ("call", "answer", "end_call"):
        names = {"call": r"^(Start Voice Call|Audio Call|Voice Call|Call)$" if call_type == "voice" else r"^(Start Video Call|Video Call)$", "answer": r"^(Accept|Answer|Join Call)$", "end_call": r"^(Disconnect|End Call|Hang Up)$"}
        button = page.get_by_role("button", name=re.compile(names[action], re.I)).filter(visible=True)
        if await button.count() != 1:
            return _failed(f"{platform.title()} mein {action} ka usable call button nahi mila. Native app mein call control available ho sakta hai.", "CALL_CONTROL_UNAVAILABLE")
        await button.click(timeout=5000)
        end_control = page.get_by_role("button", name=re.compile(names["end_call"], re.I)).filter(visible=True)
        for _ in range(12):
            if action == "end_call" and await end_control.count() == 0:
                return {"success": True, "verified": True, "status": "CALL_UI_ENDED", "message": "Call ke active controls band ho gaye."}
            if action in ("call", "answer") and await end_control.count() == 1:
                return {"success": True, "verified": True, "status": "CALL_UI_ACTIVE", "message": "Call controls active ho gaye. Dusre person ka connected hona confirm nahi hai."}
            await asyncio.sleep(.25)
        return _failed("Call action attempt hua, lekin call controls ki state verify nahi hui.", "CALL_UNVERIFIED")
    return _failed("Yeh social action supported nahi hai.", "UNSUPPORTED")


def social_chat(parameters=None, player=None, **kwargs) -> dict:
    p = {**(parameters or {}), **kwargs}
    platform = p.get("platform", "").lower()
    if platform not in ("discord", "instagram"):
        return _failed("Platform Discord ya Instagram hona chahiye.", "UNSUPPORTED")
    from actions.browser_automation import browser_automation_engine, ensure_cdp_chrome
    url = "https://discord.com/channels/@me" if platform == "discord" else "https://www.instagram.com/direct/inbox/"
    ready = ensure_cdp_chrome(url)
    if not ready.get("success"):
        return _failed("Controlled browser connect nahi hua. " + ready.get("message", ""), "BROWSER_UNAVAILABLE")
    async def run():
        page = await browser_automation_engine.get_or_open_page(f"{platform}.com", url)
        return await execute_social_chat(page, platform, p.get("action", "read"), p.get("recipient", ""), p.get("message_text", ""), p.get("call_type", "voice"))
    try:
        return browser_automation_engine.run(run(), timeout=45)
    except Exception as exc:
        return _failed(f"{platform.title()} action complete nahi hua: {str(exc)[:160]}")
