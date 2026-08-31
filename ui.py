# ui.py
# J.A.R.V.I.S — Futuristic Multi-Panel AI Command Center & Side Chat Interface (PyQt6 + WebGL + MediaPipe)

from __future__ import annotations

import json
import logging
import math
import os
import platform
import random
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("JARVIS.UI")

import psutil
from PIL import ImageGrab

from PyQt6.QtCore import (
    QEasingCurve, QMimeData, QObject, QPointF, QRectF, QSize, Qt,
    QThread, QTimer, QUrl, pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush, QColor, QDragEnterEvent, QDropEvent, QFont, QFontDatabase,
    QIcon, QKeySequence, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
    QRadialGradient, QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QPushButton, QProgressBar, QScrollArea,
    QSizePolicy, QSlider, QStackedLayout, QTextEdit, QVBoxLayout, QWidget,
)

# ── WebEngine for 3D Core (graceful fallback) ──
_HAS_WEBENGINE = False
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage
    try:
        from PyQt6.QtWebChannel import QWebChannel
    except ImportError:
        QWebChannel = None
    _HAS_WEBENGINE = True
except ImportError:
    print("[UI] PyQt6-WebEngine not available - falling back to 2D HUD Canvas")

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR   = _base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE   = CONFIG_DIR / "api_keys.json"

_DEFAULT_W, _DEFAULT_H = 1440, 880
_MIN_W,     _MIN_H     = 1100, 680

_OS = platform.system()  # "Windows" | "Darwin" | "Linux"

# ════════════════════════════════════════════════════════════
# EYE-COMFORTABLE MULTI-COLOR PALETTE SYSTEM (70 / 20 / 10)
# ════════════════════════════════════════════════════════════
class C:
    BG          = "#07111F"  # Deep navy base (70%)
    BG_MID      = "#0B1628"  # Midnight blue
    BG_SURF     = "#111D2E"  # Slate blue-gray surface
    PANEL       = "rgba(12, 24, 40, 0.78)"   # Glass panel fill
    PANEL2      = "rgba(18, 31, 50, 0.75)"   # Darker glass panel fill

    BORDER      = "rgba(86, 224, 232, 0.22)"  # Soft cyan border
    BORDER_B    = "rgba(79, 124, 255, 0.28)"  # Royal blue border
    BORDER_V    = "rgba(139, 114, 217, 0.25)" # Violet border
    BORDER_A    = "#56E0E8"

    PRI         = "#56E0E8"  # Soft cyan (20%)
    CYAN_ELEC   = "#00C8D7"  # Electric cyan
    TEAL        = "#20B8A6"  # Teal / Emerald
    BLUE_ROYAL  = "#4F7CFF"  # Royal blue
    PRI_DIM     = "#4F7CFF"
    PRI_GHO     = "rgba(86, 224, 232, 0.12)"

    INDIGO      = "#6978E8"  # Soft Indigo (10%)
    VIOLET      = "#8B72D9"  # Violet
    AMBER       = "#D9A441"  # Soft Amber/Gold
    ACC         = "#6978E8"
    GREEN       = "#20B8A6"  # Soft Teal/Emerald
    RED         = "#E53E3E"  # Soft Red

    TEXT        = "#E8EEF5"  # Main text
    TEXT_DIM    = "#A7B4C5"  # Secondary text
    TEXT_MUTED  = "#718096"  # Muted text
    WHITE       = "#E8EEF5"
    DARK        = "#07111F"


def qcol(h: str, a: int = 255) -> QColor:
    if h.startswith("rgba"):
        parts = h.replace("rgba(", "").replace(")", "").split(",")
        r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
        alpha = int(float(parts[3]) * 255) if len(parts) > 3 else a
        return QColor(r, g, b, alpha)
    c = QColor(h)
    c.setAlpha(a)
    return c


# ════════════════════════════════════════════════════════════
# SYSTEM METRICS WORKER & WIN32 HELPERS
# ════════════════════════════════════════════════════════════
class _SysMetrics:
    def __init__(self):
        self.cpu  = 0.0
        self.mem  = 0.0
        self.disk = 0.0
        self.net  = 0.0
        self.batt = 100
        self._lock = threading.Lock()
        self._last_net = psutil.net_io_counters()
        self._last_net_t = time.time()
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        while self._running:
            try:
                self._update()
            except Exception:
                pass
            time.sleep(1.5)

    def _update(self):
        cpu  = psutil.cpu_percent(interval=None)
        mem  = psutil.virtual_memory().percent
        try:
            disk = psutil.disk_usage('C:\\' if _OS == "Windows" else '/').percent
        except Exception:
            disk = 0.0

        nc  = psutil.net_io_counters()
        now = time.time()
        dt  = now - self._last_net_t
        if dt > 0:
            sent = (nc.bytes_sent - self._last_net.bytes_sent) / dt
            recv = (nc.bytes_recv - self._last_net.bytes_recv) / dt
            net  = (sent + recv) / (1024 * 1024)
        else:
            net = 0.0
        self._last_net   = nc
        self._last_net_t = now

        batt_obj = psutil.sensors_battery()
        batt = int(batt_obj.percent) if batt_obj else 100

        with self._lock:
            self.cpu  = cpu
            self.mem  = mem
            self.disk = disk
            self.net  = net
            self.batt = batt

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "cpu":  self.cpu,
                "mem":  self.mem,
                "disk": self.disk,
                "net":  self.net,
                "batt": self.batt,
            }


_metrics = _SysMetrics()


def get_active_window_info() -> tuple[str, int]:
    """Returns (active_window_title, hwnd) on Windows safely."""
    if _OS == "Windows":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                return buff.value, hwnd
        except Exception:
            pass
    return "Desktop", 0


def focus_window_by_hwnd(hwnd: int) -> bool:
    """Safely brings specified window to foreground."""
    if _OS == "Windows" and hwnd > 0:
        try:
            import ctypes
            user32 = ctypes.windll.user32
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE = 9
            user32.SetForegroundWindow(hwnd)
            return True
        except Exception:
            pass
    return False


# ════════════════════════════════════════════════════════════
# ASYNCHRONOUS HAND TRACKER WORKER THREAD
# ════════════════════════════════════════════════════════════
class HandTrackerWorker(QThread):
    hand_signal = pyqtSignal(float, float, bool, str, float)  # (x, y, detected, gesture, depth)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True

    def stop(self):
        self._running = False
        self.wait(1000)

    def run(self):
        try:
            import cv2
        except ImportError:
            print("[HandTracker] OpenCV unavailable — defaulting to mouse interaction.")
            return

        has_mp = False
        hands = None
        try:
            import mediapipe as mp
            if hasattr(mp, "solutions") and hasattr(mp.solutions, "hands"):
                mp_hands = mp.solutions.hands
                hands = mp_hands.Hands(
                    static_image_mode=False,
                    max_num_hands=1,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5
                )
                has_mp = True
        except Exception as e:
            print(f"[HandTracker] MediaPipe initialization note: {e}")

        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW if _OS == "Windows" else cv2.CAP_ANY)
        if not cap.isOpened():
            print("[HandTracker] Webcam unavailable/busy — running in standard mode.")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        while self._running:
            try:
                ret, frame = cap.read()
                if not ret or frame is None:
                    time.sleep(0.04)
                    continue

                frame = cv2.flip(frame, 1)
                h, w, _ = frame.shape
                detected = False
                gx, gy = 0.5, 0.5
                gesture = "INDEX_POINT"
                depth = 1.0

                if has_mp and hands is not None:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    results = hands.process(rgb)
                    if results.multi_hand_landmarks:
                        detected = True
                        lm = results.multi_hand_landmarks[0].landmark

                        gx = lm[8].x
                        gy = lm[8].y

                        w_x, w_y = lm[0].x, lm[0].y
                        m_x, m_y = lm[9].x, lm[9].y
                        dist_wm = math.hypot(w_x - m_x, w_y - m_y)
                        depth = max(0.5, min(1.8, dist_wm * 4.0))

                        t_x, t_y = lm[4].x, lm[4].y
                        pinch_dist = math.hypot(gx - t_x, gy - t_y)

                        idx_ext = lm[8].y < lm[6].y
                        mid_ext = lm[12].y < lm[10].y
                        rng_ext = lm[16].y < lm[14].y
                        pky_ext = lm[20].y < lm[18].y

                        ext_count = sum([idx_ext, mid_ext, rng_ext, pky_ext])

                        if pinch_dist < 0.05:
                            gesture = "PINCH"
                        elif ext_count >= 3:
                            gesture = "OPEN_PALM"
                        elif ext_count == 0:
                            gesture = "FIST"
                        else:
                            gesture = "INDEX_POINT"

                self.hand_signal.emit(gx, gy, detected, gesture, depth)
                time.sleep(0.03)

            except Exception:
                time.sleep(0.05)

        try:
            cap.release()
        except Exception:
            pass


# ════════════════════════════════════════════════════════════
# HUD AUDIO WAVEFORM VISUALIZER
# ════════════════════════════════════════════════════════════
class WaveformVisualizer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setMinimumWidth(180)
        self.audio_level = 0.1
        self.state = "IDLE"
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self.update)
        self._anim_timer.start(50)
        self._phase = 0.0

    def set_level(self, level: float):
        self.audio_level = max(0.05, min(1.0, float(level)))

    def set_state(self, state: str):
        self.state = state.upper()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        cy = H / 2.0
        p.fillRect(self.rect(), Qt.GlobalColor.transparent)

        bars = 28
        bar_w = 4.0
        gap = (W - (bars * bar_w)) / (bars + 1)

        self._phase += 0.15

        color_map = {
            "LISTENING": C.PRI,
            "THINKING":  C.AMBER,
            "SPEAKING":  C.GREEN,
            "EXECUTING": C.VIOLET,
            "MUTED":      C.RED,
        }
        main_color = qcol(color_map.get(self.state, C.PRI))

        for i in range(bars):
            x = gap + i * (bar_w + gap)
            amp = math.sin(self._phase + i * 0.4) * 0.5 + 0.5
            if self.state in ("LISTENING", "SPEAKING"):
                h = 4 + amp * self.audio_level * (H - 8)
            elif self.state == "THINKING":
                h = 4 + math.sin(self._phase * 2 + i * 0.3) * 6 + 6
            else:
                h = 4 + math.sin(self._phase + i * 0.2) * 2

            h = min(H - 4, max(4, h))
            y = cy - (h / 2.0)

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(main_color))
            p.drawRoundedRect(QRectF(x, y, bar_w, h), 2, 2)


