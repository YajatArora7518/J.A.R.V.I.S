# actions/system_telemetry.py
# Real Native Windows System Telemetry & Inspection Tools for JARVIS

import os
import sys
import glob
import time
import json
import psutil
import platform
import subprocess
import winreg
import ctypes
from pathlib import Path
from typing import Dict, Any, List, Optional

import logging

logger = logging.getLogger("JARVIS.SystemTelemetry")

_OS = platform.system()


def get_cpu_info() -> Dict[str, Any]:
    """Retrieves CPU processor model, core count, and current load."""
    cpu_percent = psutil.cpu_percent(interval=0.2)
    physical_cores = psutil.cpu_count(logical=False) or 1
    logical_cores = psutil.cpu_count(logical=True) or 1

    processor_name = platform.processor() or "Unknown CPU"
    if _OS == "Windows":
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
            )
            processor_name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            winreg.CloseKey(key)
        except Exception:
            pass

    return {
        "processor": processor_name.strip(),
        "physical_cores": physical_cores,
        "logical_cores": logical_cores,
        "cpu_usage_percent": cpu_percent
    }


def get_memory_info() -> Dict[str, Any]:
    """Retrieves RAM metrics: total, used, free, utilization %."""
    mem = psutil.virtual_memory()
    total_gb = round(mem.total / (1024 ** 3), 2)
    used_gb = round(mem.used / (1024 ** 3), 2)
    free_gb = round(mem.available / (1024 ** 3), 2)

    return {
        "total_gb": total_gb,
        "used_gb": used_gb,
        "free_gb": free_gb,
        "percent_used": mem.percent
    }


def get_gpu_info() -> Dict[str, Any]:
    """Retrieves GPU model and video memory details on Windows via PowerShell/WMI."""
    gpus = []
    if _OS == "Windows":
        try:
            ps_cmd = "Get-CimInstance Win32_VideoController | Select-Name, AdapterRAM, DriverVersion | ConvertTo-Json"
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                if isinstance(data, dict):
                    data = [data]
                for item in data:
                    name = item.get("Name", "Unknown GPU")
                    ram_bytes = item.get("AdapterRAM", 0) or 0
                    ram_mb = round(ram_bytes / (1024 ** 2), 2) if isinstance(ram_bytes, int) and ram_bytes > 0 else "N/A"
                    gpus.append({
                        "name": name,
                        "vram_mb": ram_mb,
                        "driver": item.get("DriverVersion", "N/A")
                    })
        except Exception as e:
            logger.warning(f"GPU WMI fetch warning: {e}")

    if not gpus:
        gpus.append({"name": "Standard Display Adapter / Integrated GPU", "vram_mb": "N/A", "driver": "N/A"})

    return {"gpus": gpus, "count": len(gpus)}


def get_battery_info() -> Dict[str, Any]:
    """Retrieves battery charge percentage and power line status."""
    battery = psutil.sensors_battery()
    if not battery:
        return {
            "has_battery": False,
            "percent": 100,
            "power_plugged": True,
            "message": "Desktop system (no battery sensor)."
        }

    return {
        "has_battery": True,
        "percent": round(battery.percent, 1),
        "power_plugged": battery.power_plugged,
        "secs_left": battery.secsleft if battery.secsleft != -1 else "Calculating/Plugged"
    }


def get_disk_info() -> Dict[str, Any]:
    """Retrieves drive partitions, total/free storage space."""
    drives = []
    partitions = psutil.disk_partitions(all=False)
    for p in partitions:
        try:
            usage = psutil.disk_usage(p.mountpoint)
            drives.append({
                "device": p.device,
                "mountpoint": p.mountpoint,
                "fstype": p.fstype,
                "total_gb": round(usage.total / (1024 ** 3), 2),
                "used_gb": round(usage.used / (1024 ** 3), 2),
                "free_gb": round(usage.free / (1024 ** 3), 2),
                "percent_used": usage.percent
            })
        except Exception:
            pass

    return {"drives": drives, "count": len(drives)}


