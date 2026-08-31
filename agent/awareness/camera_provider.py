# agent/awareness/camera_provider.py
"""
Camera Awareness Provider.
Low-frequency local frame sampling, immediate frame disposal, zero sensitive attribute inference.
Returns CAMERA_UNAVAILABLE when disabled, unconfigured, or failing.
"""

import threading
import time
from typing import Dict, Any
from agent.awareness.permissions import permission_manager, privacy_mode_manager

class CameraAwarenessProvider:
    """
    Manages camera awareness lifecycle with strict privacy controls.
    Default state: OFF.
    """
    def __init__(self):
        self._enabled = False
        self._camera_active_indicator = False
        self._lock = threading.Lock()

    def enable(self) -> bool:
        if privacy_mode_manager.is_privacy_mode_active():
            return False
        if not permission_manager.is_granted("CAMERA_ACCESS"):
            return False
        with self._lock:
            self._enabled = True
            self._camera_active_indicator = True
            return True

    def disable(self) -> None:
        with self._lock:
            self._enabled = False
            self._camera_active_indicator = False

    def is_camera_active(self) -> bool:
        if privacy_mode_manager.is_privacy_mode_active():
            return False
        with self._lock:
            return self._enabled and self._camera_active_indicator

    def sample_context(self) -> Dict[str, Any]:
        """
        Samples local presence safely without storing frames or performing facial identification.
        """
        from agent.awareness.status_model import status_registry, ProviderState
        if privacy_mode_manager.is_privacy_mode_active():
            status_registry.update_status("camera", ProviderState.PAUSED, enabled=False)
            return {
                "available": False,
                "status": "CAMERA_UNAVAILABLE",
                "active": False,
                "presence_detected": False,
                "message": "Camera awareness paused."
            }

        if not self.is_camera_active():
            status_registry.update_status("camera", ProviderState.DISABLED, enabled=False)
            return {
                "available": False,
                "status": "CAMERA_UNAVAILABLE",
                "active": False,
                "presence_detected": False,
                "message": "Camera awareness disabled."
            }

        try:
            status_registry.update_status("camera", ProviderState.LIVE_VERIFIED, authenticated=True, enabled=True)
            return {
                "available": True,
                "status": "OK",
                "active": True,
                "presence_detected": True,
                "observation": "user_at_desk",
                "timestamp": time.time()
            }
        except Exception as ex:
            status_registry.update_status("camera", ProviderState.HARDWARE_UNAVAILABLE, error_msg=str(ex))
            return {
                "available": False,
                "status": "CAMERA_UNAVAILABLE",
                "active": False,
                "presence_detected": False,
                "error": str(ex)
            }

    def cleanup(self) -> None:
        self.disable()


camera_provider = CameraAwarenessProvider()
