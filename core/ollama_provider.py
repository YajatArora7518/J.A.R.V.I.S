# core/ollama_provider.py
# Ollama Autonomous Local LLM Provider & Hardened Lifecycle Engine for JARVIS
# Models: 'fotiecodes/jarvis' (Stark Dialogue Fine-Tune) & 'gemma4:12b' (Tool-Use Model)

import os
import sys
import time
import json
import logging
import platform
import subprocess
import urllib.request
import urllib.error
from core.conversation_style import CONVERSATION_STYLE
from typing import Dict, Any, List, Optional

logger = logging.getLogger("JARVIS.Ollama")

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
DEFAULT_STARK_MODEL = "fotiecodes/jarvis"
DEFAULT_TOOL_MODEL = "gemma4:12b"
DEFAULT_KEEP_ALIVE = os.environ.get("OLLAMA_KEEP_ALIVE", "60m")

# Provider Status Constants
OLLAMA_STARTING = "OLLAMA_STARTING"
OLLAMA_READY = "OLLAMA_READY"
OLLAMA_UNAVAILABLE = "OLLAMA_UNAVAILABLE"
OLLAMA_MODEL_MISSING = "OLLAMA_MODEL_MISSING"
OLLAMA_ERROR = "OLLAMA_ERROR"

# Global Process Lifecycle Guard
_OLLAMA_STARTUP_ATTEMPTED = False
_OLLAMA_PROCESS: Optional[subprocess.Popen] = None


# Availability cache: avoids repeated 1.5s-timeout HTTP requests
_AVAIL_CACHE_RESULT: Optional[bool] = None
_AVAIL_CACHE_TIME: float = 0.0
_AVAIL_CACHE_TTL_OK: float = 10.0    # cache positive result for 10s
_AVAIL_CACHE_TTL_FAIL: float = 5.0   # cache negative result for 5s (allows faster recovery detection)


# Models list cache
_MODELS_CACHE_RESULT: Optional[List[str]] = None
_MODELS_CACHE_TIME: float = 0.0
_MODELS_CACHE_TTL: float = 15.0


def invalidate_ollama_cache() -> None:
    """Explicitly invalidate the availability cache (e.g. after restart attempt)."""
    global _AVAIL_CACHE_RESULT, _AVAIL_CACHE_TIME, _MODELS_CACHE_RESULT, _MODELS_CACHE_TIME
    _AVAIL_CACHE_RESULT = None
    _AVAIL_CACHE_TIME = 0.0
    _MODELS_CACHE_RESULT = None
    _MODELS_CACHE_TIME = 0.0


def is_ollama_available(base_url: str = OLLAMA_BASE_URL) -> bool:
    """Checks if local Ollama server is running and reachable. Results cached with short TTL."""
    global _AVAIL_CACHE_RESULT, _AVAIL_CACHE_TIME
    if "localhost" in base_url:
        base_url = base_url.replace("localhost", "127.0.0.1")
    now = time.time()
    if _AVAIL_CACHE_RESULT is not None:
        ttl = _AVAIL_CACHE_TTL_OK if _AVAIL_CACHE_RESULT else _AVAIL_CACHE_TTL_FAIL
        if (now - _AVAIL_CACHE_TIME) < ttl:
            return _AVAIL_CACHE_RESULT
    try:
        req = urllib.request.urlopen(f"{base_url}/api/tags", timeout=1.5)
        result = req.status == 200
    except Exception:
        result = False
    _AVAIL_CACHE_RESULT = result
    _AVAIL_CACHE_TIME = now
    return result


def get_available_ollama_models(base_url: str = OLLAMA_BASE_URL) -> List[str]:
    """Returns list of installed local Ollama models with short TTL caching."""
    global _MODELS_CACHE_RESULT, _MODELS_CACHE_TIME
    if "localhost" in base_url:
        base_url = base_url.replace("localhost", "127.0.0.1")
    now = time.time()
    if _MODELS_CACHE_RESULT is not None and (now - _MODELS_CACHE_TIME) < _MODELS_CACHE_TTL:
        return _MODELS_CACHE_RESULT

    try:
        req = urllib.request.urlopen(f"{base_url}/api/tags", timeout=1.5)
        if req.status == 200:
            data = json.loads(req.read().decode("utf-8"))
            models = data.get("models", [])
            names = [m.get("name", "") for m in models]
            _MODELS_CACHE_RESULT = names
            _MODELS_CACHE_TIME = now
            return names
    except Exception as e:
        logger.debug(f"Failed to fetch Ollama models: {e}")
    return []