# ════════════════════════════════════════════════════════════
# 2D HUD CANVAS (Fallback if WebEngine not loaded)
# ════════════════════════════════════════════════════════════
class HudCanvas(QWidget):
    def __init__(self, face_path: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumSize(320, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.muted    = False
        self.speaking = False
        self.state    = "IDLE"
        self.audio_level = 0.1

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(30)
        self._rot = 0.0

    def setState(self, state: str):
        self.state = state.upper()

    def setAudioLevel(self, val: float):
        self.audio_level = val

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), qcol(C.BG))
        W, H = self.width(), self.height()
        cx, cy = W / 2.0, H / 2.0

        self._rot += 0.8 if self.state == "THINKING" else 0.3
        radius = min(W, H) * 0.28

        state_color = {
            "LISTENING": qcol(C.PRI),
            "THINKING":  qcol(C.AMBER),
            "SPEAKING":  qcol(C.GREEN),
            "EXECUTING": qcol(C.VIOLET),
            "MUTED":      qcol(C.RED),
            "ERROR":      qcol(C.RED),
        }.get(self.state, qcol(C.PRI))

        # Outer glowing radial ring
        p.setPen(QPen(qcol(state_color.name(), 180), 2, Qt.PenStyle.DashLine))
        p.drawEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))

        # Concentric rotating inner ring
        p.save()
        p.translate(cx, cy)
        p.rotate(self._rot)
        r_inner = radius * 0.75
        p.setPen(QPen(qcol(C.BLUE_ROYAL, 200), 2))
        for deg in range(0, 360, 30):
            rad = math.radians(deg)
            x1 = math.cos(rad) * (r_inner - 6)
            y1 = math.sin(rad) * (r_inner - 6)
            x2 = math.cos(rad) * (r_inner + 6)
            y2 = math.sin(rad) * (r_inner + 6)
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        p.restore()

        # Core Pulsing Orb
        pulse = math.sin(time.time() * 3.0) * 0.08 + (self.audio_level * 0.3)
        core_r = (radius * 0.45) * (1.0 + pulse)
        grad = QRadialGradient(cx, cy, core_r)
        grad.setColorAt(0.0, state_color)
        grad.setColorAt(0.7, qcol(C.CYAN_ELEC, 180))
        grad.setColorAt(1.0, qcol(C.BG, 0))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - core_r, cy - core_r, core_r * 2, core_r * 2))

        # HUD Text Labels
        p.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.TEXT), 255))
        p.drawText(QRectF(cx - 120, cy - 18, 240, 32), Qt.AlignmentFlag.AlignCenter, "J.A.R.V.I.S")

        p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        p.setPen(QPen(state_color, 220))
        p.drawText(QRectF(cx - 100, cy + 14, 200, 20), Qt.AlignmentFlag.AlignCenter, "SYSTEM ONLINE")


# ════════════════════════════════════════════════════════════
# 3D THREE.JS WEBGL CORE WRAPPER
# ════════════════════════════════════════════════════════════
_STATE_MAP = {
    "LISTENING":    "listening",
    "THINKING":     "thinking",
    "SEARCHING":    "searching",
    "PROCESSING":   "executing",
    "SPEAKING":     "speaking",
    "EXECUTING":    "executing",
    "MUTED":        "idle",
    "INITIALISING": "idle",
    "RECOVERING":   "error",
}

# ── QWebChannel Bridge for Holographic UI ──
class HoloBridge(QObject):
    def __init__(self, main_win: MainWindow):
        super().__init__()
        self._win = main_win

    from PyQt6.QtCore import pyqtSlot
    @pyqtSlot(str)
    def sendCommand(self, text: str):
        if hasattr(self._win, "_dispatch_command"):
            self._win._dispatch_command(text)

    @pyqtSlot(str)
    def send_text_command(self, text: str):
        if hasattr(self._win, "_dispatch_command"):
            self._win._dispatch_command(text)

    @pyqtSlot()
    def toggleMute(self):
        if hasattr(self._win, "_toggle_mute"):
            self._win._toggle_mute()

    @pyqtSlot(bool)
    def set_muted(self, muted: bool):
        if hasattr(self._win, "set_muted"):
            self._win.set_muted(muted)

    @pyqtSlot()
    def focusActiveWindow(self):
        if hasattr(self._win, "_focus_active_window"):
            self._win._focus_active_window()

    @pyqtSlot()
    def openMemorySearch(self):
        if hasattr(self._win, "_show_memory_search"):
            self._win._show_memory_search()

    @pyqtSlot()
    def openToolsRegistry(self):
        if hasattr(self._win, "_show_tools_registry_dialog"):
            self._win._show_tools_registry_dialog()

    @pyqtSlot()
    def attachFile(self):
        if hasattr(self._win, "_drop_zone") and hasattr(self._win._drop_zone, "_browse"):
            self._win._drop_zone._browse()

    @pyqtSlot(int)
    def setVolume(self, val: int):
        if hasattr(self._win, "_on_vol_changed"):
            self._win._on_vol_changed(val)

    @pyqtSlot(str)
    def executeTool(self, tool_name: str):
        cmd = f"Run tool {tool_name}" if not tool_name.startswith("Run ") else tool_name
        if hasattr(self._win, "_dispatch_command"):
            self._win._dispatch_command(cmd)
        elif hasattr(self._win, "_handle_command"):
            self._win._handle_command(cmd)


