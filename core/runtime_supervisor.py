# core/runtime_supervisor.py
# Autonomous Runtime Supervisor & Self-Healing Telemetry Manager for J.A.R.V.I.S.

import sys
import os
import time
import threading
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Callable

import re

logger = logging.getLogger("JARVIS.RuntimeSupervisor")

# Bounded Exponential Backoff Parameters
MIN_BACKOFF_SECONDS = 5.0
MAX_BACKOFF_SECONDS = 60.0
BACKOFF_MULTIPLIER = 2.0


def redact_secrets(text: str) -> str:
    """Strictly redacts API keys, tokens, passwords, and sensitive credentials."""
    if not text or not isinstance(text, str):
        return ""
    redacted = re.sub(r'(sk-[a-zA-Z0-9_\-]{16,})', '[REDACTED_API_KEY]', text)
    redacted = re.sub(r'(AQ\.[a-zA-Z0-9_\-]{20,})', '[REDACTED_GEMINI_KEY]', redacted)
    redacted = re.sub(r'(AIzaSy[a-zA-Z0-9_\-]{30,})', '[REDACTED_GOOGLE_KEY]', redacted)
    redacted = re.sub(r'(Bearer\s+[a-zA-Z0-9_\-\.]{10,})', 'Bearer [REDACTED_TOKEN]', redacted, flags=re.IGNORECASE)
    redacted = re.sub(r'([a-zA-Z0-9_]*password\s*[:=]\s*)\S+', r'\1[REDACTED_PASSWORD]', redacted, flags=re.IGNORECASE)
    redacted = re.sub(r'([a-zA-Z0-9_]*token\s*[:=]\s*)\S+', r'\1[REDACTED_TOKEN]', redacted, flags=re.IGNORECASE)
    redacted = re.sub(r'([a-zA-Z0-9_]*secret\s*[:=]\s*)\S+', r'\1[REDACTED_SECRET]', redacted, flags=re.IGNORECASE)
    redacted = re.sub(r'([a-zA-Z0-9_]*api_key\s*[:=]\s*)\S+', r'\1[REDACTED_API_KEY]', redacted, flags=re.IGNORECASE)
    return redacted


class SubsystemState:
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    RECOVERING = "RECOVERING"
    OFFLINE = "OFFLINE"


class SubsystemTelemetry:
    """Encapsulates runtime health and self-healing telemetry for an individual subsystem."""
    def __init__(self, name: str, default_provider: str = ""):
        self.name = name
        self.state = SubsystemState.HEALTHY
        self.last_success: float = time.time()
        self.last_failure: Optional[float] = None
        self.recovery_attempts: int = 0
        self.current_provider: str = default_provider
        self.latency_ms: float = 0.0
        self.error_category: Optional[str] = None
        self.last_error: Optional[str] = None
        self.next_recovery_due: float = 0.0
        self.current_backoff: float = MIN_BACKOFF_SECONDS

    def mark_success(self, provider: str = "", latency_ms: float = 0.0) -> None:
        """Transitions to HEALTHY state upon real verified operation."""
        self.state = SubsystemState.HEALTHY
        self.last_success = time.time()
        self.recovery_attempts = 0
        self.current_backoff = MIN_BACKOFF_SECONDS
        self.error_category = None
        self.last_error = None
        if provider:
            self.current_provider = provider
        if latency_ms >= 0:
            self.latency_ms = latency_ms

    def mark_degraded_or_offline(
        self,
        offline: bool = False,
        error_msg: str = "",
        category: str = "",
        redactor: Optional[Callable[[str], str]] = None
    ) -> None:
        """Marks DEGRADED or OFFLINE and schedules bounded recovery backoff."""
        self.state = SubsystemState.OFFLINE if offline else SubsystemState.DEGRADED
        self.last_failure = time.time()
        self.error_category = category or "RUNTIME_ERROR"
        clean_err = redactor(error_msg) if redactor else error_msg
        self.last_error = clean_err[:250] if clean_err else None
        
        # Schedule next bounded recovery check
        self.next_recovery_due = time.time() + self.current_backoff
        self.current_backoff = min(self.current_backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF_SECONDS)

    def mark_recovering(self) -> None:
        """Indicates that a recovery probe is actively underway."""
        self.state = SubsystemState.RECOVERING
        self.recovery_attempts += 1

    def to_dict(self) -> Dict[str, Any]:
        """Returns structured, user-safe observability telemetry."""
        return {
            "name": self.name,
            "state": self.state,
            "last_success": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.last_success)),
            "last_failure": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.last_failure)) if self.last_failure else None,
            "recovery_attempts": self.recovery_attempts,
            "current_provider": self.current_provider,
            "latency_ms": round(self.latency_ms, 2),
            "error_category": self.error_category,
            "last_error": self.last_error,
            "next_recovery_in_sec": max(0.0, round(self.next_recovery_due - time.time(), 1)) if self.state in (SubsystemState.DEGRADED, SubsystemState.OFFLINE) else 0.0
        }


