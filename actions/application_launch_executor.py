# actions/application_launch_executor.py
# Universal Application Launch Executor & Verification State Machine for JARVIS

import os
import sys
import time
import uuid
import logging
import platform
import re
import subprocess
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from actions.universal_app_resolver import ApplicationDescriptor, default_app_resolver

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

            ver_res = {}
            focused = False
            for check in range(24):
                ver_res = self._verify_application_launched(descriptor)
                if ver_res.get('verified'):
                    focused = self._try_focus_existing(descriptor)
                    break  # A ready window with rejected focus is not a startup delay.
                if check < 23:
                    time.sleep(0.15)
            if ver_res.get("verified") and focused:
                ver_res["foreground_verified"] = True
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
                if ver_res.get('startup_pending'):
                    break  # Do not launch another updater while this one is running.

        # If all retries failed verification
        print(f"[JARVIS][APP][RESULT] FINAL STATUS: FAILED")
        print(f"[JARVIS][APP][RESULT] Reason: Application launch verification failed")

        result.status = "FAILED"
        result.verification_passed = False
        result.failure_reason = "verification_failed"
        result.message = f"I tried to launch {descriptor.display_name}, but its window could not be verified."
        if ver_res.get('startup_pending'):
            result.failure_reason = 'startup_pending'
            result.verification_details = ver_res
            result.message = f'{descriptor.display_name} ki update/loading window dikhi; main app window abhi ready nahi hai.'
        return result

    def _candidate_windows(self, descriptor, include_startup=False):
        """Visible windows owned by exact application processes, excluding launchers."""
        if platform.system() != 'Windows' or not _HAS_PSUTIL:
            return []
        try:
            import win32gui
            import win32process
            names = {os.path.basename(name).casefold().removesuffix('.exe')
                     for name in (descriptor.process_names or [descriptor.display_name])}
            pids = {proc.info['pid'] for proc in psutil.process_iter(['pid', 'name'])
                    if (proc.info.get('name') or '').casefold().removesuffix('.exe') in names}
            windows = []
            def collect(hwnd, _):
                title = win32gui.GetWindowText(hwnd).strip()
                pid = win32process.GetWindowThreadProcessId(hwnd)[1]
                startup = re.fullmatch(re.escape(descriptor.display_name) + r'\s+(?:updater|setup|installer|loading|splash)(?:\s*[-:].*)?', title, re.I)
                if (pid in pids and title and win32gui.IsWindowVisible(hwnd)
                        and (include_startup or not startup)):
                    windows.append((hwnd, title, pid))
            if pids:
                win32gui.EnumWindows(collect, None)
            return windows
        except Exception as error:
            logger.debug('App window discovery failed: %s', error)
            return []

    def _try_focus_existing(self, descriptor: ApplicationDescriptor) -> bool:
        """Only verify a foreground window owned by the exact app process."""
        if platform.system() != "Windows" or not _HAS_PSUTIL:
            return False
        try:
            import win32gui
            import win32com.client
            for hwnd, title, pid in self._candidate_windows(descriptor):
                try:
                    if win32gui.IsIconic(hwnd):
                        win32gui.ShowWindow(hwnd, 9)
                    win32gui.SetForegroundWindow(hwnd)
                except Exception:
                    pass
                if win32gui.GetForegroundWindow() != hwnd:
                    try:
                        win32com.client.Dispatch('WScript.Shell').AppActivate(pid)
                    except Exception:
                        pass
                for _ in range(4):
                    if win32gui.GetForegroundWindow() == hwnd and not win32gui.IsIconic(hwnd):
                        return True
                    time.sleep(0.1)
        except Exception as error:
            logger.debug('App foreground verification failed: %s', error)
        return False

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
        """A running process or a browser mentioning the app is not a ready app."""
        windows = self._candidate_windows(descriptor)
        if windows:
            hwnd, title, pid = windows[0]
            return {'verified': True, 'pid': pid, 'window_title': title, 'hwnd': hwnd}
        loading = bool(self._candidate_windows(descriptor, include_startup=True))
        return {'verified': False, 'startup_pending': loading,
                'reason': 'Only a startup/updater window was found.' if loading else 'No visible application-owned main window found.'}


# Singleton instance
default_launch_executor = ApplicationLaunchExecutor()
