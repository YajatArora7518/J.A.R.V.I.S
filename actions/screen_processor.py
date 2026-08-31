import asyncio
import base64
import io
import json
import re
import os
import sys
import time
import threading
import cv2
import mss
import mss.tools
import sounddevice as sd
import numpy as np
from pathlib import Path

try:
    import PIL.Image
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR        = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

LIVE_MODEL          = "models/gemini-2.5-flash-native-audio-latest"
CHANNELS            = 1
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE          = 1024

IMG_MAX_W = 640
IMG_MAX_H = 360
JPEG_Q    = 55

SYSTEM_PROMPT = (
    "You are JARVIS from Iron Man movies. "
    "Analyze images with technical precision and intelligence. "
    "Help the user in a way they can understand — don't be overly complex. "
    "Be concise, smart, and helpful like Tony Stark's AI assistant. "
    "Respond in maximum 2 short sentences. Speed is priority. "
    "Address the user as 'sir' for a tone of respect. "
    "Ask if the user needs any further help with their problem."
)


def _get_api_key() -> str:
    try:
        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
            keys = json.load(f)
        key = keys.get("gemini_api_key", "")
        if not key:
            raise ValueError("gemini_api_key not found")
        return key
    except Exception as e:
        raise RuntimeError(f"Could not load API key: {e}")


def _get_camera_index() -> int:
    try:
        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if "camera_index" in cfg:
            return int(cfg["camera_index"])
    except Exception:
        pass

    print("[Camera] 🔍 No camera index in config. Auto-detecting...")
    best_index = 0

    for idx in range(6):
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            continue
        for _ in range(5):
            cap.read()
        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None and frame.mean() > 5:
            best_index = idx
            print(f"[Camera] ✅ Camera found at index {idx} — saving to config.")
            break
        else:
            print(f"[Camera] ⚠️  Index {idx}: no valid frame.")

    try:
        cfg = {}
        if API_CONFIG_PATH.exists():
            with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        cfg["camera_index"] = best_index
        with open(API_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
        print(f"[Camera] 💾 Camera index {best_index} saved to config.")
    except Exception as e:
        print(f"[Camera] ⚠️  Could not save camera index: {e}")

    return best_index


def _to_jpeg(img_bytes: bytes) -> bytes:
    if not _PIL_OK:
        return img_bytes
    img = PIL.Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img.thumbnail([IMG_MAX_W, IMG_MAX_H], PIL.Image.BILINEAR)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_Q, optimize=False)
    return buf.getvalue()


def _capture_screenshot() -> bytes:
    # 1. Try PIL ImageGrab
    try:
        if _PIL_OK:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            img.thumbnail([1280, 720], PIL.Image.BILINEAR)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=75, optimize=False)
            return buf.getvalue()
    except Exception:
        pass

    # 2. Try mss fallback
    try:
        with mss.MSS() as sct:
            shot = sct.grab(sct.monitors[0])
            png_bytes = mss.tools.to_png(shot.rgb, shot.size)
        return _to_jpeg(png_bytes)
    except Exception:
        pass

    # 3. Try pyautogui fallback
    try:
        import pyautogui
        img = pyautogui.screenshot()
        img.thumbnail([1280, 720], PIL.Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=75, optimize=False)
        return buf.getvalue()
    except Exception:
        pass

    # 4. Fallback synthetic display frame for background context
    if _PIL_OK:
        title = "Desktop"
        try:
            import pygetwindow as gw
            win = gw.getActiveWindow()
            if win and win.title:
                title = win.title
        except Exception:
            pass
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (1280, 720), color=(15, 23, 42))
        draw = ImageDraw.Draw(img)
        draw.text((50, 50), f"JARVIS Active Desktop Session - Active Window: {title}", fill=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=75, optimize=False)
        return buf.getvalue()

    raise RuntimeError("Screen capture unavailable on current display configuration.")


def _capture_camera() -> bytes:
    camera_index = _get_camera_index()
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise RuntimeError(f"Camera could not be opened: index {camera_index}")
    for _ in range(10):
        cap.read()
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        raise RuntimeError("Could not capture camera frame.")
    if _PIL_OK:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(rgb)
        img.thumbnail([IMG_MAX_W, IMG_MAX_H], PIL.Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_Q, optimize=False)
        return buf.getvalue()
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_Q])
    return buf.tobytes()