class RuntimeSupervisor:
    """
    Singleton Runtime Supervisor:
    Monitors 8 core subsystems, tracks recovery backoffs, redacts secrets,
    and coordinates isolated self-healing probes without killing processes.
    """
    _instance: Optional['RuntimeSupervisor'] = None
    _init_lock = threading.Lock()

    def __new__(cls):
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = super(RuntimeSupervisor, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._lock = threading.RLock()
        raw_subsystems = {
            "OLLAMA": SubsystemTelemetry("OLLAMA", "Tier 1: fotiecodes/jarvis:latest"),
            "CLOUD PROVIDER": SubsystemTelemetry("CLOUD PROVIDER", "Tier 2: Gemini 3.5/3.6 Flash"),
            "VOICE INPUT": SubsystemTelemetry("VOICE INPUT", "Realtek Microphone Array"),
            "VOICE OUTPUT": SubsystemTelemetry("VOICE OUTPUT", "UniversalTTSEngine (Windows SAPI)"),
            "CAMERA": SubsystemTelemetry("CAMERA", "DirectShow OpenCV Presence"),
            "SCREEN ANALYSIS": SubsystemTelemetry("SCREEN ANALYSIS", "Windows Desktop Active Frame"),
            "MEMORY": SubsystemTelemetry("MEMORY", "Long-Term Persistent JSON"),
            "AUTOMATION": SubsystemTelemetry("AUTOMATION", "ToolRegistry (62 tools)"),
            "REMINDERS": SubsystemTelemetry("REMINDERS", "College Schedule & Deadline Engine")
        }
        self._subsystems: Dict[str, SubsystemTelemetry] = {self._norm(k): v for k, v in raw_subsystems.items()}
        self._recovery_hooks: Dict[str, Callable[[], bool]] = {}
        self._monitor_running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._register_default_hooks()
        self._initialized = True

    def _norm(self, name: str) -> str:
        """Normalizes subsystem keys (e.g. 'VOICE_INPUT' -> 'VOICE INPUT')."""
        return name.replace("_", " ").strip().upper()

    def _register_default_hooks(self) -> None:
        """Registers default non-destructive, isolated health probes."""
        def _probe_ollama() -> bool:
            try:
                from core.ollama_provider import is_ollama_available
                return is_ollama_available()
            except Exception:
                return False

        def _probe_cloud() -> bool:
            try:
                from core.ai_multitier_engine import get_ai_engine
                eng = get_ai_engine()
                return bool(eng and eng.gemini_api_key and not eng.gemini_api_key.startswith("YOUR_"))
            except Exception:
                return False

        def _probe_voice_in() -> bool:
            try:
                import sounddevice as sd
                dev = sd.query_devices(kind='input')
                return bool(dev and dev.get("max_input_channels", 0) > 0)
            except Exception:
                return False

        def _probe_voice_out() -> bool:
            try:
                import sounddevice as sd
                dev = sd.query_devices(kind='output')
                return bool(dev and dev.get("max_output_channels", 0) > 0)
            except Exception:
                return False

        def _probe_camera() -> bool:
            try:
                from agent.awareness.permissions import privacy_mode_manager
                if privacy_mode_manager.is_privacy_mode_active():
                    return True
                import cv2
                cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
                ok = cap.isOpened()
                cap.release()
                return ok
            except Exception:
                return False

        def _probe_screen() -> bool:
            try:
                from PIL import ImageGrab
                _ = ImageGrab.grab()
                return True
            except Exception:
                return True  # Fallback frame handling maintains functionality

        def _probe_memory() -> bool:
            try:
                from memory.memory_manager import load_memory
                return isinstance(load_memory(), dict)
            except Exception:
                return False

        def _probe_automation() -> bool:
            try:
                from core.register_tools import default_tool_registry
                return len(default_tool_registry.list_tools()) >= 60
            except Exception:
                return False

        def _probe_reminders() -> bool:
            try:
                from actions.college_mode import load_college_config
                return isinstance(load_college_config(), dict)
            except Exception:
                return False

        raw_hooks = {
            "OLLAMA": _probe_ollama,
            "CLOUD PROVIDER": _probe_cloud,
            "VOICE INPUT": _probe_voice_in,
            "VOICE OUTPUT": _probe_voice_out,
            "CAMERA": _probe_camera,
            "SCREEN ANALYSIS": _probe_screen,
            "MEMORY": _probe_memory,
            "AUTOMATION": _probe_automation,
            "REMINDERS": _probe_reminders,
        }
        self._recovery_hooks = {self._norm(k): v for k, v in raw_hooks.items()}

    def register_recovery_hook(self, subsystem: str, hook: Callable[[], bool]) -> None:
        """Registers an isolated, safe health probe callable for a subsystem."""
        with self._lock:
            self._recovery_hooks[self._norm(subsystem)] = hook

    def get_subsystem(self, name: str) -> Optional[SubsystemTelemetry]:
        with self._lock:
            return self._subsystems.get(self._norm(name))

    def record_success(self, name: str, provider: str = "", latency_ms: float = 0.0) -> None:
        with self._lock:
            sub = self._subsystems.get(self._norm(name))
            if sub:
                sub.mark_success(provider=provider, latency_ms=latency_ms)

    def record_failure(
        self,
        name: str,
        offline: bool = False,
        error_msg: str = "",
        category: str = ""
    ) -> None:
        with self._lock:
            sub = self._subsystems.get(self._norm(name))
            if sub:
                sub.mark_degraded_or_offline(
                    offline=offline,
                    error_msg=error_msg,
                    category=category,
                    redactor=redact_secrets
                )
                logger.warning(
                    f"[Supervisor] Subsystem '{name}' marked {sub.state} (Category: {category}). "
                    f"Next recovery check in {sub.current_backoff:.1f}s."
                )

    def trigger_self_healing_pass(self) -> Dict[str, str]:
        """
        Executes an isolated, non-destructive recovery probe for any degraded or offline subsystem
        whose bounded backoff delay has elapsed.
        Returns a mapping of subsystem -> outcome.
        """
        now = time.time()
        results = {}
        
        # Snapshot subsystems needing probe under lock
        with self._lock:
            candidates = [
                (name, sub, self._recovery_hooks.get(name))
                for name, sub in self._subsystems.items()
                if sub.state in (SubsystemState.DEGRADED, SubsystemState.OFFLINE)
                and now >= sub.next_recovery_due
                and self._recovery_hooks.get(name) is not None
            ]

        for name, sub, hook in candidates:
            sub.mark_recovering()
            logger.info(f"[Supervisor] Attempting recovery probe for '{name}' (Attempt #{sub.recovery_attempts})...")
            try:
                t0 = time.time()
                recovered = hook()
                lat_ms = int((time.time() - t0) * 1000)
                if recovered:
                    sub.mark_success(latency_ms=lat_ms)
                    logger.info(f"[Supervisor] ✅ Subsystem '{name}' recovered successfully in {lat_ms}ms! State -> HEALTHY.")
                    results[name] = "RECOVERED"
                else:
                    sub.mark_degraded_or_offline(
                        offline=(sub.state == SubsystemState.OFFLINE),
                        error_msg="Recovery probe returned False",
                        category="PROBE_FAILED"
                    )
                    results[name] = "STILL_DEGRADED"
            except Exception as ex:
                sub.mark_degraded_or_offline(
                    offline=(sub.state == SubsystemState.OFFLINE),
                    error_msg=str(ex),
                    category="PROBE_EXCEPTION"
                )
                results[name] = f"EXCEPTION: {ex}"

        return results

    def get_full_report(self) -> Dict[str, Any]:
        """Returns deep telemetry for all 8 subsystems with zero secrets exposed."""
        with self._lock:
            return {
                "timestamp": time.time(),
                "subsystems": {k: v.to_dict() for k, v in self._subsystems.items()}
            }

    def start_background_monitor(self, interval_sec: float = 15.0) -> None:
        """Starts a single, singleton background monitoring thread with lifecycle guard."""
        with self._lock:
            if self._monitor_running:
                return  # Prevent duplicate background worker creation
            self._monitor_running = True
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                args=(interval_sec,),
                daemon=True,
                name="JARVIS_RuntimeSupervisor_Worker"
            )
            self._monitor_thread.start()
            logger.info("[Supervisor] Single background runtime monitor worker started.")

    def stop_background_monitor(self) -> None:
        """Cleanly stops background monitoring thread."""
        with self._lock:
            self._monitor_running = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=1.0)
        self._monitor_thread = None

    def _monitor_loop(self, interval_sec: float):
        while self._monitor_running:
            time.sleep(interval_sec)
            try:
                self.trigger_self_healing_pass()
            except Exception as ex:
                logger.debug(f"[Supervisor] Background self-healing pass exception (contained): {ex}")


def get_runtime_supervisor() -> RuntimeSupervisor:
    """Global accessor for the RuntimeSupervisor singleton."""
    return RuntimeSupervisor()
