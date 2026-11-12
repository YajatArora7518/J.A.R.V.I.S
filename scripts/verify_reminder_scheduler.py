"""Register/query/remove one uniquely owned future test reminder; never let it fire."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from actions.reminder import reminder

original_run = subprocess.run
created = []


def record_run(args, **kwargs):
    result = original_run(args, **kwargs)
    if args[0] == "schtasks" and "/Create" in args and result.returncode == 0:
        created.append(args[args.index("/TN") + 1])
    return result


report = {"scheduled": False, "queried": False, "cleaned_up": False}
try:
    with patch("actions.reminder.subprocess.run", side_effect=record_run):
        result = reminder({"query": "remind me in 10 minutes to verify JARVIS test reminder"})
    report["scheduled"] = bool(result["success"])
    report["message"] = result["message"]
    if created:
        query = original_run(["schtasks", "/Query", "/TN", created[0]], capture_output=True, text=True, timeout=10)
        report["queried"] = query.returncode == 0
finally:
    for task_name in created:
        if not re.fullmatch(r"JARVISReminder_\d{8}_\d{6}_[0-9a-f]{8}", task_name):
            raise RuntimeError("Unexpected reminder task name; refusing cleanup")
        deleted = original_run(["schtasks", "/Delete", "/TN", task_name, "/F"], capture_output=True, text=True, timeout=10)
        report["cleaned_up"] = deleted.returncode == 0
        (Path(os.environ["TEMP"]) / f"{task_name}.pyw").unlink(missing_ok=True)
print(json.dumps(report, indent=2))
(Path(__file__).resolve().parent.parent / "scratch" / "reminder_scheduler_check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
if not all(report[key] for key in ("scheduled", "queried", "cleaned_up")):
    sys.exit(1)
