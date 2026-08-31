# actions/open_app.py
# JARVIS — Intelligent Application & Service Launcher (Desktop Discovery + Default Browser Web Fallback)

import os
import sys
import time
import glob
import platform
import shutil
import subprocess
import webbrowser
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

from actions.app_registry import resolve_app, find_app_path_in_registry, normalize_app_name, APP_REGISTRY
from core.verification import verify_app_launched
from actions.web_registry import resolve_website_url, open_website_in_yajat_profile
from actions.chrome_profile import chrome_profile, open_url_in_yajat_chrome


def _is_process_running(process_names: list[str]) -> bool:
    """Checks if any process matching process_names is currently running."""
    if not _HAS_PSUTIL or not process_names:
        return False

    targets = [t.lower().replace(".exe", "").strip() for t in process_names if t]
    try:
        for proc in psutil.process_iter(["name"]):
            pname = (proc.info.get("name") or "").lower().replace(".exe", "").strip()
            if not pname or len(pname) < 2:
                continue
            for t in targets:
                if t and len(t) >= 2 and (t in pname or pname in t):
                    return True
    except Exception:
        pass
    return False


def _focus_existing_window(process_names: list[str], app_name: str = "") -> bool:
    """
    Checks if a window belonging to process_names is running, and brings it to the foreground
    instead of spawning duplicate process instances.
    """
    if platform.system() != "Windows":
        return False

    targets = [t.lower().replace(".exe", "").strip() for t in process_names if t]
    if app_name:
        targets.append(app_name.lower().strip())

    for t in targets:
        if not t or len(t) < 2:
            continue
        try:
            ps_cmd = f'(New-Object -ComObject WScript.Shell).AppActivate("{t}")'
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=2)
            if "True" in res.stdout:
                print(f"[open_app] Focused existing window via AppActivate for '{t}'")
                return True
        except Exception:
            pass

    try:
        import ctypes
        user32 = ctypes.windll.user32
        found_hwnds = []

        def enum_win_cb(hwnd, lparam):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value.lower()
                    for t in targets:
                        if t and t in title:
                            found_hwnds.append(hwnd)
                            break
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        user32.EnumWindows(WNDENUMPROC(enum_win_cb), 0)

        if found_hwnds:
            hwnd = found_hwnds[0]
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
            print(f"[open_app] Focused existing window via EnumWindows for '{app_name}'")
            return True
    except Exception as e:
        print(f"[open_app] Focus window exception: {e}")

    return False


