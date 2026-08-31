# core/capability_discovery.py
# Boot-Time System Capability Discovery & Registry for JARVIS
# Detects OS, installed interpreters, admin privileges, drives, and hardware.

import os
import sys
import platform
import shutil
import subprocess
import logging
from typing import Dict, Any, List
import psutil

logger = logging.getLogger("JARVIS.CapabilityDiscovery")

class CapabilityRegistry:
    """Runtime Registry storing verified capabilities on the Windows host machine."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CapabilityRegistry, cls).__new__(cls)
            cls._instance.capabilities = {}
            cls._instance.is_discovered = False
        return cls._instance

    def discover(self) -> Dict[str, Any]:
        """Performs full hardware, runtime interpreter, and OS capability discovery."""
        caps = {}

        # 1. OS & Platform
        caps["os"] = platform.system()
        caps["os_release"] = platform.release()
        caps["os_version"] = platform.version()
        caps["hostname"] = platform.node()

        # 2. Administrator Elevation Status
        from actions.windows_uac_bridge import is_running_as_admin
        caps["is_admin"] = is_running_as_admin()

        # 3. Interpreter & CLI Tool Discovery
        caps["python"] = {
            "available": True,
            "path": sys.executable,
            "version": platform.python_version()
        }

        # PowerShell
        pwsh_path = shutil.which("pwsh") or shutil.which("powershell") or r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        pwsh_avail = os.path.exists(pwsh_path) if os.path.isabs(pwsh_path) else bool(pwsh_path)
        caps["powershell"] = {
            "available": pwsh_avail,
            "path": pwsh_path if pwsh_avail else None
        }

        # Node.js
        node_path = shutil.which("node") or r"C:\Program Files\nodejs\node.exe"
        node_avail = os.path.exists(node_path) if os.path.isabs(node_path) else bool(node_path)
        caps["node"] = {
            "available": node_avail,
            "path": node_path if node_avail else None
        }

        # Git
        git_path = shutil.which("git")
        caps["git"] = {
            "available": bool(git_path),
            "path": git_path
        }

        # 4. Hardware Telemetry
        caps["cpu_count"] = psutil.cpu_count(logical=True)
        mem = psutil.virtual_memory()
        caps["total_ram_gb"] = round(mem.total / (1024**3), 2)
        caps["available_ram_gb"] = round(mem.available / (1024**3), 2)

        # Storage Drives
        drives = []
        try:
            for part in psutil.disk_partitions(all=False):
                if os.name == 'nt' and 'cdrom' in part.opts:
                    continue
                drives.append(part.mountpoint)
        except Exception:
            drives = ["C:\\"]
        caps["drives"] = drives

        # 5. JARVIS Workspace Path
        from actions.script_executor import get_workspace_dir
        caps["workspace_dir"] = get_workspace_dir()

        self.capabilities = caps
        self.is_discovered = True
        logger.info(f"[CapabilityDiscovery] System Discovery Complete. Host: {caps['hostname']}, Admin: {caps['is_admin']}")
        return caps

    def get_summary(self) -> str:
        if not self.is_discovered:
            self.discover()
        c = self.capabilities
        return (
            f"OS: {c.get('os')} {c.get('os_release')} | "
            f"RAM: {c.get('available_ram_gb')}GB / {c.get('total_ram_gb')}GB | "
            f"Admin: {c.get('is_admin')} | "
            f"Py: {c.get('python', {}).get('version')} | "
            f"PS: {c.get('powershell', {}).get('available')}"
        )

# Global Instance
capability_registry = CapabilityRegistry()
