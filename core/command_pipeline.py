# core/command_pipeline.py
# Single Unified Command Processing Pipeline for JARVIS (Voice & Typed Chat)

import os
import sys
import re
import time
import json
import logging
import threading
import copy
from typing import Dict, Any, Optional, Tuple, Callable

from core.intent_router import classify_intent, normalize_command_prefix
from core.tool_registry import default_tool_registry
from core.security import default_security_manager
from actions.app_registry import resolve_app, is_app_installed
from actions.app_first_routing import resolve_app_or_web_target
from core.ollama_provider import generate_ollama_response, is_ollama_available

logger = logging.getLogger("JARVIS.CommandPipeline")

# Module-level flag: tool registry initialization status (thread-safe via GIL)
_tools_initialized = False

# ── Global Atomic Command Correlation ID Counter ──
_CMD_COUNTER = 0
_CMD_COUNTER_LOCK = threading.Lock()

def _next_command_id() -> str:
    """Thread-safe monotonic command ID: CMD-00001, CMD-00002, ..."""
    global _CMD_COUNTER
    with _CMD_COUNTER_LOCK:
        _CMD_COUNTER += 1
        return f"CMD-{_CMD_COUNTER:05d}"

# Global Conversation Context State Machine (thread-safe)
_CONTEXT_LOCK = threading.Lock()
_CONVERSATION_CONTEXT: Dict[str, Any] = {
    "last_app": None,
    "last_platform": None,
    "last_contact": None,
    "last_channel": None,
    "pending_disambiguation": None,  # e.g., {"app": "discord", "native_available": True, "web_available": True}
    "pending_important_message": None,  # e.g., {"contact": "Papa", "message": "Beta ghar kab aaoge?", "platform": "whatsapp"}
    "pending_screen_context": None,  # e.g., {"active_window": "VS Code", "observation": "...", "time": 12345678}
    "pending_power_action": None,
    "pending_sequence": None,
    # ── Short-Term Execution Context (for follow-ups) ──
    "last_command": None,       # raw user text
    "last_target": None,        # resolved target (e.g. "WhatsApp")
    "last_action": None,        # tool/action name (e.g. "open_app")
    "last_result": None,        # "SUCCESS" | "FAILED" | "PARTIAL"
    "last_error": None,         # error message if failed
    "last_command_id": None,    # CMD-XXXXX
    "last_timestamp": 0.0,      # time.time()
    "last_social_target": None,  # Exact verified platform/contact, shared by voice and chat.
    "pending_send_details": None,
}


def get_conversation_context() -> Dict[str, Any]:
    """Returns a thread-safe snapshot of the current conversation context."""
    with _CONTEXT_LOCK:
        return copy.copy(_CONVERSATION_CONTEXT)


def reset_conversation_context() -> None:
    """Resets conversational context (thread-safe)."""
    with _CONTEXT_LOCK:
        _CONVERSATION_CONTEXT.update({
            "last_app": None,
            "last_platform": None,
            "last_contact": None,
            "last_channel": None,
            "pending_disambiguation": None,
            "pending_important_message": None,
            "pending_screen_context": None,
            "pending_power_action": None,
            "pending_sequence": None,
            "last_command": None,
            "last_target": None,
            "last_action": None,
            "last_result": None,
            "last_error": None,
            "last_command_id": None,
            "last_timestamp": 0.0,
            "last_social_target": None,
            "pending_send_details": None,
        })


def _update_execution_context(command_id: str, raw_text: str, target: str,
                              action: str, result: str, error: str = "") -> None:
    """Records the result of the most recent command for follow-up resolution (thread-safe)."""
    with _CONTEXT_LOCK:
        _CONVERSATION_CONTEXT["last_command"] = raw_text
        _CONVERSATION_CONTEXT["last_target"] = target
        _CONVERSATION_CONTEXT["last_action"] = action
        _CONVERSATION_CONTEXT["last_result"] = result
        _CONVERSATION_CONTEXT["last_error"] = error
        _CONVERSATION_CONTEXT["last_command_id"] = command_id
        _CONVERSATION_CONTEXT["last_timestamp"] = time.time()


def _remember_social_target(command: dict, success: bool, verified: bool) -> None:
    """Only a recent, verified exact contact may authorize pronoun resolution."""
    recipient = command.get("recipient", "")
    if not recipient and command.get("action") not in ("read", "open_chat", "send", "call"):
        return
    with _CONTEXT_LOCK:
        _CONVERSATION_CONTEXT["last_social_target"] = (
            {"platform": command["platform"], "recipient": recipient, "time": time.monotonic()}
            if recipient and success and verified else None
        )
        if recipient and success and verified:
            _CONVERSATION_CONTEXT["last_contact"] = recipient
            _CONVERSATION_CONTEXT["last_platform"] = command["platform"]
            _CONVERSATION_CONTEXT["last_app"] = command["platform"]


def _resolve_social_follow_up(text: str) -> tuple[Optional[dict], Optional[dict]]:
    """Resolve only the leading recipient reference, never message contents."""
    text = normalize_command_prefix(text)
    from actions.social_chat import parse_social_command
    explicit = parse_social_command(text, include_whatsapp=True)
    reference = re.match(r"^(?:(?P<platform>discord|instagram|insta|ig|whatsapp)\s+(?:(?:p|pe|par|on)\s+)?)?(?P<pronoun>usko|usse|uske|uska|uski|same contact|same person)\b\s*", text, re.I)
    if reference and not re.search(r"\b(chat|messages?|msg|dm|send|bhej(?:o)?|reply|call|padh|padho?|bol(?:o)?)\b", text[reference.end():], re.I):
        reference = None  # Ordinary conversation is not a contact action.
    reply = re.match(r"^reply(?:\s+(?:kar(?:o)?|bhej(?:o)?)(?:\s+(?:do|de))?)?\s+(.+)$", text, re.I)
    pronouns = {"usko", "usse", "uske", "uska", "uski", "same contact", "same person"}
    parsed_reference = explicit and explicit.get("recipient", "").casefold() in pronouns
    if not reference and not reply and not parsed_reference:
        return explicit, None
    with _CONTEXT_LOCK:
        target = copy.copy(_CONVERSATION_CONTEXT.get("last_social_target"))
    requested_platform = reference["platform"].casefold() if reference and reference["platform"] else explicit["platform"] if parsed_reference else None
    requested_platform = {"insta": "instagram", "ig": "instagram"}.get(requested_platform, requested_platform)
    if not target or time.monotonic()-target["time"] > 120 or requested_platform and requested_platform != target["platform"]:
        return None, {"success": False, "verified": False, "status": "CONTACT_CONTEXT_REQUIRED", "requires_clarification": True, "message": "Kis contact ko, aur kis app par? Exact naam aur platform bata do."}
    if parsed_reference:
        return {**explicit, "recipient": target["recipient"]}, None
    if reply:
        return {"platform": target["platform"], "recipient": target["recipient"], "action": "send", "message_text": reply[1].strip().strip('"')}, None
    pronoun = reference["pronoun"].casefold()
    remainder = text[reference.end():]
    joiner = "ke" if pronoun in ("uske", "uska") else "ki" if pronoun == "uski" else "ko"
    if pronoun == "usse" and re.match(r"^(?:bol(?:o)?|bol\s+de)\s+", remainder, re.I):
        remainder = re.sub(r"^(?:bol\s+de|bol(?:o)?)\s+", "message bhejo ", remainder, count=1, flags=re.I)
    remainder = re.sub(r"^(?:ko|ke|ki)\s+", "", remainder, count=1, flags=re.I)
    resolved = parse_social_command(f'{target["platform"]} {target["recipient"]} {joiner} {remainder}', include_whatsapp=True)
    if resolved and resolved.get("recipient") == target["recipient"]:
        return resolved, None
    return None, {"success": False, "verified": False, "status": "FOLLOW_UP_DETAILS_REQUIRED", "requires_clarification": True, "message": "Us contact ke liye kya karna hai? Message ka text ya exact action bata do."}


def _collect_send_details(text: str, explicit: Optional[dict]) -> tuple[Optional[dict], Optional[dict]]:
    """Collect missing send slots from current user replies, never old AI memory."""
    from actions.social_chat import parse_social_command
    with _CONTEXT_LOCK:
        pending = copy.copy(_CONVERSATION_CONTEXT.get('pending_send_details'))
        _CONVERSATION_CONTEXT['pending_send_details'] = None
    if explicit:
        pending = None  # A fresh explicit action supersedes an unfinished one.
        if explicit.get('action') != 'send':
            return explicit, None
        command = dict(explicit)
    elif pending and time.monotonic() - pending['time'] < 120:
        if text.casefold().strip(' .!?') in ('cancel', 'nahi', 'no', 'rehne do', 'stop'):
            return None, {'success': False, 'verified': False, 'status': 'SEND_CANCELLED', 'message': 'Message request cancel kar di.'}
        if classify_intent(text).get('intent') != 'OTHER':
            return None, None  # A new laptop action must not become message text.
        command = {key: value for key, value in pending.items() if key != 'time'}
        named = parse_social_command(f"{command['platform']} {text}", include_whatsapp=True)
        if named and named.get('recipient'):
            command.update(named)
        elif not command.get('recipient'):
            contact = re.fullmatch(r'(.+?)\s+ko(?:\s+(?:bhj|bhej|bhejna|bhjna|bhejo|send|message|msg)(?:\s+hai)?)?', text, re.I)
            if contact:
                command['recipient'] = contact[1].strip()
            elif len(text) <= 80 and not re.search(r'[?!]|\b(kya|kaise|why|what|haan|yes)\b', text, re.I):
                command['recipient'] = text.strip()
        elif text.casefold().strip(' .!?') not in ('haan', 'han', 'hn', 'yes', 'okay', 'ok'):
            command['message_text'] = re.sub(r'^(?:message|msg|text)\s*[:,-]?\s+', '', text, flags=re.I).strip()
    else:
        return explicit, None
    if command.get('recipient') and command.get('message_text'):
        return command, None
    with _CONTEXT_LOCK:
        _CONVERSATION_CONTEXT['pending_send_details'] = {**command, 'time': time.monotonic()}
    message = ('Kis contact ko? WhatsApp ka exact naam batao.' if not command.get('recipient')
               else f"{command['recipient']} ko kya message bhejna hai? Exact text likho.")
    return None, {'success': False, 'verified': False, 'requires_clarification': True,
                  'status': 'SEND_DETAILS_REQUIRED', 'message': message}


