# core/local_stt.py
# 100% Local Multilingual Speech-to-Text Engine for JARVIS using faster-whisper
# Optimized for English & Indian Hinglish speech on NVIDIA CUDA (float16) with CPU fallback

import os
import io
import sys
import time
import wave
import site
import logging
import threading
from typing import Optional, Union, Tuple
import numpy as np

# Robust discovery of NVIDIA CUDA runtime DLLs (cublas, cudnn)
_SEARCH_PATHS = [
    os.path.join(sys.prefix, "Lib", "site-packages", "nvidia"),
    os.path.join(sys.prefix, "site-packages", "nvidia"),
]
try:
    for sp in site.getsitepackages():
        _SEARCH_PATHS.append(os.path.join(sp, "nvidia"))
except Exception:
    pass

for base in _SEARCH_PATHS:
    if os.path.exists(base):
        cublas_bin = os.path.join(base, "cublas", "bin")
        cudnn_bin = os.path.join(base, "cudnn", "bin")
        if os.path.exists(cublas_bin):
            os.environ["PATH"] = cublas_bin + ";" + cudnn_bin + ";" + os.environ.get("PATH", "")
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(cublas_bin)
                    if os.path.exists(cudnn_bin):
                        os.add_dll_directory(cudnn_bin)
                except Exception:
                    pass
            break

logger = logging.getLogger("JARVIS.LocalSTT")

DEFAULT_MODEL = os.environ.get("JARVIS_STT_MODEL", "small")
INITIAL_PROMPT = (
    "JARVIS assistant commands in English and Hinglish: "
    "WhatsApp kholo, message bhejo, call karo, screen check karo, volume badhao, gaana bajao."
)


class LocalSTTEngine:
    """
    Local Speech-To-Text Engine powered by faster-whisper.
    Zero cloud dependencies. High-speed CUDA float16 transcription with CPU int8 fallback.
    """
    def __init__(self, model_size: str = DEFAULT_MODEL):
        self.model_size = model_size
        self._lock = threading.Lock()
        self._model = None
        self._device = "cpu"
        self._compute_type = "int8"
        self._is_ready = False
        self._last_latency_ms = 0.0

        self._init_model()

    def _init_model(self) -> None:
        """Initializes the Whisper model on CUDA if available, else CPU."""
        from faster_whisper import WhisperModel
        import ctranslate2

        cuda_available = ctranslate2.get_cuda_device_count() > 0
        if cuda_available:
            try:
                logger.info(f"[LocalSTT] Attempting CUDA load for model '{self.model_size}' (float16)...")
                t0 = time.time()
                self._model = WhisperModel(self.model_size, device="cuda", compute_type="float16")
                self._device = "cuda"
                self._compute_type = "float16"
                self._is_ready = True
                logger.info(f"[LocalSTT] Loaded on CUDA in {time.time() - t0:.2f}s")
                return
            except Exception as e:
                logger.warning(f"[LocalSTT] CUDA load failed ({e}), falling back to CPU (int8)...")

        # CPU Fallback
        t0 = time.time()
        self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        self._device = "cpu"
        self._compute_type = "int8"
        self._is_ready = True
        logger.info(f"[LocalSTT] Loaded on CPU (int8) in {time.time() - t0:.2f}s")

    def transcribe(
        self,
        audio: Union[str, bytes, np.ndarray],
        language: Optional[str] = None,
        beam_size: int = 5
    ) -> Tuple[str, float]:
        """
        Transcribes audio into text.
        audio can be:
        - str: path to audio file (wav, mp3, etc.)
        - bytes: 16kHz 16-bit mono raw PCM bytes
        - np.ndarray: float32 audio waveform normalized to [-1.0, 1.0]

        Returns (transcribed_text, latency_ms).
        """
        if not self._is_ready or self._model is None:
            raise RuntimeError("LocalSTTEngine model is not loaded.")

        t0 = time.time()
        with self._lock:
            # Handle raw PCM bytes by wrapping into a temporary WAV buffer
            if isinstance(audio, (bytes, bytearray)):
                wav_io = io.BytesIO()
                with wave.open(wav_io, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(16000)
                    wf.writeframes(audio)
                wav_io.seek(0)
                audio_input = wav_io
            else:
                audio_input = audio

            try:
                segments, info = self._model.transcribe(
                    audio_input,
                    beam_size=beam_size,
                    language=language,
                    initial_prompt=INITIAL_PROMPT,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500)
                )
                text = " ".join([s.text.strip() for s in segments]).strip()
            except Exception as e:
                logger.error(f"[LocalSTT] Transcription error: {e}")
                text = ""

        latency_ms = (time.time() - t0) * 1000.0
        self._last_latency_ms = latency_ms
        return text, latency_ms

    def get_info(self) -> dict:
        """Returns metadata about STT engine."""
        return {
            "model": self.model_size,
            "device": self._device,
            "compute_type": self._compute_type,
            "ready": self._is_ready,
            "last_latency_ms": round(self._last_latency_ms, 1)
        }


# Thread-safe singleton
_STT_LOCK = threading.Lock()
_STT_INSTANCE: Optional[LocalSTTEngine] = None

def get_local_stt(model_size: str = DEFAULT_MODEL) -> LocalSTTEngine:
    """Thread-safe singleton accessor for LocalSTTEngine."""
    global _STT_INSTANCE
    with _STT_LOCK:
        if _STT_INSTANCE is None:
            _STT_INSTANCE = LocalSTTEngine(model_size=model_size)
        return _STT_INSTANCE
