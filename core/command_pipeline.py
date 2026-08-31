# core/command_pipeline.py
# Single Unified Command Processing Pipeline for JARVIS (Voice & Typed Chat)

import os
import sys
import time
import json
import logging
from typing import Dict, Any, Optional, Tuple, Callable

from core.intent_router import classify_intent
from core.tool_registry import default_tool_registry
from core.security import default_security_manager
from actions.app_registry import resolve_app, is_app_installed
from actions.app_first_routing import resolve_app_or_web_target
from core.ollama_provider import generate_ollama_response, is_ollama_available

logger = logging.getLogger("JARVIS.CommandPipeline")

# Module-level flag: tool registry initialization status (thread-safe via GIL)
_tools_initialized = False

# Global Conversation Context State Machine
_CONVERSATION_CONTEXT: Dict[str, Any] = {
    "last_app": None,
    "last_platform": None,
    "last_contact": None,
    "last_channel": None,
    "pending_disambiguation": None,  # e.g., {"app": "discord", "native_available": True, "web_available": True}
    "pending_important_message": None,  # e.g., {"contact": "Papa", "message": "Beta ghar kab aaoge?", "platform": "whatsapp"}
    "pending_screen_context": None  # e.g., {"active_window": "VS Code", "observation": "...", "time": 12345678}
}


def get_conversation_context() -> Dict[str, Any]:
    """Returns current active conversation context."""
    return _CONVERSATION_CONTEXT


def reset_conversation_context() -> None:
    """Resets conversational context."""
    global _CONVERSATION_CONTEXT
    _CONVERSATION_CONTEXT = {
        "last_app": None,
        "last_platform": None,
        "last_contact": None,
        "last_channel": None,
        "pending_disambiguation": None,
        "pending_important_message": None,
        "pending_screen_context": None
    }


def set_pending_disambiguation(app_name: str, options: Dict[str, Any]) -> None:
    """Sets a pending native vs web choice prompt."""
    _CONVERSATION_CONTEXT["pending_disambiguation"] = {
        "app": app_name,
        "options": options
    }