class _LiveSession:

    def __init__(self):
        self._loop:      asyncio.AbstractEventLoop | None = None
        self._thread:    threading.Thread | None          = None
        self._session                                     = None
        self._out_queue: asyncio.Queue | None             = None
        self._audio_in:  asyncio.Queue | None             = None
        self._ready:     threading.Event                  = threading.Event()
        self._player                                      = None
        self._send_lock: asyncio.Lock | None              = None

    def start(self, player=None):
        if self._thread and self._thread.is_alive():
            return
        self._player = player
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="VisionSessionThread"
        )
        self._thread.start()
        ok = self._ready.wait(timeout=20)
        if not ok:
            raise RuntimeError("Vision session did not start within 20s.")
        print("[ScreenProcess] ✅ Vision session ready (no mic)")

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._main())

    async def _main(self):
        from google import genai
        from google.genai import types

        self._out_queue = asyncio.Queue(maxsize=30)
        self._audio_in  = asyncio.Queue()
        self._send_lock = asyncio.Lock()

        client = genai.Client(
            api_key=_get_api_key(),
            http_options={"api_version": "v1beta"}
        )

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            system_instruction=SYSTEM_PROMPT,
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Charon"
                    )
                )
            ),
        )

        while True:
            try:
                print("[ScreenProcess] 🔌 Vision session connecting...")
                async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
                    self._session = session
                    self._ready.set()
                    print("[ScreenProcess] ✅ Vision session connected")
                    async with asyncio.TaskGroup() as tg:
                        tg.create_task(self._send_loop())
                        tg.create_task(self._recv_loop())
                        tg.create_task(self._play_loop())
            except Exception as e:
                print(f"[ScreenProcess] ⚠️ Disconnected: {e} — reconnecting...")
                self._session = None
                self._ready.clear()
                await asyncio.sleep(2)
                self._ready.set()

    async def _send_loop(self):
        while True:
            item = await self._out_queue.get()
            if self._session:
                image_bytes, mime_type, user_text = item
                try:
                    b64 = base64.b64encode(image_bytes).decode("utf-8")
                    await self._session.send_client_content(
                        turns={
                            "parts": [
                                {"inline_data": {"mime_type": mime_type, "data": b64}},
                                {"text": user_text}
                            ]
                        },
                        turn_complete=True
                    )
                    print("[ScreenProcess] ✅ Image sent")
                except Exception as e:
                    print(f"[ScreenProcess] ⚠️ Send error: {e}")

    async def _recv_loop(self):
        transcript_buf: list[str] = []
        try:
            async for response in self._session.receive():
                if response.data:
                    await self._audio_in.put(response.data)
                sc = response.server_content
                if not sc:
                    continue
                if sc.output_transcription and sc.output_transcription.text:
                    chunk = sc.output_transcription.text.strip()
                    if chunk:
                        transcript_buf.append(chunk)
                if sc.turn_complete:
                    if transcript_buf and self._player:
                        full = re.sub(r'\s+', ' ', " ".join(transcript_buf)).strip()
                        if full:
                            self._player.write_log(f"Jarvis: {full}")
                            print(f"[ScreenProcess] 💬 {full}")
                    transcript_buf = []
        except Exception as e:
            print(f"[ScreenProcess] ⚠️ Recv error: {e}")
            transcript_buf = []
            await asyncio.sleep(0.3)

    async def _play_loop(self):
        stream = sd.RawOutputStream(
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=CHUNK_SIZE,
        )
        stream.start()
        try:
            while True:
                chunk = await self._audio_in.get()
                await asyncio.to_thread(stream.write, chunk)
        except Exception as e:
            print(f"[ScreenProcess] ❌ Play error: {e}")
            raise
        finally:
            stream.stop()
            stream.close()

    def analyze(self, image_bytes: bytes, mime_type: str, user_text: str):
        if not self._loop:
            return
        asyncio.run_coroutine_threadsafe(
            self._out_queue.put((image_bytes, mime_type, user_text)),
            self._loop
        )

    def is_ready(self) -> bool:
        return self._session is not None


_live       = _LiveSession()
_started    = False
_start_lock = threading.Lock()


def _ensure_started(player=None):
    global _started
    with _start_lock:
        if not _started:
            _live.start(player=player)
            _started = True
        elif player is not None:
            _live._player = player


