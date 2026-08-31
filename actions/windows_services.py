# actions/windows_services.py
# Windows Service Management Module for JARVIS
# Inspects, starts, stops, and restarts Windows services safely.

import os
import subprocess
import logging
from typing import Dict, Any, List, Optional
import psutil

logger = logging.getLogger("JARVIS.WindowsServices")

def list_services(filter_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lists Windows services using psutil or sc.exe."""
    services = []
    try:
        for s in psutil.win_service_iter():
            try:
                info = s.as_dict()
                name = info.get("name", "")
                display_name = info.get("display_name", "")
                status = info.get("status", "")

                if filter_name:
                    fn = filter_name.lower()
                    if fn not in name.lower() and fn not in display_name.lower():
                        continue

                services.append({
                    "name": name,
                    "display_name": display_name,
                    "status": status,
                    "start_type": info.get("start_type", "")
                })
            except Exception:
                continue
    except Exception as e:
        logger.error(f"[WindowsServices] Error listing services: {e}")

    return services

def get_service_status(service_name: str) -> Dict[str, Any]:
    """Gets detailed status of a specific Windows service."""
    if not service_name:
        return {"success": False, "error": "Service name required."}

    try:
        srv = psutil.win_service_get(service_name)
        info = srv.as_dict()
        return {
            "success": True,
            "name": info.get("name"),
            "display_name": info.get("display_name"),
            "status": info.get("status"),
            "start_type": info.get("start_type"),
            "binpath": info.get("binpath"),
            "description": info.get("description")
        }
    except psutil.NoSuchProcess:
        # Fallback to sc.exe query
        try:
            res = subprocess.run(
                ["sc.exe", "query", service_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            if "RUNNING" in res.stdout:
                status = "running"
            elif "STOPPED" in res.stdout:
                status = "stopped"
            else:
                status = "unknown"

            return {
                "success": res.returncode == 0,
                "name": service_name,
                "status": status,
                "raw": res.stdout.strip()
            }
        except Exception as ex:
            return {"success": False, "name": service_name, "error": f"Service not found: {ex}"}
    except Exception as e:
        return {"success": False, "name": service_name, "error": str(e)}

def _manage_service(action: str, service_name: str, elevated: bool = False) -> Dict[str, Any]:
    """Internal helper to start/stop/restart a Windows service."""
    if not service_name:
        return {"success": False, "error": "Service name required."}

    sc_cmd = "start" if action == "start" else ("stop" if action == "stop" else "restart")

    if elevated:
        from actions.windows_uac_bridge import execute_elevated_command
        res = execute_elevated_command("sc.exe", f"{sc_cmd} {service_name}", timeout=15)
        return {
            "success": res["success"],
            "action": f"{action}_service",
            "service_name": service_name,
            "elevated": True,
            "stdout": res["stdout"],
            "stderr": res["stderr"]
        }

    # Non-elevated execution check
    try:
        res = subprocess.run(
            ["sc.exe", sc_cmd, service_name],
            capture_output=True,
            text=True,
            timeout=15
        )
        success = res.returncode == 0
        return {
            "success": success,
            "action": f"{action}_service",
            "service_name": service_name,
            "elevated": False,
            "exit_code": res.returncode,
            "stdout": res.stdout.strip(),
            "stderr": res.stderr.strip()
        }
    except Exception as e:
        return {
            "success": False,
            "action": f"{action}_service",
            "service_name": service_name,
            "elevated": False,
            "error": str(e)
        }

def start_service(service_name: str, elevated: bool = False) -> Dict[str, Any]:
    return _manage_service("start", service_name, elevated=elevated)

def stop_service(service_name: str, elevated: bool = False) -> Dict[str, Any]:
    return _manage_service("stop", service_name, elevated=elevated)

def restart_service(service_name: str, elevated: bool = False) -> Dict[str, Any]:
    return _manage_service("restart", service_name, elevated=elevated)