class JARVIS3DCore(QWidget):
    """Wraps QWebEngineView to render Three.js 3D AI Core."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.muted    = False
        self.speaking = False
        self.state    = "INITIALISING"

        self._page_ready = False
        self._pending_calls: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._web = QWebEngineView(self)
        settings = self._web.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        self._web.page().setBackgroundColor(QColor(7, 17, 31, 0))
        layout.addWidget(self._web)

        html_path = BASE_DIR / "assets" / "jarvis_holographic_ui.html"
        if not html_path.exists():
            html_path = BASE_DIR / "assets" / "jarvis_3d_core_holographic.html"
        if not html_path.exists():
            html_path = BASE_DIR / "assets" / "jarvis_3d_core.html"  # guaranteed fallback
        if html_path.exists():
            logger.info(f"[UI] Loading WebEngine HTML from: {html_path.resolve()}")
            self._web.setUrl(QUrl.fromLocalFile(str(html_path.resolve())))

        self._ready_timer = QTimer(self)
        self._ready_timer.timeout.connect(self._check_ready)
        self._ready_timer.start(200)

    def closeEvent(self, event):
        if hasattr(self, "_ready_timer") and self._ready_timer.isActive():
            self._ready_timer.stop()
        super().closeEvent(event)

    def _check_ready(self):
        if not hasattr(self, "_web") or self._web is None or self._page_ready:
            return
        try:
            self._web.page().runJavaScript(
                "typeof window._jarvis3dReady !== 'undefined' && window._jarvis3dReady === true",
                self._on_ready_result
            )
        except Exception:
            pass

    def _on_ready_result(self, result):
        if result and not self._page_ready:
            self._page_ready = True
            self._ready_timer.stop()
            for js in self._pending_calls:
                self._web.page().runJavaScript(js)
            self._pending_calls.clear()

    def _run_js(self, js: str):
        if self._page_ready:
            self._web.page().runJavaScript(js)
        else:
            self._pending_calls.append(js)

    def setState(self, state: str):
        if getattr(self, "_last_sent_state", None) == state:
            return
        self._last_sent_state = state
        self.state = state
        mapped = _STATE_MAP.get(state.upper(), "idle")
        self._run_js(f'window.JARVIS3DCore && window.JARVIS3DCore.setState("{mapped}")')

    def setCameraActive(self, active: bool):
        b_str = "true" if active else "false"
        self._run_js(f'window.setCameraState && window.setCameraState({b_str})')

    def setAudioLevel(self, value: float):
        v = max(0.0, min(1.0, float(value)))
        last_v = getattr(self, "_last_audio_level", -1.0)
        if abs(v - last_v) < 0.02 and (v < 0.03 or last_v < 0.03):
            return
        self._last_audio_level = v
        self._run_js(f'window.JARVIS3DCore && window.JARVIS3DCore.setAudioLevel({v:.4f})')

    def setHandPosition(self, x: float, y: float, gesture: str, depth: float):
        self._run_js(f'window.JARVIS3DCore && window.JARVIS3DCore.setHandPosition({x:.3f}, {y:.3f}, "{gesture}", {depth:.2f})')

    def setTelemetry(self, cpu: float, mem: float, disk: float, net: float, gpu: Any = None):
        if os.environ.get("JARVIS_HOLOGRAPHIC_INFO", "1") == "0":
            return
        gpu_val = f"{float(gpu):.1f}" if isinstance(gpu, (int, float)) else "null"
        self._run_js(f'window.JARVIS3DCore && window.JARVIS3DCore.setTelemetry && window.JARVIS3DCore.setTelemetry({cpu:.1f}, {mem:.1f}, {disk:.1f}, {net:.1f}, {gpu_val})')

    def setWeather(self, location: str, temp: Any, feels_like: Any = None, condition: str = "", humidity: Any = "", wind: Any = ""):
        if os.environ.get("JARVIS_HOLOGRAPHIC_INFO", "1") == "0":
            return
        loc_js = json.dumps(str(location or ""))
        cond_js = json.dumps(str(condition or ""))
        t_js = json.dumps(str(temp or ""))
        fl_js = json.dumps(str(feels_like or ""))
        h_js = json.dumps(str(humidity or ""))
        w_js = json.dumps(str(wind or ""))
        self._run_js(f'window.JARVIS3DCore && window.JARVIS3DCore.setWeather && window.JARVIS3DCore.setWeather({loc_js}, {t_js}, {fl_js}, {cond_js}, {h_js}, {w_js})')

    def setTime(self, time_str: str, date_str: str):
        if os.environ.get("JARVIS_HOLOGRAPHIC_INFO", "1") == "0":
            return
        t_js = json.dumps(str(time_str or ""))
        d_js = json.dumps(str(date_str or ""))
        self._run_js(f'window.JARVIS3DCore && window.JARVIS3DCore.setTime && window.JARVIS3DCore.setTime({t_js}, {d_js})')

    def setNews(self, query: str, headline: str):
        if os.environ.get("JARVIS_HOLOGRAPHIC_INFO", "1") == "0":
            return
        q_js = json.dumps(str(query or ""))
        h_js = json.dumps(str(headline or ""))
        self._run_js(f'window.JARVIS3DCore && window.JARVIS3DCore.setNews && window.JARVIS3DCore.setNews({q_js}, {h_js})')

    def setSearchResults(self, query: str, results: Any):
        if os.environ.get("JARVIS_HOLOGRAPHIC_INFO", "1") == "0":
            return
        q_js = json.dumps(str(query or ""))
        res_js = json.dumps(results if isinstance(results, (list, dict)) else str(results or ""))
        self._run_js(f'window.JARVIS3DCore && window.JARVIS3DCore.setSearchResults && window.JARVIS3DCore.setSearchResults({q_js}, {res_js})')

    def setResponse(self, text: str):
        if os.environ.get("JARVIS_HOLOGRAPHIC_INFO", "1") == "0":
            return
        txt_js = json.dumps(str(text or ""))
        self._run_js(f'window.JARVIS3DCore && window.JARVIS3DCore.setResponse && window.JARVIS3DCore.setResponse({txt_js})')

    def setTools(self, tools_list: list):
        tools_js = json.dumps(tools_list if isinstance(tools_list, list) else [])
        self._run_js(f'window.JARVIS3DCore && window.JARVIS3DCore.setTools && window.JARVIS3DCore.setTools({tools_js})')

    def setBattery(self, batt: int):
        self._run_js(f'window.JARVIS3DCore && window.JARVIS3DCore.setBattery && window.JARVIS3DCore.setBattery({int(batt)})')

    def setMicState(self, is_on: bool):
        b_str = "true" if is_on else "false"
        self._run_js(f'window.JARVIS3DCore && window.JARVIS3DCore.setMicState && window.JARVIS3DCore.setMicState({b_str})')

    def setAwareness(self, summary_str: str):
        sum_js = json.dumps(str(summary_str or ""))
        self._run_js(f'window.JARVIS3DCore && window.JARVIS3DCore.setAwareness && window.JARVIS3DCore.setAwareness({sum_js})')

    def setActiveWindow(self, title: str):
        t_js = json.dumps(str(title or ""))
        self._run_js(f'window.JARVIS3DCore && window.JARVIS3DCore.setActiveWindow && window.JARVIS3DCore.setActiveWindow({t_js})')

    def addAction(self, text: str):
        txt_js = json.dumps(str(text or ""))
        self._run_js(f'window.JARVIS3DCore && window.JARVIS3DCore.addAction && window.JARVIS3DCore.addAction({txt_js})')

    def appendLog(self, text: str):
        txt_js = json.dumps(str(text or ""))
        self._run_js(f'window.JARVIS3DCore && window.JARVIS3DCore.appendLog && window.JARVIS3DCore.appendLog({txt_js})')

    def appendChat(self, sender: str, message: str):
        s_js = json.dumps(str(sender or ""))
        m_js = json.dumps(str(message or ""))
        self._run_js(f'window.JARVIS3DCore && window.JARVIS3DCore.appendChat && window.JARVIS3DCore.appendChat({s_js}, {m_js})')

    def setCollegeInfo(self, text: str):
        txt_js = json.dumps(str(text or ""))
        self._run_js(f'window.JARVIS3DCore && window.JARVIS3DCore.setCollegeInfo && window.JARVIS3DCore.setCollegeInfo({txt_js})')

    def setMemoryStats(self, items: int, topics: int, updated: str):
        up_js = json.dumps(str(updated or ""))
        self._run_js(f'window.JARVIS3DCore && window.JARVIS3DCore.setMemoryStats && window.JARVIS3DCore.setMemoryStats({items}, {topics}, {up_js})')


# ════════════════════════════════════════════════════════════
# DEDICATED SIDE CHAT PANEL WIDGET
# ════════════════════════════════════════════════════════════
class JarvisChatPanel(QWidget):
    """Side Chat Panel for real-time conversation history with JARVIS."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(320)
        self.setMaximumWidth(440)
        self.setStyleSheet(f"""
            QWidget {{
                background: {C.PANEL};
                border: 1px solid {C.BORDER_B};
                border-radius: 12px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        # Header
        hdr_row = QHBoxLayout()
        hdr = QLabel("◈ JARVIS CHAT")
        hdr.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; border: none; background: transparent;")
        hdr_row.addWidget(hdr)
        hdr_row.addStretch()

        status_tag = QLabel("ONLINE")
        status_tag.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        status_tag.setStyleSheet(f"color: {C.GREEN}; background: {C.PANEL2}; border: 1px solid {C.GREEN}; border-radius: 8px; padding: 2px 8px;")
        hdr_row.addWidget(status_tag)
        lay.addLayout(hdr_row)

        # Chat Text Display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setFont(QFont("Segoe UI", 9))
        self.chat_display.setStyleSheet(f"""
            QTextEdit {{
                background: {C.PANEL2};
                color: {C.TEXT};
                border: 1px solid {C.BORDER};
                border-radius: 8px;
                padding: 10px;
            }}
            QScrollBar:vertical {{
                background: {C.BG};
                width: 5px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {C.PRI_DIM};
                border-radius: 2px;
            }}
        """)
        lay.addWidget(self.chat_display, stretch=1)

        # Chat Input Row
        in_row = QHBoxLayout()
        in_row.setSpacing(6)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Ask JARVIS anything...")
        self.input_field.setFont(QFont("Segoe UI", 9))
        self.input_field.setFixedHeight(34)
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                background: {C.PANEL2};
                color: {C.TEXT};
                border: 1px solid {C.BORDER_B};
                border-radius: 17px;
                padding: 4px 14px;
            }}
            QLineEdit:focus {{
                border-color: {C.PRI};
            }}
        """)
        in_row.addWidget(self.input_field)

        send_btn = QPushButton("➤")
        send_btn.setFixedSize(34, 34)
        send_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        send_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PRI};
                color: {C.DARK};
                border: none;
                border-radius: 17px;
            }}
            QPushButton:hover {{
                background: {C.PRI_DIM};
                color: #FFFFFF;
            }}
        """)
        in_row.addWidget(send_btn)

        lay.addLayout(in_row)

        self.on_send = None
        send_btn.clicked.connect(self._handle_send)
        self.input_field.returnPressed.connect(self._handle_send)

        self.append_message("JARVIS", "Hello sir, how may I assist you today?")

    def _handle_send(self):
        txt = self.input_field.text().strip()
        if not txt:
            return
        self.input_field.clear()
        self.append_message("You", txt)
        if self.on_send:
            self.on_send(txt)

    def append_message(self, sender: str, message: str):
        ts = time.strftime("[%H:%M]")
        if sender.lower() == "you":
            html = f'<div style="text-align: right; margin: 4px 0;"><span style="font-size: 8px; color: {C.TEXT_DIM};">{ts} </span><span style="font-weight: bold; color: {C.BLUE_ROYAL};">You:</span> <span style="color: {C.TEXT};">{message}</span></div>'
        elif sender.lower() == "jarvis":
            html = f'<div style="text-align: left; margin: 4px 0;"><span style="font-weight: bold; color: {C.PRI};">JARVIS:</span> <span style="color: {C.TEXT};">{message}</span> <span style="font-size: 8px; color: {C.TEXT_DIM};">{ts}</span></div>'
        else:
            html = f'<div style="text-align: left; margin: 2px 0;"><span style="font-size: 8px; color: {C.TEAL};">{ts} {message}</span></div>'

        self.chat_display.append(html)
        self.chat_display.ensureCursorVisible()


# ════════════════════════════════════════════════════════════
# SYSTEM EVENT CONSOLE LOG WIDGET
# ════════════════════════════════════════════════════════════
class LogWidget(QTextEdit):
    _sig = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Consolas", 8))
        self.setStyleSheet(f"""
            QTextEdit {{
                background: {C.PANEL2};
                color: {C.TEXT};
                border: 1px solid {C.BORDER};
                border-radius: 8px;
                padding: 6px;
            }}
            QScrollBar:vertical {{
                background: {C.BG};
                width: 4px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {C.PRI_DIM};
                border-radius: 2px;
            }}
        """)
        self._sig.connect(self._append)

    def append_log(self, text: str):
        self._sig.emit(text)

    def _append(self, text: str):
        ts = time.strftime("[%H:%M:%S]")
        colored = text
        if text.startswith("ERR") or "error" in text.lower() or "fail" in text.lower():
            colored = f'<span style="color: {C.RED}; font-weight: bold;">[ERROR] {text}</span>'
        elif text.startswith("SYS:") or "online" in text.lower() or "success" in text.lower():
            colored = f'<span style="color: {C.GREEN}; font-weight: bold;">[SUCCESS] {text}</span>'
        elif text.startswith("WARN") or "warning" in text.lower():
            colored = f'<span style="color: {C.AMBER}; font-weight: bold;">[WARNING] {text}</span>'
        else:
            colored = f'<span style="color: {C.PRI};">[INFO] {text}</span>'

        self.append(f'<span style="color: {C.TEXT_DIM};">{ts}</span> {colored}')
        self.ensureCursorVisible()


# ════════════════════════════════════════════════════════════
# FILE DROP ZONE / ATTACH BUTTON
# ════════════════════════════════════════════════════════════
class FileDropZone(QWidget):
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(34)
        self._current_file: str | None = None
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._btn = QPushButton("📎 Attach")
        self._btn.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self._btn.setFixedHeight(34)
        self._btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2}; color: {C.TEXT_DIM};
                border: 1px solid {C.BORDER}; border-radius: 17px;
                padding: 0 12px;
            }}
            QPushButton:hover {{ border-color: {C.PRI}; color: {C.PRI}; }}
        """)
        self._btn.clicked.connect(self._browse)
        layout.addWidget(self._btn)

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent):
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).is_file():
                self._set_file(path)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Attach File for JARVIS", str(Path.home()), "All Files (*.*)")
        if path:
            self._set_file(path)

    def _set_file(self, path: str):
        self._current_file = path
        p = Path(path)
        self._btn.setText(f"📄 {p.name}")
        self._btn.setStyleSheet(f"QPushButton {{ background: {C.PANEL2}; color: {C.GREEN}; border: 1px solid {C.GREEN}; border-radius: 17px; padding: 0 12px; }}")
        self.file_selected.emit(path)

    def current_file(self) -> str | None:
        return self._current_file