def _launch_desktop_windows(entry: Dict[str, Any]) -> Tuple[bool, str, str]:
    """
    7-Step Windows Application Discovery Order:
    STEP 0: Focus running process window (prevent duplicate process instances)
    STEP 1: Windows protocol handlers (e.g. whatsapp:, discord:, tg:, spotify:, ms-settings:, ms-outlook:)
    STEP 2: PATH executable discovery (shutil.which)
    STEP 3: Windows Registry App Paths (HKCU & HKLM App Paths with WOW64 support)
    STEP 4: Common installation directories (%LOCALAPPDATA%, %PROGRAMFILES%, %PROGRAMFILES(X86)%)
    STEP 5: Start Menu shortcuts (.lnk files in APPDATA & PROGRAMDATA Start Menu)
    STEP 6: UWP / Windows Store AppUserModelID shell launch
    STEP 7: Handled outside by web_url fallback
    """
    app_name = entry["name"]
    executables = entry.get("executables", [])
    protocols = entry.get("protocols", [])
    install_dirs = entry.get("install_dirs", [])
    process_names = entry.get("process_names", executables)

    # STEP 0: Check if process is already running -> FOCUS existing window
    if _is_process_running(process_names):
        print(f"[open_app] STEP 0: Process for '{app_name}' is already running. Attempting window focus.")
        focused = _focus_existing_window(process_names, app_name)
        if focused:
            return True, "desktop", f"Focused active {app_name} Desktop window"
        else:
            return True, "desktop", f"{app_name} Desktop is active"

    # STEP 1: Windows Protocol Handlers (Safe local system protocols only)
    for proto in protocols:
        if proto and ":" in proto:
            proto_lower = proto.lower()
            if any(bad in proto_lower for bad in ["customdesktopapp", "ms-windows-store", "http", "https"]):
                continue
            try:
                print(f"[open_app] STEP 1: Trying Windows protocol handler '{proto}'")
                os.startfile(proto)
                time.sleep(1.2)
                res = verify_app_launched(app_name, timeout=2.0)
                if res["verified"] or _is_process_running(process_names):
                    return True, "desktop", f"{app_name} Desktop launched via protocol handler '{proto}'"
            except Exception as e:
                print(f"[open_app] Protocol '{proto}' error: {e}")

    # STEP 2: PATH Executable Discovery (shutil.which)
    for exe in executables:
        if exe:
            bin_path = shutil.which(exe) or shutil.which(f"{exe}.exe")
            if bin_path:
                try:
                    print(f"[open_app] STEP 2: Found binary on PATH: '{bin_path}'")
                    subprocess.Popen([bin_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    res = verify_app_launched(app_name, timeout=2.5)
                    if res["verified"] or _is_process_running(process_names):
                        return True, "desktop", f"{app_name} Desktop launched ({bin_path})"
                except Exception as e:
                    print(f"[open_app] PATH binary launch error: {e}")

    # STEP 3: Windows Registry App Paths (HKCU & HKLM App Paths)
    for exe in executables:
        if exe:
            reg_path = find_app_path_in_registry(exe)
            if reg_path:
                try:
                    print(f"[open_app] STEP 3: Found executable in Registry: '{reg_path}'")
                    subprocess.Popen([reg_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    res = verify_app_launched(app_name, timeout=2.5)
                    if res["verified"] or _is_process_running(process_names):
                        return True, "desktop", f"{app_name} Desktop launched ({reg_path})"
                except Exception as e:
                    print(f"[open_app] Registry binary launch error: {e}")

    # STEP 4: Common Installation Locations
    search_roots = []
    local_appdata = os.environ.get("LOCALAPPDATA")
    program_files = os.environ.get("ProgramFiles")
    program_files_x86 = os.environ.get("ProgramFiles(x86)")
    user_profile = os.environ.get("USERPROFILE")

    if local_appdata:
        search_roots.extend([os.path.join(local_appdata, "Programs"), local_appdata, os.path.join(local_appdata, "WhatsApp")])
    if program_files:
        search_roots.append(program_files)
    if program_files_x86:
        search_roots.append(program_files_x86)
    if user_profile:
        search_roots.extend([
            os.path.join(user_profile, "AppData", "Roaming"),
            os.path.join(user_profile, "AppData", "Local", "Programs"),
            os.path.join(user_profile, "AppData", "Local", "WhatsApp")
        ])

    for root in search_roots:
        if not os.path.exists(root):
            continue
        for adir in install_dirs:
            for exe in executables:
                candidates = [
                    os.path.join(root, adir, exe),
                    os.path.join(root, adir, f"{exe}.exe"),
                    os.path.join(root, exe),
                    os.path.join(root, f"{exe}.exe")
                ]
                for cand in candidates:
                    if os.path.exists(cand) and os.path.isfile(cand):
                        try:
                            print(f"[open_app] STEP 4: Found candidate in install dir: '{cand}'")
                            subprocess.Popen([cand], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            res = verify_app_launched(app_name, timeout=3.0)
                            if res["verified"] or _is_process_running(process_names):
                                return True, "desktop", f"{app_name} Desktop launched ({cand})"
                        except Exception as e:
                            print(f"[open_app] Candidate launch error: {e}")

    # STEP 5: Start Menu Shortcuts (.lnk Search)
    sm_paths = [
        os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
        os.path.expandvars(r"%ALLUSERSPROFILE%\Microsoft\Windows\Start Menu\Programs"),
    ]
    clean_name = app_name.lower().replace(" ", "")
    for sm in sm_paths:
        if os.path.exists(sm):
            try:
                for lnk in glob.glob(os.path.join(sm, "**", "*.lnk"), recursive=True):
                    lnk_base = os.path.basename(lnk).lower().replace(" ", "").replace(".lnk", "")
                    if lnk_base and len(lnk_base) >= 3 and (clean_name in lnk_base or lnk_base in clean_name):
                        if os.path.exists(lnk) and os.path.isfile(lnk):
                            try:
                                print(f"[open_app] STEP 5: Found Start Menu shortcut: '{lnk}'")
                                os.startfile(lnk)
                                time.sleep(1.5)
                                res = verify_app_launched(app_name, timeout=3.0)
                                if res["verified"] or _is_process_running(process_names):
                                    return True, "desktop", f"{app_name} Desktop launched via Start Menu shortcut"
                            except Exception as e:
                                print(f"[open_app] Shortcut launch error: {e}")
            except Exception:
                pass

    # STEP 6: UWP / Windows Store AppUserModelID shell launch
    app_ids = entry.get("uwp_app_ids", [])
    for app_id in app_ids:
        try:
            print(f"[open_app] STEP 6: Trying UWP AppUserModelID '{app_id}'")
            os.startfile(f"shell:AppsFolder\\{app_id}")
            time.sleep(1.5)
            res = verify_app_launched(app_name, timeout=3.0)
            if res["verified"] or _is_process_running(process_names):
                return True, "desktop", f"{app_name} Desktop launched via UWP shell"
        except Exception as e:
            print(f"[open_app] UWP launch error: {e}")

    return False, "", f"Desktop application '{app_name}' not found on local system"


def open_app_structured(input_name: str) -> Dict[str, Any]:
    """
    Executes Universal Installed Application Discovery & Verification pipeline:
    {
        "success": bool,
        "app": str,
        "mode": "desktop" | "web_fallback" | "none",
        "message": str
    }
    """
    if not input_name or not input_name.strip():
        return {"success": False, "app": "", "mode": "none", "message": "Please specify an application or service."}

    raw_clean = input_name.lower().strip()

    # Check if user EXPLICITLY requested Web / Web URL
    # (e.g. "whatsapp web", "open whatsapp web", "discord web", "youtube.com", "open google.com")
    is_explicit_web = (
        "web" in raw_clean.split() or 
        raw_clean.endswith(".com") or 
        raw_clean.endswith(".org") or 
        raw_clean.endswith(".net") or
        raw_clean.startswith("http://") or
        raw_clean.startswith("https://")
    )

    if is_explicit_web:
        resolved_web = resolve_website_url(input_name)
        if resolved_web:
            web_res = open_website_in_yajat_profile(input_name)
            if web_res.get("success"):
                return {
                    "success": True,
                    "app": resolved_web["name"],
                    "mode": "web_fallback",
                    "message": web_res.get("message", f"Opening {resolved_web['name']} in your Yajat Chrome profile.")
                }
            else:
                return {
                    "success": False,
                    "app": input_name,
                    "mode": "none",
                    "message": web_res.get("message", "Yajat Chrome profile was not found.")
                }

    # APP-FIRST POLICY: Universal Application Resolver
    if any(k in raw_clean for k in ["whatsapp", "whats app"]):
        from actions.windows_whatsapp_desktop_executor import set_whatsapp_user_action_requested, windows_whatsapp_desktop_executor
        set_whatsapp_user_action_requested(True)
        w_res = windows_whatsapp_desktop_executor.focus_installed_whatsapp_desktop()
        return {
            "success": w_res[0],
            "app": "WhatsApp",
            "mode": "desktop",
            "message": w_res[1]
        }

    from actions.universal_app_resolver import default_app_resolver
    from actions.application_launch_executor import default_launch_executor

    descriptor = default_app_resolver.resolve_application(input_name)

    # Special handling for Google Chrome: must use Yajat profile
    if descriptor and (descriptor.normalized_name == "chrome" or raw_clean in ["chrome", "google chrome", "browser"]):
        c_res = chrome_profile(action="open", profile_name="Yajat")
        if c_res.get("success"):
            return {
                "success": True,
                "app": "Google Chrome (Yajat Profile)",
                "mode": "desktop",
                "message": c_res.get("message", "Opened Google Chrome with Yajat profile.")
            }

    if descriptor:
        act_res = default_launch_executor.launch_application(input_name, descriptor=descriptor)
        if act_res.status == "COMPLETED" and act_res.verification_passed:
            return {
                "success": True,
                "app": descriptor.display_name,
                "mode": "desktop",
                "message": act_res.message or f"Opened {descriptor.display_name}.",
                "action_result": act_res
            }
        else:
            return {
                "success": False,
                "app": descriptor.display_name,
                "mode": "none",
                "message": act_res.message or f"Failed to launch {descriptor.display_name}.",
                "action_result": act_res
            }

    # CRITICAL RULE: Local App Not Found -> NO automatic Store or Web Search fallback!
    print(f"[open_app] Application '{input_name}' not found locally. Honest failure returned.")
    return {
        "success": False,
        "app": input_name,
        "mode": "none",
        "message": f"I couldn't find an installed application matching '{input_name}'."
    }


def open_app(
    parameters: Optional[Dict[str, Any]] = None,
    response: Any = None,
    player: Any = None,
    session_memory: Any = None,
    **kwargs
) -> str:
    """
    Tool handler for JARVIS tool registry.
    Triggers structured execution, logs structured activity to player, drives 3D Core state transitions,
    and returns concise verbal response for TTS.
    """
    params = parameters or kwargs or {}
    raw_name = (params.get("app_name") or params.get("name") or "").strip()

    if player and hasattr(player, "set_state"):
        try:
            player.set_state("EXECUTING")
        except Exception:
            pass

    res = open_app_structured(raw_name)
    app_name = res.get("app", raw_name.title())

    # Log structured Activity Log to UI
    if player and hasattr(player, "write_log"):
        player.write_log(f"COMMAND\nOPEN {app_name.upper()}")
        player.write_log(f"RESOLUTION\n{app_name}")

        if res["success"]:
            player.write_log(f"EXECUTION\n{app_name} Desktop launched")
            player.write_log("RESULT\nSUCCESS")
        else:
            player.write_log(f"EXECUTION\nUnable to launch {app_name}")
            player.write_log("RESULT\nERROR")

    # Update 3D Core State Machine
    if player and hasattr(player, "set_state"):
        try:
            if res["success"]:
                player.set_state("SUCCESS")
            else:
                player.set_state("RECOVERING")
        except Exception:
            pass

    # Concise Verbal Response for Voice TTS & Tool Registry Verification
    if res["success"]:
        return {
            "success": True,
            "message": f"Opening {app_name}.",
            "app": app_name,
            "mode": res.get("mode", "desktop")
        }

    return {
        "success": False,
        "message": f"I couldn't find or launch {app_name}, sir.",
        "app": app_name,
        "mode": "none"
    }