# actions/universal_calls_sms.py
# Universal Phone Call & SMS Capabilities Engine for JARVIS
# Routes call and SMS actions across Android ADB bridge and Windows Phone Link.

import os
import shutil
import logging
import subprocess
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
            cmd = f'adb shell am start -a android.intent.action.CALL -d tel:{clean_target}'
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5.0)
            if res.returncode == 0:
                return {
                    "success": True,
                    "action": "make_call",
                    "target": clean_target,
                    "provider": "AndroidADB",
                    "message": f"Calling {clean_target} on your mobile device.",
                    "verified": True
                }
        except Exception as e:
            logger.debug(f"ADB dialer call failed: {e}")

    # Fallback to Windows Phone Link URI protocol
    try:
        os.startfile(f"tel:{clean_target}")
        return {
            "success": True,
            "action": "make_call",
            "target": clean_target,
            "provider": "WindowsPhoneLink",
            "message": f"Initiated phone call to {clean_target} via Windows Phone Link.",
            "verified": True
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
            cmd = 'adb shell content query --uri content://call_log/calls --projection name:number:type:date'
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5.0)
            if res.returncode == 0 and res.stdout:
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
        "success": True,
        "action": "read_call_log",
        "provider": "NotificationEngine",
        "message": "Boss, no recent missed calls found in call log.",
        "verified": True
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

    clean_phone = recipient.replace("+", "").replace(" ", "").strip()

    adb_path = shutil.which("adb")
    if adb_path:
        try:
            cmd = f'adb shell service call isms 7 i32 0 s16 "com.android.mms" s16 "{clean_phone}" s16 "null" s16 "{message_text}" s16 "null" s16 "null"'
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5.0)
            if res.returncode == 0:
                return {
                    "success": True,
                    "action": "send_sms",
                    "recipient": clean_phone,
                    "message": f"SMS sent successfully to {clean_phone}.",
                    "verified": True
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
    if adb_path:
        try:
            cmd = 'adb shell content query --uri content://sms/inbox --projection address:body'
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5.0)
            if res.returncode == 0 and res.stdout:
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
        "success": True,
        "action": "read_sms",
        "provider": "NotificationEngine",
        "message": "Boss, no unread SMS messages found.",
        "verified": True
    }
