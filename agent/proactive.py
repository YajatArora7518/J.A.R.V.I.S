# agent/proactive.py
# Proactive System & Health Monitor for JARVIS

import time
import threading
from typing import Callable, Optional

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False


class ProactiveMonitor:
    """
    Monitors system battery, CPU/RAM thresholds, and active task progress.
    Emits alerts to UI/Voice without automatically triggering destructive actions.
    """
    def __init__(self, alert_callback: Optional[Callable[[str], None]] = None):
        self.alert_callback = alert_callback
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._battery_alerted = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="ProactiveMonitorThread")
        self._thread.start()
        try:
            from agent.ambient_orchestrator import ambient_orchestrator
            ambient_orchestrator.speak_callback = self.alert_callback
            ambient_orchestrator.start()
        except Exception:
            pass

    def stop(self) -> None:
        self._running = False
        try:
            from agent.ambient_orchestrator import ambient_orchestrator
            ambient_orchestrator.stop()
        except Exception:
            pass

    def _monitor_loop(self) -> None:
        while self._running:
            time.sleep(30)
            if not self._running:
                break

            # 1. Battery Check
            if _HAS_PSUTIL:
                try:
                    battery = psutil.sensors_battery()
                    if battery:
                        percent = battery.percent
                        is_plugged = battery.power_plugged
                        if percent <= 15 and not is_plugged and not self._battery_alerted:
                            msg = f"Sir, your battery is at {int(percent)}%. Please connect your power adapter."
                            print(f"[Proactive] ⚠️ {msg}")
                            if self.alert_callback:
                                self.alert_callback(msg)
                            self._battery_alerted = True
                        elif percent > 20:
                            self._battery_alerted = False
                except Exception:
                    pass


default_proactive_monitor = ProactiveMonitor()