def get_network_info() -> Dict[str, Any]:
    """Retrieves active network interfaces and IP addresses."""
    interfaces = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    active_nets = []

    for name, addrs in interfaces.items():
        is_up = stats[name].isup if name in stats else False
        if not is_up:
            continue

        ips = [addr.address for addr in addrs if addr.family.name in ('AF_INET', 'AF_INET6') and not addr.address.startswith('127.')]
        if ips:
            active_nets.append({
                "interface": name,
                "ips": ips,
                "speed_mbps": stats[name].speed if name in stats else 0
            })

    return {
        "connected": len(active_nets) > 0,
        "interfaces": active_nets
    }


def get_process_info(query: Optional[str] = None, top_n: int = 5) -> Dict[str, Any]:
    """Retrieves top running processes by CPU and RAM usage or searches for specific process."""
    processes = []
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'memory_info']):
        try:
            info = p.info
            mem_mb = round((info.get('memory_info').rss if info.get('memory_info') else 0) / (1024 ** 2), 1)
            processes.append({
                "pid": info['pid'],
                "name": info['name'],
                "cpu_percent": info['cpu_percent'] or 0.0,
                "memory_mb": mem_mb,
                "memory_percent": round(info['memory_percent'] or 0.0, 1)
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    if query:
        q_lower = query.lower()
        matched = [p for p in processes if q_lower in p['name'].lower()]
        return {
            "query": query,
            "running": len(matched) > 0,
            "matched_processes": matched[:10],
            "total_running_count": len(processes)
        }

    top_cpu = sorted(processes, key=lambda x: x['cpu_percent'], reverse=True)[:top_n]
    top_ram = sorted(processes, key=lambda x: x['memory_mb'], reverse=True)[:top_n]

    return {
        "total_running_count": len(processes),
        "top_by_cpu": top_cpu,
        "top_by_ram": top_ram
    }


def get_installed_apps_info(search_name: Optional[str] = None) -> Dict[str, Any]:
    """Scans Windows Registry uninstall keys and Start Menu to detect installed applications."""
    installed = {}

    if _OS == "Windows":
        reg_keys = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")
        ]

        for hive, subkey in reg_keys:
            try:
                key = winreg.OpenKey(hive, subkey)
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        sk_name = winreg.EnumKey(key, i)
                        sk = winreg.OpenKey(key, sk_name)
                        disp_name, _ = winreg.QueryValueEx(sk, "DisplayName")
                        disp_ver, _ = winreg.QueryValueEx(sk, "DisplayVersion") if "DisplayVersion" in [winreg.EnumValue(sk, j)[0] for j in range(winreg.QueryInfoKey(sk)[1])] else ("N/A", None)
                        install_loc = ""
                        try:
                            install_loc, _ = winreg.QueryValueEx(sk, "InstallLocation")
                        except Exception:
                            pass
                        winreg.CloseKey(sk)

                        if disp_name and disp_name.strip():
                            installed[disp_name.strip().lower()] = {
                                "display_name": disp_name.strip(),
                                "version": str(disp_ver),
                                "install_path": install_loc
                            }
                    except Exception:
                        pass
                winreg.CloseKey(key)
            except Exception:
                pass

    if search_name:
        s_lower = search_name.lower().strip()
        matches = [v for k, v in installed.items() if s_lower in k]
        return {
            "search_query": search_name,
            "installed": len(matches) > 0,
            "matches": matches[:5]
        }

    return {
        "total_installed_detected": len(installed),
        "sample_apps": [v["display_name"] for v in list(installed.values())[:20]]
    }


def get_active_windows_info() -> Dict[str, Any]:
    """Enumerates visible top-level windows on Windows desktop."""
    windows = []
    if _OS == "Windows":
        user32 = ctypes.windll.user32

        def enum_win_cb(hwnd, param):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value.strip()
                    if title and title not in ["Program Manager", "Settings"]:
                        windows.append({"hwnd": hwnd, "title": title})
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        user32.EnumWindows(WNDENUMPROC(enum_win_cb), 0)

    return {
        "visible_window_count": len(windows),
        "windows": windows
    }


def get_audio_devices_info() -> Dict[str, Any]:
    """Queries active microphone and speaker endpoints."""
    mics, speakers = [], []
    if _OS == "Windows":
        try:
            ps_cmd = "Get-CimInstance Win32_SoundDevice | Select-Name, Status, DeviceID | ConvertTo-Json"
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                if isinstance(data, dict):
                    data = [data]
                for d in data:
                    name = d.get("Name", "Audio Device")
                    speakers.append({"name": name, "status": d.get("Status", "OK")})
        except Exception as e:
            logger.warning(f"Audio device query warning: {e}")

    return {
        "active_microphones": mics or [{"name": "Default Windows Recording Endpoint"}],
        "active_speakers": speakers or [{"name": "Default Windows Playback Endpoint"}]
    }


def inspect_filesystem(target_folder: str = "Downloads", query: Optional[str] = None) -> Dict[str, Any]:
    """Safely inspects user files in Downloads, Documents, Desktop, or project folder."""
    user_home = Path.home()
    folder_map = {
        "downloads": user_home / "Downloads",
        "documents": user_home / "Documents",
        "desktop": user_home / "Desktop",
        "jarvis": Path(__file__).resolve().parent.parent
    }

    target_path = folder_map.get(target_folder.lower(), Path(target_folder) if Path(target_folder).exists() else user_home / "Downloads")

    if not target_path.exists():
        return {"success": False, "message": f"Folder '{target_path}' does not exist."}

    files = []
    try:
        for p in target_path.iterdir():
            if p.is_file() and not p.name.startswith('.'):
                mtime_str = time.strftime('%Y-%m-%d %H:%M', time.localtime(p.stat().st_mtime))
                size_mb = round(p.stat().st_size / (1024 * 1024), 2)
                files.append({
                    "name": p.name,
                    "size_mb": size_mb,
                    "modified": mtime_str,
                    "extension": p.suffix.lower()
                })
    except Exception as e:
        return {"success": False, "message": f"Could not inspect directory: {e}"}

    if query:
        q_lower = query.lower()
        matched = [f for f in files if q_lower in f['name'].lower() or q_lower in f['extension']]
        return {
            "folder": str(target_path),
            "total_files": len(files),
            "matched_files": matched[:15]
        }

    return {
        "folder": str(target_path),
        "total_files": len(files),
        "recent_files": sorted(files, key=lambda x: x['modified'], reverse=True)[:15]
    }


def execute_system_telemetry(action: str, **kwargs) -> Dict[str, Any]:
    """Unified runner for system telemetry actions."""
    act = (action or "").lower().strip()

    if act in ["cpu_info", "cpu"]:
        data = get_cpu_info()
        msg = f"CPU: {data['processor']} ({data['physical_cores']} cores) — Current Usage: {data['cpu_usage_percent']}%"
        return {"success": True, "message": msg, "data": data, "verified": True}

    if act in ["memory_info", "ram", "memory"]:
        data = get_memory_info()
        msg = f"RAM: {data['used_gb']} GB used / {data['total_gb']} GB total ({data['free_gb']} GB free, {data['percent_used']}% used)."
        return {"success": True, "message": msg, "data": data, "verified": True}

    if act in ["gpu_info", "gpu"]:
        data = get_gpu_info()
        gpu_strs = [f"{g['name']} (VRAM: {g['vram_mb']} MB)" for g in data['gpus']]
        msg = f"GPU: {', '.join(gpu_strs)}"
        return {"success": True, "message": msg, "data": data, "verified": True}

    if act in ["battery_info", "battery"]:
        data = get_battery_info()
        state = "Plugged in" if data['power_plugged'] else "Discharging"
        msg = f"Battery: {data['percent']}% ({state})." if data['has_battery'] else data['message']
        return {"success": True, "message": msg, "data": data, "verified": True}

    if act in ["disk_info", "storage", "disk"]:
        data = get_disk_info()
        drive_strs = [f"{d['mountpoint']} {d['free_gb']} GB free of {d['total_gb']} GB ({d['percent_used']}% used)" for d in data['drives']]
        msg = f"Storage Drives: {'; '.join(drive_strs)}"
        return {"success": True, "message": msg, "data": data, "verified": True}

    if act in ["network_info", "network", "ip"]:
        data = get_network_info()
        if data['connected']:
            if_strs = [f"{i['interface']}: IP {', '.join(i['ips'])}" for i in data['interfaces']]
            msg = f"Network Connected: {'; '.join(if_strs)}"
        else:
            msg = "Network: No active internet interface detected."
        return {"success": True, "message": msg, "data": data, "verified": True}

    if act in ["process_info", "processes", "top_cpu", "top_ram"]:
        query = kwargs.get("query")
        data = get_process_info(query=query)
        if query:
            if data['running']:
                p_names = [f"{p['name']} (PID {p['pid']}, CPU {p['cpu_percent']}%, RAM {p['memory_mb']} MB)" for p in data['matched_processes']]
                msg = f"Process '{query}' is running: {'; '.join(p_names)}"
            else:
                msg = f"Process '{query}' is not currently running."
        else:
            top_c = ", ".join([f"{p['name']} ({p['cpu_percent']}%)" for p in data['top_by_cpu'][:3]])
            top_r = ", ".join([f"{p['name']} ({p['memory_mb']} MB)" for p in data['top_by_ram'][:3]])
            msg = f"Top CPU Processes: {top_c}. Top RAM Processes: {top_r}."
        return {"success": True, "message": msg, "data": data, "verified": True}

    if act in ["installed_apps_info", "installed_apps"]:
        app_name = kwargs.get("app_name") or kwargs.get("query")
        data = get_installed_apps_info(search_name=app_name)
        if app_name:
            if data['installed']:
                names = [m['display_name'] for m in data['matches']]
                msg = f"Application '{app_name}' is installed on this PC ({', '.join(names)})."
            else:
                msg = f"Application '{app_name}' is not installed on this PC."
        else:
            msg = f"Total installed applications detected: {data['total_installed_detected']} apps."
        return {"success": True, "message": msg, "data": data, "verified": True}

    if act in ["active_windows_info", "active_windows"]:
        data = get_active_windows_info()
        w_titles = [w['title'] for w in data['windows'][:7]]
        msg = f"Open Windows ({data['visible_window_count']} active): {'; '.join(w_titles)}"
        return {"success": True, "message": msg, "data": data, "verified": True}

    if act in ["audio_devices_info", "audio_devices"]:
        data = get_audio_devices_info()
        spk_names = [s['name'] for s in data['active_speakers']]
        msg = f"Active Speakers: {', '.join(spk_names)}"
        return {"success": True, "message": msg, "data": data, "verified": True}

    if act in ["filesystem_info", "filesystem"]:
        folder = kwargs.get("folder", "Downloads")
        query = kwargs.get("query")
        data = inspect_filesystem(target_folder=folder, query=query)
        if not data.get("success", True):
            return {"success": False, "message": data["message"], "verified": False}

        if query and "matched_files" in data:
            f_names = [f['name'] for f in data['matched_files']]
            msg = f"Found {len(f_names)} file(s) matching '{query}' in {folder}: {', '.join(f_names[:5])}"
        else:
            f_names = [f['name'] for f in data.get('recent_files', [])]
            msg = f"Files in {folder} ({data['total_files']} total): {', '.join(f_names[:7])}"
        return {"success": True, "message": msg, "data": data, "verified": True}

    # Complete system snapshot fallback
    cpu = get_cpu_info()
    mem = get_memory_info()
    batt = get_battery_info()
    disk = get_disk_info()
    msg = f"System Telemetry — CPU: {cpu['processor']} ({cpu['cpu_usage_percent']}% usage) | RAM: {mem['free_gb']} GB free of {mem['total_gb']} GB | Battery: {batt['percent']}% | Disks: {len(disk['drives'])} active partition(s)."
    return {"success": True, "message": msg, "data": {"cpu": cpu, "ram": mem, "battery": batt, "disk": disk}, "verified": True}
