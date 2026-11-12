# actions/reminder.py

import subprocess
import os
import sys
from datetime import datetime
from xml.sax.saxutils import escape
import uuid


def _schedule_reminder(
    parameters: dict,
    response: str | None = None,
    player=None,
    session_memory=None
) -> str:
    """
    Sets a timed reminder using Windows Task Scheduler.

    parameters:
        - date    (str) YYYY-MM-DD
        - time    (str) HH:MM
        - message (str)

    Returns a result string — Live API voices it automatically.
    No edge_speak needed.
    """

    date_str = parameters.get("date")
    time_str = parameters.get("time")
    message  = parameters.get("message", "Reminder")

    if not date_str or not time_str:
        return "I need both a date and a time to set a reminder."

    try:
        target_dt = datetime.fromisoformat(f"{date_str}T{time_str}")

        if target_dt <= datetime.now():
            return "That time is already in the past."

        task_name    = f"JARVISReminder_{target_dt.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        safe_message = str(message).strip()[:1000]

        python_exe = sys.executable
        if python_exe.lower().endswith("python.exe"):
            pythonw = python_exe.replace("python.exe", "pythonw.exe")
            if os.path.exists(pythonw):
                python_exe = pythonw

        temp_dir      = os.environ.get("TEMP", "C:\\Temp")
        notify_script = os.path.join(temp_dir, f"{task_name}.pyw")
        project_root  = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..")
        )

        script_code = f'''import sys, os, time
sys.path.insert(0, {project_root!r})
message = {safe_message!r}

try:
    import win32com.client
    voice = win32com.client.Dispatch("SAPI.SpVoice")
    voice.Speak("Reminder. " + message, 0)
except Exception:
    pass

try:
    import winsound
    for freq in [800, 1000, 1200]:
        winsound.Beep(freq, 200)
        time.sleep(0.1)
except Exception:
    pass

try:
    import win32com.client
    win32com.client.Dispatch("WScript.Shell").Popup(message, 15, "JARVIS Reminder", 0x40)
except Exception:
    pass  # Speech/beeps remain available; never leave an indefinite modal task.

time.sleep(3)
try:
    os.remove(__file__)
except Exception:
    pass
'''
        with open(notify_script, "w", encoding="utf-8") as f:
            f.write(script_code)

        xml_content = f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>JARVIS Reminder: {escape(safe_message)}</Description>
  </RegistrationInfo>
  <Triggers>
    <TimeTrigger>
      <StartBoundary>{target_dt.strftime("%Y-%m-%dT%H:%M:%S")}</StartBoundary>
      <Enabled>true</Enabled>
    </TimeTrigger>
  </Triggers>
  <Actions>
    <Exec>
      <Command>{escape(python_exe)}</Command>
      <Arguments>"{escape(notify_script)}"</Arguments>
    </Exec>
  </Actions>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <WakeToRun>true</WakeToRun>
    <ExecutionTimeLimit>PT5M</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Principals>
    <Principal>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
</Task>'''

        xml_path = os.path.join(temp_dir, f"{task_name}.xml")
        with open(xml_path, "w", encoding="utf-16") as f:
            f.write(xml_content)

        result = subprocess.run(
            ["schtasks", "/Create", "/TN", task_name, "/XML", xml_path, "/F"],
            capture_output=True, text=True, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )

        try:
            os.remove(xml_path)
        except Exception:
            pass

        if result.returncode != 0:
            err = result.stderr.strip() or result.stdout.strip()
            print(f"[Reminder] ❌ schtasks failed: {err}")
            try:
                os.remove(notify_script)
            except Exception:
                pass
            return "I couldn't schedule the reminder due to a system error."

        if player:
            player.write_log(f"[reminder] set for {date_str} {time_str}")

        return f"Reminder set for {target_dt.strftime('%B %d at %I:%M %p')}."

    except ValueError:
        return "I couldn't understand that date or time format."

    except Exception as e:
        return f"Something went wrong while scheduling the reminder: {str(e)[:80]}"


def reminder(parameters: dict, response=None, player=None, session_memory=None, **kwargs) -> dict:
    p = dict(parameters or {})
    if not p.get("date") or not p.get("time"):
        from core.reminder_parser import parse_reminder_query
        try:
            p.update(parse_reminder_query(p.get("query", "")))
        except ValueError as exc:
            return {"success": False, "verified": False, "requires_details": True, "message": str(exc)}
    message = _schedule_reminder(p, response=response, player=player, session_memory=session_memory)
    success = message.startswith("Reminder set for")
    return {"success": success, "verified": success, "message": message, "date": p.get("date"), "time": p.get("time")}