def _log_command_telemetry(
    command_id: str,
    wake_word: str,
    raw_transcript: str,
    normalized_transcript: str,
    intent: str,
    tool: str,
    arguments: Any,
    execution_result: str,
    verification_result: Any,
    final_response: str,
    tts_status: str = "SENT",
    process_info: str = "",
    window_info: str = "",
    target_app: str = "",
    target_contact: str = ""
) -> None:
    """Emits structured end-to-end command diagnostics for real voice & PC-control validation."""
    lines = [
        "==================================================",
        f"[COMMAND_TELEMETRY] {command_id}",
        f"Wake: {wake_word or 'Jarvis'}",
        f"Transcript: {raw_transcript}",
        f"Normalized: {normalized_transcript}",
        f"Intent: {intent}",
        f"Tool: {tool}",
        f"Arguments: {arguments}",
        f"Execution: {execution_result}",
    ]
    if target_app:
        lines.append(f"TargetApp: {target_app}")
    if target_contact:
        lines.append(f"TargetContact: {target_contact}")
    if process_info:
        lines.append(f"Process: {process_info}")
    if window_info:
        lines.append(f"Window: {window_info}")
    lines.extend([
        f"Verification: {verification_result}",
        f"Response: {final_response}",
        f"TTS: {tts_status}",
        "=================================================="
    ])
    block = "\n".join(lines)
    logger.info(block)
    print(block, flush=True)


def _log_failure_stage(stage_letter: str, stage_name: str, command_id: str, details: str) -> None:
    """Logs diagnostic failure at specific stage (A through L) to identify exact break in voice chain."""
    msg = f"[VOICE_DIAGNOSTIC] [{command_id}] STAGE_{stage_letter}_FAIL ({stage_name}): {details}"
    logger.warning(msg)
    print(msg, flush=True)



# ── Frustration / Follow-Up Detection ──
_FRUSTRATION_WORDS = [
    "bakchodi", "gandu", "chutiya", "bsdk", "mc", "bc",
    "kyu nahi", "kaam nahi", "chal nahi", "tu kuch karta nahi",
    "kuch nahi hota", "kya fayda", "bekar", "faltu", "useless",
    "tu bekaar hai", "kuch kar bhi", "abe", "oye",
]

_RETRY_WORDS = [
    "dobara", "fir se", "phir se", "retry", "again", "ek aur baar",
    "wapas", "try again", "dubara", "same", "wahi", "firse",
]

_FAILURE_REFERENCE_WORDS = [
    "nahi hua", "nahi khula", "nahi chala", "nahi ho raha",
    "open nahi", "kyu nahi", "tu kyu", "khul nahi",
    "nahi chal raha", "kaam nahi", "kuch nahi",
]

_CLOSE_PREV_WORDS = [
    "isko band", "isko close", "ye band", "ye close",
    "ise band", "ise close", "band kar isko",
]


def _detect_follow_up_intent(lower_text: str) -> Optional[Dict[str, Any]]:
    """Detects if the user's input is a contextual follow-up to a previous command."""
    with _CONTEXT_LOCK:
        ctx = copy.copy(_CONVERSATION_CONTEXT)
    last_target = ctx.get("last_target")
    last_result = ctx.get("last_result")
    last_action = ctx.get("last_action")
    last_error = ctx.get("last_error", "")
    last_ts = ctx.get("last_timestamp", 0.0)

    # Only consider follow-ups within 60 seconds
    if not last_target or (time.time() - last_ts) > 60.0:
        return None

    # ── Frustration about previous failure ──
    is_frustrated = any(w in lower_text for w in _FRUSTRATION_WORDS)
    is_failure_ref = any(w in lower_text for w in _FAILURE_REFERENCE_WORDS)

    if is_frustrated or is_failure_ref:
        if last_result == "FAILED":
            reason = last_error or f"{last_target} ka command fail hua tha"
            if is_frustrated:
                msg = f"Arre haan bhai, meri galti — {last_target} wala command properly execute nahi hua. Reason: {reason}. Ab actual fix try karta hoon."
            else:
                msg = f"Ha bhai, {last_target} ka pichla command fail hua tha. Reason: {reason}."
            return {
                "type": "frustration_followup",
                "message": msg,
                "last_target": last_target,
                "last_action": last_action,
            }
        elif last_result == "SUCCESS":
            msg = f"Boss, {last_target} wala command toh successfully execute hua tha. Koi aur issue hai kya?"
            return {
                "type": "frustration_followup",
                "message": msg,
                "last_target": last_target,
                "last_action": last_action,
            }

    # ── Retry previous failed action ──
    if any(w in lower_text for w in _RETRY_WORDS):
        if last_action and last_target:
            return {
                "type": "retry",
                "target": last_target,
                "action": last_action,
            }

    # ── Close previous target ──
    if any(w in lower_text for w in _CLOSE_PREV_WORDS):
        if last_target:
            return {
                "type": "close_previous",
                "target": last_target,
            }

    return None


def set_pending_disambiguation(app_name: str, options: Dict[str, Any]) -> None:
    """Sets a pending native vs web choice prompt (thread-safe)."""
    with _CONTEXT_LOCK:
        _CONVERSATION_CONTEXT["pending_disambiguation"] = {
            "app": app_name,
            "options": options
        }


def set_pending_important_message(contact: str, message: str, platform: str = "whatsapp") -> None:
    """Sets a pending important message read-aloud confirmation prompt (thread-safe)."""
    with _CONTEXT_LOCK:
        _CONVERSATION_CONTEXT["pending_important_message"] = {
            "contact": contact,
            "message": message,
            "platform": platform
        }


def _parse_power_request(text: str) -> Optional[dict]:
    value = normalize_command_prefix(text).casefold().strip(' .!?,')
    value = re.sub(r'^(?:please|can you|could you|will you)\s+', '', value)
    device = r'(?:my\s+|the\s+|mera\s+|mere\s+)?(?:laptop|pc|computer|system|desktop|phone|mobile|android|लैपटॉप|कंप्यूटर|फोन|फ़ोन|पीसी)'
    action = r'(?:shut\s*down|shutdown|restart|reboot|turn\s*off|band|off|बंद|रीस्टार्ट|शटडाउन)'
    suffix = r'(?:\s+(?:kar\s+(?:do|de)|kar|karo|kardo|karde|krdo|kro|please|कर\s+दो|करो))?'
    direct = re.fullmatch(rf'(?P<action>{action})(?:\s+(?P<device>{device}))?{suffix}', value)
    reverse = re.fullmatch(rf'(?P<device>{device})(?:\s+ko)?\s+(?P<action>{action}){suffix}', value)
    match = direct or reverse
    if not match:
        return None
    if not match.group('device') and match.group('action') in ('band', 'off', 'बंद'):
        return None
    target = match.group('device') or 'laptop'
    return {'action': 'restart' if match.group('action') in ('restart', 'reboot', 'रीस्टार्ट') else 'shutdown',
            'target_device': 'android' if re.search(r'phone|mobile|android|फोन|फ़ोन', target) else 'pc'}


def _power_confirmation_kind(text: str) -> Optional[str]:
    value = normalize_command_prefix(text).casefold().strip(' .!?,')
    if re.fullmatch(r'(?:haan|han|ha|hn|yes|yep|confirm|sure|ok|okay|हाँ|हां|जी)(?:\s+(?:kar do|kardo|karo|do it|please|कर दो|करो))?|kar do|do it', value):
        return 'yes'
    if re.fullmatch(r'(?:nahi|no|mat|dont|don\x27t|stop|cancel|reject|rehne do|नहीं|मत|रुको)(?:\s+(?:karo|karna|do it))?', value):
        return 'no'
    return None


def is_pending_power_confirmation(text: str) -> bool:
    if _power_confirmation_kind(text) is None:
        return False
    with _CONTEXT_LOCK:
        pending = _CONVERSATION_CONTEXT.get('pending_power_action')
        return bool(pending and time.time() <= pending['expires_at'])


