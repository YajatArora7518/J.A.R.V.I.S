# actions/windows_uac_bridge.py
# Legitimate Windows UAC Elevation Bridge
# Executes administrative operations via official Windows UAC ("runas") prompts.
# NEVER bypasses Windows UAC or security controls.

import os
import sys
import ctypes
import tempfile
import subprocess
import time
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("JARVIS.WindowsUACBridge")

def is_running_as_admin() -> bool:
    """Checks whether the current Python process has Administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception as e:
        logger.debug(f"IsUserAnAdmin check failed: {e}")
        return False

def execute_elevated_command(
    executable: str,
    args: str = "",
    cwd: Optional[str] = None,
    timeout: int = 30
) -> Dict[str, Any]:
    """
    Executes a process with elevated Administrator privileges via official Windows UAC ("runas").
    Captures stdout, stderr, and exit code using a temporary output file.
    """
    if is_running_as_admin():
        # Already elevated, run directly via subprocess
        try:
            full_cmd = f'"{executable}" {args}' if args else f'"{executable}"'
            proc = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=timeout,
                shell=True
            )
            return {
                "success": proc.returncode == 0,
                "exit_code": proc.returncode,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
                "elevated": True,
                "uac_prompted": False
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Elevated execution timed out after {timeout} seconds.",
                "elevated": True,
                "uac_prompted": False
            }
        except Exception as ex:
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": str(ex),
                "elevated": True,
                "uac_prompted": False
            }

    # Standard non-elevated user process: trigger official Windows UAC prompt via PowerShell Start-Process -Verb RunAs
    temp_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "JARVIS", "workspace")
    os.makedirs(temp_dir, exist_ok=True)
    out_file = os.path.join(temp_dir, f"uac_out_{int(time.time()*1000)}.log")

    try:
        # Wrap execution in PowerShell script that redirects output to file and captures exit code
        ps_cmd = (
            f'$proc = Start-Process -FilePath "{executable}" '
            f'-ArgumentList "{args}" '
            f'-RedirectStandardOutput "{out_file}" '
            f'-RedirectStandardError "{out_file}.err" '
            f'-Verb RunAs -PassThru -Wait; '
            f'exit $proc.ExitCode'
        )
        
        logger.info(f"[UACBridge] Invoking Windows UAC elevation prompt for: {executable} {args}")
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout + 15
        )

        stdout = ""
        stderr = ""
        if os.path.exists(out_file):
            try:
                with open(out_file, "r", encoding="utf-8", errors="ignore") as f:
                    stdout = f.read().strip()
                os.remove(out_file)
            except Exception:
                pass

        err_file = f"{out_file}.err"
        if os.path.exists(err_file):
            try:
                with open(err_file, "r", encoding="utf-8", errors="ignore") as f:
                    stderr = f.read().strip()
                os.remove(err_file)
            except Exception:
                pass

        if not stderr and proc.stderr:
            stderr = proc.stderr.strip()

        return {
            "success": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "elevated": True,
            "uac_prompted": True
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"UAC elevated execution timed out after {timeout} seconds or user dismissed UAC prompt.",
            "elevated": True,
            "uac_prompted": True
        }
    except Exception as e:
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"UAC elevation failed: {e}",
            "elevated": True,
            "uac_prompted": True
        }
