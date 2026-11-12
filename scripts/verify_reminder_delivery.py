"""Fire one owned local test reminder, verify task completion, and clean up."""
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from actions.reminder import reminder
import win32com.client

original_run = subprocess.run
created = []
def record_run(args, **kwargs):
    result = original_run(args, **kwargs)
    if args[0] == "schtasks" and "/Create" in args and result.returncode == 0:
        created.append(args[args.index("/TN") + 1])
    return result

report = {"scheduled": False, "executed": False, "completed": False, "cleaned_up": False}
try:
    target = datetime.now() + timedelta(seconds=12)
    with patch("actions.reminder.subprocess.run", side_effect=record_run):
        result = reminder({"date": target.strftime("%Y-%m-%d"), "time": target.strftime("%H:%M:%S"), "message": "JARVIS test reminder"})
    report["scheduled"] = bool(result["success"])
    print(json.dumps({"scheduled": report["scheduled"], "test": "one local reminder"}), flush=True)
    if created:
        scheduler = win32com.client.Dispatch("Schedule.Service")
        scheduler.Connect()
        folder = scheduler.GetFolder("\\")
        deadline = time.monotonic() + 85
        while time.monotonic() < deadline:
            task = folder.GetTask(created[0])
            if task.LastRunTime.year >= target.year and task.LastRunTime.month == target.month and task.LastRunTime.day == target.day:
                report["executed"] = True
                if task.State != 4:  # TASK_STATE_RUNNING
                    report["last_task_result"] = int(task.LastTaskResult)
                    report["completed"] = task.LastTaskResult == 0
                    break
            time.sleep(.5)
finally:
    for task_name in created:
        if not re.fullmatch(r"JARVISReminder_\d{8}_\d{6}_[0-9a-f]{8}", task_name):
            raise RuntimeError("Unexpected task; refusing cleanup")
        if report["executed"] and not report["completed"]:
            original_run(["schtasks", "/End", "/TN", task_name], capture_output=True, text=True, timeout=10)
        removed = original_run(["schtasks", "/Delete", "/TN", task_name, "/F"], capture_output=True, text=True, timeout=10)
        report["cleaned_up"] = removed.returncode == 0
        (Path(os.environ["TEMP"])/f"{task_name}.pyw").unlink(missing_ok=True)

output = Path(__file__).resolve().parent.parent/"scratch"/"reminder_delivery_check.json"
output.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2), flush=True)
if not all(report[key] for key in ("scheduled", "executed", "completed", "cleaned_up")):
    sys.exit(1)