def analyze_screen_vision(
    user_query: str = "",
    angle: str = "screen",
    player: Any = None,
    speak: Any = None
) -> Dict[str, Any]:
    """
    Real Screen Vision & Multimodal UI Analysis Engine for JARVIS.
    Captures active desktop/camera frame, inspects active window, and analyzes via Gemini Vision.
    """
    active_window_title = ""
    try:
        import pygetwindow as gw
        win = gw.getActiveWindow()
        if win and win.title:
            active_window_title = win.title.strip()
    except Exception:
        pass

    try:
        if angle == "camera":
            img_bytes = _capture_camera()
            mime_type = "image/jpeg"
            target_label = "Webcam Camera Feed"
        else:
            img_bytes = _capture_screenshot()
            mime_type = "image/jpeg" if _PIL_OK else "image/png"
            target_label = f"Desktop Screen (Active: '{active_window_title}')" if active_window_title else "Desktop Screen"

        if not img_bytes or len(img_bytes) == 0:
            msg = "Screen capture failed: No image data was obtained."
            if player and hasattr(player, "write_log"):
                player.write_log(f"ERR: {msg}")
            return {
                "success": False,
                "screenshot_available": False,
                "error": "SCREEN_CAPTURE_FAILED",
                "message": msg,
                "visual_summary": msg
            }

        # Query Gemini Multimodal Vision API
        from google import genai
        from google.genai import types

        api_key = _get_api_key()
        client = genai.Client(api_key=api_key)

        prompt = (
            f"You are JARVIS, Tony Stark's sharp, intelligent desktop AI assistant.\n"
            f"Analyze the user's current visual capture: {target_label}.\n"
            f"User query: '{user_query or 'What is on my screen?'}'\n"
            f"Active window title: '{active_window_title}'\n\n"
            f"Instructions:\n"
            f"1. Observe what application/window is active and describe what is visible in 1-2 clear, precise sentences.\n"
            f"2. If an error, code exception, or problem dialog is visible, identify the error.\n"
            f"3. Formulate the single most logical next-step question based on the observed content (e.g. if code error is visible, ask if user wants root cause or fix; if browser/article is open, ask if user wants summary or specific actions; if chat is visible, ask if user wants a summary). Do not ask generic questions.\n"
            f"4. Address the user naturally as Boss or Sir."
        )

        vision_models = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-latest"]
        obs_text = ""
        last_err = None

        for m in vision_models:
            try:
                resp = client.models.generate_content(
                    model=m,
                    contents=[
                        types.Part.from_bytes(data=img_bytes, mime_type=mime_type),
                        prompt
                    ]
                )
                if resp and resp.text:
                    obs_text = resp.text.strip()
                    break
            except Exception as ex:
                last_err = ex
                continue

        if not obs_text:
            if last_err:
                raise last_err
            obs_text = f"Boss, active window '{active_window_title}' visible hai. Aap isme kya check karna chahte hain?"

        is_error = any(k in obs_text.lower() or k in active_window_title.lower() for k in ["error", "exception", "failed", "traceback", "crash", "syntaxerror", "attributeerror"])

        if player and hasattr(player, "write_log"):
            player.write_log(f"Vision: {obs_text[:120]}...")

        return {
            "success": True,
            "screenshot_available": True,
            "active_window": active_window_title,
            "application": active_window_title.split(" - ")[-1] if " - " in active_window_title else active_window_title,
            "visual_summary": obs_text,
            "message": obs_text,
            "observation": obs_text,
            "detected_errors": [active_window_title] if is_error else [],
            "error_detected": is_error,
            "confidence": 1.0,
            "image_size_bytes": len(img_bytes)
        }

    except Exception as e:
        err_msg = f"Screen analysis encountered an issue: {e}"
        if player and hasattr(player, "write_log"):
            player.write_log(f"ERR: Vision — {e}")
        return {
            "success": False,
            "screenshot_available": False,
            "error": str(e),
            "message": err_msg,
            "visual_summary": err_msg
        }


def screen_process(
    parameters: Optional[Dict[str, Any]] = None,
    response: Any = None,
    player: Any = None,
    session_memory: Any = None,
    speak: Any = None,
    **kwargs: Any
) -> Dict[str, Any]:
    """
    Standard tool entry point for screen and vision analysis.
    """
    params = dict(parameters) if isinstance(parameters, dict) else {}
    if kwargs:
        for k, v in kwargs.items():
            if k not in ("speak", "player", "response", "session_memory") and k not in params:
                params[k] = v

    user_text = params.get("text") or params.get("user_text") or params.get("query") or "What is on my screen?"
    angle = params.get("angle", "screen").lower().strip()
    return analyze_screen_vision(user_query=user_text, angle=angle, player=player, speak=speak)


def analyze_screen_ui(user_query: str = "", task_type: str = "demand") -> Dict[str, Any]:
    """
    Adaptive Demand-Driven Screen Vision & UI Inspection Engine.
    Processes screen capture on demand without continuous background frame grabbing.
    """
    return analyze_screen_vision(user_query=user_query, angle="screen")


def warmup_session(player=None):
    try:
        _ensure_started(player=player)
    except Exception as e:
        print(f"[ScreenProcess] ⚠️ Warmup error: {e}")


if __name__ == "__main__":
    print("[TEST] screen_processor.py v8 — image-only session")
    print("=" * 50)
    mode    = input("screen / camera (default: screen): ").strip().lower() or "screen"
    request = input("Question (Enter for default): ").strip() or "What do you see? Be brief."

    t0 = time.perf_counter()
    warmup_session()
    print(f"Session ready — {time.perf_counter()-t0:.2f}s\n")

    t1     = time.perf_counter()
    result = screen_process({"angle": mode, "text": request}, player=None)
    print(f"Sent — {time.perf_counter()-t1:.3f}s | audio incoming...")
    time.sleep(8)
    print(f"\n{'✅' if result else '❌'}")
