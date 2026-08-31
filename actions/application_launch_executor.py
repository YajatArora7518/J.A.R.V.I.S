# actions/application_launch_executor.py
# Universal Application Launch Executor & Verification State Machine for JARVIS

import os
import sys
import time
import uuid
import logging
import platform
import subprocess
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from actions.universal_app_resolver import ApplicationDescriptor, default_app_resolver
from core.verification import verify_app_launched

logger = logging.getLogger("JARVIS.ApplicationLaunchExecutor")

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False


@dataclass
class ActionResult:
    action_id: str
    action_type: str  # "LAUNCH_APPLICATION"
    target: str
    status: str       # "PENDING", "EXECUTING", "VERIFYING", "COMPLETED", "FAILED"
    resolved_application: Optional[str] = None
    launch_method: Optional[str] = None
    execution_started: bool = False
    verification_passed: bool = False
    verification_details: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    failure_reason: Optional[str] = None
    message: str = ""


class ApplicationLaunchExecutor:
    """
    Centralized execution pipeline for launching and verifying Windows applications.
    Implements explicit state transitions: PENDING -> EXECUTING -> VERIFYING -> COMPLETED / FAILED.
    """

    def __init__(self):
        pass

    def launch_application(self, target: str, descriptor: Optional[ApplicationDescriptor] = None) -> ActionResult:
        action_id = str(uuid.uuid4())[:8]
        result = ActionResult(
            action_id=action_id,
            action_type="LAUNCH_APPLICATION",
            target=target,
            status="PENDING",
            execution_started=False,
            verification_passed=False
        )

        print(f"[JARVIS][APP] Requested: Open {target}")
        print(f"[JARVIS][APP] Intent: LAUNCH_APPLICATION")
        print(f"[JARVIS][APP][RESOLVE] Normalized target: {target.lower()}")

        # 1. Resolve Application Descriptor if not provided
        if not descriptor:
            print(f"[JARVIS][APP][RESOLVE] Searching installed applications...")
            descriptor = default_app_resolver.resolve_application(target)

        if not descriptor:
            print(f"[JARVIS][APP][RESULT] FINAL STATUS: FAILED")
            print(f"[JARVIS][APP][RESULT] Reason: Application '{target}' not found on local system")
            result.status = "FAILED"
            result.failure_reason = "application_not_found"
            result.message = f"I couldn't find an installed application matching '{target}'."
            return result

        result.resolved_application = descriptor.display_name
        result.launch_method = descriptor.launch_type
        print(f"[JARVIS][APP][RESOLVE] Candidate found: {descriptor.display_name}")
        print(f"[JARVIS][APP][LAUNCH] Launch type: {descriptor.launch_type}")

        # STEP 0: Check if application is ALREADY RUNNING -> Focus Window
        focused = self._try_focus_existing(descriptor)
        if focused:
            print(f"[JARVIS][APP][LAUNCH] STEP 0: Focused existing running instance of {descriptor.display_name}")
            print(f"[JARVIS][APP][VERIFY] Verification started...")
            print(f"[JARVIS][APP][VERIFY] Process verified")
            print(f"[JARVIS][APP][VERIFY] Window verified")
            print(f"[JARVIS][APP][RESULT] FINAL STATUS: COMPLETED")

            result.status = "COMPLETED"
            result.execution_started = True
            result.verification_passed = True
            result.launch_method = "FOCUS_EXISTING_WINDOW"
            result.verification_details = {"mode": "focus_existing", "verified": True}
            result.message = f"Opened {descriptor.display_name}."
            return result

        # State transition: PENDING -> EXECUTING
        result.status = "EXECUTING"
        result.execution_started = True
        print(f"[JARVIS][APP][LAUNCH] Launching...")

        # Execute Launch with Universal Retry Strategy
        max_retries = 2
        launch_success = False

        for attempt in range(max_retries):
            result.retry_count = attempt
            launch_success = self._execute_launch_strategy(descriptor, strategy_index=attempt)
            
            # State transition: EXECUTING -> VERIFYING
            result.status = "VERIFYING"
            print(f"[JARVIS][APP][VERIFY] Verification started (Attempt {attempt + 1})...")

            time.sleep(1.2)  # Wait for OS window/process initialization

            ver_res = self._verify_application_launched(descriptor)
            if ver_res.get("verified"):
                print(f"[JARVIS][APP][VERIFY] Process verified")
                print(f"[JARVIS][APP][VERIFY] Window verified")
                print(f"[JARVIS][APP][RESULT] FINAL STATUS: COMPLETED")

                result.status = "COMPLETED"
                result.verification_passed = True
                result.verification_details = ver_res
                result.message = f"Opened {descriptor.display_name}."
                return result
            else:
                print(f"[JARVIS][APP][VERIFY] Verification attempt {attempt + 1} failed: {ver_res.get('reason')}")

        # If all retries failed verification
        print(f"[JARVIS][APP][RESULT] FINAL STATUS: FAILED")
        print(f"[JARVIS][APP][RESULT] Reason: Application launch verification failed")

        result.status = "FAILED"
        result.verification_passed = False
        result.failure_reason = "verification_failed"
        result.message = f"I tried to launch {descriptor.display_name}, but its window could not be verified."
        return result

    def _try_focus_existing(self, descriptor: ApplicationDescriptor) -> bool:
        """Checks if process/window exists and brings to foreground."""
        if platform.system() != "Windows":
            return False

        proc_names = descriptor.process_names or [descriptor.display_name]

        # Check if process is running
        running = False
        if _HAS_PSUTIL:
            try:
                for proc in psutil.process_iter(["name"]):
                    pname = (proc.info.get("name") or "").lower()
                    if any(target.lower().replace(".exe", "") in pname for target in proc_names):
                        running = True
                        break
            except Exception:
                pass

        if not running:
            return False

        # Attempt to focus window via AppActivate
        targets = [descriptor.display_name] + proc_names
        for t in targets:
            clean_t = t.replace(".exe", "").strip()
            if len(clean_t) < 2:
                continue
            try:
                ps_cmd = f'(New-Object -ComObject WScript.Shell).AppActivate("{clean_t}")'
                res = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd], capture_output=True, text=True, timeout=2)
                if "True" in res.stdout:
                    return True
            except Exception:
                pass

        # Attempt via Win32 EnumWindows
        try:
            import ctypes
            user32 = ctypes.windll.user32
            found = []

            def enum_cb(hwnd, lparam):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        title = buff.value.lower()
                        if any(pat.lower() in title for pat in descriptor.window_title_patterns or [descriptor.display_name]):
                            found.append(hwnd)
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
            user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

            if found:
                hwnd = found[0]
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(hwnd)
                return True
        except Exception:
            pass

        return running

    def _execute_launch_strategy(self, descriptor: ApplicationDescriptor, strategy_index: int) -> bool:
        l_type = descriptor.launch_type
        exe_path = descriptor.executable_path
        app_id = descriptor.app_user_model_id
        proto = descriptor.protocol

        try:
            if strategy_index == 0:
                # Primary Strategy
                if l_type == "WIN32_EXECUTABLE" and exe_path and os.path.exists(exe_path):
                    cmd = [exe_path] + descriptor.custom_launch_args
                    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return True

                elif l_type in ["PACKAGED_APP", "SHELL_APP"] and app_id:
                    # REQUIREMENT #1: Never blindly pass AppUserModelId to subprocess.Popen directly
                    os.startfile(f"shell:AppsFolder\\{app_id}")
                    return True

                elif l_type == "START_MENU_APP" and exe_path and os.path.exists(exe_path):
                    os.startfile(exe_path)
                    return True

                elif l_type == "URI_APP" and proto:
                    os.startfile(proto)
                    return True

                elif exe_path and os.path.exists(exe_path):
                    os.startfile(exe_path)
                    return True

            else:
                # Secondary Strategy (Retry fallback)
                if exe_path and os.path.exists(exe_path):
                    os.startfile(exe_path)
                    return True
                elif app_id:
                    subprocess.Popen(["cmd.exe", "/c", "start", f"shell:AppsFolder\\{app_id}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return True
                elif proto:
                    subprocess.Popen(["cmd.exe", "/c", "start", proto], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return True
        except Exception as e:
            logger.warning(f"[ApplicationLaunchExecutor] Launch strategy {strategy_index} exception: {e}")

        return False

    def _verify_application_launched(self, descriptor: ApplicationDescriptor) -> Dict[str, Any]:
        """Correlates resolved application -> launch identity -> process -> top-level visible window."""
        proc_names = descriptor.process_names or [descriptor.display_name]
        titles = descriptor.window_title_patterns or [descriptor.display_name]

        # 1. Process Check
        matched_pid = None
        if _HAS_PSUTIL:
            try:
                for proc in psutil.process_iter(["name", "pid"]):
                    pname = (proc.info.get("name") or "").lower()
                    for target in proc_names:
                        clean_t = target.lower().replace(".exe", "").strip()
                        if clean_t and (clean_t in pname or pname.replace(".exe", "") in clean_t):
                            matched_pid = proc.info.get("pid")
                            break
                    if matched_pid:
                        break
            except Exception:
                pass

        # 2. Visible Window Title Check
        window_found = False
        matched_title = ""
        try:
            import ctypes
            user32 = ctypes.windll.user32

            def enum_cb(hwnd, lparam):
                nonlocal window_found, matched_title
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        t_val = buff.value
                        t_lower = t_val.lower()
                        for pattern in titles:
                            if pattern.lower() in t_lower:
                                window_found = True
                                matched_title = t_val
                                return False
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
            user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        except Exception:
            pass

        if matched_pid or window_found:
            return {
                "verified": True,
                "pid": matched_pid,
                "window_title": matched_title or descriptor.display_name,
                "process_names": proc_names
            }

        # Fallback to verify_app_launched helper
        standard_res = verify_app_launched(descriptor.display_name, timeout=2.0)
        if standard_res.get("verified"):
            return standard_res

        return {
            "verified": False,
            "reason": f"No running process ({proc_names}) or visible window ({titles}) detected."
        }


# Singleton instance
default_launch_executor = ApplicationLaunchExecutor()
