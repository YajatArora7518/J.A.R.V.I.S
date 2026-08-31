# actions/desktop_shortcut.py
# Windows Desktop Shortcut & Icon Manager for JARVIS

import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent
ICON_PATH = BASE_DIR / "assets" / "icons" / "jarvis.ico"
SHORTCUT_NAME = "J.A.R.V.I.S.lnk"


def get_desktop_paths() -> list[Path]:
    """Finds standard and OneDrive desktop directory paths."""
    user_home = Path.home()
    desktops = [
        user_home / "Desktop",
        user_home / "OneDrive" / "Desktop",
    ]
    return [d for d in desktops if d.exists()]


def setup_desktop_shortcut(action: str = "update", **kwargs) -> Dict[str, Any]:
    """
    Creates or updates the Windows Desktop shortcut pointing to JARVIS and jarvis.ico.
    Actions: 'update' | 'create' | 'status'
    """
    action = (action or "update").lower().strip()
    desktops = get_desktop_paths()

    if not desktops:
        return {"success": False, "tool": "desktop_shortcut", "result": None, "error": "Desktop directory not found."}

    if not ICON_PATH.exists():
        return {"success": False, "tool": "desktop_shortcut", "result": None, "error": f"Icon file missing at {ICON_PATH}"}

    target_bat = BASE_DIR / "start_jarvis.bat"
    target_exe = shutil_which_jarvis() or str(target_bat)

    results = []

    for desktop in desktops:
        shortcut_path = desktop / SHORTCUT_NAME

        if action in ["update", "create"]:
            ps_script = f"""
            $WshShell = New-Object -ComObject WScript.Shell
            $Shortcut = $WshShell.CreateShortcut('{shortcut_path}')
            $Shortcut.TargetPath = '{target_exe}'
            $Shortcut.WorkingDirectory = '{BASE_DIR}'
            $Shortcut.IconLocation = '{ICON_PATH}'
            $Shortcut.Description = 'J.A.R.V.I.S. Windows AI Assistant'
            $Shortcut.Save()
            """
            try:
                subprocess.run(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                    capture_output=True, text=True, check=True
                )
                results.append(str(shortcut_path))
            except Exception as e:
                return {"success": False, "tool": "desktop_shortcut", "result": None, "error": f"Failed PowerShell shortcut creation: {e}"}

        elif action == "status":
            exists = shortcut_path.exists()
            results.append(f"{shortcut_path} ({'EXISTS' if exists else 'MISSING'})")

    return {
        "success": True,
        "tool": "desktop_shortcut",
        "result": f"Desktop shortcut operation '{action}' complete on: {', '.join(results)}",
        "icon_path": str(ICON_PATH),
        "target_path": target_exe,
        "error": None
    }


def shutil_which_jarvis() -> str | None:
    import shutil
    return shutil.which("jarvis") or shutil.which("jarvis.exe")
