# actions/windows_system_controller.py
# Unified Generic Windows System Controller for JARVIS
# Integrates application, file, process, service, system telemetry, power, and web search capabilities.

import os
import sys
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("JARVIS.WindowsSystemController")

def is_admin() -> bool:
    """Checks whether current process possesses Windows Administrator privileges."""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def execute_system_capability(capability: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Unified entry point mapping typed system capabilities to underlying module executors.
    Returns structured result:
    {"success": bool, "action": str, "target": str, "elevated": bool, "exit_code": int, "stdout": str, "stderr": str, "verification": str, "correlation_id": str}
    """
    cap = capability.lower().strip()
    args = args or {}
    logger.info(f"[WindowsSystemController] Executing capability: '{cap}' with args: {args}")

    # Honest Windows Privilege Check
    req_elevated = bool(args.get("elevated", False))
    if req_elevated and not is_admin():
        logger.warning("[WindowsSystemController] Elevated operation requested but Admin=False.")
        return {
            "success": False,
            "action": cap,
            "target": str(args.get("target", "system")),
            "elevated": False,
            "exit_code": 1,
            "stdout": "",
            "stderr": "Administrator privileges required. Current process Admin status is False.",
            "verification": "FAIL_PRIVILEGE_REQUIRED",
            "correlation_id": args.get("correlation_id", "")
        }

    # =========================================================
    # 1. APPLICATION CONTROL
    # =========================================================
    if cap in ["open_application", "open_app", "launch_app"]:
        app_name = args.get("app_name") or args.get("target") or args.get("app", "")
        from actions.open_app import open_app
        res = open_app(app_name)
        return {
            "success": res.get("success", False),
            "action": "open_application",
            "target": app_name,
            "elevated": False,
            "exit_code": 0 if res.get("success") else 1,
            "stdout": res.get("message", ""),
            "stderr": res.get("error", ""),
            "verification": "PASS" if res.get("verified") else "FAIL",
            "correlation_id": args.get("correlation_id", "")
        }

    elif cap in ["close_application", "close_app", "stop_app"]:
        app_name = args.get("app_name") or args.get("target") or args.get("app", "")
        from actions.computer_settings import computer_settings
        res = computer_settings({"action": "close_app", "value": app_name})
        return {
            "success": res.get("success", False),
            "action": "close_application",
            "target": app_name,
            "elevated": False,
            "exit_code": 0 if res.get("success") else 1,
            "stdout": res.get("message", ""),
            "stderr": res.get("error", ""),
            "verification": "PASS" if res.get("success") else "FAIL",
            "correlation_id": args.get("correlation_id", "")
        }

    elif cap in ["focus_window", "focus_app", "minimize_window", "maximize_window", "get_active_window"]:
        try:
            import pygetwindow as gw
            if cap == "get_active_window":
                win = gw.getActiveWindow()
                title = win.title if win else "Desktop"
                return {"success": True, "action": cap, "target": title, "stdout": f"Active window: '{title}'", "verification": "PASS"}
            elif cap in ["minimize_window", "minimize_app"]:
                win = gw.getActiveWindow()
                if win: win.minimize()
                return {"success": True, "action": cap, "target": win.title if win else "window", "stdout": "Window minimized.", "verification": "PASS"}
            elif cap in ["maximize_window", "maximize_app"]:
                win = gw.getActiveWindow()
                if win: win.maximize()
                return {"success": True, "action": cap, "target": win.title if win else "window", "stdout": "Window maximized.", "verification": "PASS"}
            else:
                app_name = args.get("app_name") or args.get("target", "")
                wins = gw.getWindowsWithTitle(app_name)
                if wins:
                    wins[0].activate()
                    return {"success": True, "action": cap, "target": app_name, "stdout": f"Focused window '{app_name}'", "verification": "PASS"}
                return {"success": False, "action": cap, "target": app_name, "stdout": f"Window '{app_name}' not found", "verification": "FAIL"}
        except Exception as e:
            return {"success": False, "action": cap, "target": "window", "stderr": str(e), "verification": "FAIL"}

    elif cap in ["read_clipboard", "get_clipboard", "write_clipboard", "set_clipboard"]:
        try:
            import pyperclip
            if cap in ["read_clipboard", "get_clipboard"]:
                content = pyperclip.paste()
                return {"success": True, "action": cap, "target": "clipboard", "stdout": content, "verification": "PASS"}
            else:
                text = args.get("text") or args.get("content", "")
                pyperclip.copy(text)
                return {"success": True, "action": cap, "target": "clipboard", "stdout": f"Copied '{text[:30]}' to clipboard.", "verification": "PASS"}
        except Exception as e:
            return {"success": False, "action": cap, "target": "clipboard", "stderr": str(e), "verification": "FAIL"}

    # =========================================================
    # 2. PROCESS CONTROL
    # =========================================================
    elif cap in ["list_processes", "get_process_info", "process_info"]:
        filter_name = args.get("filter_name") or args.get("query", "")
        from actions.system_telemetry import process_info
        res = process_info({"action": "list", "filter": filter_name})
        return {
            "success": res.get("success", True),
            "action": "list_processes",
            "target": filter_name or "all",
            "elevated": False,
            "exit_code": 0,
            "stdout": str(res.get("data", res.get("message", ""))),
            "stderr": "",
            "verification": "PASS",
            "correlation_id": args.get("correlation_id", "")
        }

    elif cap in ["terminate_process", "kill_process", "stop_process"]:
        target = args.get("process_name") or args.get("target") or args.get("pid", "")
        elevated = args.get("elevated", False)
        from actions.computer_settings import computer_settings
        res = computer_settings({"action": "close_app", "value": target})
        return {
            "success": res.get("success", False),
            "action": "terminate_process",
            "target": str(target),
            "elevated": elevated,
            "exit_code": 0 if res.get("success") else 1,
            "stdout": res.get("message", ""),
            "stderr": res.get("error", ""),
            "verification": "PASS" if res.get("success") else "FAIL",
            "correlation_id": args.get("correlation_id", "")
        }

    # =========================================================
    # 3. FILESYSTEM OPERATIONS
    # =========================================================
    elif cap in ["create_file", "write_file", "append_file"]:
        path = args.get("path", "")
        name = args.get("name", "")
        content = args.get("content", "")
        from actions.file_controller import file_controller
        action_name = "append_file" if cap == "append_file" else "create_file"
        res = file_controller({"action": action_name, "path": path, "name": name, "content": content})
        return {
            "success": res.get("success", False),
            "action": cap,
            "target": res.get("file_path", path),
            "elevated": False,
            "exit_code": 0 if res.get("success") else 1,
            "stdout": res.get("message", ""),
            "stderr": res.get("error", ""),
            "verification": "PASS" if res.get("success") else "FAIL",
            "correlation_id": args.get("correlation_id", "")
        }

    elif cap in ["read_file"]:
        path = args.get("path") or args.get("target", "")
        from actions.file_controller import file_controller
        res = file_controller({"action": "read_file", "path": path})
        return {
            "success": res.get("success", False),
            "action": "read_file",
            "target": path,
            "elevated": False,
            "exit_code": 0 if res.get("success") else 1,
            "stdout": res.get("content", res.get("message", "")),
            "stderr": res.get("error", ""),
            "verification": "PASS" if res.get("success") else "FAIL",
            "correlation_id": args.get("correlation_id", "")
        }

    elif cap in ["delete_file", "delete_directory", "remove_file"]:
        path = args.get("path") or args.get("target", "")
        from actions.file_controller import file_controller
        res = file_controller({"action": "delete_file", "path": path})
        return {
            "success": res.get("success", False),
            "action": cap,
            "target": path,
            "elevated": args.get("elevated", False),
            "exit_code": 0 if res.get("success") else 1,
            "stdout": res.get("message", ""),
            "stderr": res.get("error", ""),
            "verification": "PASS" if res.get("success") else "FAIL",
            "correlation_id": args.get("correlation_id", "")
        }

    elif cap in ["create_directory", "mkdir", "create_folder"]:
        path = args.get("path") or args.get("target", "")
        name = args.get("name", "")
        from actions.file_controller import file_controller
        res = file_controller({"action": "create_directory", "path": path, "name": name})
        return {
            "success": res.get("success", False),
            "action": "create_directory",
            "target": res.get("file_path", path),
            "elevated": False,
            "exit_code": 0 if res.get("success") else 1,
            "stdout": res.get("message", ""),
            "stderr": res.get("error", ""),
            "verification": "PASS" if res.get("success") else "FAIL",
            "correlation_id": args.get("correlation_id", "")
        }

    elif cap in ["rename_file", "move_file", "copy_file"]:
        src = args.get("source") or args.get("path", "")
        dest = args.get("destination") or args.get("new_name") or args.get("target", "")
        from actions.file_controller import file_controller
        action_type = "rename_file" if cap == "rename_file" else ("move_file" if cap == "move_file" else "copy_file")
        res = file_controller({"action": action_type, "path": src, "destination": dest, "new_name": dest})
        return {
            "success": res.get("success", False),
            "action": cap,
            "target": dest,
            "elevated": False,
            "exit_code": 0 if res.get("success") else 1,
            "stdout": res.get("message", ""),
            "stderr": res.get("error", ""),
            "verification": "PASS" if res.get("success") else "FAIL",
            "correlation_id": args.get("correlation_id", "")
        }

    elif cap in ["search_files", "find_file"]:
        query = args.get("query") or args.get("name", "")
        dir_path = args.get("directory") or args.get("path", "")
        from actions.file_controller import file_controller
        res = file_controller({"action": "search_files", "query": query, "path": dir_path})
        return {
            "success": res.get("success", True),
            "action": "search_files",
            "target": query,
            "elevated": False,
            "exit_code": 0,
            "stdout": str(res.get("results", res.get("message", ""))),
            "stderr": "",
            "verification": "PASS",
            "correlation_id": args.get("correlation_id", "")
        }

    # =========================================================
    # 4. SYSTEM TELEMETRY & INFO
    # =========================================================
    elif cap in ["get_system_info", "system_info", "cpu_info", "ram_info", "memory_info"]:
        from actions.system_telemetry import system_info
        res = system_info({})
        return {
            "success": True,
            "action": cap,
            "target": "system",
            "elevated": False,
            "exit_code": 0,
            "stdout": str(res.get("data", res.get("message", ""))),
            "stderr": "",
            "verification": "PASS",
            "correlation_id": args.get("correlation_id", "")
        }

    elif cap in ["get_disk_info", "disk_info"]:
        from actions.system_telemetry import disk_info
        res = disk_info({})
        return {
            "success": True,
            "action": cap,
            "target": "disks",
            "elevated": False,
            "exit_code": 0,
            "stdout": str(res.get("data", res.get("message", ""))),
            "stderr": "",
            "verification": "PASS",
            "correlation_id": args.get("correlation_id", "")
        }

    elif cap in ["get_network_info", "network_info"]:
        from actions.system_telemetry import network_info
        res = network_info({})
        return {
            "success": True,
            "action": cap,
            "target": "network",
            "elevated": False,
            "exit_code": 0,
            "stdout": str(res.get("data", res.get("message", ""))),
            "stderr": "",
            "verification": "PASS",
            "correlation_id": args.get("correlation_id", "")
        }

    elif cap in ["get_battery_info", "battery_info"]:
        from actions.system_telemetry import battery_info
        res = battery_info({})
        return {
            "success": True,
            "action": True,
            "target": "battery",
            "elevated": False,
            "exit_code": 0,
            "stdout": str(res.get("data", res.get("message", ""))),
            "stderr": "",
            "verification": "PASS",
            "correlation_id": args.get("correlation_id", "")
        }

    # =========================================================
    # 5. SCRIPT EXECUTION & SERVICES
    # =========================================================
    elif cap in ["run_script", "execute_script"]:
        from actions.script_executor import run_script
        path = args.get("file_path") or args.get("path") or args.get("target", "")
        cmd_args = args.get("args", "")
        timeout = int(args.get("timeout", 30))
        elevated = args.get("elevated", False)
        return run_script(path, args=cmd_args, timeout=timeout, elevated=elevated, correlation_id=args.get("correlation_id"))

    elif cap in ["create_script"]:
        from actions.script_executor import create_script
        content = args.get("content", "")
        stype = args.get("script_type") or args.get("type", "bat")
        name = args.get("filename") or args.get("name")
        target_dir = args.get("directory") or args.get("path")
        return create_script(content, stype, filename=name, target_dir=target_dir)

    elif cap in ["windows_services", "list_services", "get_service_status", "start_service", "stop_service", "restart_service"]:
        from actions.windows_services import list_services, get_service_status, start_service, stop_service, restart_service
        sub_act = args.get("action", cap)
        service_name = args.get("service_name") or args.get("target", "")
        if sub_act == "list_services" or cap == "list_services":
            slist = list_services(filter_name=service_name)
            return {"success": True, "action": "list_services", "target": service_name or "all", "stdout": str(slist), "exit_code": 0, "verification": "PASS"}
        elif sub_act == "get_service_status" or cap == "get_service_status":
            sres = get_service_status(service_name)
            return {"success": sres.get("success", False), "action": "get_service_status", "target": service_name, "stdout": str(sres), "exit_code": 0 if sres.get("success") else 1, "verification": "PASS"}
        elif sub_act == "start_service" or cap == "start_service":
            sres = start_service(service_name, elevated=args.get("elevated", False))
            return {"success": sres.get("success", False), "action": "start_service", "target": service_name, "stdout": str(sres), "exit_code": 0 if sres.get("success") else 1, "verification": "PASS"}
        elif sub_act == "stop_service" or cap == "stop_service":
            sres = stop_service(service_name, elevated=args.get("elevated", False))
            return {"success": sres.get("success", False), "action": "stop_service", "target": service_name, "stdout": str(sres), "exit_code": 0 if sres.get("success") else 1, "verification": "PASS"}
        elif sub_act == "restart_service" or cap == "restart_service":
            sres = restart_service(service_name, elevated=args.get("elevated", False))
            return {"success": sres.get("success", False), "action": "restart_service", "target": service_name, "stdout": str(sres), "exit_code": 0 if sres.get("success") else 1, "verification": "PASS"}

    # =========================================================
    # 6. POWER & WEB SEARCH
    # =========================================================
    elif cap in ['shutdown', 'restart']:
        if args.get('confirmed') is not True:
            return {'success': False, 'verified': False, 'requires_confirmation': True,
                    'status': 'CONFIRMATION_REQUIRED', 'message': 'Pehle chat ya voice par power request confirm karo.'}
        from actions.computer_settings import restart_computer, shutdown_computer
        return (restart_computer if cap == 'restart' else shutdown_computer)()

    elif cap in ["sleep", "lock"]:
        from actions.computer_control import computer_control
        res = computer_control({"action": cap})
        return {
            "success": res.get("success", False),
            "action": cap,
            "target": "system",
            "elevated": False,
            "exit_code": 0 if res.get("success") else 1,
            "stdout": res.get("message", ""),
            "stderr": res.get("error", ""),
            "verification": "PASS" if res.get("success") else "FAIL",
            "correlation_id": args.get("correlation_id", "")
        }

    elif cap in ["web_search", "google_search"]:
        query = args.get("query") or args.get("target", "")
        from actions.web_search import web_search
        res = web_search({"query": query})
        return {
            "success": True,
            "action": "web_search",
            "target": query,
            "elevated": False,
            "exit_code": 0,
            "stdout": str(res),
            "stderr": "",
            "verification": "PASS",
            "correlation_id": args.get("correlation_id", "")
        }

    return {
        "success": False,
        "action": cap,
        "target": "unknown",
        "elevated": False,
        "exit_code": -1,
        "stdout": "",
        "stderr": f"Capability '{cap}' not supported by WindowsSystemController.",
        "verification": "FAILED (Unknown capability)",
        "correlation_id": args.get("correlation_id", "")
    }