def _handle_power_request(text: str, source: str, command_id: str) -> Optional[dict]:
    with _CONTEXT_LOCK:
        pending = _CONVERSATION_CONTEXT.get('pending_power_action')
        _CONVERSATION_CONTEXT['pending_power_action'] = None
    answer = _power_confirmation_kind(text)
    affirmative, negative = answer == 'yes', answer == 'no'
    if pending and time.time() <= pending['expires_at']:
        if negative:
            return {'success': True, 'verified': True, 'status': 'POWER_CANCELLED',
                    'confirmation_id': pending.get('confirmation_id'),
                    'action': 'power_control_cancel', 'message': 'Theek hai, power request cancel kar di.',
                    'source': source, 'command_id': command_id}
        if affirmative:
            action = pending['action']
            if pending['target_device'] == 'pc':
                from actions.windows_system_controller import execute_system_capability
                result = execute_system_capability(action, {'confirmed': True})
            else:
                from actions.mobile_pc_gateway import handle_mobile_gateway_command
                result = handle_mobile_gateway_command('android', action, {})
            success = result.get('success') is True
            verified = success and result.get('verified') is True
            return {'success': success, 'verified': verified, 'action': f'power_{action}',
                    'confirmation_id': pending.get('confirmation_id'),
                    'status': result.get('status') or ('POWER_REQUEST_ACCEPTED' if success else 'POWER_FAILED'),
                    'message': result.get('message') or result.get('stdout') or result.get('stderr') or 'Power request execute nahi hui.',
                    'data': result, 'source': source, 'command_id': command_id}
    elif pending and affirmative:
        return {'success': False, 'verified': False, 'status': 'CONFIRMATION_EXPIRED',
                'confirmation_id': pending.get('confirmation_id'),
                'message': 'Confirmation expire ho gayi. Shutdown/restart ka command dobara do.',
                'source': source, 'command_id': command_id}
    request = _parse_power_request(text)
    if request:
        with _CONTEXT_LOCK:
            _CONVERSATION_CONTEXT['pending_power_action'] = {**request, 'expires_at': time.time() + 30, 'confirmation_id': command_id}
            _CONVERSATION_CONTEXT['pending_send_details'] = None
        device = 'laptop' if request['target_device'] == 'pc' else 'phone'
        return {'success': True, 'verified': False, 'requires_confirmation': True,
                'confirmation_id': command_id,
                'status': 'CONFIRMATION_REQUIRED', 'action': 'power_confirmation_prompt',
                'message': f"{device.title()} {request['action']} karna hai? Unsaved kaam save kar lo; 30 seconds mein 'haan' ya 'cancel' bolo/likho.",
                'source': source, 'command_id': command_id}
    return None


def _remember_sequence_confirmation(result):
    if result.get('requires_confirmation') and result.get('confirmation_id'):
        with _CONTEXT_LOCK:
            _CONVERSATION_CONTEXT['pending_sequence'] = {
                'confirmation_id': result['confirmation_id'], 'expires_at': time.time() + 30,
                'remaining_commands': list(result.get('remaining_commands', [])),
                'steps': copy.deepcopy(result.get('steps', []))}


def _resume_confirmed_sequence(result, source, progress):
    with _CONTEXT_LOCK:
        pending = _CONVERSATION_CONTEXT.get('pending_sequence')
        _CONVERSATION_CONTEXT['pending_sequence'] = None
    if not pending or result.get('confirmation_id') != pending['confirmation_id']:
        return result
    if (time.time() > pending['expires_at'] or result.get('status') in {'POWER_CANCELLED', 'CONFIRMATION_EXPIRED'}
            or not result.get('success') or not result.get('verified')):
        if pending['remaining_commands']:
            return {**result, 'remaining_commands': pending['remaining_commands'],
                    'message': str(result.get('message', '')) + '\nBaaki steps nahi chale; confirmation ka verified successful result zaroori hai.'}
        return result
    previous = pending['steps']
    if previous:
        previous[-1]['result'] = result
    from core.command_sequence import run_sequence_steps
    resumed = run_sequence_steps(pending['remaining_commands'], source, process_user_command, progress, previous=previous)
    _remember_sequence_confirmation(resumed)
    return resumed


