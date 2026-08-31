# actions/script_executor.py
# Generic Script & Program Execution Engine for JARVIS
# Supports .bat, .cmd, .ps1, .py, .js, .exe, .msi
# Dynamic interpreter detection (Python, PowerShell, Node.js)
# Workspace at %LOCALAPPDATA%\JARVIS\workspace

import os
import sys
import shutil
import subprocess
import time
import uuid
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("JARVIS.ScriptExecutor")

def get_workspace_dir() -> str:
    """Returns the dedicated JARVIS script workspace directory."""
    local_appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    workspace = os.path.join(local_appdata, "JARVIS", "workspace")
    os.makedirs(workspace, exist_ok=True)
    return workspace

def resolve_interpreter(script_type: str) -> Optional[str]:
    """Dynamically detects installed interpreters without hardcoding assumptions."""
    stype = script_type.lower().replace(".", "").strip()
    
    if stype == "py" or stype == "python":
        # Prefer current running Python executable
        if sys.executable and os.path.exists(sys.executable):
            return sys.executable
        py_path = shutil.which("python") or shutil.which("py")
        return py_path

    elif stype == "ps1" or stype == "powershell":
        pwsh = shutil.which("pwsh") or shutil.which("powershell")
        if pwsh:
            return pwsh
        default_ps = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        if os.path.exists(default_ps):
            return default_ps
        return "powershell"

    elif stype == "js" or stype == "node":
        node_path = shutil.which("node")
        if node_path:
            return node_path
        default_node = r"C:\Program Files\nodejs\node.exe"
        if os.path.exists(default_node):
            return default_node
        return None

    elif stype in ["bat", "cmd"]:
        cmd_path = os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe")
        return cmd_path

    return None

def resolve_safe_path(raw_path: str, default_dir: Optional[str] = None) -> str:
    """
    Canonicalizes path and resolves absolute path.
    Does NOT blindly reject '..'. Resolves final absolute location safely.
    """
    if not raw_path:
        raise ValueError("Empty file path provided.")
    
    expanded = os.path.expanduser(os.path.expandvars(raw_path))
    if not os.path.isabs(expanded):
        base = default_dir or get_workspace_dir()
        expanded = os.path.join(base, expanded)
    
    abs_path = os.path.abspath(expanded)
    return abs_path

