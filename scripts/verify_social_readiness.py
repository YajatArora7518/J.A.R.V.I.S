"""Read-only account readiness and authorized WhatsApp visible-read check.

No messages are sent, no calls are placed, and conversation contents are not
printed or saved. Reading a chat can update the platform's read receipts.
"""
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from actions.browser_automation import browser_automation_engine


async def accounts():
    results = {}
    for service in ("discord", "instagram"):
        results[service] = await browser_automation_engine._check_service_auth_async(service)
    return results


report = {"accounts": browser_automation_engine.run(accounts(), timeout=25)}
if "--whatsapp-divyansh-read" in sys.argv:
    from core.command_pipeline import process_user_command
    previous_logging = logging.root.manager.disable
    try:
        logging.disable(logging.CRITICAL)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = process_user_command("Divyansh ka WhatsApp message batao", source="text")
        report["whatsapp_visible_read"] = {"success": bool(result.get("success")), "verified": bool(result.get("verified"))}
    finally:
        logging.disable(previous_logging)
print(json.dumps(report, indent=2))
(ROOT / "scratch" / "social_readiness.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
