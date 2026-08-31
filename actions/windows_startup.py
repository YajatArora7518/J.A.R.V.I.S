# actions/windows_startup.py
# Optional Windows Startup Registration for JARVIS

import os
import sys
import winreg
from pathlib import Path
from typing import Dict, Any

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "JARVIS_AI_Assistant"


def windows_startup(action: str = "status", **kwargs) -> Dict[str, Any]:
    """
    Manages optional Windows Startup registry registration.
    Actions: 'enable' | 'disable' | 'status'
    """
    action = (action or "status").lower().strip()

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_ALL_ACCESS)
    except Exception as e:
        return {"success": False, "tool": "windows_startup", "result": None, "error": f"Failed to access registry: {e}"}

    try:
        if action == "enable":
            executable = sys.executable
            main_script = Path(__file__).resolve().parent.parent / "main.py"
            cmd = f'"{executable}" "{main_script}"'

            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(key)
            return {
                "success": True,
                "tool": "windows_startup",
                "result": "JARVIS configured to start automatically with Windows.",
                "error": None
            }

        elif action == "disable":
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
            winreg.CloseKey(key)
            return {
                "success": True,
                "tool": "windows_startup",
                "result": "JARVIS startup entry removed from Windows registry.",
                "error": None
            }

        elif action == "status":
            enabled = False
            try:
                val, _ = winreg.QueryValueEx(key, APP_NAME)
                if val:
                    enabled = True
            except FileNotFoundError:
                enabled = False
            winreg.CloseKey(key)

            return {
                "success": True,
                "tool": "windows_startup",
                "result": f"Windows Startup: {'ENABLED' if enabled else 'DISABLED'}",
                "enabled": enabled,
                "error": None
            }

    except Exception as e:
        winreg.CloseKey(key)
        return {"success": False, "tool": "windows_startup", "result": None, "error": str(e)}

    return {"success": False, "tool": "windows_startup", "result": None, "error": f"Unknown action '{action}'."}