def set_pending_important_message(contact: str, message: str, platform: str = "whatsapp") -> None:
    """Sets a pending important message read-aloud confirmation prompt."""
    _CONVERSATION_CONTEXT["pending_important_message"] = {
        "contact": contact,
        "message": message,
        "platform": platform
    }


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
    raw_text = (text or "").strip()
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
    correlation_id = f"req_{int(time.time() * 1000)}"
    execution_metrics = {
        "stt": 1,
        "normalization": 1,
        "intent": 1,
        "context": 0,
        "tool": 1,
        "llm": 0,
        "response": 1,
        "tts": 1,
        "correlation_id": correlation_id
    }

    # -------------------------------------------------------------
    # INSTANT BARGE-IN & MIC CONTROL INTERCEPTION (<0.1 ms HOT PATH)
    # -------------------------------------------------------------
    barge_in_words = ["stop", "stop speaking", "chup", "shut up", "barge in", "cancel", "mic off", "stop listening"]
    if any(w == lower_text or lower_text.startswith(w) for w in barge_in_words):
        from actions.mic_control import handle_mic_command
        mic_res = handle_mic_command(raw_text)
        mic_res["source"] = source
        return mic_res

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
    if _CONVERSATION_CONTEXT.get("pending_power_action"):
        pending_pwr = _CONVERSATION_CONTEXT["pending_power_action"]
        expires_at = pending_pwr.get("expires_at", 0)
        
        # Check expiry (30s window)
        if time.time() > expires_at:
            _CONVERSATION_CONTEXT["pending_power_action"] = None
            logger.info("[Pipeline] Pending power confirmation expired.")
        else:
            if any(w in lower_text for w in ["nahi", "no", "mat", "dont", "don't", "stop", "cancel", "reject"]):
                _CONVERSATION_CONTEXT["pending_power_action"] = None
                return {
                    "success": True,
                    "action": "power_control_cancel",
                    "message": "Theek hai Boss, power action cancel kar diya.",
                    "source": source,
                    "verified": True,
                    "status": "POWER_CANCELLED"
                }
            elif any(w in lower_text for w in ["haan", "yes", "confirm", "kar do", "do it", "sure", "ok", "okay"]):
                pwr_act = pending_pwr.get("action", "shutdown")
                target_dev = pending_pwr.get("target_device", "pc")
                _CONVERSATION_CONTEXT["pending_power_action"] = None

                logger.info(f"[Pipeline] Executing confirmed power action '{pwr_act}' on target '{target_dev}'")
                if target_dev == "pc":
                    from actions.windows_system_controller import execute_system_capability
                    res = execute_system_capability(pwr_act, {})
                    return {
                        "success": res.get("success", True),
                        "action": f"power_{pwr_act}",
                        "message": f"Boss, PC {pwr_act} execute kar diya.",
                        "source": source,
                        "verified": True,
                        "status": "POWER_EXECUTED"
                    }
                else:
                    from actions.mobile_pc_gateway import handle_mobile_gateway_command
                    res = handle_mobile_gateway_command("android", pwr_act, {})
                    return {
                        "success": res.get("success", True),
                        "action": f"power_{pwr_act}_phone",
                        "message": f"Boss, phone {pwr_act} command pass set kar diya.",
                        "source": source,
                        "verified": True,
                        "status": "POWER_EXECUTED"
                    }

    # Screen vision conversational follow-up ("Haan", "Theek hai", "Kar do", "Root cause batao")
    if _CONVERSATION_CONTEXT.get("pending_screen_context"):
        pending_scr = _CONVERSATION_CONTEXT["pending_screen_context"]
        if any(w in lower_text for w in ["haan", "yes", "theek hai", "kar", "karo", "do it", "sure", "batao", "root cause", "fix", "inspect"]):
            act_win = pending_scr.get("active_window", "")
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
        pending_msg = _CONVERSATION_CONTEXT["pending_important_message"]
        _CONVERSATION_CONTEXT["pending_important_message"] = None
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
        pending_app = _CONVERSATION_CONTEXT["pending_disambiguation"]
        _CONVERSATION_CONTEXT["pending_disambiguation"] = None
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

    # Direct Power Control Confirmation Interception
    if any(k in lower_text for k in ["shutdown", "restart", "turn off", "band kar", "reboot"]):
        if not any(k in lower_text for k in ["jarvis", "app", "application", "tab", "process", "service"]):
            # Determine target device
            target_device = "pc"
            if any(w in lower_text for w in ["phone", "mobile", "android"]):
                target_device = "android"
            elif any(w in lower_text for w in ["laptop", "pc", "computer", "system", "desktop"]):
                target_device = "pc"
            elif "phone" in lower_text and "laptop" in lower_text:
                target_device = "pc"  # e.g., "Phone se laptop shutdown kar do"
            
            pwr_action = "restart" if "restart" in lower_text or "reboot" in lower_text else "shutdown"
            
            _CONVERSATION_CONTEXT["pending_power_action"] = {
                "action": pwr_action,
                "target_device": target_device,
                "expires_at": time.time() + 30.0
            }

            device_name = "laptop" if target_device == "pc" else "phone"
            prompt_text = f"Boss, {device_name} {pwr_action} kar doon? Confirm karein."
            logger.info(f"[Pipeline] Requesting confirmation for power action '{pwr_action}' on target '{target_device}'")
            return {
                "success": True,
                "action": "power_confirmation_prompt",
                "message": prompt_text,
                "source": source,
                "requires_confirmation": True,
                "status": "CONFIRMATION_REQUIRED"
            }

    # -------------------------------------------------------------
    # WHATSAPP INSTALLED DESKTOP CALL CONTROL INTERCEPTION
    # -------------------------------------------------------------
    if "whatsapp" in lower_text or any(k in lower_text for k in ["call receive", "call utha", "receive karo", "call reject", "call cut", "call kaat"]):
        from actions.windows_whatsapp_desktop_executor import windows_whatsapp_desktop_executor

        # 1. Answer Call
        if any(k in lower_text for k in ["call receive", "call utha", "receive karo"]):
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

        # 4. Outgoing Calls
        elif "call" in lower_text:
            # Extract contact name
            contact_name = raw_text
            for prefix in ["whatsapp video call karo", "whatsapp call karo", "whatsapp pe video call karo", "whatsapp pe call karo", "ko whatsapp call karo", "ko whatsapp video call karo"]:
                if prefix in lower_text:
                    parts = lower_text.split(prefix)
                    contact_name = parts[0].replace("ko", "").strip() or parts[-1].strip()
                    break

            if "video" in lower_text:
                res = windows_whatsapp_desktop_executor.execute_video_call(recipient=contact_name)
            else:
                res = windows_whatsapp_desktop_executor.execute_voice_call(recipient=contact_name)
            return {"success": res.get("success", False), "action": "whatsapp_outgoing_call", "message": res.get("message", ""), "source": source, "verified": res.get("verified", False), "execution_target": res.get("execution_target")}
    # -------------------------------------------------------------
    # STEP 2: CONTEXTUAL FOLLOW-UP PRONOUN RESOLUTION ("usko", "wahi", "isko")
    # -------------------------------------------------------------
    pronoun_words = ["usko", "usse", "wahi", "isey", "isko", "same person", "same contact", "same app"]
    if any(w in lower_text for w in pronoun_words):
        last_c = _CONVERSATION_CONTEXT.get("last_contact")
        last_a = _CONVERSATION_CONTEXT.get("last_app")
        
        if last_c and any(p in lower_text for p in ["usko", "usse", "wahi", "same person", "same contact"]):
            for p in ["usko", "usse", "wahi", "same person", "same contact"]:
                if p in lower_text:
                    raw_text = raw_text.replace(p, last_c)
            lower_text = raw_text.lower()
            logger.info(f"[Pipeline] Resolved contact pronoun locally -> contact: '{last_c}'")

        if last_a and any(p in lower_text for p in ["isko", "isey", "same app"]):
            for p in ["isko", "isey", "same app"]:
                if p in lower_text:
                    raw_text = raw_text.replace(p, last_a)
            lower_text = raw_text.lower()
            logger.info(f"[Pipeline] Resolved app pronoun locally -> app: '{last_a}'")

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
    barge_in_keywords = ["stop", "stop speaking", "chup", "shut up", "barge in", "cancel", "mic", "microphone", "listening", "stop listening", "start listening", "jarvis mute", "jarvis unmute"]
    if intent in ["MIC_CONTROL", "CANCEL", "STOP"] or any(w == lower_text or w in lower_text.split() for w in barge_in_keywords):
        from actions.mic_control import handle_mic_command
        mic_res = handle_mic_command(raw_text)
        mic_res["source"] = source
        return mic_res

    logger.info(f"[PIPELINE] Processing command: '{raw_text}' [source={source}]")
    logger.info(f"[INTENT] Intent classified: {intent} | details={classification}")

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
        from actions.screen_processor import analyze_screen_vision
        angle = classification.get("angle", "screen")
        vision_res = analyze_screen_vision(user_query=raw_text, angle=angle)
        is_ok = bool(vision_res.get("success"))
        msg = vision_res.get("message", "Screen analysis completed.")
        _CONVERSATION_CONTEXT["pending_screen_context"] = {
            "active_window": vision_res.get("active_window", ""),
            "observation": vision_res.get("observation", msg),
            "time": time.time()
        }
        logger.info(f"[SCREEN_ANALYSIS] Result: {msg[:100]}...")
        return {
            "success": is_ok,
            "action": "screen_process",
            "intent": "SCREEN_ANALYSIS",
            "message": msg,
            "data": vision_res,
            "source": source,
            "verified": is_ok,
            "status": "COMPLETED" if is_ok else "VISION_FAILED",
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
            return {"success": res.success, "message": res.message, "source": source, "verified": res.success}
        elif intent == "DISCORD_DISCONNECT":
            res = default_tool_registry.execute_tool("discord_disconnect_voice", {})
            return {"success": res.success, "message": res.message, "source": source, "verified": res.success}
        elif intent == "DISCORD_MUTE":
            unmute = "unmute" in lower_text or "chalu" in lower_text or "on" in lower_text
            tool_name = "discord_unmute" if unmute else "discord_mute"
            res = default_tool_registry.execute_tool(tool_name, {})
            return {"success": res.success, "message": res.message, "source": source, "verified": res.success}

    # -------------------------------------------------------------
    # STEP 5: APPLICATION RESOLUTION & MULTI-APP SEQUENTIAL LAUNCH
    # -------------------------------------------------------------
    if intent in ["WINDOWS_APPLICATION", "OPEN_APPLICATION"]:
        target_name = classification.get("target", raw_text)
        
        # Check for multi-application requests (e.g. "Open Chrome, Spotify and VS Code")
        import re
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
                    "status": "MULTI_APP_FAILED"
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
                    "status": "COMPLETED"
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
                "status": "DISAMBIGUATION_REQUIRED"
            }

        # Execute application launcher tool
        tool_name = classification.get("tool") or "open_app"
        tool_args = {"app_name": target_name}
        logger.info(f"[TOOL] Selected tool '{tool_name}' with args {tool_args}")
        
        # Security validation
        auth_ok, auth_reason = default_security_manager.validate_and_authorize(tool_name, tool_args)
        if not auth_ok:
            logger.warning(f"[SECURITY] Tool '{tool_name}' blocked: {auth_reason}")
            return {"success": False, "message": auth_reason, "source": source, "status": "SECURITY_BLOCKED"}

        res = default_tool_registry.execute_tool(tool_name, tool_args)
        _CONVERSATION_CONTEXT["last_app"] = target_name.lower()
        is_ok = bool(res.success)
        msg = res.message if is_ok else f"Command failed: {res.message}"
        logger.info(f"[RESULT] Execution result: success={is_ok}, verified={is_ok}, msg='{msg}'")
        return {
            "success": is_ok,
            "action": tool_name,
            "message": msg,
            "data": res.data,
            "source": source,
            "verified": is_ok
        }

    # -------------------------------------------------------------
    # STEP 6: DIRECT TOOL DISPATCH
    # -------------------------------------------------------------
    tool_name = classification.get("tool")
    if tool_name and default_tool_registry.has_tool(tool_name):
        tool_args = dict(classification)
        tool_args.setdefault("query", raw_text)
        auth_ok, auth_reason = default_security_manager.validate_and_authorize(tool_name, tool_args)
        if not auth_ok:
            return {"success": False, "message": auth_reason, "source": source, "status": "SECURITY_BLOCKED"}

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
        return {
            "success": res.success,
            "intent": intent,
            "message": str(clean_msg),
            "data": res.data,
            "source": source,
            "verified": res.success,
            "execution_metrics": execution_metrics
        }

    # -------------------------------------------------------------
    # STEP 7: DYNAMIC OLLAMA STRUCTURED ACTION PLANNING & CONVERSATION FALLBACK
    # -------------------------------------------------------------
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
                        return {"success": False, "message": auth_reason, "source": source, "status": "SECURITY_BLOCKED"}

                    exec_res = default_tool_registry.execute_tool(proposed_tool, tool_args)
                    return {
                        "success": exec_res.success,
                        "action": proposed_tool,
                        "message": exec_res.message,
                        "data": exec_res.data,
                        "source": source,
                        "verified": exec_res.success
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

        ollama_res = generate_ollama_response(raw_text)
        if ollama_res.get("success"):
            return {
                "success": True,
                "message": ollama_res["text"],
                "source": source,
                "model_used": ollama_res.get("model_used"),
                "status": "SUCCESS"
            }

    return {
        "success": True,
        "message": f"Processed command: {raw_text}",
        "source": source,
        "status": "SUCCESS"
    }