def create_script(
    content: str,
    script_type: str,
    filename: Optional[str] = None,
    target_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Creates a script file in specified target_dir or default JARVIS workspace.
    """
    stype = script_type.lower().replace(".", "").strip()
    if not filename:
        filename = f"script_{uuid.uuid4().hex[:8]}.{stype}"
    elif not filename.endswith(f".{stype}"):
        filename = f"{filename}.{stype}"

    dest_dir = target_dir or get_workspace_dir()
    os.makedirs(dest_dir, exist_ok=True)
    full_path = resolve_safe_path(os.path.join(dest_dir, filename))

    try:
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

        return {
            "success": True,
            "action": "create_script",
            "target": full_path,
            "script_type": stype,
            "size_bytes": os.path.getsize(full_path),
            "message": f"Script created successfully at {full_path}.",
            "verified": True
        }
    except Exception as e:
        logger.error(f"[ScriptExecutor] Failed to create script at {full_path}: {e}")
        return {
            "success": False,
            "action": "create_script",
            "target": full_path,
            "error": str(e),
            "message": f"Failed to create script: {e}",
            "verified": False
        }

def run_script(
    file_path: str,
    args: str = "",
    timeout: int = 30,
    elevated: bool = False,
    correlation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes a .bat, .cmd, .ps1, .py, .js, .exe, or .msi file.
    Captures stdout, stderr, exit_code, and duration.
    """
    cid = correlation_id or uuid.uuid4().hex[:8]
    abs_path = resolve_safe_path(file_path)

    if not os.path.exists(abs_path):
        return {
            "success": False,
            "action": "run_script",
            "target": abs_path,
            "elevated": elevated,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Script file not found: {abs_path}",
            "verification": "FAILED (File not found)",
            "correlation_id": cid
        }

    ext = os.path.splitext(abs_path)[1].lower().replace(".", "")

    # Elevated execution request via Windows UAC Bridge
    if elevated:
        from actions.windows_uac_bridge import execute_elevated_command
        interp = resolve_interpreter(ext)
        if ext == "msi":
            exec_cmd = "msiexec.exe"
            exec_args = f'/i "{abs_path}" {args}'
        elif ext in ["bat", "cmd"]:
            exec_cmd = "cmd.exe"
            exec_args = f'/c "{abs_path}" {args}'
        elif ext == "ps1":
            exec_cmd = interp or "powershell.exe"
            exec_args = f'-NoProfile -ExecutionPolicy Bypass -File "{abs_path}" {args}'
        elif ext == "py":
            exec_cmd = interp or sys.executable
            exec_args = f'"{abs_path}" {args}'
        elif ext == "js":
            exec_cmd = interp or "node.exe"
            exec_args = f'"{abs_path}" {args}'
        elif ext == "exe":
            exec_cmd = abs_path
            exec_args = args
        else:
            exec_cmd = abs_path
            exec_args = args

        res = execute_elevated_command(exec_cmd, exec_args, cwd=os.path.dirname(abs_path), timeout=timeout)
        res["action"] = "run_script"
        res["target"] = abs_path
        res["correlation_id"] = cid
        res["verification"] = "PASS" if res["success"] else "FAIL (Elevated exit code non-zero)"
        return res

    # Standard Execution
    cmd_list = []
    if ext == "msi":
        # Windows Installer via msiexec
        cmd_list = ["msiexec.exe", "/i", abs_path]
        if args:
            cmd_list.extend(args.split())
    elif ext in ["bat", "cmd"]:
        cmd_list = [os.environ.get("COMSPEC", "cmd.exe"), "/c", abs_path]
        if args:
            cmd_list.extend(args.split())
    elif ext == "ps1":
        interp = resolve_interpreter("ps1") or "powershell"
        cmd_list = [interp, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", abs_path]
        if args:
            cmd_list.extend(args.split())
    elif ext == "py":
        interp = resolve_interpreter("py") or sys.executable
        cmd_list = [interp, abs_path]
        if args:
            cmd_list.extend(args.split())
    elif ext == "js":
        interp = resolve_interpreter("js")
        if not interp:
            return {
                "success": False,
                "action": "run_script",
                "target": abs_path,
                "elevated": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": "Node.js interpreter not detected on system.",
                "verification": "FAILED (Node.js missing)",
                "correlation_id": cid
            }
        cmd_list = [interp, abs_path]
        if args:
            cmd_list.extend(args.split())
    elif ext == "exe":
        cmd_list = [abs_path]
        if args:
            cmd_list.extend(args.split())
    else:
        cmd_list = [abs_path]
        if args:
            cmd_list.extend(args.split())

    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd_list,
            capture_output=True,
            text=True,
            cwd=os.path.dirname(abs_path),
            timeout=timeout
        )
        duration = round(time.time() - t0, 3)
        success = proc.returncode == 0
        return {
            "success": success,
            "action": "run_script",
            "target": abs_path,
            "elevated": False,
            "exit_code": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "duration_sec": duration,
            "verification": "PASS" if success else f"FAIL (Exit code {proc.returncode})",
            "correlation_id": cid
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "action": "run_script",
            "target": abs_path,
            "elevated": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Execution timed out after {timeout} seconds.",
            "verification": "FAILED (Timeout)",
            "correlation_id": cid
        }
    except Exception as e:
        return {
            "success": False,
            "action": "run_script",
            "target": abs_path,
            "elevated": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "verification": f"FAILED ({e})",
            "correlation_id": cid
        }