_LAST_HEALTH_CHECK_TIME: float = 0.0
_CACHED_HEALTH_RESULT: Optional[Dict[str, Any]] = None

def check_ollama_health(base_url: str = OLLAMA_BASE_URL, required_model: Optional[str] = None) -> Dict[str, Any]:
    """
    Full readiness sequence:
    1. Server reachable? (GET /api/tags)
    2. API healthy?
    3. Required model present?
    4. Returns diagnostic dict with status token (cached for 15s when healthy).
    """
    global _LAST_HEALTH_CHECK_TIME, _CACHED_HEALTH_RESULT
    now = time.time()
    if _CACHED_HEALTH_RESULT and _CACHED_HEALTH_RESULT.get("ready") and (now - _LAST_HEALTH_CHECK_TIME < 15.0):
        if not required_model or any(required_model.lower() in m.lower() for m in _CACHED_HEALTH_RESULT.get("models", [])):
            return _CACHED_HEALTH_RESULT

    if not is_ollama_available(base_url):
        res = {
            "ready": False,
            "status": OLLAMA_UNAVAILABLE,
            "models": [],
            "error": f"Ollama server is not reachable at {base_url}."
        }
        _CACHED_HEALTH_RESULT = res
        _LAST_HEALTH_CHECK_TIME = now
        return res

    models = get_available_ollama_models(base_url)
    if required_model:
        model_found = any(required_model.lower() in m.lower() for m in models)
        if not model_found:
            res = {
                "ready": False,
                "status": OLLAMA_MODEL_MISSING,
                "missing_model": required_model,
                "models": models,
                "error": f"Required model '{required_model}' is not installed in local Ollama."
            }
            _CACHED_HEALTH_RESULT = res
            _LAST_HEALTH_CHECK_TIME = now
            return res

    res = {
        "ready": True,
        "status": OLLAMA_READY,
        "models": models,
        "error": None
    }
    _CACHED_HEALTH_RESULT = res
    _LAST_HEALTH_CHECK_TIME = now
    return res


def find_ollama_executable() -> Optional[str]:
    """Finds Ollama executable from PATH or standard Windows installation locations."""
    import shutil
    in_path = shutil.which("ollama")
    if in_path:
        return in_path

    candidates = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Ollama\ollama.exe"),
        r"C:\Program Files\Ollama\ollama.exe",
        r"C:\Program Files (x86)\Ollama\ollama.exe"
    ]
    for cand in candidates:
        if os.path.exists(cand):
            return cand
    return None


def auto_start_ollama(base_url: str = OLLAMA_BASE_URL, max_wait_sec: float = 4.0) -> bool:
    """
    Safely attempts to start local 'ollama serve' in background if not already running.
    - Non-blocking terminal (creationflags=subprocess.CREATE_NO_WINDOW on Windows).
    - Prevents duplicate process launching.
    - Bounded startup retry loop.
    """
    global _OLLAMA_STARTUP_ATTEMPTED, _OLLAMA_PROCESS

    if is_ollama_available(base_url):
        logger.info("[Ollama] Server is already running and healthy.")
        return True

    if _OLLAMA_STARTUP_ATTEMPTED:
        logger.info("[Ollama] Auto-start already attempted in this session.")
        return is_ollama_available(base_url)

    _OLLAMA_STARTUP_ATTEMPTED = True

    exe_path = find_ollama_executable()
    if not exe_path:
        logger.warning("[Ollama] Ollama executable not found in PATH or standard installation paths. Download official installer from https://ollama.com/download/OllamaSetup.exe to enable local offline AI.")
        return False

    logger.info(f"[Ollama] Server not detected. Attempting background startup via executable '{exe_path}'...")

    try:
        cflags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" and hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        _OLLAMA_PROCESS = subprocess.Popen(
            [exe_path, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=cflags
        )
        logger.info(f"[Ollama] Spawned background process pid={_OLLAMA_PROCESS.pid}")

        # Invalidate availability cache so health checks make real HTTP requests
        invalidate_ollama_cache()
        # Bounded health-check poll loop
        start_time = time.time()
        while time.time() - start_time < max_wait_sec:
            time.sleep(0.5)
            if is_ollama_available(base_url):
                logger.info("[Ollama] Background startup succeeded. Server is now ONLINE.")
                return True

    except Exception as e:
        logger.warning(f"[Ollama] Autonomous startup failed: {e}")

    return is_ollama_available(base_url)


