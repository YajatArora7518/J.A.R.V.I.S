# core/sleep_wake_monitor.py
# Windows Sleep / Wake Hardware Recovery Coordinator for J.A.R.V.I.S.

import time
import logging
import threading
from typing import Callable, List, Optional, Dict, Any

logger = logging.getLogger("JARVIS.SleepWakeMonitor")

class SleepWakeMonitor:
    """
    Singleton Sleep/Wake & Hardware Hot-Swap Monitor:
    - Tracks monotonic drift to reliably detect system sleep/wake cycles.
    - Coordinates non-destructive re-probing for audio, camera, network, and Ollama upon wake.
    - Zero duplicate background worker threads.
    - Zero leaked hardware handles.
    - Preserves Privacy Mode strictly across sleep/wake events.
    """
    _instance: Optional['SleepWakeMonitor'] = None
    _init_lock = threading.Lock()

    def __new__(cls):
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = super(SleepWakeMonitor, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._lock = threading.RLock()
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._callbacks: List[Callable[[float], None]] = []
        self._drift_threshold_sec = 10.0  # Unexpected time jump indicating system sleep
        self._check_interval_sec = 3.0
        self._last_wake_time: float = 0.0
        self._wake_count: int = 0
        self._initialized = True

    def register_wake_callback(self, callback: Callable[[float], None]) -> None:
        """Registers a callback to execute upon detected system wake."""
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def trigger_wake_recovery(self, elapsed_sleep_sec: float = 0.0) -> Dict[str, Any]:
        """
        Executes bounded, safe hardware recovery pass.
        Can be triggered automatically by clock drift or programmatically by tests/OS events.
        """
        with self._lock:
            self._last_wake_time = time.time()
            self._wake_count += 1
            callbacks = list(self._callbacks)

        logger.info(f"[SleepWake] System wake event #{self._wake_count} detected (Drift: {elapsed_sleep_sec:.1f}s). Initiating hardware recovery...")

        recovery_report: Dict[str, Any] = {
            "wake_count": self._wake_count,
            "elapsed_sleep_sec": elapsed_sleep_sec,
            "subsystems_probed": []
        }

        # 1. Re-probe Audio Input / Output
        try:
            import sounddevice as sd
            in_dev = sd.query_devices(kind='input')
            out_dev = sd.query_devices(kind='output')
            audio_ok = bool(in_dev and out_dev)
            recovery_report["subsystems_probed"].append({
                "name": "AUDIO",
                "status": "RECOVERED" if audio_ok else "DEGRADED",
                "details": f"In: {in_dev.get('name') if in_dev else None} | Out: {out_dev.get('name') if out_dev else None}"
            })
            from core.runtime_supervisor import get_runtime_supervisor
            sup = get_runtime_supervisor()
            if in_dev and in_dev.get("max_input_channels", 0) > 0:
                sup.record_success("VOICE INPUT")
            if out_dev and out_dev.get("max_output_channels", 0) > 0:
                sup.record_success("VOICE OUTPUT")
        except Exception as ae:
            recovery_report["subsystems_probed"].append({"name": "AUDIO", "status": "ERROR", "error": str(ae)})

        # 2. Re-probe Camera (Strictly respect Privacy Mode)
        try:
            from agent.awareness.permissions import privacy_mode_manager
            is_privacy = privacy_mode_manager.is_privacy_mode_active()
            if is_privacy:
                # Privacy mode active: Do NOT touch camera hardware
                recovery_report["subsystems_probed"].append({
                    "name": "CAMERA",
                    "status": "PRESERVED_PRIVACY",
                    "details": "Privacy Mode active: Hardware probe bypassed"
                })
            else:
                import cv2
                cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
                cam_ok = cap.isOpened()
                cap.release()
                recovery_report["subsystems_probed"].append({
                    "name": "CAMERA",
                    "status": "RECOVERED" if cam_ok else "OFFLINE",
                    "details": f"Camera opened: {cam_ok}"
                })
                from core.runtime_supervisor import get_runtime_supervisor
                if cam_ok:
                    get_runtime_supervisor().record_success("CAMERA")
        except Exception as ce:
            recovery_report["subsystems_probed"].append({"name": "CAMERA", "status": "ERROR", "error": str(ce)})

        # 3. Re-probe Local Ollama & Cloud
        try:
            from core.runtime_supervisor import get_runtime_supervisor
            sup = get_runtime_supervisor()
            healing_results = sup.trigger_self_healing_pass()
            recovery_report["supervisor_healing"] = healing_results
        except Exception as se:
            recovery_report["supervisor_healing"] = {"error": str(se)}

        # 4. Invoke Registered Callbacks
        for cb in callbacks:
            try:
                cb(elapsed_sleep_sec)
            except Exception as cbe:
                logger.debug(f"[SleepWake] Wake callback error (contained): {cbe}")

        logger.info("[SleepWake] Hardware recovery pass completed.")
        return recovery_report

    def start_monitoring(self) -> None:
        """Starts a single, guarded background thread checking for system sleep/wake drift."""
        with self._lock:
            if self._running:
                return  # Prevent duplicate monitor threads
            self._running = True
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                daemon=True,
                name="JARVIS_SleepWake_Worker"
            )
            self._monitor_thread.start()
            logger.info("[SleepWake] Background sleep/wake monitor thread started.")

    def stop_monitoring(self) -> None:
        """Cleanly stops the background thread."""
        with self._lock:
            self._running = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=1.0)
        self._monitor_thread = None

    def _monitor_loop(self) -> None:
        last_tick = time.monotonic()
        while self._running:
            time.sleep(self._check_interval_sec)
            if not self._running:
                break
            now_tick = time.monotonic()
            expected_elapsed = self._check_interval_sec
            actual_elapsed = now_tick - last_tick
            drift = actual_elapsed - expected_elapsed

            if drift > self._drift_threshold_sec:
                logger.warning(f"[SleepWake] Monotonic clock jump detected ({drift:.1f}s drift). System likely woke from sleep.")
                try:
                    self.trigger_wake_recovery(elapsed_sleep_sec=drift)
                except Exception as ex:
                    logger.debug(f"[SleepWake] Wake recovery exception (contained): {ex}")

            last_tick = time.monotonic()


def get_sleep_wake_monitor() -> SleepWakeMonitor:
    """Global accessor for SleepWakeMonitor singleton."""
    return SleepWakeMonitor()
