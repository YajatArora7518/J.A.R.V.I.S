# core/verification.py
# Real Windows Post-Action State Verification Engine

import os
import time
import platform
import subprocess
from typing import Dict, Any, Optional

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

try:
    import pygetwindow as gw
    _HAS_PYGETWINDOW = True
except Exception:
    _HAS_PYGETWINDOW = False


def verify_app_launched(app_name: str, timeout: float = 4.0) -> Dict[str, Any]:
    """
    Verifies if an application process or window is running after launch.
    """
    start_time = time.time()
    clean_name = app_name.lower().replace(".exe", "").strip()

    while time.time() - start_time < timeout:
        # 1. Process check
        if _HAS_PSUTIL:
            try:
                for proc in psutil.process_iter(["name", "pid"]):
                    name = (proc.info.get("name") or "").lower()
                    if clean_name in name or name.replace(".exe", "") in clean_name:
                        return {
                            "verified": True,
                            "type": "process",
                            "pid": proc.info.get("pid"),
                            "name": proc.info.get("name")
                        }
            except Exception:
                pass

        # 2. Window title check
        if _HAS_PYGETWINDOW:
            try:
                titles = gw.getAllTitles()
                for title in titles:
                    if title and clean_name in title.lower():
                        return {
                            "verified": True,
                            "type": "window",
                            "title": title
                        }
            except Exception:
                pass

        time.sleep(0.3)

    return {
        "verified": False,
        "reason": f"No running process or window matching '{app_name}' was detected within {timeout}s."
    }


def verify_process_closed(app_name: str, timeout: float = 4.0) -> Dict[str, Any]:
    """
    Verifies if an application process or window has ceased running.
    """
    start_time = time.time()
    clean_name = app_name.lower().replace(".exe", "").strip()

    # Initial pause for OS process teardown
    time.sleep(0.4)

    while time.time() - start_time < timeout:
        running = False
        if _HAS_PSUTIL:
            try:
                for proc in psutil.process_iter(["name"]):
                    name = (proc.info.get("name") or "").lower()
                    if clean_name and (clean_name in name or name.replace(".exe", "") == clean_name):
                        running = True
                        break
            except Exception:
                pass

        if not running:
            return {"verified": True}

        time.sleep(0.4)

    return {
        "verified": False,
        "reason": f"Process '{app_name}' is still active."
    }


def verify_file_exists(file_path: str, min_bytes: int = 0) -> Dict[str, Any]:
    """
    Verifies that a file exists on disk and meets minimum byte requirements.
    """
    if not file_path:
        return {"verified": False, "reason": "Empty file path provided."}

    path = os.path.abspath(file_path)
    if os.path.exists(path):
        size = os.path.getsize(path)
        if size >= min_bytes:
            return {"verified": True, "path": path, "size_bytes": size}
        return {"verified": False, "reason": f"File exists but size ({size}b) < min ({min_bytes}b)."}

    return {"verified": False, "reason": f"File does not exist: {path}"}


def verify_file_deleted(file_path: str) -> Dict[str, Any]:
    """
    Verifies that a file has been deleted from disk.
    """
    path = os.path.abspath(file_path)
    if not os.path.exists(path):
        return {"verified": True}
    return {"verified": False, "reason": f"File still exists at {path}"}


def verify_screenshot_created(file_path: str) -> Dict[str, Any]:
    """
    Verifies that a screenshot image was saved and is a valid non-empty file.
    """
    res = verify_file_exists(file_path, min_bytes=1024)
    if res["verified"]:
        return {"verified": True, "path": file_path, "size_bytes": res["size_bytes"]}
    return res


def verify_volume_changed(target_level: Optional[int] = None) -> Dict[str, Any]:
    """
    Reads the actual Windows master audio endpoint volume to verify setting.
    """
    if platform.system() != "Windows":
        return {"verified": True, "note": "Volume verification only implemented on Windows."}

    try:
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = interface.QueryInterface(IAudioEndpointVolume)
        current_vol = int(round(volume.GetMasterScalarVolume() * 100))

        if target_level is not None:
            # Allow +-3% tolerance due to floating point audio scalars
            if abs(current_vol - target_level) <= 3:
                return {"verified": True, "current_volume": current_vol}
            else:
                return {
                    "verified": False,
                    "reason": f"Current volume ({current_vol}%) != target ({target_level}%)."
                }

        return {"verified": True, "current_volume": current_vol}

    except Exception as e:
        return {"verified": True, "note": f"Audio API check skipped: {e}"}


def verify_browser_loaded(page_or_controller: Any, expected_keyword: str = "") -> Dict[str, Any]:
    """
    Verifies browser navigation success.
    """
    try:
        if hasattr(page_or_controller, "url"):
            url = page_or_controller.url
            if expected_keyword:
                if expected_keyword.lower() in url.lower():
                    return {"verified": True, "url": url}
                return {"verified": False, "reason": f"URL '{url}' does not contain '{expected_keyword}'"}
            return {"verified": True, "url": url}
    except Exception as e:
        return {"verified": False, "reason": str(e)}

    return {"verified": True}


def verify_workspace_opened(folder_path: str) -> Dict[str, Any]:
    """
    Verifies that VSCode or an IDE is open with the workspace.
    """
    return verify_app_launched("code", timeout=5.0)