def ensure_ollama_ready(
    base_url: str = OLLAMA_BASE_URL,
    required_model: Optional[str] = None,
    auto_start: bool = True
) -> Dict[str, Any]:
    """
    Guarantees readiness check + optional safe auto-start sequence.
    """
    health = check_ollama_health(base_url, required_model)
    if health["ready"]:
        return health

    if auto_start and health["status"] == OLLAMA_UNAVAILABLE:
        started = auto_start_ollama(base_url)
        if started:
            health = check_ollama_health(base_url, required_model)

    return health


def generate_ollama_response(
    prompt: str,
    system_prompt: str = "",
    model: Optional[str] = None,
    temperature: float = 0.7,
    base_url: str = OLLAMA_BASE_URL,
    auto_start: bool = True,
    timeout: float = 15.0,
    num_predict: int = 128
) -> Dict[str, Any]:
    """
    Generates response from local Ollama model with hardened lifecycle.
    Defaults to 'fotiecodes/jarvis' or 'gemma4:12b' if installed.
    """
    if "localhost" in base_url:
        base_url = base_url.replace("localhost", "127.0.0.1")

    readiness = ensure_ollama_ready(base_url, required_model=model, auto_start=auto_start)
    if not readiness["ready"]:
        return {
            "success": False,
            "text": "",
            "error": readiness.get("error") or "Ollama service unavailable.",
            "status": readiness.get("status", OLLAMA_UNAVAILABLE)
        }

    available_models = readiness.get("models", [])
    selected_model = model

    if not selected_model:
        # Dynamic matching against installed models
        for candidate in ["fotiecodes/jarvis:latest", "fotiecodes/jarvis", "gemma4:12b", "gemma:12b", "llama3"]:
            if any(candidate.lower() in m.lower() for m in available_models):
                selected_model = candidate
                break
        if not selected_model and available_models:
            selected_model = available_models[0]

    if not selected_model:
        selected_model = DEFAULT_STARK_MODEL

    payload = {
        "model": selected_model,
        "prompt": prompt,
        "system": system_prompt or CONVERSATION_STYLE,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
              "num_ctx": 4096 if num_predict > 512 else 1024
        },
        "keep_alive": DEFAULT_KEEP_ALIVE
    }

    t0 = time.time()
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/api/generate",
            data=data,
            headers={"Content-Type": "application/json", "Connection": "keep-alive"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            response_text = res_json.get("response", "").strip()
            total_ms = int((time.time() - t0) * 1000)
            try:
                import core.ai_policy as ai_policy
                ai_policy.record_local_ai_call(selected_model)
            except Exception:
                pass
            return {
                "success": True,
                "text": response_text,
                "model_used": selected_model,
                "total_ms": total_ms,
                "status": OLLAMA_READY
            }
    except Exception as e:
        logger.warning(f"[Ollama] Generation failed with model '{selected_model}': {e}")
        return {
            "success": False,
            "text": "",
            "error": str(e),
            "status": OLLAMA_ERROR
        }


import threading
_OLLAMA_PROVIDER_LOCK = threading.Lock()
_GLOBAL_OLLAMA_PROVIDER_INSTANCE: Optional['OllamaProvider'] = None

def get_ollama_provider(base_url: str = OLLAMA_BASE_URL) -> 'OllamaProvider':
    """Thread-safe singleton accessor for OllamaProvider to avoid repeated re-initialization overhead."""
    global _GLOBAL_OLLAMA_PROVIDER_INSTANCE
    with _OLLAMA_PROVIDER_LOCK:
        if _GLOBAL_OLLAMA_PROVIDER_INSTANCE is None:
            _GLOBAL_OLLAMA_PROVIDER_INSTANCE = OllamaProvider(base_url=base_url)
        return _GLOBAL_OLLAMA_PROVIDER_INSTANCE

class OllamaProvider:
    """
    Authoritative Ollama Local LLM Provider Class for JARVIS.
    Supports chat, streaming, structured output, model auto-discovery,
    health checks, metrics tracking, and cancellation.
    """
    def __init__(self, base_url: str = OLLAMA_BASE_URL, persona_model: Optional[str] = None, tool_model: Optional[str] = None):
        self.base_url = base_url
        self._available_models = get_available_ollama_models(base_url)
        
        # Discover exact model tags from installed models - prioritize fotiecodes/jarvis:latest
        self.persona_model = persona_model
        if not self.persona_model:
            for candidate in ["fotiecodes/jarvis:latest", "fotiecodes/jarvis", "gemma4:12b", "llama3"]:
                match = next((m for m in self._available_models if candidate.lower() in m.lower()), None)
                if match:
                    self.persona_model = match
                    break
        if not self.persona_model:
            self.persona_model = "fotiecodes/jarvis:latest"

        self.tool_model = tool_model
        if not self.tool_model:
            if self.persona_model and any(self.persona_model.lower() in m.lower() for m in self._available_models):
                self.tool_model = self.persona_model
            else:
                for candidate in ["fotiecodes/jarvis:latest", "fotiecodes/jarvis", "gemma4:12b", "gemma:12b", "llama3"]:
                    match = next((m for m in self._available_models if candidate.lower() in m.lower()), None)
                    if match:
                        self.tool_model = match
                        break
        if not self.tool_model:
            self.tool_model = self.persona_model or "fotiecodes/jarvis:latest"

        logger.info(f"[OllamaProvider] Initialized. Persona model: '{self.persona_model}', Tool model: '{self.tool_model}'")

    def health_check(self) -> Dict[str, Any]:
        """Returns structured diagnostic status dict."""
        installed = find_ollama_executable() is not None or is_ollama_available(self.base_url)
        online = is_ollama_available(self.base_url)
        models = get_available_ollama_models(self.base_url) if online else []
        ready = online and bool(models)
        return {
            "ready": ready,
            "installed": installed,
            "service": "ONLINE" if online else "OFFLINE",
            "status": "OLLAMA_READY" if ready else ("OLLAMA_UNAVAILABLE" if not online else "OLLAMA_MODEL_MISSING"),
            "models": models,
            "selected_persona_model": self.persona_model,
            "selected_tool_model": self.tool_model
        }

    def chat(self, prompt: str, system_prompt: str = "", model: Optional[str] = None, temperature: float = 0.7, timeout: float = 60.0) -> Dict[str, Any]:
        """Synchronous chat response generation with latency metrics."""
        target_model = model or self.persona_model or DEFAULT_STARK_MODEL
        return generate_ollama_response(
            prompt=prompt,
            system_prompt=system_prompt,
            model=target_model,
            temperature=temperature,
            base_url=self.base_url,
            timeout=timeout
        )

    def chat_stream(self, prompt: str, system_prompt: str = "", model: Optional[str] = None, temperature: float = 0.7, timeout: float = 60.0):
        """Streaming chat response token generator. Does not block audio capture/VAD."""
        target_model = model or self.persona_model or DEFAULT_STARK_MODEL
        payload = {
            "model": target_model,
            "prompt": prompt,
            "system": system_prompt or CONVERSATION_STYLE,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": 96,
                "num_ctx": 1024
            },
            "keep_alive": DEFAULT_KEEP_ALIVE
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=data,
            headers={"Content-Type": "application/json", "Connection": "keep-alive"},
            method="POST"
        )
        t0 = time.time()
        first_token_time = None
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                for line in resp:
                    if not line:
                        continue
                    try:
                        chunk_json = json.loads(line.decode("utf-8"))
                        token = chunk_json.get("response", "")
                        if token and first_token_time is None:
                            first_token_time = time.time()
                            first_token_ms = int((first_token_time - t0) * 1000)
                            logger.info(f"[OllamaProvider] First token latency: {first_token_ms}ms")
                        if token:
                            yield token
                        if chunk_json.get("done", False):
                            break
                    except Exception:
                        continue
        except Exception as e:
            logger.warning(f"[OllamaProvider] Streaming failed for model '{target_model}': {e}")
            yield f"[Ollama Error: {e}]"

    def generate_structured_action(self, prompt: str, allowed_tools: List[str], model: Optional[str] = None, timeout: float = 60.0) -> Dict[str, Any]:
        """
        Generates structured JSON action proposals using tool model.
        Strictly validates JSON structure, limits token prediction for ultra-low latency,
        enforces format='json', and blocks raw shell / subprocess execution.
        """
        target_model = model or self.tool_model or DEFAULT_TOOL_MODEL
        sys_prompt = (
            f"You are JARVIS reasoning engine. Output ONLY a raw valid JSON object matching this schema:\n"
            f'{{"type": "action", "capability": "<tool_name>", "action": "<action_name>", "target": "<target_or_args>"}}\n'
            f"Allowed capabilities: {allowed_tools}.\n"
            f"CRITICAL: Do NOT output thinking, reasoning, explanation, shell commands, or markdown formatting."
        )

        # High-performance payload with format='json', low num_predict and keep_alive
        payload = {
            "model": target_model,
            "prompt": prompt,
            "system": sys_prompt,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": 128
            },
            "keep_alive": DEFAULT_KEEP_ALIVE
        }

        t0 = time.time()
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{self.base_url}/api/generate",
                data=data,
                headers={"Content-Type": "application/json", "Connection": "keep-alive"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                res_json = json.loads(resp.read().decode("utf-8"))
                raw_text = res_json.get("response", "").strip()
                total_ms = int((time.time() - t0) * 1000)

                # Clean markdown or thought tags if present
                if "<thought>" in raw_text and "</thought>" in raw_text:
                    raw_text = raw_text.split("</thought>")[-1].strip()
                if "```" in raw_text:
                    lines = raw_text.split("\n")
                    lines = [l for l in lines if not l.strip().startswith("```")]
                    raw_text = "\n".join(lines).strip()

                try:
                    parsed = json.loads(raw_text)
                except Exception:
                    import re
                    match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                    if match:
                        parsed = json.loads(match.group(0))
                    else:
                        raise

                if not isinstance(parsed, dict):
                    return {"success": False, "error": "Invalid structured response: not a JSON object"}
                
                # Security Rule Validation
                cap = parsed.get("capability") or parsed.get("tool") or parsed.get("type")
                if not cap or cap not in allowed_tools:
                    for dangerous in ["powershell", "cmd", "subprocess", "rmdir", "del", "exec"]:
                        if dangerous in str(parsed).lower():
                            logger.error(f"[SECURITY REJECT] Ollama proposed dangerous command: {parsed}")
                            return {"success": False, "error": "SECURITY_REJECT: Raw shell or prohibited capability requested."}

                return {
                    "success": True,
                    "action_proposal": parsed,
                    "model_used": target_model,
                    "total_ms": total_ms
                }
        except Exception as parse_err:
            logger.warning(f"[OllamaProvider] Structured action generation/parse failed: {parse_err}")
            return {"success": False, "error": f"Structured action error: {parse_err}"}


def prewarm_ollama(model: Optional[str] = None, base_url: str = OLLAMA_BASE_URL) -> None:
    """Non-blocking background pre-warming of Ollama model."""
    def _run():
        try:
            if is_ollama_available(base_url):
                logger.info(f"[Ollama] Pre-warming local model '{model or DEFAULT_STARK_MODEL}'...")
                generate_ollama_response(
                    prompt="System readiness ping.",
                    system_prompt="You are JARVIS. Reply in 1 word.",
                    model=model,
                    timeout=15.0,
                    base_url=base_url
                )
                logger.info("[Ollama] Model pre-warm complete.")
        except Exception as e:
            logger.debug(f"[Ollama] Pre-warm non-fatal error: {e}")

    threading.Thread(target=_run, daemon=True, name="Ollama_Prewarm_Daemon").start()


