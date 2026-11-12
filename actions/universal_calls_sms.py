# actions/universal_calls_sms.py
# Universal Phone Call & SMS Capabilities Engine for JARVIS
# Routes call and SMS actions across Android ADB bridge and Windows Phone Link.

import os
import shutil
import logging
import subprocess
import re
import shlex
from typing import Dict, Any, List

logger = logging.getLogger("JARVIS.CallsSMS")


def make_call(recipient: str, call_type: str = "voice", confirm_call: bool = False) -> Dict[str, Any]:
    """
    Executes phone call via Android ADB bridge or Windows Phone Link.
    Requires user confirmation for external high-risk voice calls.
    """
    if not recipient or not recipient.strip():
        return {
            "success": False,
            "action": "make_call",
            "message": "Please specify a recipient or phone number to call.",
            "verified": False
        }

    clean_target = recipient.strip()
    phone_number = re.sub(r"[\s().-]", "", clean_target)
    if not re.fullmatch(r"\+?\d{3,15}", phone_number):
        return {"success": False, "verified": False, "action": "make_call",
                "message": "Phone call ke liye exact phone number do; contact name ko number se link nahi kiya gaya hai."}

    # High-risk action safety check
    if not confirm_call:
        return {
            "success": False,
            "action": "make_call",
            "target": clean_target,
            "call_type": call_type,
            "message": f"Boss, ready to place a {call_type} call to '{clean_target}'. Shall I proceed?",
            "requires_confirmation": True,
            "verified": False
        }

    # Attempt Android ADB dialer
    adb_path = shutil.which("adb")
    if adb_path:
        try:
            cmd = [adb_path, "shell", "am", "start", "-a", "android.intent.action.CALL", "-d", f"tel:{phone_number}"]
            res = subprocess.run(cmd, shell=False, capture_output=True, text=True, timeout=5.0)
            if res.returncode == 0:
                return {
                    "success": True,
                    "action": "make_call",
                    "target": clean_target,
                    "provider": "AndroidADB",
                    "message": f"Phone ko {clean_target} par call request bheji. Connection confirm nahi hai.",
                    "verified": False,
                    "status": "CALL_REQUESTED"
                }
        except Exception as e:
            logger.debug(f"ADB dialer call failed: {e}")

    # Fallback to Windows Phone Link URI protocol
    try:
        os.startfile(f"tel:{phone_number}")
        return {
            "success": True,
            "action": "make_call",
            "target": clean_target,
            "provider": "WindowsPhoneLink",
            "message": f"{clean_target} ke liye Windows phone handler khola. Call connection confirm nahi hai.",
            "verified": False,
            "status": "CALL_REQUESTED"
        }
    except Exception as e:
        return {
            "success": False,
            "action": "make_call",
            "target": clean_target,
            "message": f"Could not place call to {clean_target}: {e}",
            "verified": False
        }


def read_call_log() -> Dict[str, Any]:
    """Reads call log history from Android ADB bridge or notification engine."""
    adb_path = shutil.which("adb")
    if adb_path:
        try:
            cmd = [adb_path, "shell", "content", "query", "--uri", "content://call_log/calls", "--projection", "name:number:type:date"]
            res = subprocess.run(cmd, shell=False, capture_output=True, text=True, timeout=5.0)
            if res.returncode == 0 and res.stdout and not res.stdout.lstrip().lower().startswith(("error", "exception")):
                return {
                    "success": True,
                    "action": "read_call_log",
                    "provider": "AndroidADB",
                    "log_data": res.stdout[:500],
                    "message": "Fetched phone call log from Android device.",
                    "verified": True
                }
        except Exception:
            pass

    return {
        "success": False,
        "action": "read_call_log",
        "provider": "NotificationEngine",
        "message": "Phone call log ka live access connected nahi hai; missed calls verify nahi hue.",
        "verified": False
    }


def send_sms_message(recipient: str, message_text: str) -> Dict[str, Any]:
    """Sends SMS via Android ADB bridge or Windows Phone Link."""
    if not recipient or not message_text:
        return {
            "success": False,
            "action": "send_sms",
            "message": "Please specify recipient and message text for SMS.",
            "verified": False
        }

    clean_phone = re.sub(r"[\s().-]", "", recipient.strip())
    if not re.fullmatch(r"\+?\d{3,15}", clean_phone):
        return {"success": False, "verified": False, "message": "SMS ke liye exact phone number do."}

    adb_path = shutil.which("adb")
    if adb_path:
        try:
            # Open a draft instead of pretending an undocumented binder call
            # proves delivery. Quote the Android shell command as well.
            remote = ["am", "start", "-a", "android.intent.action.SENDTO", "-d", f"smsto:{clean_phone}", "--es", "sms_body", message_text]
            cmd = [adb_path, "shell", shlex.join(remote)]
            res = subprocess.run(cmd, shell=False, capture_output=True, text=True, timeout=5.0)
            if res.returncode == 0:
                return {
                    "success": True,
                    "action": "send_sms",
                    "recipient": clean_phone,
                    "message": f"{clean_phone} ke liye phone par SMS draft khola. Send/delivery confirm nahi hai.",
                    "verified": False,
                    "status": "SMS_DRAFT_REQUESTED"
                }
        except Exception:
            pass

    return {
        "success": False,
        "action": "send_sms",
        "recipient": clean_phone,
        "message": "I couldn't confirm that the SMS was sent, so I won't claim it was.",
        "verified": False
    }


def read_sms_messages(target: str = "") -> Dict[str, Any]:
    """Reads SMS messages from Android bridge."""
    adb_path = shutil.which("adb")
    clean_target = re.sub(r"[\s().-]", "", target.strip())
    if target and not re.fullmatch(r"\+?\d{3,15}", clean_target):
        return {"success": False, "verified": False, "message": "SMS recipient ke liye exact phone number do."}
    if adb_path:
        try:
            remote = ["content", "query", "--uri", "content://sms/inbox", "--projection", "address:body"]
            if target:
                remote.extend(["--where", f"address='{clean_target}'"])
            res = subprocess.run([adb_path, "shell", shlex.join(remote)], shell=False, capture_output=True, text=True, timeout=5.0)
            if res.returncode == 0 and res.stdout and not res.stdout.lstrip().lower().startswith(("error", "exception")):
                return {
                    "success": True,
                    "action": "read_sms",
                    "provider": "AndroidADB",
                    "sms_data": res.stdout[:500],
                    "message": "Fetched recent SMS messages from Android device.",
                    "verified": True
                }
        except Exception:
            pass

    return {
        "success": False,
        "action": "read_sms",
        "provider": "NotificationEngine",
        "message": "Phone SMS ka live access connected nahi hai; unread messages verify nahi hue.",
        "verified": False
    }