def process_user_command(text: str, source: str = "voice", stream_callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """
    Unified entry point for both VOICE speech input and TYPED CHAT input.
    Guarantees 100% feature parity between voice and chat interfaces.

    Pipeline:
    1. Input normalization & pending conversation prompt check
    2. Intent Classification (core/intent_router.py)
    3. Context Resolution (Conversational follow-ups)
    4. App & Entity Resolution (actions/app_registry.py)
    5. Native vs Web Disambiguation Check
    6. Security Authorization (core/security.py)
    7. Tool Execution & State Machine Verification
    8. Truthful Response Generation
    """
    # File paths are data and must never enter the multi-action parser.
    if text.startswith('[FILE_UPLOADED] '):
        from core.study_documents import handle_attachment_command
        return {**handle_attachment_command(text), 'source': source}
    raw_text = normalize_command_prefix(text)
    if not raw_text:
        return {
            "success": False,
            "message": "Empty command provided.",
            "source": source,
            "status": "EMPTY_INPUT"
        }

    # Ensure tool registry is populated (check once, not every command)
    global _tools_initialized
    if not _tools_initialized:
        if not default_tool_registry.list_tools():
            try:
                from core.register_tools import initialize_all_tools
                initialize_all_tools()
            except Exception:
                pass
        # Mark initialized even if empty — prevents repeated failed attempts
        if default_tool_registry.list_tools():
            _tools_initialized = True

    logger.info(f"[Pipeline] Processing command from [{source.upper()}]: '{raw_text}'")
    lower_text = raw_text.lower()
    command_id = _next_command_id()
    logger.info(f"[{command_id}] INPUT: '{raw_text}' [source={source}]")
    execution_metrics = {
        "stt": 1,
        "normalization": 1,
        "intent": 1,
        "context": 0,
        "tool": 1,
        "llm": 0,
        "response": 1,
        "tts": 1,
        "command_id": command_id
    }

    from core.command_sequence import execute_sequence
    # Any new request invalidates a prior approval; only exact yes/no can resolve it.
    if _power_confirmation_kind(raw_text) is None:
        with _CONTEXT_LOCK:
            _CONVERSATION_CONTEXT['pending_sequence'] = None
            _CONVERSATION_CONTEXT['pending_power_action'] = None
    sequence_result = execute_sequence(raw_text, source, process_user_command, progress=stream_callback)
    if sequence_result is not None:
        _remember_sequence_confirmation(sequence_result)
        return {**sequence_result, 'source': source, 'command_id': command_id}
    from core.memory_commands import handle_memory_command
    memory_result = handle_memory_command(raw_text)
    if memory_result is not None:
        return {**memory_result, 'source': source, 'command_id': command_id}
    power_result = _handle_power_request(raw_text, source, command_id)
    if power_result is not None:
        return _resume_confirmed_sequence(power_result, source, stream_callback)
    from core.conversation_style import handle_banter_command
    banter_result = handle_banter_command(raw_text)
    if banter_result is not None:
        return {**banter_result, 'source': source, 'command_id': command_id}
    from agent.daily_planner import get_daily_planner
    planner_reply = get_daily_planner().handle_command(raw_text, intent=classify_intent(raw_text).get('intent', 'OTHER'))
    if planner_reply:
        return {**planner_reply, 'source': source, 'command_id': command_id}
    if classify_intent(raw_text).get('intent') == 'DRAFT_TEXT':
        from core.ai_multitier_engine import get_ai_engine
        from core.conversation_style import get_conversation_style
        with _CONTEXT_LOCK:
            _CONVERSATION_CONTEXT['pending_send_details'] = None
        result = get_ai_engine().generate_response(raw_text, system_override=get_conversation_style(for_draft=True),
                                                   response_tokens=1200)
        return {'success': bool(result.get('success') and result.get('text')), 'verified': bool(result.get('success') and result.get('text')),
                'action': 'draft_text', 'status': 'DRAFT_READY' if result.get('success') else 'DRAFT_FAILED',
                'message': result.get('text') or 'Draft nahi ban paya; dobara try karo.',
                'source': source, 'command_id': command_id, 'draft_only': True}

    # -------------------------------------------------------------
    # Voice and chat share verified short-term recipient context.
    communication_command, context_error = _resolve_social_follow_up(raw_text)
    if context_error:
        return {**context_error, "source": source, "command_id": command_id}
    communication_command, detail_error = _collect_send_details(raw_text, communication_command)
    if detail_error:
        return {**detail_error, 'source': source, 'command_id': command_id}
    lower_text = raw_text.lower()
    # Explicit social actions must not be intercepted by WhatsApp's generic verbs.
    social_command = communication_command if communication_command and communication_command["platform"] in ("discord", "instagram") else None
    if social_command:
        res = default_tool_registry.execute_tool("social_chat", social_command)
        _remember_social_target(social_command, res.success, res.verification.get("verified", False))
        _update_execution_context(command_id, raw_text, social_command.get("recipient", ""), "social_chat", "SUCCESS" if res.success else "FAILED", "" if res.success else res.message)
        return {"success": res.success, "verified": res.verification.get("verified", False),
                "message": res.message, "data": res.data, "source": source,
                "action": "social_chat", "command_id": command_id}

    whatsapp_command = communication_command if communication_command and communication_command["platform"] == "whatsapp" else None
    if whatsapp_command and whatsapp_command["platform"] == "whatsapp" and whatsapp_command["action"] in ("send", "read", "open_chat", "call", "answer", "end_call"):
        from actions.windows_whatsapp_desktop_executor import set_whatsapp_user_action_requested
        set_whatsapp_user_action_requested(True)
        if whatsapp_command["action"] in ("call", "answer", "end_call"):
            from actions.whatsapp import whatsapp
            call_action = "video_call" if whatsapp_command.get("call_type") == "video" else "call"
            if whatsapp_command["action"] != "call":
                call_action = whatsapp_command["action"]
            result = whatsapp(action=call_action, contact=whatsapp_command.get("recipient", ""), confirm_call=True)
            _remember_social_target(whatsapp_command, result.get("success", False), result.get("verified", False))
            return {**result, "source": source, "command_id": command_id}
        tool = "whatsapp_send_message" if whatsapp_command["action"] == "send" else "whatsapp_read_messages"
        if whatsapp_command["action"] == "open_chat":
            tool = "whatsapp_open_chat"
        parameters = {"contact": whatsapp_command.get("recipient", "")}
        if whatsapp_command["action"] == "send":
            parameters["message"] = whatsapp_command.get("message_text", "")
            parameters["force_send"] = True  # Explicit send command with an exact recipient and payload.
        res = default_tool_registry.execute_tool(tool, parameters)
        _remember_social_target(whatsapp_command, res.success, res.verification.get("verified", False))
        with _CONTEXT_LOCK:
            _CONVERSATION_CONTEXT["last_app"] = "whatsapp"
            _CONVERSATION_CONTEXT["last_platform"] = "whatsapp"
            if parameters["contact"]:
                _CONVERSATION_CONTEXT["last_contact"] = parameters["contact"]
        return {"success": res.success, "verified": res.verification.get("verified", False),
                "message": res.message, "data": res.data, "source": source,
                "action": tool, "command_id": command_id}

    # Attachment follow-ups retain one shared document across voice and chat.
    # Explicit social sends above take priority so message payloads are never analyzed.
    from core.study_documents import handle_attachment_command
    study_result = handle_attachment_command(raw_text)
    if study_result is not None:
        return {**study_result, 'source': source, 'command_id': command_id}

    # INSTANT BARGE-IN & MIC CONTROL INTERCEPTION (<0.1 ms HOT PATH)
    # -------------------------------------------------------------
    pure_barge_in = ["stop", "stop speaking", "chup", "bas", "shut up", "barge in", "cancel", "quiet", "silence", "shh", "ruko"]
    if lower_text.strip(" .!?,") in pure_barge_in:
        try:
            from core.tts_engine import get_tts_engine
            get_tts_engine().barge_in_stop()
        except Exception:
            pass
        return {
            "success": True,
            "message": "Stopped.",
            "barge_in": True,
            "source": source,
            "command_id": command_id
        }

    mic_ctrl_words = ["mic off", "mic on", "stop listening", "start listening", "mute mic", "unmute mic", "jarvis mute", "jarvis unmute"]
    if any(w in lower_text for w in mic_ctrl_words):
        from actions.mic_control import handle_mic_command
        mic_res = handle_mic_command(raw_text)
        mic_res["source"] = source
        mic_res["command_id"] = command_id
        return mic_res

    # -------------------------------------------------------------
    # CONTEXTUAL FOLLOW-UP DETECTION (frustration, retry, close previous)
    # -------------------------------------------------------------
    followup = _detect_follow_up_intent(lower_text)
    if followup:
        fu_type = followup.get("type")
        if fu_type == "frustration_followup":
            logger.info(f"[{command_id}] FOLLOW-UP: frustration/failure reference -> {followup.get('last_target')}")
            return {
                "success": True,
                "action": "followup_frustration",
                "message": followup["message"],
                "source": source,
                "verified": True,
                "status": "FOLLOWUP",
                "command_id": command_id,
            }
        elif fu_type == "retry":
            # Re-execute the last action
            retry_target = followup["target"]
            retry_action = followup["action"]
            logger.info(f"[{command_id}] FOLLOW-UP: retry -> action={retry_action}, target={retry_target}")
            if retry_action in ["open_app", "WINDOWS_APPLICATION", "OPEN_APPLICATION"]:
                raw_text = f"open {retry_target}"
                lower_text = raw_text.lower()
                # Fall through to normal processing with rewritten command
            else:
                raw_text = f"{retry_action} {retry_target}"
                lower_text = raw_text.lower()
        elif fu_type == "close_previous":
            close_target = followup["target"]
            logger.info(f"[{command_id}] FOLLOW-UP: close previous -> {close_target}")
            raw_text = f"close {close_target}"
            lower_text = raw_text.lower()


    # Reset WhatsApp action runtime gate by default (lazy import)
    is_wa = any(w in lower_text for w in ["whatsapp", "whats app", "wa pe", "wa message", "wa call"])
    if is_wa:
        from actions.windows_whatsapp_desktop_executor import set_whatsapp_user_action_requested
        set_whatsapp_user_action_requested(True)
    else:
        try:
            from actions.windows_whatsapp_desktop_executor import set_whatsapp_user_action_requested
            set_whatsapp_user_action_requested(False)
        except ImportError:
            pass  # WhatsApp executor not loaded yet — no action needed

    # -------------------------------------------------------------
    # WHATSAPP EXPLICIT CLOSE INTERCEPTION
    # -------------------------------------------------------------
    if any(k in lower_text for k in ["whatsapp band karo", "whatsapp close karo", "close whatsapp", "whatsapp band"]):
        from actions.windows_whatsapp_desktop_executor import set_whatsapp_user_action_requested, windows_whatsapp_desktop_executor
        set_whatsapp_user_action_requested(True)
        res = windows_whatsapp_desktop_executor.close_whatsapp()
        return {
            "success": res[0],
            "action": "whatsapp_close",
            "message": res[1],
            "source": source,
            "verified": True,
            "execution_target": "WINDOWS_INSTALLED_WHATSAPP_DESKTOP"
        }
    # Screen vision conversational follow-up ("Haan", "Theek hai", "Kar do", "Root cause")
    if _CONVERSATION_CONTEXT.get("pending_screen_context"):
        with _CONTEXT_LOCK:
            pending_scr = _CONVERSATION_CONTEXT.get("pending_screen_context")
        if pending_scr:
            scr_time = pending_scr.get("time", 0)
            if time.time() - scr_time > 20.0:
                with _CONTEXT_LOCK:
                    _CONVERSATION_CONTEXT["pending_screen_context"] = None
            else:
                words_set = set(lower_text.split())
                is_screen_followup = (
                    any(w in words_set for w in ["haan", "yes", "sure", "fix", "inspect", "kar", "karo"]) or
                    any(phrase in lower_text for phrase in ["theek hai", "kar do", "do it", "root cause"])
                )
                is_new_command = any(k in lower_text for k in ["time", "weather", "assignment", "submit", "project", "open ", "launch ", "close ", "delete ", "task", "calculate"])
                if is_screen_followup and not is_new_command:
                    act_win = pending_scr.get("active_window", "")
                    with _CONTEXT_LOCK:
                        _CONVERSATION_CONTEXT["pending_screen_context"] = None
                    msg = f"Theek hai Boss, {act_win} ke context mein action inspect kar raha hoon." if act_win else "Theek hai Boss, screen context par action inspect kar raha hoon."
                    return {
                        "success": True,
                        "action": "screen_followup_acknowledged",
                        "message": msg,
                        "source": source,
                        "verified": True,
                        "status": "COMPLETED"
                    }

    # Handle un-bound "Haan" without pending confirmation
    if lower_text in ["haan", "yes", "confirm", "kar do", "do it"] and not any(_CONVERSATION_CONTEXT.values()):
        return {
            "success": True,
            "action": "unbound_affirmation",
            "message": "Boss, koi pending request confirmation nahi hai.",
            "source": source,
            "verified": True,
            "status": "NO_OP"
        }

    if _CONVERSATION_CONTEXT.get("pending_important_message"):
        with _CONTEXT_LOCK:
            pending_msg = _CONVERSATION_CONTEXT.get("pending_important_message")
            _CONVERSATION_CONTEXT["pending_important_message"] = None
        if pending_msg:
            if any(w in lower_text for w in ["nahi", "no", "mat", "dont", "don't", "stop", "cancel", "reject"]):
                return {
                    "success": True,
                    "action": "read_important_message",
                    "message": "Theek hai Boss, message nahi padh raha hoon.",
                    "source": source,
                    "verified": True,
                    "status": "READ_ALOUD_REJECTED"
                }
            else:
                res_text = f"{pending_msg['contact']} ka message hai: '{pending_msg['message']}'"
                return {
                    "success": True,
                    "action": "read_important_message",
                    "message": res_text,
                    "source": source,
                    "verified": True,
                    "status": "MESSAGE_READ_ALOUD"
                }

    if _CONVERSATION_CONTEXT.get("pending_disambiguation"):
        with _CONTEXT_LOCK:
            pending_app = _CONVERSATION_CONTEXT.get("pending_disambiguation")
            _CONVERSATION_CONTEXT["pending_disambiguation"] = None
        if pending_app:
            target_app = pending_app["app"]

            if any(w in lower_text for w in ["desktop", "app", "native", "software"]):
                res = default_tool_registry.execute_tool("open_app", {"app_name": f"{target_app} app"})
                return {
                    "success": True,
                    "action": "open_app",
                    "message": f"Opened native {target_app.title()} Desktop app.",
                    "source": source,
                    "verified": True,
                    "status": "NATIVE_APP_LAUNCHED"
                }
            elif any(w in lower_text for w in ["web", "browser", "chrome", "edge", "site"]):
                res = default_tool_registry.execute_tool("open_app", {"app_name": f"{target_app} web"})
                return {
                    "success": True,
                    "action": "open_app",
                    "message": f"Opened {target_app.title()} Web in browser.",
                    "source": source,
                    "verified": True,
                    "status": "WEB_APP_LAUNCHED"
                }

    # STEP 2: CONTEXTUAL FOLLOW-UP PRONOUN RESOLUTION ("usko", "usse", "wahi", "isko")
    # -------------------------------------------------------------
    pronoun_words = ["usko", "usse", "wahi", "isey", "isko", "same person", "same contact", "same app"]
    if any(w in lower_text for w in pronoun_words):
        last_a = _CONVERSATION_CONTEXT.get("last_app")

        if last_a and any(p in lower_text for p in ["isko", "isey", "same app"]):
            for p in ["isko", "isey", "same app"]:
                if p in lower_text:
                    raw_text = re.sub(rf"\b{p}\b", last_a, raw_text, flags=re.IGNORECASE)
            lower_text = raw_text.lower()
            logger.info(f"[Pipeline] Resolved app pronoun locally -> '{raw_text}' (app: '{last_a}')")

    # -------------------------------------------------------------
    # WHATSAPP INSTALLED DESKTOP CALL CONTROL INTERCEPTION
    # -------------------------------------------------------------
    if "whatsapp" in lower_text or any(k in lower_text for k in ["call receive", "call utha", "answer call", "answer the call", "pick up call", "receive karo", "call reject", "call cut", "call kaat", "call laga", "call kar", "video call"]):
        from actions.windows_whatsapp_desktop_executor import windows_whatsapp_desktop_executor, resolve_contact_ambiguity, set_whatsapp_user_action_requested
        set_whatsapp_user_action_requested(True)

        # 1. Answer Call
        if any(k in lower_text for k in ["call receive", "call utha", "answer call", "answer the call", "pick up call", "receive karo"]):
            res = windows_whatsapp_desktop_executor.execute_answer_call()
            return {"success": res["success"], "action": "whatsapp_answer_call", "message": res["message"], "source": source, "verified": res.get("verified", False), "execution_target": res.get("execution_target")}

        # 2. Decline Call
        elif any(k in lower_text for k in ["call reject", "call decline", "reject karo"]):
            res = windows_whatsapp_desktop_executor.execute_decline_call()
            return {"success": res["success"], "action": "whatsapp_decline_call", "message": res["message"], "source": source, "verified": res.get("verified", False), "execution_target": res.get("execution_target")}

        # 3. End Active Call
        elif any(k in lower_text for k in ["call kaat", "call end", "call disconnect", "whatsapp call end"]):
            res = windows_whatsapp_desktop_executor.execute_end_call()
            return {"success": res["success"], "action": "whatsapp_end_call", "message": res["message"], "source": source, "verified": res.get("verified", False), "execution_target": res.get("execution_target")}

        # 4. Outgoing Call (Voice or Video)
        call_patterns = [
            (r"^(?:ab\s+|bhai\s+|jarvis\s+)?([a-zA-Z0-9_\s]+?)\s+ko\s+(?:whatsapp\s+)?video\s+call\s+(?:laga|kar|karo|lagao)\s*$", "video"),
            (r"^(?:ab\s+|bhai\s+|jarvis\s+)?([a-zA-Z0-9_\s]+?)\s+ko\s+(?:whatsapp\s+)?(?:voice\s+)?call\s+(?:laga|kar|karo|lagao)\s*$", "voice"),
            (r"\bwhatsapp\s+(?:pe\s+)?video\s+call\s+(?:karo|laga)\s+([a-zA-Z0-9_\s]+)\s*$", "video"),
            (r"\bwhatsapp\s+(?:pe\s+)?call\s+(?:karo|laga)\s+([a-zA-Z0-9_\s]+)\s*$", "voice"),
        ]
        for cpat, ctype in call_patterns:
            cm = re.search(cpat, lower_text, re.IGNORECASE)
            if cm:
                contact_raw = cm.group(1).strip()
                contact_raw = re.sub(r"^(?:ab|bhai|jarvis|please|zara|aur|fir|phir)\s+", "", contact_raw, flags=re.IGNORECASE).strip()

                # Check ambiguity
                amb_check = resolve_contact_ambiguity(contact_raw)
                if amb_check.get("status") == "AMBIGUOUS_CONTACT":
                    return {
                        "success": False,
                        "action": f"whatsapp_{ctype}_call",
                        "message": amb_check["message"],
                        "matches": amb_check.get("matches", []),
                        "requires_clarification": True,
                        "source": source,
                        "verified": False,
                        "command_id": command_id
                    }
                target_contact = amb_check.get("contact", contact_raw)

                if ctype == "video":
                    res = windows_whatsapp_desktop_executor.execute_video_call(recipient=target_contact)
                else:
                    res = windows_whatsapp_desktop_executor.execute_voice_call(recipient=target_contact)

                with _CONTEXT_LOCK:
                    _CONVERSATION_CONTEXT["last_contact"] = target_contact
                    _CONVERSATION_CONTEXT["last_app"] = "whatsapp"
                    _CONVERSATION_CONTEXT["last_action"] = f"whatsapp_{ctype}_call"

                _log_command_telemetry(
                    command_id=command_id,
                    wake_word="Jarvis" if "jarvis" in raw_text.lower() else "None (Direct)",
                    raw_transcript=raw_text,
                    normalized_transcript=f"WhatsApp {ctype} call {target_contact}",
                    intent=f"WHATSAPP_{ctype.upper()}_CALL",
                    tool=f"whatsapp_{ctype}_call",
                    arguments={"contact": target_contact},
                    execution_result="SUCCESS" if res.get("success") else "FAILED",
                    verification_result=res.get("verified", False),
                    final_response=res.get("message", ""),
                    target_app="WHATSAPP_DESKTOP",
                    target_contact=target_contact
                )

                return {
                    "success": res.get("success", False),
                    "action": f"whatsapp_{ctype}_call",
                    "recipient": target_contact,
                    "message": res.get("message", ""),
                    "call_state": res.get("call_state"),
                    "source": source,
                    "verified": res.get("verified", False),
                    "execution_target": res.get("execution_target", "WINDOWS_INSTALLED_WHATSAPP_DESKTOP"),
                    "command_id": command_id
                }

    # -------------------------------------------------------------
    # WHATSAPP MESSAGE & MULTI-STEP DIRECT HANDLING (Desktop-First, Auto-Send)
    # -------------------------------------------------------------
    is_wa_multistep = bool(re.search(r"\b(?:whatsapp\s+(?:kholo|open\s*kar|chala)|open\s+whatsapp)\b\s+(?:aur|and|then)\s+", lower_text, re.IGNORECASE))
    clean_wa_text = re.sub(r"\b(?:whatsapp\s+(?:kholo|open\s*kar|chala)|open\s+whatsapp)\b\s+(?:aur|and|then)\s+", "", raw_text, flags=re.IGNORECASE).strip() if is_wa_multistep else raw_text

    _wa_msg_patterns = [
        r"^(?:ab\s+|fir\s+|phir\s+|bhai\s+|jarvis\s+)?([a-zA-Z0-9_\s]+?)\s+ko\s+(.+?)\s+(?:bhej|bhejo|bhej\s*de|send\s+kar|send\s+karo)\s*$",
        r"^(?:ab\s+|fir\s+|phir\s+|bhai\s+|jarvis\s+)?([a-zA-Z0-9_\s]+?)\s+ko\s+(?:bol|bolo|bol\s*de|bolna)\s+(.+)$",
        r"^(?:ab\s+|fir\s+|phir\s+|bhai\s+|jarvis\s+)?([a-zA-Z0-9_\s]+?)\s+ko\s+(?:message|msg)\s+(?:kar|karo|bhej|bhejo)\s+(.+)$",
        r"^(?:ab\s+|fir\s+|phir\s+|bhai\s+|jarvis\s+)?([a-zA-Z0-9_\s]+?)\s+ko\s+(?:message|msg)\s+(?:kar|karo|kar\s*do)\s*$",
        r"^(?:ab\s+|fir\s+|phir\s+|bhai\s+|jarvis\s+)?([a-zA-Z0-9_\s]+?)\s+ko\s+ping\s+(?:kar|karo)\s*$",
        r"^(?:ab\s+|fir\s+|phir\s+|bhai\s+|jarvis\s+)?(?:usko|usse)\s+(?:bol|bolo|bol\s*de)\s+(.+)$",
    ]
    _wa_msg_match = None
    _matched_pat = None
    for _pat in _wa_msg_patterns:
        _wa_msg_match = re.search(_pat, clean_wa_text, re.IGNORECASE)
        if _wa_msg_match:
            _matched_pat = _pat
            break

    if _wa_msg_match and any(w in clean_wa_text.lower() for w in ["bhej", "bhejo", "bol", "bolo", "message", "msg", "send", "ping"]):
        from actions.windows_whatsapp_desktop_executor import (
            windows_whatsapp_desktop_executor,
            resolve_contact_ambiguity,
            set_whatsapp_user_action_requested,
        )
        set_whatsapp_user_action_requested(True)

        # Multi-Step Requirement: Step 1: Open/focus Desktop WhatsApp
        if is_wa_multistep:
            logger.info(f"[{command_id}] Multi-step execution: Step 1: Opening/verifying WhatsApp Desktop")
            desk_ok, desk_msg = windows_whatsapp_desktop_executor.focus_installed_whatsapp_desktop()
            if not desk_ok:
                logger.error(f"[{command_id}] Multi-step failed at Step 1: {desk_msg}")
                return {
                    "success": False,
                    "action": "whatsapp_multistep",
                    "message": f"WhatsApp Desktop open nahi ho paya: {desk_msg}. Message nahi bheja gaya.",
                    "source": source,
                    "verified": False,
                    "execution_target": "WINDOWS_INSTALLED_WHATSAPP_DESKTOP",
                    "command_id": command_id
                }

        # Parse contact and message from the match
        if "usko" in _matched_pat:
            contact_raw = _CONVERSATION_CONTEXT.get("last_contact") or ""
            msg_body = _wa_msg_match.group(1).strip()
        else:
            contact_raw = _wa_msg_match.group(1).strip()
            try:
                msg_body = _wa_msg_match.group(2).strip()
            except (IndexError, AttributeError):
                msg_body = ""

        # Strip conversational fillers from contact
        contact_raw = re.sub(r"^(?:ab|bhai|jarvis|please|zara|aur|fir|phir)\s+", "", contact_raw, flags=re.IGNORECASE).strip()

        # Strip action verbs from message body
        for verb in ["bhej", "bhejo", "bhej de", "send kar", "send karo", "bol", "bolo", "bol de", "bolna", "message kar", "msg kar", "ping kar"]:
            if msg_body.lower().endswith(verb):
                msg_body = msg_body[:-(len(verb))].strip()

        # Resolve contact via unified config-based resolver
        contact_res = resolve_contact_ambiguity(contact_raw)
        if contact_res.get("status") == "AMBIGUOUS_CONTACT":
            return {
                "success": False,
                "action": "whatsapp_send",
                "message": contact_res["message"],
                "matches": contact_res.get("matches", []),
                "requires_clarification": True,
                "source": source,
                "verified": False,
                "command_id": command_id,
            }

        resolved_contact = contact_res.get("contact", contact_raw)

        # Security validation
        auth_ok, auth_reason = default_security_manager.validate_and_authorize(
            "whatsapp_send_message", {"contact": resolved_contact, "message": msg_body, "force_send": True}
        )
        if not auth_ok:
            return {"success": False, "message": auth_reason, "source": source, "status": "SECURITY_BLOCKED", "command_id": command_id}

        if msg_body:
            # Direct send via desktop executor
            res = windows_whatsapp_desktop_executor.execute_send_message(
                recipient=resolved_contact, message=msg_body
            )
        else:
            res = {"success": False, "message": "Kya message bhejna hai?", "verified": False,
                   "status": "MESSAGE_REQUIRED", "execution_target": "WINDOWS_INSTALLED_WHATSAPP_DESKTOP"}

        # Rule 13: if send verification fails, do NOT claim success
        send_verified = res.get("verified", False)
        is_success = res.get("success", False) and send_verified

        # Update conversation context with last contact
        with _CONTEXT_LOCK:
            _CONVERSATION_CONTEXT["last_contact"] = resolved_contact
            _CONVERSATION_CONTEXT["last_app"] = "whatsapp"
            _CONVERSATION_CONTEXT["last_action"] = "whatsapp_send_message"
            _CONVERSATION_CONTEXT["last_platform"] = "whatsapp"

        _update_execution_context(
            command_id, raw_text, resolved_contact, "whatsapp_send_message",
            "SUCCESS" if is_success else "FAILED",
            "" if is_success else res.get("message", "")
        )

        _log_command_telemetry(
            command_id=command_id,
            wake_word="Jarvis" if "jarvis" in raw_text.lower() else "None (Direct)",
            raw_transcript=raw_text,
            normalized_transcript=f"WhatsApp message to {resolved_contact}: {msg_body}",
            intent="WHATSAPP_MESSAGE",
            tool="whatsapp_send_message",
            arguments={"contact": resolved_contact, "message": msg_body},
            execution_result="SUCCESS" if is_success else "FAILED",
            verification_result=send_verified,
            final_response=res.get("message", ""),
            target_app="WHATSAPP_DESKTOP",
            target_contact=resolved_contact
        )

        return {
            "success": is_success,
            "action": "whatsapp_send",
            "recipient": resolved_contact,
            "message": res.get("message", ""),
            "source": source,
            "verified": send_verified,
            "execution_target": res.get("execution_target", "WINDOWS_INSTALLED_WHATSAPP_DESKTOP"),
            "command_id": command_id,
        }

    classification = classify_intent(raw_text)
    intent = classification.get("intent", "OTHER")

    # Contextual follow-up overrides (e.g. "Connect karo", "General channel kholo", "Mute karo")
    if intent == "OTHER" and _CONVERSATION_CONTEXT.get("last_app") == "discord":
        if any(w in lower_text for w in ["connect", "join voice", "vc join"]):
            classification = {"intent": "DISCORD_CONNECT", "query": raw_text, "tool": "discord_connect_voice"}
        elif any(w in lower_text for w in ["disconnect", "leave voice", "vc leave"]):
            classification = {"intent": "DISCORD_DISCONNECT", "query": raw_text, "tool": "discord_disconnect_voice"}
        elif any(w in lower_text for w in ["mute", "unmute"]):
            classification = {"intent": "DISCORD_MUTE", "query": raw_text, "tool": "discord_mute"}
        elif "channel" in lower_text or "general" in lower_text:
            classification = {"intent": "DISCORD_CHANNEL", "query": raw_text, "tool": "discord_navigate_channel"}

    # -------------------------------------------------------------
    # STEP 3: SCOPED MIC CONTROL & INSTANT BARGE-IN HANDLING
    # -------------------------------------------------------------
    pure_barge_in = ["stop", "stop speaking", "chup", "bas", "shut up", "barge in", "cancel", "quiet", "silence", "shh", "ruko"]
    if lower_text in pure_barge_in or intent in ["CANCEL", "STOP"]:
        try:
            from core.tts_engine import get_tts_engine
            get_tts_engine().barge_in_stop()
        except Exception:
            pass
        return {
            "success": True,
            "message": "Stopped.",
            "barge_in": True,
            "source": source
        }

    mic_keywords = ["mic", "microphone", "listening", "stop listening", "start listening", "jarvis mute", "jarvis unmute", "band karo mic", "mic band", "mic chalu"]
    if intent == "MIC_CONTROL" or any(w in lower_text for w in mic_keywords):
        from actions.mic_control import handle_mic_command
        mic_res = handle_mic_command(raw_text)
        mic_res["source"] = source
        return mic_res

    logger.info(f"[PIPELINE] Processing command: '{raw_text}' [source={source}]")
    logger.info(f"[INTENT] Intent classified: {intent} | details={classification}")

    # -------------------------------------------------------------
    # STEP 3.4: CURRENT TIME & DATE INTENT DISPATCH
    # -------------------------------------------------------------
    if intent == "CURRENT_TIME":
        import datetime
        now = datetime.datetime.now()
        time_str = now.strftime("%I:%M %p").lstrip("0")
        date_str = now.strftime("%A, %B %d, %Y")
        if any(k in lower_text for k in ["date", "din", "day", "tarikh", "aaj"]):
            msg = f"Sir, today is {date_str}, and the current time is {time_str}."
        else:
            msg = f"Sir, the current time is {time_str}."
        logger.info(f"[CURRENT_TIME] Result: {msg}")
        return {
            "success": True,
            "action": "current_time",
            "intent": "CURRENT_TIME",
            "message": msg,
            "source": source,
            "verified": True,
            "status": "COMPLETED",
            "execution_metrics": execution_metrics
        }

    # -------------------------------------------------------------
    # STEP 3.5: COMPUTATIONAL INTENT DISPATCH (SAFE AST EVALUATOR)
    # -------------------------------------------------------------
    if intent == "COMPUTATION":
        from core.safe_calculator import calculate
        calc_res = calculate(raw_text)
        is_ok = bool(calc_res.get("success"))
        msg = calc_res.get("message", f"The answer is {calc_res.get('result')}.")
        logger.info(f"[COMPUTATION] Result: {calc_res.get('result')} | Expr: {calc_res.get('expression')}")
        return {
            "success": is_ok,
            "action": "computation",
            "intent": "COMPUTATION",
            "message": msg,
            "data": calc_res,
            "source": source,
            "verified": is_ok,
            "status": "COMPLETED" if is_ok else "CALCULATION_FAILED",
            "execution_metrics": execution_metrics
        }

    # -------------------------------------------------------------
    # STEP 3.6: SCREEN OBSERVATION & VISION ANALYSIS DISPATCH
    # -------------------------------------------------------------
    if intent == "SCREEN_ANALYSIS":
        from actions.screen_processor import analyze_screen_vision, is_screen_cache_valid
        angle = classification.get("angle", "screen")

        vision_res = analyze_screen_vision(user_query=raw_text, angle=angle)
        is_ok = bool(vision_res.get("success"))
        msg = vision_res.get("message", "Screen analysis completed.")
        _CONVERSATION_CONTEXT["pending_screen_context"] = {
            "active_window": vision_res.get("active_window", ""),
            "observation": vision_res.get("observation", msg),
            "time": time.time()
        } if is_ok else None
        logger.info(f"[SCREEN_ANALYSIS] Result: {msg[:100]}...")
        return {
            "success": is_ok,
            "action": "screen_process",
            "intent": "SCREEN_ANALYSIS",
            "message": msg,
            "spoken_message": vision_res.get('spoken_message', msg),
            "authoritative_response": True,
            "data": vision_res,
            "source": source,
            "verified": is_ok,
            "status": "COMPLETED" if is_ok else "VISION_FAILED",
            "execution_metrics": execution_metrics
        }

    # -------------------------------------------------------------
    # STEP 3.7: COMPLEX MULTI-STEP PLANNER DISPATCH (Phase 4A & 4H)
    # -------------------------------------------------------------
    if intent == "COMPLEX_PLANNER":
        # Immediate natural acknowledgement for multi-step tasks (>1.5s)
        from agent.task_planner import default_task_planner
        plan = default_task_planner.create_plan(raw_text)
        executed_plan = default_task_planner.execute_plan(plan, auto_confirm_medium=True)
        is_ok = (executed_plan.status == "COMPLETED")
        msg = executed_plan.summary or executed_plan.error or "Multi-step plan execution finished."
        logger.info(f"[COMPLEX_PLANNER] Plan '{executed_plan.plan_id}' status: {executed_plan.status}")
        return {
            "success": is_ok,
            "action": "task_planner",
            "intent": "COMPLEX_PLANNER",
            "message": msg,
            "data": executed_plan.to_dict(),
            "source": source,
            "verified": is_ok,
            "status": executed_plan.status,
            "execution_metrics": execution_metrics
        }

    # -------------------------------------------------------------
    # STEP 3.8: SELF-DIAGNOSTICS & SYSTEM TELEMETRY (Phase 4G & 4H)
    # -------------------------------------------------------------
    if intent == "DIAGNOSTICS":
        from core.diagnostics import default_diagnostics
        diag_msg = default_diagnostics.handle_diagnostic_query(raw_text) or "All subsystems operating normally."
        logger.info(f"[DIAGNOSTICS] Report: {diag_msg[:100]}...")
        return {
            "success": True,
            "action": "diagnostics",
            "intent": "DIAGNOSTICS",
            "message": diag_msg,
            "source": source,
            "verified": True,
            "status": "COMPLETED",
            "execution_metrics": execution_metrics
        }

    # -------------------------------------------------------------
    # STEP 3.9: UNIFIED TASK MANAGER DISPATCH (Phase 4E & 4H)
    # -------------------------------------------------------------
    if intent == "TASK_MANAGER":
        from agent.task_manager import default_task_manager
        tm_msg = default_task_manager.handle_natural_command(classification.get('query', raw_text))
        if not tm_msg:
            return {'success': False, 'verified': False, 'status': 'TASK_DETAILS_REQUIRED',
                    'message': 'Task ka title aur kya karna hai batao.', 'source': source}
        logger.info(f"[TASK_MANAGER] Result: {tm_msg[:100]}...")
        return {
            "success": True,
            "action": "task_manager",
            "intent": "TASK_MANAGER",
            "message": tm_msg,
            "source": source,
            "verified": True,
            "status": "COMPLETED",
            "execution_metrics": execution_metrics
        }

    # -------------------------------------------------------------
    # STEP 3.10: AMBIGUOUS QUERY CLARIFICATION (Phase 4H)
    # -------------------------------------------------------------
    if intent == "AMBIGUOUS":
        target = classification.get("target", "command")
        clarify_msg = f"Boss, '{target}' thoda ambiguous hai. Please batayein aap specifically kya karna chahte hain?"
        return {
            "success": True,
            "action": "clarification",
            "intent": "AMBIGUOUS",
            "message": clarify_msg,
            "source": source,
            "verified": True,
            "status": "CLARIFICATION_REQUESTED",
            "execution_metrics": execution_metrics
        }

    # -------------------------------------------------------------
    # STEP 3.11: SENSITIVE HIGH/CRITICAL RISK SECURITY GATE (Phase 4O)
    # -------------------------------------------------------------
    if intent == "SENSITIVE":
        auth_ok, reason = default_security_manager.validate_and_authorize(
            "windows_system_controller",
            {"action": "delete_all", "query": raw_text}
        )
        if not auth_ok:
            return {
                "success": False,
                "action": "security_confirmation",
                "intent": "SENSITIVE",
                "message": reason or "Critical security action blocked.",
                "source": source,
                "verified": False,
                "status": "SECURITY_CONFIRMATION_REQUIRED",
                "execution_metrics": execution_metrics
            }

    # -------------------------------------------------------------
    # STEP 4: DISCORD / SOCIAL PLATFORM ACTION DISPATCH
    # -------------------------------------------------------------
    if intent.startswith("DISCORD_"):
        _CONVERSATION_CONTEXT["last_app"] = "discord"
        _CONVERSATION_CONTEXT["last_platform"] = "discord"

        if intent == "DISCORD_CONNECT":
            res = default_tool_registry.execute_tool("discord_connect_voice", {"channel": "General"})
            return {"success": res.success, "message": res.message, "source": source, "verified": bool(res.verification.get("verified", False))}
        elif intent == "DISCORD_DISCONNECT":
            res = default_tool_registry.execute_tool("discord_disconnect_voice", {})
            return {"success": res.success, "message": res.message, "source": source, "verified": bool(res.verification.get("verified", False))}
        elif intent == "DISCORD_MUTE":
            unmute = "unmute" in lower_text or "chalu" in lower_text or "on" in lower_text
            tool_name = "discord_unmute" if unmute else "discord_mute"
            res = default_tool_registry.execute_tool(tool_name, {})
            return {"success": res.success, "message": res.message, "source": source, "verified": bool(res.verification.get("verified", False))}

    # -------------------------------------------------------------
    # STEP 5: APPLICATION RESOLUTION & MULTI-APP SEQUENTIAL LAUNCH
    # -------------------------------------------------------------
    if intent in ["WINDOWS_APPLICATION", "OPEN_APPLICATION"]:
        target_name = str(classification.get("target", raw_text) or "").strip(" '\"`.,")

        # Check for multi-application requests (e.g. "Open Chrome, Spotify and VS Code")
        # re is already imported at module level
        split_targets = [t.strip() for t in re.split(r",|\band\b|\baur\b", target_name, flags=re.IGNORECASE) if t.strip()]

        if len(split_targets) > 1:
            logger.info(f"[PIPELINE] Multi-application request detected: {split_targets}")
            successful_apps = []
            failed_app = None
            failure_msg = ""

            for target_app in split_targets:
                tool_name = "open_app"
                tool_args = {"app_name": target_app}
                auth_ok, auth_reason = default_security_manager.validate_and_authorize(tool_name, tool_args)
                if not auth_ok:
                    failed_app = target_app
                    failure_msg = auth_reason
                    break

                res = default_tool_registry.execute_tool(tool_name, tool_args)
                if res.success:
                    successful_apps.append(target_app)
                    time.sleep(0.5)  # Brief pause between sequential launches
                else:
                    failed_app = target_app
                    failure_msg = res.message
                    break  # Stop execution of remaining actions on failure

            if failed_app:
                msg = f"Opened {', '.join(successful_apps)}, but failed to launch '{failed_app}': {failure_msg}" if successful_apps else f"Failed to launch '{failed_app}': {failure_msg}"
                logger.warning(f"[PIPELINE] Multi-app launch partial failure: {msg}")
                return {
                    "success": False,
                    "action": "open_app",
                    "message": msg,
                    "source": source,
                    "verified": False,
                    "status": "MULTI_APP_FAILED",
                    "command_id": command_id,
                }
            else:
                success_msg = f"Opened {', '.join(successful_apps)}."
                logger.info(f"[PIPELINE] Multi-app launch ALL VERIFIED SUCCESS: {success_msg}")
                return {
                    "success": True,
                    "action": "open_app",
                    "message": success_msg,
                    "source": source,
                    "verified": True,
                    "status": "COMPLETED",
                    "command_id": command_id,
                }

        # Single Application Request
        route = resolve_app_or_web_target(target_name)
        if route.get("status") == "AMBIGUOUS_NATIVE_AND_WEB":
            app_canonical = route.get("app_canonical", target_name)
            set_pending_disambiguation(app_canonical, route)
            prompt_msg = f"Boss, {app_canonical.title()} Desktop app aur {app_canonical.title()} Web dono available hain. Kaunsa open karun?"
            return {
                "success": True,
                "action": "disambiguation_prompt",
                "message": prompt_msg,
                "source": source,
                "requires_choice": True,
                "status": "DISAMBIGUATION_REQUIRED",
                "command_id": command_id,
            }

        # Execute application launcher tool
        tool_name = classification.get("tool") or "open_app"
        tool_args = {"app_name": target_name}
        logger.info(f"[{command_id}] TOOL: '{tool_name}' args={tool_args}")

        # Security validation
        auth_ok, auth_reason = default_security_manager.validate_and_authorize(tool_name, tool_args)
        if not auth_ok:
            logger.warning(f"[{command_id}] SECURITY: Tool '{tool_name}' blocked: {auth_reason}")
            _update_execution_context(command_id, raw_text, target_name, tool_name, "FAILED", auth_reason)
            return {"success": False, "message": auth_reason, "source": source, "status": "SECURITY_BLOCKED", "command_id": command_id}

        res = default_tool_registry.execute_tool(tool_name, tool_args)
        with _CONTEXT_LOCK:
            _CONVERSATION_CONTEXT["last_app"] = target_name.lower()
        is_ok = bool(res.success)
        # Truthful response based on actual result
        if is_ok:
            msg = res.message or f"{target_name.title()} khol diya boss."
        else:
            msg = f"{target_name.title()} open nahi hua boss. {res.message}"
        result_status = "SUCCESS" if is_ok else "FAILED"
        _update_execution_context(command_id, raw_text, target_name, tool_name, result_status, "" if is_ok else res.message)
        logger.info(f"[{command_id}] RESULT: success={is_ok}, msg='{msg}'")

        proc_str = ""
        win_str = ""
        if isinstance(res.data, dict):
            proc_str = str(res.data.get("process", "FOUND" if is_ok else "NOT_FOUND"))
            win_str = str(res.data.get("window", "FOUND" if is_ok else "NOT_FOUND"))

        _log_command_telemetry(
            command_id=command_id,
            wake_word="Jarvis" if "jarvis" in raw_text.lower() else "None (Direct)",
            raw_transcript=raw_text,
            normalized_transcript=target_name,
            intent=intent,
            tool=tool_name,
            arguments=tool_args,
            execution_result=result_status,
            verification_result="TRUE" if is_ok else "FALSE",
            final_response=msg,
            tts_status="SENT" if (source == "voice" or is_ok) else "N/A",
            process_info=proc_str,
            window_info=win_str,
        )
        if not is_ok:
            _log_failure_stage("I", "Tool executed but Windows action failed", command_id, str(res.message))

        return {
            "success": is_ok,
            "action": tool_name,
            "message": msg,
            "data": res.data,
            "source": source,
            "verified": is_ok,
            "command_id": command_id,
        }

    # -------------------------------------------------------------
    # STEP 6: DIRECT TOOL DISPATCH
    # -------------------------------------------------------------
    tool_name = classification.get("tool")
    if tool_name and default_tool_registry.has_tool(tool_name):
        tool_args = dict(classification)
        tool_args.setdefault("query", raw_text)
        if tool_name == "open_app" and "app_name" not in tool_args and "target" in tool_args:
            tool_args["app_name"] = str(tool_args["target"]).strip(" '\"`.,")
        auth_ok, auth_reason = default_security_manager.validate_and_authorize(tool_name, tool_args)
        if not auth_ok:
            _update_execution_context(command_id, raw_text, str(tool_args.get('target', '')), tool_name, "FAILED", auth_reason)
            return {"success": False, "message": auth_reason, "source": source, "status": "SECURITY_BLOCKED", "command_id": command_id}

        # Handle TYPING intent: focus window if last_app exists, execute typing, verify foreground window
        if intent == "TYPING" or (tool_name == "computer_control" and tool_args.get("action") == "type"):
            with _CONTEXT_LOCK:
                target_app = _CONVERSATION_CONTEXT.get("last_app")
            if target_app:
                try:
                    from actions.computer_control import _focus_window
                    _focus_window(target_app)
                except Exception:
                    pass

        res = default_tool_registry.execute_tool(tool_name, tool_args)
        clean_msg = res.message
        if isinstance(clean_msg, str) and clean_msg.startswith("{") and "'message':" in clean_msg:
            try:
                import ast
                parsed = ast.literal_eval(clean_msg)
                if isinstance(parsed, dict) and "message" in parsed:
                    clean_msg = parsed["message"]
            except Exception:
                pass

        if intent == "TYPING":
            with _CONTEXT_LOCK:
                target_app = _CONVERSATION_CONTEXT.get("last_app")
            text_val = tool_args.get("text", tool_args.get("target", ""))
            if res.success:
                clean_msg = f"{target_app.title()} mein '{text_val}' type kar diya boss." if target_app else f"'{text_val}' type kar diya boss."
            else:
                clean_msg = f"{target_app.title()} mein type nahi ho paya boss. {clean_msg}" if target_app else f"Type nahi ho paya boss. {clean_msg}"

        result_status = "SUCCESS" if res.success else "FAILED"
        _update_execution_context(command_id, raw_text, str(tool_args.get('target', '')), tool_name, result_status, "" if res.success else str(clean_msg))
        logger.info(f"[{command_id}] RESULT: tool={tool_name} success={res.success} msg='{clean_msg}'")

        _log_command_telemetry(
            command_id=command_id,
            wake_word="Jarvis" if "jarvis" in raw_text.lower() else "None (Direct)",
            raw_transcript=raw_text,
            normalized_transcript=str(tool_args.get("text", tool_args.get("target", raw_text))),
            intent=intent,
            tool=tool_name,
            arguments=tool_args,
            execution_result=result_status,
            verification_result="TRUE" if res.verification.get("verified", False) else "FALSE",
            final_response=str(clean_msg),
            tts_status="SENT" if (source == "voice" or res.success) else "N/A"
        )
        if not res.success:
            _log_failure_stage("I", "Tool executed but Windows action failed", command_id, str(clean_msg))

        return {
            "success": res.success,
            "intent": intent,
            "message": str(clean_msg),
            "spoken_message": res.data.get('spoken_message', str(clean_msg)),
            "authoritative_response": bool(res.data.get('authoritative_response', False)),
            "data": res.data,
            "source": source,
            "verified": bool(res.verification.get("verified", False)),
            "execution_metrics": execution_metrics,
            "command_id": command_id,
        }

    # -------------------------------------------------------------
    # STEP 7: DYNAMIC OLLAMA STRUCTURED ACTION PLANNING & CONVERSATION FALLBACK
    # -------------------------------------------------------------
    ai_already_invoked = False
    if is_ollama_available():
        struct_res = {}
        try:
            q_lower = raw_text.lower().strip()
            action_verbs = ["open", "close", "start", "stop", "play", "set", "call", "send", "turn", "launch", "bhejo", "kholo", "badhao", "ghatao", "padho", "utha", "kaat", "disconnect", "connect", "mute", "unmute"]
            words = q_lower.split()
            has_action_verb = any(w in words for w in action_verbs)

            conv_keywords = ["kya", "kyun", "kaise", "aur", "what", "why", "how", "tell", "explain", "who", "where", "when", "bata", "batao", "bataiye", "meaning", "definition", "ye", "yeh", "baare", "phir", "uske", "uska", "iska", "isey", "faida", "difference", "vs", "summary", "detail", "info", "about"]
            is_conversational_query = any(w in q_lower.split() for w in conv_keywords) or q_lower.endswith("?") or (intent == "OTHER" and not has_action_verb)

            if not is_conversational_query:
                from core.ollama_provider import get_ollama_provider
                provider = get_ollama_provider()
                allowed_tools = default_tool_registry.list_tools()

                struct_res = provider.generate_structured_action(raw_text, allowed_tools=allowed_tools)

            if struct_res and struct_res.get("success"):
                action_proposal = struct_res.get("action_proposal", {})
                proposed_tool = action_proposal.get("capability") or action_proposal.get("tool")
                if proposed_tool and default_tool_registry.has_tool(proposed_tool):
                    tool_args = action_proposal.get("parameters", {})
                    if not isinstance(tool_args, dict):
                        tool_args = {}
                    if "target" in action_proposal and action_proposal["target"]:
                        tool_args.setdefault("target", action_proposal["target"])
                        tool_args.setdefault("app_name", action_proposal["target"])
                    if "action" in action_proposal and action_proposal["action"]:
                        tool_args.setdefault("action", action_proposal["action"])
                    tool_args.setdefault("query", raw_text)

                    auth_ok, auth_reason = default_security_manager.validate_and_authorize(proposed_tool, tool_args)
                    if not auth_ok:
                        _update_execution_context(command_id, raw_text, str(tool_args.get('target', '')), proposed_tool, "FAILED", auth_reason)
                        return {"success": False, "message": auth_reason, "source": source, "status": "SECURITY_BLOCKED", "command_id": command_id}

                    exec_res = default_tool_registry.execute_tool(proposed_tool, tool_args)
                    result_status = "SUCCESS" if exec_res.success else "FAILED"
                    _update_execution_context(command_id, raw_text, str(tool_args.get('target', '')), proposed_tool, result_status, "" if exec_res.success else exec_res.message)
                    logger.info(f"[{command_id}] RESULT: ollama_action tool={proposed_tool} success={exec_res.success}")
                    return {
                        "success": exec_res.success,
                        "action": proposed_tool,
                        "message": exec_res.message,
                        "data": exec_res.data,
                        "source": source,
                        "verified": bool(exec_res.verification.get("verified", False)),
                        "command_id": command_id,
                    }
        except Exception as err:
            logger.debug(f"[Pipeline] Ollama structured planning exception: {err}")

        if stream_callback and is_ollama_available():
            from core.ollama_provider import get_ollama_provider
            prov = get_ollama_provider()
            tokens = []
            sentence_buffer = ""
            for tok in prov.chat_stream(raw_text):
                if not tok:
                    continue
                tokens.append(tok)
                sentence_buffer += tok
                if any(p in tok for p in [".", "!", "?", "\n", ","]):
                    stream_callback(sentence_buffer)
                    sentence_buffer = ""
            if sentence_buffer.strip():
                stream_callback(sentence_buffer)
            full_text = "".join(tokens).strip()
            if full_text:
                return {
                    "success": True,
                    "message": full_text,
                    "source": source,
                    "model_used": prov.persona_model,
                    "status": "SUCCESS"
                }

        # Multi-Tier AI Brain: Tier 1 Ollama -> Tier 2 Gemini 3.6 Flash -> Tier 3 OpenRouter
        from core.ai_multitier_engine import get_ai_engine
        ai_brain = get_ai_engine()
        ai_already_invoked = True
        ai_res = ai_brain.generate_response(raw_text)
        logger.info(
            f"[AI_TELEMETRY] request_id={command_id} provider={ai_res.get('tier', 'UNKNOWN')} "
            f"model={ai_res.get('model', 'UNKNOWN')} reason=CONVERSATIONAL_CHAT latency_ms={ai_res.get('duration_ms', 0)}"
        )
        if ai_res.get("success") and ai_res.get("text"):
            return {
                "success": True,
                "message": ai_res["text"].strip(),
                "source": source,
                "model_used": ai_res.get("model", ai_res.get("tier")),
                "tier": ai_res.get("tier"),
                "status": "SUCCESS",
                "verified": True,
                "execution_metrics": execution_metrics
            }
        elif ai_res.get("text"):
            return {
                "success": False,
                "message": ai_res["text"].strip(),
                "source": source,
                "status": "DEGRADED",
                "verified": False,
                "execution_metrics": execution_metrics
            }

    # Final guaranteed conversational fallback via Multi-Tier AI Brain (only if not already invoked)
    if not ai_already_invoked:
        try:
            from core.ai_multitier_engine import get_ai_engine
            ai_brain = get_ai_engine()
            ai_res = ai_brain.generate_response(raw_text)
            logger.info(
                f"[AI_TELEMETRY] request_id={command_id} provider={ai_res.get('tier', 'UNKNOWN')} "
                f"model={ai_res.get('model', 'UNKNOWN')} reason=FALLBACK_CHAT latency_ms={ai_res.get('duration_ms', 0)}"
            )
            if ai_res.get("text"):
                return {
                    "success": ai_res.get("success", True),
                    "message": ai_res["text"].strip(),
                    "source": source,
                    "model_used": ai_res.get("model", "ai_brain"),
                    "status": "SUCCESS" if ai_res.get("success") else "DEGRADED",
                    "verified": bool(ai_res.get("success")),
                    "execution_metrics": execution_metrics
                }
        except Exception as final_err:
            logger.error(f"[Pipeline] Final AI Brain fallback error: {final_err}")

    return {
        "success": False,
        "message": "Command samajh nahi aaya ya AI connection unavailable hai. App ka naam ya action thoda clearly batao.",
        "source": source,
        "status": "UNRESOLVED",
        "verified": False
    }
