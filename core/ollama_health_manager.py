# core/ollama_health_manager.py
# Autonomous Local Ollama Health Monitor, Latency Tracker & Auto-Recovery Engine for JARVIS

import os
import time
import logging
import threading
from typing import Dict, Any, List, Optional
import statistics

from core.ollama_provider import (
    is_ollama_available,
    check_ollama_health,
    auto_start_ollama,
    get_available_ollama_models,
    OLLAMA_BASE_URL,
    OLLAMA_READY,
    OLLAMA_UNAVAILABLE,
    OLLAMA_STARTING,
    OLLAMA_MODEL_MISSING,
    OLLAMA_ERROR
)

logger = logging.getLogger("JARVIS.OllamaHealth")

# Status Constants for UI/HUD
STATUS_ONLINE = "ONLINE"
STATUS_STARTING = "STARTING"
STATUS_UNAVAILABLE = "UNAVAILABLE"
STATUS_DEGRADED = "DEGRADED"
STATUS_RECOVERING = "RECOVERING"

MAX_BOUNDED_TIMEOUT_SEC = 15.0  # Strict upper bound for any local inference call


class OllamaHealthManager:
    """
    Supervises local Ollama server health, tracks rolling inference latency,
    provides bounded timeout guards, and performs autonomous recovery.
    """
    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        poll_interval_sec: float = 10.0,
        max_latency_history: int = 50
    ):
        self.base_url = base_url
        self.poll_interval_sec = poll_interval_sec
        self.max_latency_history = max_latency_history

        self._lock = threading.Lock()
        self._latencies: List[float] = []
        self._consecutive_failures = 0
        self._last_check_time = 0.0
        self._last_status = STATUS_STARTING
        self._cached_health: Dict[str, Any] = {}
        self._is_recovering = False
        self._next_recovery_at = 0.0
        self._recovery_cooldown_sec = 300.0

        # Run initial check synchronously
        self._run_check()

        # Start non-blocking background supervisor thread
        self._stop_event = threading.Event()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="OllamaHealthMonitor_Daemon"
        )
        self._monitor_thread.start()
        logger.info(f"[OllamaHealthManager] Initialized. Current status: {self._last_status}")

    def record_latency(self, latency_ms: float) -> None:
        """Records a successful inference call latency."""
        with self._lock:
            self._latencies.append(latency_ms)
            if len(self._latencies) > self.max_latency_history:
                self._latencies.pop(0)

    def get_latency_metrics(self) -> Dict[str, Any]:
        """Calculates p50, p90, p95, min, max and avg latency across rolling history."""
        with self._lock:
            if not self._latencies:
                return {
                    "count": 0,
                    "last_ms": None,
                    "p50_ms": None,
                    "p90_ms": None,
                    "p95_ms": None,
                    "avg_ms": None,
                    "min_ms": None,
                    "max_ms": None
                }
            sorted_lat = sorted(self._latencies)
            n = len(sorted_lat)

            def percentile(p: float) -> float:
                idx = max(0, min(int(p * n) - 1, n - 1))
                return sorted_lat[idx]

            return {
                "count": n,
                "last_ms": round(self._latencies[-1], 2),
                "p50_ms": round(percentile(0.50), 2),
                "p90_ms": round(percentile(0.90), 2),
                "p95_ms": round(percentile(0.95), 2),
                "avg_ms": round(statistics.mean(self._latencies), 2),
                "min_ms": round(sorted_lat[0], 2),
                "max_ms": round(sorted_lat[-1], 2)
            }

    def _run_check(self) -> Dict[str, Any]:
        """Performs atomic health check and auto-recovery if needed."""
        now = time.time()
        health = check_ollama_health(self.base_url)
        self._cached_health = health
        self._last_check_time = now

        if health.get("ready"):
            with self._lock:
                self._consecutive_failures = 0
                self._next_recovery_at = 0.0
                # If latency p95 > 8000ms, mark degraded
                metrics = self._latencies
                if metrics and len(metrics) >= 3 and metrics[-1] > 8000.0:
                    self._last_status = STATUS_DEGRADED
                else:
                    self._last_status = STATUS_ONLINE
        else:
            with self._lock:
                self._consecutive_failures += 1
                if self._is_recovering:
                    self._last_status = STATUS_RECOVERING
                elif self._consecutive_failures >= 2:
                    self._last_status = STATUS_UNAVAILABLE
                else:
                    self._last_status = STATUS_DEGRADED

            # Auto-recovery trigger on failure
            if not self._is_recovering and self._consecutive_failures >= 1:
                self._trigger_recovery()

        return self._cached_health

    def _trigger_recovery(self) -> None:
        """Attempts background autonomous restart of Ollama."""
        with self._lock:
            now = time.monotonic()
            if self._is_recovering or now < self._next_recovery_at:
                return
            # Reserve before spawning so concurrent checks cannot queue workers.
            self._is_recovering = True
            self._next_recovery_at = now + self._recovery_cooldown_sec
            self._last_status = STATUS_RECOVERING

        def _recover():
            logger.warning("[OllamaHealthManager] Initiating autonomous recovery for Ollama...")
            try:
                success = auto_start_ollama(self.base_url, max_wait_sec=4.0)
                if success:
                    logger.info("[OllamaHealthManager] Autonomous recovery succeeded. Ollama is back ONLINE.")
                    with self._lock:
                        self._consecutive_failures = 0
                        self._last_status = STATUS_ONLINE
                else:
                    logger.error("[OllamaHealthManager] Autonomous recovery failed. Ollama remains UNAVAILABLE.")
                    with self._lock:
                        self._last_status = STATUS_UNAVAILABLE
            except Exception as e:
                logger.error(f"[OllamaHealthManager] Recovery exception: {e}")
                with self._lock:
                    self._last_status = STATUS_UNAVAILABLE
            finally:
                with self._lock:
                    self._is_recovering = False

        threading.Thread(target=_recover, daemon=True, name="Ollama_AutoRecovery_Worker").start()

    def _monitor_loop(self) -> None:
        """Continuous background monitor loop."""
        while not self._stop_event.is_set():
            if self._stop_event.wait(self.poll_interval_sec):
                break
            try:
                self._run_check()
            except Exception as e:
                logger.debug(f"[OllamaHealthManager] Background check error: {e}")

    def get_status(self) -> str:
        """Returns current high-level status string."""
        with self._lock:
            return self._last_status

    def is_healthy(self) -> bool:
        """Returns True if local Ollama is ready and responsive."""
        return bool(self._cached_health.get("ready")) and self.get_status() in (STATUS_ONLINE, STATUS_DEGRADED)

    def get_bounded_timeout(self, requested_timeout: float = 15.0) -> float:
        """Clamps requested timeout to MAX_BOUNDED_TIMEOUT_SEC to prevent infinite hangs."""
        return max(1.0, min(requested_timeout, MAX_BOUNDED_TIMEOUT_SEC))

    def get_hud_status(self) -> Dict[str, Any]:
        """Provides rich status dictionary formatted for JARVIS HUD / UI."""
        status = self.get_status()
        color_map = {
            STATUS_ONLINE: "green",
            STATUS_DEGRADED: "yellow",
            STATUS_STARTING: "cyan",
            STATUS_RECOVERING: "orange",
            STATUS_UNAVAILABLE: "red"
        }
        lat_metrics = self.get_latency_metrics()
        models = self._cached_health.get("models", [])
        return {
            "component": "Local Ollama Brain",
            "status": status,
            "color": color_map.get(status, "gray"),
            "is_online": self.is_healthy(),
            "available_models": models,
            "model_count": len(models),
            "latency": lat_metrics,
            "last_check": round(self._last_check_time, 2)
        }

    def stop(self) -> None:
        """Stops background monitor thread."""
        self._stop_event.set()


# Thread-safe singleton
_HEALTH_MGR_LOCK = threading.Lock()
_HEALTH_MGR_INSTANCE: Optional[OllamaHealthManager] = None

def get_health_manager(base_url: str = OLLAMA_BASE_URL) -> OllamaHealthManager:
    """Thread-safe singleton accessor for OllamaHealthManager."""
    global _HEALTH_MGR_INSTANCE
    with _HEALTH_MGR_LOCK:
        if _HEALTH_MGR_INSTANCE is None:
            _HEALTH_MGR_INSTANCE = OllamaHealthManager(base_url=base_url)
        return _HEALTH_MGR_INSTANCE