# ════════════════════════════════════════════════════════════
# DIALOGS & OVERLAYS (Memory Search, Setup Overlay)
# ════════════════════════════════════════════════════════════
class MemorySearchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🧠 JARVIS Memory Intelligence Search")
        self.setFixedSize(500, 440)
        self.setStyleSheet(f"background: {C.BG}; border: 1px solid {C.BORDER_B}; border-radius: 12px;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        hdr = QLabel("🧠 MEMORY RECALL & QUERY")
        hdr.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; border-bottom: 1px solid {C.BORDER}; padding-bottom: 6px;")
        lay.addWidget(hdr)

        search_row = QHBoxLayout()
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Search remembered facts, topics, preferences...")
        self.query_input.setStyleSheet(f"background: {C.PANEL2}; color: {C.TEXT}; border: 1px solid {C.BORDER_B}; border-radius: 6px; padding: 8px;")
        search_row.addWidget(self.query_input)

        btn = QPushButton("Search")
        btn.setStyleSheet(f"background: {C.PRI}; color: {C.DARK}; font-weight: bold; padding: 8px 16px; border-radius: 6px;")
        btn.clicked.connect(self._do_search)
        self.query_input.returnPressed.connect(self._do_search)
        search_row.addWidget(btn)
        lay.addLayout(search_row)

        self.res_display = QTextEdit()
        self.res_display.setReadOnly(True)
        self.res_display.setStyleSheet(f"background: {C.PANEL2}; color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 8px; padding: 10px;")
        lay.addWidget(self.res_display, stretch=1)

        self._do_search()

    def _do_search(self):
        query_text = self.query_input.text().strip()
        try:
            from memory.memory_manager import query_memory
            res = query_memory(query_text)
            self.res_display.setText(res if res else "No relevant memory items found.")
        except Exception as ex:
            self.res_display.setText(f"Memory Query Result: {ex}")


class SetupOverlay(QWidget):
    done = pyqtSignal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: rgba(7, 17, 31, 0.95); border: 1px solid {C.BORDER_B}; border-radius: 12px;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        lbl = QLabel("◈ SYSTEM INITIALISATION REQUIRED")
        lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("Gemini API Key...")
        self._key_input.setStyleSheet(f"background: {C.PANEL2}; color: {C.TEXT}; border: 1px solid {C.BORDER_B}; border-radius: 6px; padding: 8px;")
        layout.addWidget(self._key_input)

        self._or_input = QLineEdit()
        self._or_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._or_input.setPlaceholderText("OpenRouter API Key (Optional)...")
        self._or_input.setStyleSheet(f"background: {C.PANEL2}; color: {C.TEXT}; border: 1px solid {C.BORDER_B}; border-radius: 6px; padding: 8px;")
        layout.addWidget(self._or_input)

        btn = QPushButton("▸ INITIALISE JARVIS CORE")
        btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        btn.setFixedHeight(36)
        btn.setStyleSheet(f"background: {C.PRI}; color: {C.DARK}; border-radius: 6px;")
        btn.clicked.connect(self._submit)
        layout.addWidget(btn)

    def _submit(self):
        k1, k2 = self._key_input.text().strip(), self._or_input.text().strip()
        if k1:
            self.done.emit(k1, k2, "windows")


class SecurityConfirmationDialog(QDialog):
    """PyQt6 Security Confirmation Modal Dialog for HIGH/CRITICAL risk operations."""

    def __init__(self, prompt_msg: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🛡️ JARVIS Security Alert")
        self.setFixedSize(460, 260)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet(f"background: {C.BG}; border: 2px solid {C.RED}; border-radius: 12px;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)

        hdr_row = QHBoxLayout()
        hdr = QLabel("🛡️ HIGH-RISK SECURITY ALERT")
        hdr.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.RED}; border: none; background: transparent;")
        hdr_row.addWidget(hdr)
        hdr_row.addStretch()

        tag = QLabel("REQUIRES APPROVAL")
        tag.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        tag.setStyleSheet(f"color: {C.RED}; background: {C.PANEL2}; border: 1px solid {C.RED}; border-radius: 6px; padding: 2px 6px;")
        hdr_row.addWidget(tag)
        lay.addLayout(hdr_row)

        msg_lbl = QLabel(prompt_msg)
        msg_lbl.setFont(QFont("Segoe UI", 9))
        msg_lbl.setStyleSheet(f"color: {C.TEXT}; background: {C.PANEL2}; border: 1px solid {C.BORDER_B}; border-radius: 8px; padding: 12px;")
        msg_lbl.setWordWrap(True)
        lay.addWidget(msg_lbl, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        cancel_btn = QPushButton("✖ CANCEL (REJECT)")
        cancel_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        cancel_btn.setFixedHeight(36)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2};
                color: {C.RED};
                border: 1px solid {C.RED};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background: {C.RED};
                color: #FFFFFF;
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        allow_btn = QPushButton("✔ ALLOW EXECUTION")
        allow_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        allow_btn.setFixedHeight(36)
        allow_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        allow_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PRI};
                color: {C.DARK};
                border: none;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background: {C.PRI_DIM};
                color: #FFFFFF;
            }}
        """)
        allow_btn.clicked.connect(self.accept)
        btn_row.addWidget(allow_btn)

        lay.addLayout(btn_row)


# ════════════════════════════════════════════════════════════
# HOLOGRAPHIC CIRCULAR GAUGE WIDGET
# ════════════════════════════════════════════════════════════
class HoloCircularGauge(QWidget):
    """Compact 3D/2.5D Holographic Circular Gauge widget drawn with anti-aliased QPainter."""

    def __init__(self, label: str = "CPU", color: str = C.PRI, parent=None):
        super().__init__(parent)
        self.label_text = label
        self.color_hex = color
        self.val = 0.0
        self.status_text = ""
        self.setMinimumSize(60, 68)

    def setValue(self, val: float, status_text: str = ""):
        self.val = max(0.0, min(100.0, float(val)))
        if status_text:
            self.status_text = status_text
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        side = min(w, h - 16)
        rect = QRectF((w - side) / 2.0 + 4, 4, side - 8, side - 8)

        # Background track ring
        track_pen = QPen(QColor(18, 31, 50, 210), 4)
        painter.setPen(track_pen)
        painter.drawEllipse(rect)

        # Progress Arc
        main_color = QColor(self.color_hex)
        arc_pen = QPen(main_color, 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(arc_pen)

        span_angle = int(-(self.val / 100.0) * 360 * 16)
        start_angle = 90 * 16  # start at 12 o'clock
        painter.drawArc(rect, start_angle, span_angle)

        # Center Text readout
        painter.setPen(QColor("#E2F9FB"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        val_str = self.status_text if self.status_text else f"{int(self.val)}%"
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, val_str)

        # Small bottom label
        painter.setPen(QColor(C.TEXT_DIM))
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        lbl_rect = QRectF(0, h - 16, w, 16)
        painter.drawText(lbl_rect, Qt.AlignmentFlag.AlignCenter, self.label_text.upper())


# ════════════════════════════════════════════════════════════
# MAIN DASHBOARD APPLICATION WINDOW
# ════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    _log_sig   = pyqtSignal(str)
    _state_sig = pyqtSignal(str)
    _audio_sig = pyqtSignal(float)
    _action_sig = pyqtSignal(str)
    _security_sig = pyqtSignal(str, object, object)

    def __init__(self, face_path: str = "", parent=None):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S — Futuristic AI Command Center")
        self.setMinimumSize(_MIN_W, _MIN_H)
        self.resize(_DEFAULT_W, _DEFAULT_H)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move((screen.width() - _DEFAULT_W) // 2, (screen.height() - _DEFAULT_H) // 2)

        self.on_text_command  = None
        self._muted           = False
        self._current_file: str | None = None
        self._current_state   = "READY"
        self._active_hwnd     = 0

        # Connect Signals & Initialize Log Widget FIRST before panel creation
        self._log = LogWidget()
        self._log_sig.connect(self._on_log_received)
        self._state_sig.connect(self._apply_state)
        self._audio_sig.connect(self._apply_audio_level)
        self._action_sig.connect(self._add_action_entry)
        self._security_sig.connect(self._on_security_confirm_slot)

        try:
            from core.security import default_security_manager
            default_security_manager.set_confirmation_callback(self._request_security_confirm)
        except Exception as ex:
            print(f"[UI] ⚠️ Security callback setup warning: {ex}")

        _HOLOGRAPHIC_UI = os.environ.get("JARVIS_HOLOGRAPHIC_UI", "1") != "0"
        if _HAS_WEBENGINE and _HOLOGRAPHIC_UI:
            try:
                self.hud = JARVIS3DCore(self)
                if QWebChannel is not None and hasattr(self.hud, "_web"):
                    try:
                        self._channel = QWebChannel(self.hud._web.page())
                        self._holo_bridge = HoloBridge(self)
                        self._channel.registerObject("pyBridge", self._holo_bridge)
                        self.hud._web.page().setWebChannel(self._channel)
                    except Exception as ex:
                        print(f"[UI] ⚠️ QWebChannel bridge note: {ex}")
                self.setCentralWidget(self.hud)
                # Contract & Compatibility Attributes for Fullscreen Holographic UI
                self.chat_panel = JarvisChatPanel()
                self.chat_panel.on_send = self._dispatch_command
                self.chat_panel.hide()
                self._input = QLineEdit()
                self._mute_btn = QPushButton("🎙️ Mic ON")
                self._response_card = QLabel('JARVIS: "Online and standing by for commands, sir."')
                self.vol_slider = QSlider(Qt.Orientation.Horizontal)
                self.recent_list = QTextEdit()
                self.cpu_lbl = QLabel("CPU Usage: 0%")
                self.cpu_bar = QProgressBar()
                self.ram_lbl = QLabel("Memory Usage: 0%")
                self.ram_bar = QProgressBar()
                self.disk_lbl = QLabel("Disk Usage: 0%")
                self.disk_bar = QProgressBar()
                self.net_lbl = QLabel("Network: Connected")
                self._hdr_batt = QLabel("🔋 100%")
                self._clock_lbl = QLabel("00:00:00 AM")
                self._date_lbl = QLabel("SUN 09 AUG 2026")
                self.win_title_lbl = QLabel("J.A.R.V.I.S — Futuristic AI Command Center")
                self.voice_state_badge = QLabel("LISTENING...")
            except Exception as ex:
                print(f"[UI] ⚠️ Fullscreen Holographic UI init note: {ex}")
                self._build_legacy_layout(central=QWidget())
        else:
            self._build_legacy_layout(central=QWidget())

        # System Timers

        # System Timers
        self._clock_tmr = QTimer(self)
        self._clock_tmr.timeout.connect(self._tick_clock)
        self._clock_tmr.start(1000)
        self._tick_clock()

        self._metric_tmr = QTimer(self)
        self._metric_tmr.timeout.connect(self._update_metrics)
        self._metric_tmr.start(1500)
        self._update_metrics()

        # Start Hand Tracker Worker
        self._hand_worker = HandTrackerWorker(self)
        self._hand_worker.hand_signal.connect(self._on_hand_signal)
        self._hand_worker.start()

        # Check API Key configuration
        self._overlay: SetupOverlay | None = None
        self._ready = self._check_config()
        if not self._ready:
            self._show_setup()

    def _build_legacy_layout(self, central: QWidget):
        central.setStyleSheet(f"background: {C.BG};")
        self.setCentralWidget(central)

        self.master_layout = QHBoxLayout(central)
        self.master_layout.setContentsMargins(10, 8, 10, 8)
        self.master_layout.setSpacing(10)

        dash_widget = QWidget()
        dash_lay = QVBoxLayout(dash_widget)
        dash_lay.setContentsMargins(0, 0, 0, 0)
        dash_lay.setSpacing(8)

        dash_lay.addWidget(self._build_top_header())

        body_layout = QHBoxLayout()
        body_layout.setSpacing(10)

        left_col = QVBoxLayout()
        left_col.setSpacing(8)
        self._sys_status_panel = self._build_system_status_panel()
        self._sys_status_panel.hide()

        left_col.addWidget(self._build_active_window_panel())
        left_col.addWidget(self._build_recent_actions_panel())
        left_col.addWidget(self._build_voice_status_panel())
        body_layout.addLayout(left_col, stretch=22)

        center_col = QVBoxLayout()
        center_col.setSpacing(8)
        center_col.addWidget(self._build_central_core_panel(), stretch=35)
        center_col.addWidget(self._build_response_card(), stretch=25)
        center_col.addWidget(self._build_command_input_area())
        center_col.addWidget(self._build_console_panel(), stretch=20)
        body_layout.addLayout(center_col, stretch=53)

        right_col = QVBoxLayout()
        right_col.setSpacing(8)
        right_col.addWidget(self._build_tools_panel(), stretch=35)
        right_col.addWidget(self._build_college_mode_panel())
        right_col.addWidget(self._build_memory_panel())
        right_col.addWidget(self._build_quick_controls_panel())
        body_layout.addLayout(right_col, stretch=25)

        dash_lay.addLayout(body_layout, stretch=1)
        self.master_layout.addWidget(dash_widget, stretch=3)

        self.chat_panel = JarvisChatPanel()
        self.chat_panel.on_send = self._dispatch_command
        self.master_layout.addWidget(self.chat_panel, stretch=1)

    # ── 1. TOP HEADER BUILDER ──
    def _build_top_header(self) -> QWidget:
        w = QFrame()
        w.setFixedHeight(46)
        w.setStyleSheet(f"QFrame {{ background: {C.PANEL}; border: 1px solid {C.BORDER_B}; border-radius: 10px; }}")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(14, 0, 14, 0)

        # Left: Logo & System Indicator
        left_box = QHBoxLayout()
        left_box.setSpacing(10)
        logo = QLabel("◈ J.A.R.V.I.S")
        logo.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        logo.setStyleSheet(f"color: {C.PRI}; border: none; background: transparent;")
        left_box.addWidget(logo)

        sys_tag = QLabel("● ONLINE")
        sys_tag.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        sys_tag.setStyleSheet(f"color: {C.GREEN}; background: {C.PANEL2}; border: 1px solid {C.GREEN}; border-radius: 8px; padding: 2px 8px;")
        left_box.addWidget(sys_tag)
        lay.addLayout(left_box)

        lay.addStretch()

        # Center: Live Clock with Seconds
        self._clock_lbl = QLabel("00:00:00 AM")
        self._clock_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self._clock_lbl.setStyleSheet(f"color: {C.TEXT}; border: none; background: transparent;")
        lay.addWidget(self._clock_lbl)

        self._date_lbl = QLabel("SAT 08 AUG")
        self._date_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self._date_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; border: none; background: transparent; margin-left: 6px;")
        lay.addWidget(self._date_lbl)

        lay.addStretch()

        # Right: Live Telemetry Indicators & Chat Toggle
        right_box = QHBoxLayout()
        right_box.setSpacing(12)

        self._hdr_net = QLabel("📡 Wi-Fi")
        self._hdr_net.setFont(QFont("Segoe UI", 8))
        self._hdr_net.setStyleSheet(f"color: {C.TEAL}; border: none; background: transparent;")
        right_box.addWidget(self._hdr_net)

        self._hdr_mic = QLabel("🎙️ Mic ON")
        self._hdr_mic.setFont(QFont("Segoe UI", 8))
        self._hdr_mic.setStyleSheet(f"color: {C.GREEN}; border: none; background: transparent;")
        right_box.addWidget(self._hdr_mic)

        self._hdr_spk = QLabel("🔊 Audio")
        self._hdr_spk.setFont(QFont("Segoe UI", 8))
        self._hdr_spk.setStyleSheet(f"color: {C.TEXT_DIM}; border: none; background: transparent;")
        right_box.addWidget(self._hdr_spk)

        self._hdr_batt = QLabel("🔋 99%")
        self._hdr_batt.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self._hdr_batt.setStyleSheet(f"color: {C.PRI}; border: none; background: transparent;")
        right_box.addWidget(self._hdr_batt)

        self._hdr_awareness = QLabel("◈ AWARENESS: CAM LIVE | SCREEN LIVE | WA UNAVAIL | MAIL AUTH | CAL AUTH | IG CFG")
        self._hdr_awareness.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        self._hdr_awareness.setStyleSheet(f"color: {C.PRI}; background: rgba(86, 224, 232, 0.12); border: 1px solid {C.PRI}; border-radius: 6px; padding: 2px 6px;")
        right_box.addWidget(self._hdr_awareness)

        # Toggle Chat Panel Button
        chat_btn = QPushButton("💬 CHAT")
        chat_btn.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        chat_btn.setFixedHeight(26)
        chat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        chat_btn.setStyleSheet(f"""
            QPushButton {{ background: {C.PANEL2}; color: {C.PRI}; border: 1px solid {C.PRI}; border-radius: 13px; padding: 0 10px; }}
            QPushButton:hover {{ background: {C.PRI}; color: {C.DARK}; }}
        """)
        chat_btn.clicked.connect(self._toggle_chat_panel)
        right_box.addWidget(chat_btn)

        lay.addLayout(right_box)
        return w

    # ── 2. SYSTEM STATUS PANEL (HOLOGRAPHIC TELEMETRY CONTAINER) ──
    def _build_system_status_panel(self) -> QWidget:
        w = QFrame()
        w.setObjectName("holo-telemetry-panel")
        w.setStyleSheet(f"""
            QFrame#holo-telemetry-panel {{
                background: rgba(8, 20, 36, 0.85);
                border: 1px solid rgba(86, 224, 232, 0.4);
                border-radius: 12px;
            }}
        """)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)

        hdr_row = QHBoxLayout()
        hdr = QLabel("┌ ⚙ LIVE TELEMETRY ┐")
        hdr.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; border: none; background: transparent; letter-spacing: 1px;")
        hdr_row.addWidget(hdr)

        tag = QLabel("HUD ACTIVE")
        tag.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        tag.setStyleSheet(f"color: {C.PRI}; background: rgba(86, 224, 232, 0.15); border: 1px solid {C.PRI}; border-radius: 6px; padding: 1px 6px;")
        hdr_row.addWidget(tag, alignment=Qt.AlignmentFlag.AlignRight)
        lay.addLayout(hdr_row)

        # 2x2 Holographic Circular Gauges Grid
        gauges_grid = QGridLayout()
        gauges_grid.setSpacing(4)

        self.cpu_gauge = HoloCircularGauge("CPU", C.PRI)
        self.ram_gauge = HoloCircularGauge("RAM", C.BLUE_ROYAL)
        self.disk_gauge = HoloCircularGauge("DISK", C.VIOLET)
        self.net_gauge = HoloCircularGauge("NET", C.TEAL)

        gauges_grid.addWidget(self.cpu_gauge, 0, 0)
        gauges_grid.addWidget(self.ram_gauge, 0, 1)
        gauges_grid.addWidget(self.disk_gauge, 1, 0)
        gauges_grid.addWidget(self.net_gauge, 1, 1)
        lay.addLayout(gauges_grid)

        # Backend Compatibility Labels & Bars (hidden layout references)
        self.cpu_lbl = QLabel("CPU Usage: 0%")
        self.cpu_bar = QProgressBar()
        self.ram_lbl = QLabel("Memory Usage: 0%")
        self.ram_bar = QProgressBar()
        self.disk_lbl = QLabel("Disk Usage: 0%")
        self.disk_bar = QProgressBar()
        self.net_lbl = QLabel("Network: Connected (0.0 MB/s)")
        return w

    # ── 3. ACTIVE WINDOW PANEL ──
    def _build_active_window_panel(self) -> QWidget:
        w = QFrame()
        w.setObjectName("holo-active-window")
        w.setStyleSheet(f"""
            QFrame#holo-active-window {{
                background: rgba(8, 20, 36, 0.85);
                border: 1px solid rgba(86, 224, 232, 0.35);
                border-radius: 12px;
            }}
            QFrame#holo-active-window:hover {{
                border-color: rgba(86, 224, 232, 0.65);
            }}
        """)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        hdr_row = QHBoxLayout()
        hdr = QLabel("┌ 📌 ACTIVE WINDOW ┐")
        hdr.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; border: none; background: transparent; letter-spacing: 1px;")
        hdr_row.addWidget(hdr)

        focus_btn = QPushButton("🎯 FOCUS")
        focus_btn.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        focus_btn.setFixedHeight(22)
        focus_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        focus_btn.setStyleSheet(f"""
            QPushButton {{ background: rgba(86, 224, 232, 0.15); color: {C.PRI}; border: 1px solid {C.PRI}; border-radius: 4px; padding: 0 8px; }}
            QPushButton:hover {{ background: {C.PRI}; color: {C.DARK}; }}
        """)
        focus_btn.clicked.connect(self._focus_active_window)
        hdr_row.addWidget(focus_btn)
        lay.addLayout(hdr_row)

        self.win_title_lbl = QLabel("J.A.R.V.I.S — Futuristic AI Command Center")
        self.win_title_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.win_title_lbl.setStyleSheet(f"color: #E2F9FB; border: none;")
        self.win_title_lbl.setWordWrap(True)
        lay.addWidget(self.win_title_lbl)

        return w

    # ── 4. RECENT ACTIONS PANEL (HOLOGRAPHIC EVENT STREAM) ──
    def _build_recent_actions_panel(self) -> QWidget:
        w = QFrame()
        w.setObjectName("holo-recent-actions")
        w.setStyleSheet(f"""
            QFrame#holo-recent-actions {{
                background: rgba(8, 20, 36, 0.85);
                border: 1px solid rgba(86, 224, 232, 0.35);
                border-radius: 12px;
            }}
        """)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        hdr = QLabel("┌ 📋 HOLOGRAPHIC EVENT STREAM ┐")
        hdr.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; border: none; background: transparent; letter-spacing: 1px;")
        lay.addWidget(hdr)

        self.recent_list = QTextEdit()
        self.recent_list.setReadOnly(True)
        self.recent_list.setFont(QFont("Consolas", 8))
        self.recent_list.setStyleSheet(f"""
            QTextEdit {{
                background: rgba(11, 22, 40, 0.7);
                color: #C8EAF6;
                border: 1px solid rgba(86, 224, 232, 0.2);
                border-radius: 8px;
                padding: 6px;
                line-height: 1.4;
            }}
        """)
        lay.addWidget(self.recent_list, stretch=1)

        self._add_action_entry("System initialized and ready")
        return w

    # ── 5. VOICE STATUS PANEL (LIVE AUDIO MODULE) ──
    def _build_voice_status_panel(self) -> QWidget:
        w = QFrame()
        w.setObjectName("holo-voice-status")
        w.setStyleSheet(f"""
            QFrame#holo-voice-status {{
                background: rgba(8, 20, 36, 0.85);
                border: 1px solid rgba(86, 224, 232, 0.35);
                border-radius: 12px;
            }}
        """)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        hdr_row = QHBoxLayout()
        hdr = QLabel("┌ 🎙️ LIVE AUDIO MODULE ┐")
        hdr.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; border: none; background: transparent; letter-spacing: 1px;")
        hdr_row.addWidget(hdr)

        self.voice_state_badge = QLabel("● LISTENING")
        self.voice_state_badge.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        self.voice_state_badge.setStyleSheet(f"color: {C.GREEN}; background: rgba(32, 184, 166, 0.15); border: 1px solid {C.GREEN}; border-radius: 8px; padding: 2px 8px;")
        hdr_row.addWidget(self.voice_state_badge)
        lay.addLayout(hdr_row)

        self.waveform_widget = WaveformVisualizer()
        lay.addWidget(self.waveform_widget)

        return w

    # ── 6. CENTRAL CORE PANEL ──
    def _build_central_core_panel(self) -> QWidget:
        w = QFrame()
        w.setStyleSheet(f"QFrame {{ background: {C.PANEL}; border: 1px solid {C.BORDER_B}; border-radius: 12px; }}")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)

        self._use_3d_core = False
        if _HAS_WEBENGINE:
            try:
                self.hud = JARVIS3DCore()
                self._use_3d_core = True
                if QWebChannel is not None and hasattr(self.hud, "_web"):
                    try:
                        self._channel = QWebChannel(self.hud._web.page())
                        self._holo_bridge = HoloBridge(self)
                        self._channel.registerObject("pyBridge", self._holo_bridge)
                        self.hud._web.page().setWebChannel(self._channel)
                    except Exception as ex:
                        print(f"[UI] ⚠️ QWebChannel bridge note: {ex}")
            except Exception as ex:
                print(f"[UI] 3D Core init note: {ex}")
                self.hud = HudCanvas("face.png")
        else:
            self.hud = HudCanvas("face.png")

        lay.addWidget(self.hud)
        return w

    # ── 7. MAIN CENTRAL HOLOGRAPHIC RESPONSE DISPLAY ──
    def _build_response_card(self) -> QWidget:
        w = QFrame()
        w.setObjectName("holo-response-panel")
        w.setMinimumHeight(110)
        w.setStyleSheet(f"""
            QFrame#holo-response-panel {{
                background: rgba(8, 20, 36, 0.88);
                border: 1px solid rgba(86, 224, 232, 0.5);
                border-radius: 14px;
            }}
            QFrame#holo-response-panel:hover {{
                border-color: rgba(86, 224, 232, 0.8);
            }}
        """)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(6)

        hdr_box = QHBoxLayout()
        hdr_tag = QLabel("◈ J.A.R.V.I.S HOLOGRAPHIC RESPONSE ◈")
        hdr_tag.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        hdr_tag.setStyleSheet(f"color: {C.PRI}; border: none; background: transparent; letter-spacing: 1.5px;")
        hdr_box.addWidget(hdr_tag, alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addLayout(hdr_box)

        self._response_card = QLabel('JARVIS: "Online and standing by for commands, sir."')
        self._response_card.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._response_card.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._response_card.setStyleSheet(f"color: #E2F9FB; border: none; text-shadow: 0 0 12px {C.PRI_GHO}; line-height: 1.3;")
        self._response_card.setWordWrap(True)
        lay.addWidget(self._response_card)
        return w

    # ── 8. COMMAND INPUT AREA ──
    def _build_command_input_area(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self._drop_zone = FileDropZone()
        self._drop_zone.file_selected.connect(self._on_file_selected)
        lay.addWidget(self._drop_zone)

        self._mute_btn = QPushButton("🎙️ Mic ON")
        self._mute_btn.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self._mute_btn.setFixedSize(80, 36)
        self._mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mute_btn.setStyleSheet(f"QPushButton {{ background: {C.PANEL}; color: {C.GREEN}; border: 1px solid {C.GREEN}; border-radius: 18px; }}")
        self._mute_btn.clicked.connect(self._toggle_mute)
        lay.addWidget(self._mute_btn)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a command or speak...")
        self._input.setFont(QFont("Segoe UI", 9))
        self._input.setFixedHeight(36)
        self._input.setStyleSheet(f"QLineEdit {{ background: {C.PANEL}; color: {C.TEXT}; border: 1px solid {C.BORDER_B}; border-radius: 18px; padding: 4px 16px; }} QLineEdit:focus {{ border-color: {C.PRI}; }}")
        self._input.returnPressed.connect(self._send)
        lay.addWidget(self._input)

        send_btn = QPushButton("➤")
        send_btn.setFixedSize(36, 36)
        send_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        send_btn.setStyleSheet(f"QPushButton {{ background: {C.PRI}; color: {C.DARK}; border: none; border-radius: 18px; }} QPushButton:hover {{ background: {C.PRI_DIM}; color: #FFF; }}")
        send_btn.clicked.connect(self._send)
        lay.addWidget(send_btn)

        return w

    # ── 9. CONSOLE PANEL (HOLOGRAPHIC LOG DISPLAY) ──
    def _build_console_panel(self) -> QWidget:
        w = QFrame()
        w.setObjectName("holo-console-panel")
        w.setStyleSheet(f"""
            QFrame#holo-console-panel {{
                background: rgba(5, 11, 20, 0.92);
                border: 1px solid rgba(86, 224, 232, 0.4);
                border-radius: 12px;
            }}
        """)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)

        hdr_row = QHBoxLayout()
        hdr = QLabel("┌ 💻 JARVIS CONSOLE LOGS ┐")
        hdr.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; border: none; background: transparent; letter-spacing: 1px;")
        hdr_row.addWidget(hdr)

        tag = QLabel("SYS MONITOR")
        tag.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        tag.setStyleSheet(f"color: {C.GREEN}; background: rgba(32, 184, 166, 0.15); border: 1px solid {C.GREEN}; border-radius: 6px; padding: 1px 6px;")
        hdr_row.addWidget(tag, alignment=Qt.AlignmentFlag.AlignRight)
        lay.addLayout(hdr_row)

        lay.addWidget(self._log, stretch=1)
        return w

    # ── 10. TOOLS PANEL (HOLOGRAPHIC CONTROL TILES GRID) ──
    def _build_tools_panel(self) -> QWidget:
        w = QFrame()
        w.setObjectName("holo-tools-panel")
        w.setStyleSheet(f"""
            QFrame#holo-tools-panel {{
                background: rgba(8, 20, 36, 0.85);
                border: 1px solid rgba(86, 224, 232, 0.35);
                border-radius: 12px;
            }}
        """)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        num_tools = 23
        try:
            from core.tool_registry import default_tool_registry
            num_tools = len(default_tool_registry.list_tools())
        except Exception:
            pass

        self.tools_hdr = QLabel(f"┌ ⚡ CONTROL TILES — {num_tools} LOADED ┐")
        self.tools_hdr.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.tools_hdr.setStyleSheet(f"color: {C.PRI}; border: none; background: transparent; letter-spacing: 1px;")
        lay.addWidget(self.tools_hdr)

        grid = QGridLayout()
        grid.setSpacing(6)

        tool_defs = [
            ("📱 Open App", self._act_open_app),
            ("🌐 Browser", lambda: self._dispatch_command("Open browser")),
            ("🔍 Search", self._act_search),
            ("📷 Screenshot", self._act_screenshot),
            ("📁 File Ops", lambda: self._dispatch_command("Find my JARVIS project")),
            ("🖱️ Mouse", lambda: self._dispatch_command("Click middle of screen")),
            ("⌨️ Keyboard", lambda: self._dispatch_command("Type Hello World")),
            ("📹 Camera", self._act_camera),
            ("🧠 Memory", self._show_memory_search),
            ("🎓 College", self._act_college),
            ("👁️ Vision", lambda: self._dispatch_command("Look at my screen")),
            ("⚡ More", self._show_tools_registry_dialog),
        ]

        for i, (lbl, func) in enumerate(tool_defs):
            b = QPushButton(lbl)
            b.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            b.setFixedHeight(28)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(11, 22, 40, 0.7);
                    color: #E2F9FB;
                    border: 1px solid rgba(86, 224, 232, 0.25);
                    border-radius: 6px;
                }}
                QPushButton:hover {{
                    border-color: rgba(86, 224, 232, 0.7);
                    background: rgba(86, 224, 232, 0.15);
                    color: #56E0E8;
                }}
            """)
            b.clicked.connect(func)
            grid.addWidget(b, i // 3, i % 3)

        lay.addLayout(grid)
        return w

    # ── 11. COLLEGE MODE PANEL (HOLOGRAPHIC SCHEDULER) ──
    def _build_college_mode_panel(self) -> QWidget:
        w = QFrame()
        w.setObjectName("holo-college-panel")
        w.setStyleSheet(f"""
            QFrame#holo-college-panel {{
                background: rgba(8, 20, 36, 0.85);
                border: 1px solid rgba(86, 224, 232, 0.35);
                border-radius: 12px;
            }}
        """)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        hdr = QLabel("┌ 🎓 COLLEGE MODE ┐")
        hdr.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; border: none; background: transparent; letter-spacing: 1px;")
        lay.addWidget(hdr)

        self.college_lbl = QLabel("Schedule: Loading timetable...")
        self.college_lbl.setFont(QFont("Segoe UI", 8))
        self.college_lbl.setStyleSheet(f"color: #C8EAF6; border: none;")
        self.college_lbl.setWordWrap(True)
        lay.addWidget(self.college_lbl)

        self._refresh_college_data()
        return w

    def _refresh_college_data(self):
        try:
            from actions.college_mode import college_mode
            res = college_mode({"action": "schedule"})
            msg = res.get("message", "College Mode active.")
            self.college_lbl.setText(msg[:120])
        except Exception:
            self.college_lbl.setText("College Mode: Ready for timetable queries.")

    # ── 12. MEMORY PANEL (NEURAL MEMORY INTELLIGENCE) ──
    def _build_memory_panel(self) -> QWidget:
        w = QFrame()
        w.setObjectName("holo-memory-panel")
        w.setStyleSheet(f"""
            QFrame#holo-memory-panel {{
                background: rgba(8, 20, 36, 0.85);
                border: 1px solid rgba(86, 224, 232, 0.35);
                border-radius: 12px;
            }}
        """)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        hdr_row = QHBoxLayout()
        hdr = QLabel("┌ 🧠 NEURAL MEMORY ┐")
        hdr.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; border: none; background: transparent; letter-spacing: 1px;")
        hdr_row.addWidget(hdr)

        nodes_tag = QLabel("◈─◈─◈")
        nodes_tag.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        nodes_tag.setStyleSheet(f"color: {C.BLUE_ROYAL}; border: none; background: transparent;")
        hdr_row.addWidget(nodes_tag, alignment=Qt.AlignmentFlag.AlignRight)
        lay.addLayout(hdr_row)

        self.mem_items_lbl = QLabel("Remembered Items: 0")
        self.mem_items_lbl.setFont(QFont("Segoe UI", 8))
        self.mem_items_lbl.setStyleSheet(f"color: #C8EAF6; border: none;")
        lay.addWidget(self.mem_items_lbl)

        self.mem_topics_lbl = QLabel("Topics: 6 Categories")
        self.mem_topics_lbl.setFont(QFont("Segoe UI", 8))
        self.mem_topics_lbl.setStyleSheet(f"color: #C8EAF6; border: none;")
        lay.addWidget(self.mem_topics_lbl)

        self.mem_updated_lbl = QLabel("Last Updated: Just now")
        self.mem_updated_lbl.setFont(QFont("Segoe UI", 8))
        self.mem_updated_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; border: none;")
        lay.addWidget(self.mem_updated_lbl)

        mem_btn = QPushButton("🔍 SEARCH MEMORY")
        mem_btn.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        mem_btn.setFixedHeight(24)
        mem_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        mem_btn.setStyleSheet(f"""
            QPushButton {{ background: rgba(86, 224, 232, 0.12); color: {C.PRI}; border: 1px solid {C.PRI}; border-radius: 4px; }}
            QPushButton:hover {{ background: {C.PRI}; color: {C.DARK}; }}
        """)
        mem_btn.clicked.connect(self._show_memory_search)
        lay.addWidget(mem_btn)

        self._refresh_memory_stats()
        return w

    def _refresh_memory_stats(self):
        try:
            from memory.memory_manager import load_memory
            m = load_memory()
            count = 0
            for cat, items in m.items():
                if isinstance(items, dict):
                    count += len(items)
            self.mem_items_lbl.setText(f"Remembered Items: {count}")
            self.mem_topics_lbl.setText(f"Topics: {len(m)} Categories")
            self.mem_updated_lbl.setText(f"Last Updated: {time.strftime('%I:%M %p')}")
        except Exception:
            pass

    # ── 13. QUICK CONTROLS PANEL (HOLOGRAPHIC CIRCULAR CONTROLS) ──
    def _build_quick_controls_panel(self) -> QWidget:
        w = QFrame()
        w.setObjectName("holo-quick-controls")
        w.setStyleSheet(f"""
            QFrame#holo-quick-controls {{
                background: rgba(8, 20, 36, 0.85);
                border: 1px solid rgba(86, 224, 232, 0.35);
                border-radius: 12px;
            }}
        """)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        hdr = QLabel("┌ 🎛️ QUICK CONTROLS ┐")
        hdr.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; border: none; background: transparent; letter-spacing: 1px;")
        lay.addWidget(hdr)

        vol_row = QHBoxLayout()
        vol_lbl = QLabel("VOL:")
        vol_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        vol_lbl.setStyleSheet(f"color: {C.PRI}; border: none;")
        vol_row.addWidget(vol_lbl)

        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(50)
        self.vol_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{ background: rgba(18, 31, 50, 0.8); height: 4px; border-radius: 2px; }}
            QSlider::handle:horizontal {{ background: {C.PRI}; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }}
        """)
        self.vol_slider.valueChanged.connect(self._on_vol_changed)
        vol_row.addWidget(self.vol_slider)
        lay.addLayout(vol_row)

        ctrl_btn_row = QHBoxLayout()
        v_up = QPushButton("Vol +")
        v_up.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        v_up.setFixedHeight(22)
        v_up.setStyleSheet(f"QPushButton {{ background: {C.PANEL2}; color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 4px; }}")
        v_up.clicked.connect(lambda: self._dispatch_command("Increase volume"))
        ctrl_btn_row.addWidget(v_up)

        v_down = QPushButton("Vol -")
        v_down.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        v_down.setFixedHeight(22)
        v_down.setStyleSheet(f"QPushButton {{ background: {C.PANEL2}; color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 4px; }}")
        v_down.clicked.connect(lambda: self._dispatch_command("Decrease volume"))
        ctrl_btn_row.addWidget(v_down)

        v_mute = QPushButton("Mute")
        v_mute.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        v_mute.setFixedHeight(22)
        v_mute.setStyleSheet(f"QPushButton {{ background: {C.PANEL2}; color: {C.RED}; border: 1px solid {C.RED}; border-radius: 4px; }}")
        v_mute.clicked.connect(lambda: self._dispatch_command("Mute volume"))
        ctrl_btn_row.addWidget(v_mute)

        lay.addLayout(ctrl_btn_row)
        return w

    # ── ACTION HANDLERS FOR TOOL BUTTONS ──
    def _act_open_app(self):
        self._dispatch_command("Open Chrome")

    def _act_search(self):
        self._dispatch_command("Search Google for latest tech news")

    def _act_screenshot(self):
        try:
            ss_dir = BASE_DIR / "assets" / "screenshots"
            ss_dir.mkdir(parents=True, exist_ok=True)
            path = ss_dir / f"screenshot_{int(time.time())}.png"
            img = ImageGrab.grab()
            img.save(str(path))
            msg = f"Screenshot captured: {path.name}"
            self._add_action_entry(msg)
            self._on_log_received(f"SYS: {msg}")
            self._response_card.setText(f'JARVIS: "{msg}"')
        except Exception as ex:
            self._on_log_received(f"ERR: Screenshot failed: {ex}")

    def _act_camera(self):
        active = getattr(self, "_cam_active", False)
        self._cam_active = not active
        if hasattr(self, "hud") and hasattr(self.hud, "setCameraActive"):
            self.hud.setCameraActive(self._cam_active)
        status_txt = "Camera turned ON" if self._cam_active else "Camera turned OFF"
        self._add_action_entry(status_txt)
        self._on_log_received(f"SYS: {status_txt}")

    def _act_college(self):
        self._dispatch_command("What is my schedule for today?")

    def _show_memory_search(self):
        dlg = MemorySearchDialog(self)
        dlg.exec()

    def _show_tools_registry_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("⚡ JARVIS Registered Tool Directory")
        dlg.setFixedSize(520, 460)
        dlg.setStyleSheet(f"background: {C.BG}; border: 1px solid {C.BORDER_B}; border-radius: 10px;")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 16, 16, 16)

        hdr = QLabel("⚡ ALL REGISTERED SYSTEM TOOLS")
        hdr.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; border-bottom: 1px solid {C.BORDER}; padding-bottom: 6px;")
        lay.addWidget(hdr)

        grid = QGridLayout()
        grid.setSpacing(6)
        try:
            from core.tool_registry import default_tool_registry
            tools = default_tool_registry.list_tools()
        except Exception:
            tools = ["open_app", "web_search", "computer_settings", "computer_control", "file_controller", "browser_control", "code_helper", "dev_agent", "file_processor", "youtube_video", "desktop_control", "game_updater", "flight_finder"]

        for i, t_name in enumerate(tools):
            b = QPushButton(f"⚡ {t_name}")
            b.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            b.setFixedHeight(30)
            b.setStyleSheet(f"QPushButton {{ background: {C.PANEL2}; color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 4px; }} QPushButton:hover {{ border-color: {C.PRI}; color: {C.PRI}; }}")
            b.clicked.connect(lambda _, n=t_name, d=dlg: (d.accept(), self._dispatch_command(f"Run tool {n}")))
            grid.addWidget(b, i // 3, i % 3)

        lay.addLayout(grid)
        dlg.exec()

    def _focus_active_window(self):
        if self._active_hwnd > 0:
            success = focus_window_by_hwnd(self._active_hwnd)
            if success:
                self._add_action_entry(f"Focused window: {self.win_title_lbl.text()[:24]}")

    def _toggle_chat_panel(self):
        visible = self.chat_panel.isVisible()
        self.chat_panel.setVisible(not visible)

    def _on_vol_changed(self, val: int):
        self._dispatch_command(f"Set volume to {val} percent")

    # ── TIMER TICK & METRIC UPDATES ──
    def _tick_clock(self):
        t_str = time.strftime("%I:%M:%S %p")
        d_str = time.strftime("%a %d %b %Y").upper()
        if getattr(self, "_clock_lbl", None) is not None:
            self._clock_lbl.setText(t_str)
        if getattr(self, "_date_lbl", None) is not None:
            self._date_lbl.setText(d_str)
        if hasattr(self, "hud") and hasattr(self.hud, "setTime"):
            self.hud.setTime(t_str, d_str)
        if hasattr(self, "telemetry_hud") and hasattr(self.telemetry_hud, "setTime"):
            self.telemetry_hud.setTime(t_str, d_str)

    def _send_tools_to_hud(self):
        try:
            from core.tool_registry import default_tool_registry
            tools = default_tool_registry.list_tools()
            if hasattr(self, "hud") and hasattr(self.hud, "setTools"):
                self.hud.setTools(tools)
        except Exception:
            pass

    def _update_metrics(self):
        snap = _metrics.snapshot()
        cpu, mem, disk, net, batt = snap["cpu"], snap["mem"], snap["disk"], snap["net"], snap["batt"]

        if getattr(self, "cpu_lbl", None) is not None:
            self.cpu_lbl.setText(f"CPU Usage: {cpu:.0f}%")
        if getattr(self, "cpu_bar", None) is not None:
            self.cpu_bar.setValue(int(cpu))

        if getattr(self, "ram_lbl", None) is not None:
            self.ram_lbl.setText(f"Memory Usage: {mem:.0f}%")
        if getattr(self, "ram_bar", None) is not None:
            self.ram_bar.setValue(int(mem))

        if getattr(self, "disk_lbl", None) is not None:
            self.disk_lbl.setText(f"Disk Usage: {disk:.0f}%")
        if getattr(self, "disk_bar", None) is not None:
            self.disk_bar.setValue(int(disk))

        if getattr(self, "net_lbl", None) is not None:
            self.net_lbl.setText(f"Network: Connected ({net:.1f} MB/s)")
        if getattr(self, "_hdr_batt", None) is not None:
            self._hdr_batt.setText(f"🔋 {batt}%")

        if hasattr(self, "cpu_gauge"):
            self.cpu_gauge.setValue(cpu)
            self.ram_gauge.setValue(mem)
            self.disk_gauge.setValue(disk)
            self.net_gauge.setValue(100.0 if net > 0 else 50.0, "LIVE" if net > 0 else "IDLE")

        if hasattr(self, "_hdr_awareness"):
            try:
                from agent.awareness.status_model import status_registry
                self._hdr_awareness.setText(status_registry.get_summary_string())
            except Exception:
                pass

        if hasattr(self, "hud") and hasattr(self.hud, "setTelemetry"):
            self.hud.setTelemetry(cpu, mem, disk, net, None)
        if hasattr(self, "telemetry_hud") and hasattr(self.telemetry_hud, "setTelemetry"):
            self.telemetry_hud.setTelemetry(cpu, mem, disk, net, None)

        if hasattr(self, "hud"):
            if hasattr(self.hud, "setBattery"):
                self.hud.setBattery(batt)
            if hasattr(self, "_hdr_awareness") and hasattr(self.hud, "setAwareness"):
                self.hud.setAwareness(self._hdr_awareness.text())

        title, hwnd = get_active_window_info()
        if title:
            self._active_hwnd = hwnd
            if getattr(self, "win_title_lbl", None) is not None:
                self.win_title_lbl.setText(title[:45])
            if hasattr(self, "hud") and hasattr(self.hud, "setActiveWindow"):
                self.hud.setActiveWindow(title[:45])

        self._send_tools_to_hud()

    def _on_hand_signal(self, x: float, y: float, detected: bool, gesture: str, depth: float):
        if hasattr(self, "hud") and hasattr(self.hud, "setHandPosition"):
            self.hud.setHandPosition(x, y, gesture if detected else "NONE", depth)

    # ── RECENT ACTIONS & CONSOLE LOG MIRROR ──
    def _add_action_entry(self, text: str):
        ts = time.strftime("[%I:%M %p]")
        if getattr(self, "recent_list", None) is not None:
            self.recent_list.append(f'<span style="color: {C.PRI};">{ts}</span> • {text}')
            self.recent_list.ensureCursorVisible()
        if hasattr(self, "hud") and hasattr(self.hud, "addAction"):
            self.hud.addAction(text)

    def _on_log_received(self, text: str):
        self._log.append_log(text)
        if hasattr(self, "hud") and hasattr(self.hud, "appendLog"):
            self.hud.appendLog(text)
        if text.startswith("Jarvis:") or text.startswith("JARVIS:"):
            msg = text.split(":", 1)[1].strip()
            if getattr(self, "_response_card", None) is not None:
                self._response_card.setText(f'JARVIS: "{msg}"')
            if hasattr(self, "hud") and hasattr(self.hud, "setResponse"):
                self.hud.setResponse(msg)
            if hasattr(self, "hud") and hasattr(self.hud, "appendChat"):
                self.hud.appendChat("JARVIS", msg)
            if hasattr(self, "chat_panel"):
                self.chat_panel.append_message("JARVIS", msg)
        elif text.startswith("You:"):
            pass

    def _dispatch_command(self, cmd: str):
        if not cmd or not cmd.strip():
            return
        raw_cmd = cmd.strip()
        cid = ""
        clean_cmd = raw_cmd
        if raw_cmd.startswith("[CID:"):
            try:
                parts = raw_cmd.split("] ", 1)
                cid = parts[0].replace("[CID:", "").strip()
                clean_cmd = parts[1].strip() if len(parts) > 1 else raw_cmd
            except Exception:
                clean_cmd = raw_cmd

        cid_log = f"[CID={cid}] " if cid else ""
        logger.info(f"[DISPATCH]{cid_log}_dispatch_command received: '{clean_cmd}'")
        self._log.append_log(f"You: {clean_cmd}")
        self._add_action_entry(f"Executing: {clean_cmd}")
        if getattr(self, "_response_card", None) is not None:
            self._response_card.setText(f'JARVIS: "Processing {clean_cmd}..."')
        if hasattr(self, "hud") and hasattr(self.hud, "setResponse"):
            self.hud.setResponse(f"Processing {clean_cmd}...")
        if hasattr(self, "hud") and hasattr(self.hud, "appendChat"):
            self.hud.appendChat("You", clean_cmd)
        if hasattr(self, "chat_panel"):
            self.chat_panel.append_message("You", clean_cmd)
        if self.on_text_command:
            try:
                threading.Thread(target=self.on_text_command, args=(raw_cmd,), daemon=True).start()
            except Exception as e:
                logger.error(f"[DISPATCH]{cid_log}Thread error: {e}")
                self._on_log_received(f"JARVIS: System error dispatching command — {e}")

    def _send(self):
        txt = self._input.text().strip()
        if not txt:
            return
        self._input.clear()
        self._dispatch_command(txt)

    def _on_file_selected(self, path: str):
        p = Path(path)
        self._log.append_log(f"FILE: {p.name} attached")
        self._add_action_entry(f"Attached file {p.name}")
        if hasattr(self, "chat_panel"):
            self.chat_panel.append_message("SYSTEM", f"Attached file: {p.name}")
        if self.on_text_command:
            msg = f"[FILE_UPLOADED] path={path} | name={p.name}"
            threading.Thread(target=self.on_text_command, args=(msg,), daemon=True).start()

    def set_muted(self, muted: bool):
        """Authoritatively updates UI mic mute state and QWebChannel bridge indicator."""
        self._muted = bool(muted)
        try:
            from actions.mic_control import _MIC_STATES
            _MIC_STATES["jarvis_mic"] = not self._muted
        except Exception:
            pass

        if hasattr(self, "hud"):
            self.hud.muted = self._muted
            if hasattr(self.hud, "setMicState"):
                self.hud.setMicState(not self._muted)

        if self._muted:
            if getattr(self, "_mute_btn", None) is not None:
                self._mute_btn.setText("🎙️ Mic OFF / MUTED")
                self._mute_btn.setStyleSheet(f"QPushButton {{ background: {C.PANEL}; color: {C.RED}; border: 1px solid {C.RED}; border-radius: 18px; }}")
            self._apply_state("MUTED")
            self._on_log_received("SYS: Microphone muted.")
        else:
            if getattr(self, "_mute_btn", None) is not None:
                self._mute_btn.setText("🎙️ Mic ON")
                self._mute_btn.setStyleSheet(f"QPushButton {{ background: {C.PANEL}; color: {C.GREEN}; border: 1px solid {C.GREEN}; border-radius: 18px; }}")
            self._apply_state("LISTENING")
            self._on_log_received("SYS: Microphone unmuted.")

    def _toggle_mute(self):
        new_muted = not getattr(self, "_muted", False)
        try:
            from actions.mic_control import set_jarvis_mic_enabled
            set_jarvis_mic_enabled(not new_muted, ui_instance=self)
        except Exception:
            self.set_muted(new_muted)

    def _request_security_confirm(self, prompt_msg: str) -> bool:
        if QThread.currentThread() == self.thread():
            dlg = SecurityConfirmationDialog(prompt_msg, self)
            return dlg.exec() == QDialog.DialogCode.Accepted
        else:
            event = threading.Event()
            res_box = {"confirmed": False}
            self._security_sig.emit(prompt_msg, event, res_box)
            event.wait(timeout=30.0)
            return res_box["confirmed"]

    def _on_security_confirm_slot(self, prompt_msg: str, event: threading.Event, res_box: dict):
        dlg = SecurityConfirmationDialog(prompt_msg, self)
        accepted = (dlg.exec() == QDialog.DialogCode.Accepted)
        res_box["confirmed"] = accepted
        event.set()

    def _apply_state(self, state: str):
        self._current_state = state
        if hasattr(self, "hud"):
            self.hud.setState(state)
        if hasattr(self, "waveform_widget"):
            self.waveform_widget.set_state(state)

        st_map = {
            "LISTENING": ("color: " + C.GREEN + "; border: 1px solid " + C.GREEN + ";", "LISTENING..."),
            "THINKING":  ("color: " + C.AMBER + "; border: 1px solid " + C.AMBER + ";", "THINKING..."),
            "SPEAKING":  ("color: " + C.GREEN + "; border: 1px solid " + C.GREEN + ";", "SPEAKING..."),
            "EXECUTING": ("color: " + C.VIOLET + "; border: 1px solid " + C.VIOLET + ";", "EXECUTING..."),
            "MUTED":      ("color: " + C.RED + "; border: 1px solid " + C.RED + ";", "MUTED"),
        }
        b_style, b_text = st_map.get(state.upper(), ("color: " + C.PRI + "; border: 1px solid " + C.PRI + ";", state.upper()))
        if getattr(self, "voice_state_badge", None) is not None:
            self.voice_state_badge.setStyleSheet(f"QLabel {{ {b_style} background: {C.PANEL2}; border-radius: 8px; padding: 2px 8px; }}")
            self.voice_state_badge.setText(b_text)

    def _apply_audio_level(self, level: float):
        if hasattr(self, "hud"):
            self.hud.setAudioLevel(level)
        if hasattr(self, "waveform_widget"):
            self.waveform_widget.set_level(level)

    def _check_config(self) -> bool:
        if not API_FILE.exists():
            return False
        try:
            d = json.loads(API_FILE.read_text(encoding="utf-8"))
            return bool(d.get("gemini_api_key"))
        except Exception:
            return False

    def _show_setup(self):
        ov = SetupOverlay(self.centralWidget())
        cw = self.centralWidget()
        ow, oh = 460, 390
        ov.setGeometry((cw.width() - ow) // 2, (cw.height() - oh) // 2, ow, oh)
        ov.done.connect(self._on_setup_done)
        ov.show()
        self._overlay = ov

    def _on_setup_done(self, key: str, or_key: str, os_name: str):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        API_FILE.write_text(json.dumps({"gemini_api_key": key, "openrouter_api_key": or_key, "os_system": os_name}, indent=4), encoding="utf-8")
        self._ready = True
        if self._overlay:
            self._overlay.hide()
            self._overlay = None
        self._apply_state("LISTENING")
        self._on_log_received("SYS: Initialised. JARVIS online.")

    def closeEvent(self, event):
        if hasattr(self, "_clock_tmr") and self._clock_tmr.isActive():
            self._clock_tmr.stop()
        if hasattr(self, "_metric_tmr") and self._metric_tmr.isActive():
            self._metric_tmr.stop()
        if hasattr(self, "hud") and hasattr(self.hud, "_ready_timer") and self.hud._ready_timer.isActive():
            self.hud._ready_timer.stop()
        if hasattr(self, "_hand_worker"):
            self._hand_worker.stop()
        event.accept()


# ════════════════════════════════════════════════════════════
# ROOT APPLICATION WRAPPER & PUBLIC INTERFACE
# ════════════════════════════════════════════════════════════
class _RootShim:
    def __init__(self, app: QApplication):
        self._app = app

    def mainloop(self):
        self._app.exec()

    def protocol(self, *_):
        pass


class JarvisUI:
    def __init__(self, face_path: str, size=None):
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        icon_path = BASE_DIR / "assets" / "icons" / "jarvis.ico"
        if icon_path.exists():
            ico = QIcon(str(icon_path))
            self._app.setWindowIcon(ico)
        self._win = MainWindow(face_path)
        if icon_path.exists():
            self._win.setWindowIcon(QIcon(str(icon_path)))
        self._win.show()
        self._win.raise_()
        self._win.activateWindow()
        self.root = _RootShim(self._app)

    @property
    def muted(self) -> bool:
        return self._win._muted

    @muted.setter
    def muted(self, v: bool):
        if v != self._win._muted:
            self._win._toggle_mute()

    @property
    def current_file(self) -> str | None:
        return self._win._drop_zone.current_file()

    @property
    def on_text_command(self):
        return self._win.on_text_command

    @on_text_command.setter
    def on_text_command(self, cb):
        self._win.on_text_command = cb

    def set_state(self, state: str):
        self._win._state_sig.emit(state)

    def set_camera_active(self, active: bool):
        try:
            if hasattr(self._win, "hud") and hasattr(self._win.hud, "setCameraActive"):
                self._win.hud.setCameraActive(active)
        except Exception:
            pass

    def set_audio_level(self, level: float):
        try:
            self._win._audio_sig.emit(float(level))
        except Exception:
            pass

    def write_log(self, text: str):
        self._win._log_sig.emit(text)

    def add_recent_action(self, text: str):
        self._win._action_sig.emit(text)

    def wait_for_api_key(self, timeout_sec: float = 5.0):
        start_t = time.time()
        while not getattr(self._win, "_ready", False):
            if hasattr(self._win, "_check_config") and self._win._check_config():
                self._win._ready = True
                break
            if time.time() - start_t > timeout_sec:
                print("[UI] ⚠️ API key wait timeout reached — proceeding with runtime startup.")
                break
            time.sleep(0.1)

    def start_speaking(self):
        self.set_state("SPEAKING")

    def stop_speaking(self):
        if not self.muted:
            self.set_state("LISTENING")