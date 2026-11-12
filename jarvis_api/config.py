# jarvis_api/config.py
# Hierarchical Configuration Management for JARVIS SDK & API

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any


def get_base_dir() -> Path:
    return Path(__file__).resolve().parent.parent


class JarvisConfig:
    """
    Manages JARVIS SDK configuration with priority:
    1. Explicit constructor arguments
    2. Environment variables (JARVIS_API_KEY, JARVIS_HOST, JARVIS_PORT, etc.)
    3. Disk configuration file (config/api_keys.json)
    4. Safe default values
    """
    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        openrouter_api_key: Optional[str] = None,
        api_server_key: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        data_dir: Optional[Path] = None,
    ):
        self.base_dir = get_base_dir()
        self.data_dir = data_dir or self.base_dir

        disk_cfg = self._load_disk_config()

        self.gemini_api_key = (
            gemini_api_key or
            os.environ.get("GEMINI_API_KEY") or
            disk_cfg.get("gemini_api_key") or
            ""
        ).strip()

        self.openrouter_api_key = (
            openrouter_api_key or
            os.environ.get("OPENROUTER_API_KEY") or
            disk_cfg.get("openrouter_api_key") or
            ""
        ).strip()

        self.api_server_key = (
            api_server_key or
            os.environ.get("JARVIS_API_KEY") or
            disk_cfg.get("jarvis_api_key") or
            ""
        ).strip()

        self.host = (
            host or
            os.environ.get("JARVIS_HOST") or
            "127.0.0.1"
        )

        self.port = int(
            port or
            os.environ.get("JARVIS_PORT") or
            8000
        )

        self.os_system = disk_cfg.get("os_system", "windows")

    def _load_disk_config(self) -> Dict[str, Any]:
        cfg_path = self.base_dir / "config" / "api_keys.json"
        if cfg_path.exists():
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "os_system": self.os_system,
            "has_gemini_key": bool(self.gemini_api_key),
            "has_openrouter_key": bool(self.openrouter_api_key),
            "has_api_server_key": bool(self.api_server_key),
        }
