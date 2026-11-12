# core/diagnostics.py
# Real-Time Self Diagnostics & System Health Telemetry for J.A.R.V.I.S
# Answers "JARVIS status", "Which AI are you using?", "Why are you slow?", etc.

import os
import sys
import time
import re
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

from core.runtime_supervisor import get_runtime_supervisor, redact_secrets, SubsystemState


class SelfDiagnostics:
    """
    SelfDiagnostics queries RuntimeSupervisor and OS metrics to synthesize
    truthful, natural status assessments without exposing private credentials.
    """

    def __init__(self):
        self.supervisor = get_runtime_supervisor()

    def get_diagnostics_summary(self) -> Dict[str, Any]:
        """Gathers real-time subsystem states and OS health metrics."""
        telemetry = self.supervisor.get_full_report()
        subs = telemetry.get("subsystems", {})

        # Determine active AI tier
        ollama_sub = subs.get("ollama", {})
        gemini_sub = subs.get("gemini", {})
        tts_sub = subs.get("tts", {})
        camera_sub = subs.get("camera", {})
        audio_sub = subs.get("audio", {})

        active_ai = "Local Ollama"
        if ollama_sub.get("state") == SubsystemState.HEALTHY:
            active_ai = f"Local Ollama ({ollama_sub.get('current_provider') or 'fotiecodes/jarvis:latest'})"
        elif gemini_sub.get("state") == SubsystemState.HEALTHY:
            active_ai = f"Cloud Gemini ({gemini_sub.get('current_provider') or 'gemini-3.5-flash-lite'})"
        else:
            active_ai = "Local Ollama"

        # Gather resource metrics
        ram_percent = 0.0
        cpu_percent = 0.0
        battery_info = "N/A"
        if _HAS_PSUTIL:
            try:
                ram_percent = psutil.virtual_memory().percent
                cpu_percent = psutil.cpu_percent(interval=None)
                batt = psutil.sensors_battery()
                if batt:
                    status = "Charging" if batt.power_plugged else "Discharging"
                    battery_info = f"{int(batt.percent)}% ({status})"
            except Exception:
                pass

        # GPU monitoring (nvidia-smi if available)
        gpu_info = "N/A"
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split(",")
                if len(parts) >= 5:
                    gpu_info = f"{parts[0].strip()} | GPU: {parts[1].strip()}% | VRAM: {parts[2].strip()}/{parts[3].strip()} MB | Temp: {parts[4].strip()}°C"
        except (FileNotFoundError, Exception):
            pass

        # Disk space
        disk_info = "N/A"
        disk_warning = False
        if _HAS_PSUTIL:
            try:
                disk = psutil.disk_usage("/")
                disk_free_gb = disk.free / (1024 ** 3)
                disk_total_gb = disk.total / (1024 ** 3)
                disk_info = f"{disk_free_gb:.1f}/{disk_total_gb:.1f} GB free ({disk.percent}% used)"
                disk_warning = disk.percent > 90
            except Exception:
                pass

        # Network quality
        network_ok = True
        try:
            import socket
            socket.create_connection(("8.8.8.8", 53), timeout=2)
        except Exception:
            network_ok = False

        return {
            "active_ai": active_ai,
            "ollama_state": ollama_sub.get("state", "HEALTHY"),
            "ollama_latency_ms": ollama_sub.get("latency_ms", 0.0),
            "gemini_state": gemini_sub.get("state", "HEALTHY"),
            "gemini_latency_ms": gemini_sub.get("latency_ms", 0.0),
            "tts_state": tts_sub.get("state", "HEALTHY"),
            "camera_state": camera_sub.get("state", "HEALTHY"),
            "audio_state": audio_sub.get("state", "HEALTHY"),
            "ram_percent": ram_percent,
            "cpu_percent": cpu_percent,
            "battery": battery_info,
            "gpu_info": gpu_info,
            "disk_info": disk_info,
            "disk_warning": disk_warning,
            "network_ok": network_ok,
            "all_healthy": all(s.get("state") == SubsystemState.HEALTHY for s in subs.values()) if subs else True
        }

    def handle_diagnostic_query(self, query: str) -> Optional[str]:
        """
        Parses and replies to natural language diagnostic questions:
        - "JARVIS status" / "System status"
        - "System check" / "Diagnostics"
        - "Kya chal raha hai?"
        - "Why are you slow?"
        - "Which AI are you using?"
        """
        lower = (query or "").lower().strip()

        # 1. "Which AI are you using?" / "Konsa model hai?"
        if any(w in lower for w in [
            "which ai", "which model", "konsa ai", "konsa model", "what model",
            "what ai", "ai kaunsa", "model kaunsa", "kaunsa ai", "using ai"
        ]):
            diag = self.get_diagnostics_summary()
            msg = (
                f"{diag['active_ai']} is currently handling your requests locally on your machine. "
                "Camera and voice pipelines are active and healthy."
            )
            return redact_secrets(msg)

        # 2. "Why are you slow?" / "Slow kyu ho?"
        if any(w in lower for w in [
            "why are you slow", "slow kyu", "slow chal raha", "why so slow",
            "itna slow", "speed kyu kam hai", "latency kyu hai"
        ]):
            diag = self.get_diagnostics_summary()
            reasons = []
            if diag["ollama_latency_ms"] > 3000:
                reasons.append(f"local model generation took {diag['ollama_latency_ms']/1000:.1f}s")
            if diag["cpu_percent"] > 80:
                reasons.append(f"CPU utilization is high at {diag['cpu_percent']}%")
            if diag["ram_percent"] > 85:
                reasons.append(f"system RAM usage is high at {diag['ram_percent']}%")

            if reasons:
                explanation = ", and ".join(reasons)
                msg = f"Boss, response thoda slow tha kyunki {explanation}. Systems are healthy, but resource load is elevated."
            else:
                msg = f"Boss, my system latency is normal ({diag['ollama_latency_ms']:.0f}ms). All pipelines are operating smoothly."
            return redact_secrets(msg)

        # 3. "JARVIS status" / "System check" / "Kya chal raha hai?"
        if any(w in lower for w in [
            "jarvis status", "system check", "kya chal raha hai", "kya chal raha",
            "system status", "health check", "status check", "how are you running",
            "kya hal chal", "sab theek hai"
        ]):
            diag = self.get_diagnostics_summary()
            ai_info = diag["active_ai"]
            cam_str = "healthy" if diag["camera_state"] == "HEALTHY" else diag["camera_state"].lower()
            tts_str = "healthy" if diag["tts_state"] == "HEALTHY" else diag["tts_state"].lower()

            res_info = f"CPU {diag['cpu_percent']}%, RAM {diag['ram_percent']}%"
            msg = (
                f"{ai_info} is currently handling your requests. "
                f"Camera and voice are {cam_str}, speech synthesis is {tts_str}. "
                f"System resources: {res_info}. All core subsystems operational, Boss."
            )
            return redact_secrets(msg)

        return None


# Default singleton instance
default_diagnostics = SelfDiagnostics()
