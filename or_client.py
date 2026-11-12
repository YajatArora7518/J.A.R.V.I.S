import json
import sys
import time
import base64
import logging
from core.conversation_style import CONVERSATION_STYLE

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from pathlib import Path
from typing import Optional

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("openrouter_client")

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR     = _get_base_dir()
API_KEY_PATH = BASE_DIR / "config" / "api_keys.json"

def _load_api_key() -> str:
    from config import get_api_key
    return get_api_key("openrouter_api_key")

TEXT_MODELS: list[str] = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "google/gemma-2-9b-it:free",
    "qwen/qwen-2.5-72b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "deepseek/deepseek-r1-distill-llama-70b:free",
]

VISION_MODELS: list[str] = [
    "google/gemma-2-9b-it:free",
    "meta-llama/llama-3.3-70b-instruct:free",
]

API_URL               = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MAX_TOKENS    = 4096
DEFAULT_TEMPERATURE   = 0.7
REQUEST_TIMEOUT       = 30   # seconds per request
MAX_RETRIES_PER_MODEL = 1    # attempts before moving to next model
RETRY_DELAY           = 1    # seconds between retries
RATE_LIMIT_COOLDOWN   = 60   # seconds before retrying a rate-limited model

_rate_limited: dict[str, float] = {}

class OpenRouterClient:

    def __init__(self):
        self._api_key = None

    @property
    def api_key(self) -> str:
        if not self._api_key:
            self._api_key = _load_api_key()
        return self._api_key

    def _is_rate_limited(self, model: str) -> bool:
        until = _rate_limited.get(model, 0)
        if time.time() < until:
            return True
        return False

    def _set_rate_limited(self, model: str):
        _rate_limited[model] = time.time() + RATE_LIMIT_COOLDOWN
        logger.warning(
            f"[OpenRouter] Rate limited: {model} — "
            f"cooling down for {RATE_LIMIT_COOLDOWN}s"
        )

    def _call(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
        response_format: Optional[dict] = None,
    ) -> Optional[str]:
        from core.ai_policy import assert_cloud_ai_allowed
        assert_cloud_ai_allowed("OpenRouter")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/json",
            "HTTP-Referer":   "https://github.com/jarvis-assistant",
            "X-Title":        "JARVIS AI Assistant",
        }
        payload = {
            "model":       model,
            "messages":    messages,
            "max_tokens":  max_tokens,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format

        for attempt in range(1, MAX_RETRIES_PER_MODEL + 1):
            try:
                resp = requests.post(
                    API_URL,
                    headers=headers,
                    data=json.dumps(payload),
                    timeout=REQUEST_TIMEOUT,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0]["message"]["content"].strip()
                elif resp.status_code in (429, 403):
                    self._set_rate_limited(model)
                    return None
                else:
                    logger.warning(
                        f"[OpenRouter] {model} → HTTP {resp.status_code} "
                        f"(attempt {attempt}/{MAX_RETRIES_PER_MODEL})"
                    )
            except requests.exceptions.Timeout:
                logger.warning(
                    f"[OpenRouter] {model} → Timeout "
                    f"(attempt {attempt}/{MAX_RETRIES_PER_MODEL})"
                )
            except Exception as e:
                logger.error(f"[OpenRouter] {model} → Unexpected error: {e}")

            if attempt < MAX_RETRIES_PER_MODEL:
                time.sleep(RETRY_DELAY)

        return None

    def _call_with_fallback(
        self,
        pool: list[str],
        messages: list[dict],
        model: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        response_format: Optional[dict] = None,
    ) -> str:
        from core.ai_policy import is_cloud_ai_allowed
        has_images = any(isinstance(m.get("content"), list) for m in messages)
        if is_cloud_ai_allowed() and self.api_key:
            for candidate in ([model] if model else pool[:2]):
                if self._is_rate_limited(candidate):
                    continue
                response = self._call(candidate, messages, max_tokens, temperature, response_format)
                if response:
                    return response
        if has_images:
            # Never turn image bytes into a text prompt and pretend it is vision.
            raise RuntimeError("Image analysis unavailable: configure a cloud vision provider or use screen analysis.")
        try:
            from core.ollama_provider import is_ollama_available, auto_start_ollama, get_ollama_provider
            if not is_ollama_available():
                logger.info("[AIProvider] Ollama server offline. Attempting controlled local recovery...")
                auto_start_ollama(max_wait_sec=3.0)

            if is_ollama_available():
                logger.info("[AIProvider] Primary Provider selected: OLLAMA_LOCAL (fotiecodes/jarvis:latest)")
                provider = get_ollama_provider()
                system_prompt = "\n".join(str(m.get("content", "")) for m in messages if m.get("role") == "system")
                full_prompt = "\n".join(f"{m.get('role', 'user').upper()}: {m.get('content', '')}" for m in messages if m.get("role") != "system")
                
                # Check for generate/chat response
                if hasattr(provider, "chat"):
                    res = provider.chat(prompt=full_prompt, system_prompt=system_prompt, timeout=15.0)
                    if res.get("success") and res.get("response"):
                        logger.info("[AIProvider] ✓ Success via OLLAMA_LOCAL")
                        return res["response"].strip()
                    elif res.get("success") and res.get("text"):
                        logger.info("[AIProvider] ✓ Success via OLLAMA_LOCAL")
                        return res["text"].strip()
            else:
                logger.warning("[AIProvider] Ollama Local is unavailable after recovery attempt.")
        except Exception as o_err:
            logger.error(f"[AIProvider] Ollama Local execution exception: {o_err}")

        # Strict Ollama-First Enforcement: ZERO normal cloud AI calls, ZERO HTTP 404 cascades
        logger.warning("[AIProvider] Returning honest local-AI-unavailable message. Cloud fallbacks disabled.")
        raise RuntimeError("AI providers are unavailable. Check your configured cloud key or local Ollama connection.")

    def chat(
        self,
        prompt: str,
        system: str = (
            "You are JARVIS, Yajat's practical laptop assistant. "
            "Use short, natural Hinglish unless another language is requested. "
            "No movie roleplay, invented protocols or unrelated coffee jokes. "
            "Never claim an action happened without its verified tool result.\n" + CONVERSATION_STYLE
        ),
        model: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ]
        return self._call_with_fallback(
            TEXT_MODELS, messages, model, max_tokens, temperature
        )

    def chat_json(
        self,
        prompt: str,
        system: str = (
            "Return ONLY valid JSON. "
            "No markdown fences, no extra text, no explanation."
        ),
        model: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> dict:
        messages = [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ]
        raw = self._call_with_fallback(
            TEXT_MODELS, messages, model, max_tokens, temperature=0.2
        )

        clean = raw.strip()
        if clean.startswith("```"):
            parts = clean.split("```")
            clean = parts[1] if len(parts) > 1 else clean
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip().rstrip("`").strip()

        try:
            return json.loads(clean)
        except json.JSONDecodeError as e:
            logger.error(
                f"[OpenRouter] JSON parse failed: {e}\n"
                f"Raw response (first 300 chars): {raw[:300]}"
            )
            raise ValueError(
                f"Model returned unparseable JSON: {e}\n"
                f"Raw output: {raw[:200]}"
            )

    def vision(
        self,
        prompt: str,
        image_b64: str,
        mime: str = "image/png",
        system: str = "Analyze the image and describe what you see clearly and concisely.",
        model: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> str:
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime};base64,{image_b64}"
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            },
        ]
        return self._call_with_fallback(
            VISION_MODELS, messages, model, max_tokens, temperature=0.2
        )

    def vision_from_file(
        self,
        prompt: str,
        image_path: str,
        system: str = "Analyze the image and describe what you see clearly and concisely.",
        model: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> str:
        path = Path(image_path)
        mime_map = {
            ".png":  "image/png",
            ".jpg":  "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif":  "image/gif",
        }
        mime = mime_map.get(path.suffix.lower(), "image/png")

        with open(path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")

        return self.vision(prompt, image_b64, mime, system, model, max_tokens)

    def multi_turn(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> str:
    
        return self._call_with_fallback(
            TEXT_MODELS, messages, model, max_tokens, temperature
        )

    def available_models(self) -> dict:
        return {
            "text_models":   TEXT_MODELS,
            "vision_models": VISION_MODELS,
            "rate_limited":  list(_rate_limited.keys()),
            "total_text":    len(TEXT_MODELS),
            "total_vision":  len(VISION_MODELS),
        }

client = OpenRouterClient()

if __name__ == "__main__":
    print("=" * 55)
    print("  JARVIS — OpenRouter Client Self-Test")
    print("=" * 55)

    print("\n[TEST 1] Basic chat...")
    try:
        reply = client.chat("Introduce yourself in one sentence.")
        print(f"  Response : {reply}")
        print(f"  Status   : PASS ✓")
    except Exception as e:
        print(f"  Status   : FAIL ✗ — {e}")

    print("\n[TEST 2] JSON mode...")
    try:
        data = client.chat_json(
            'List 3 programming languages. Format: {"languages": ["a", "b", "c"]}',
            system="Return only valid JSON. No extra text."
        )
        print(f"  Response : {data}")
        print(f"  Status   : PASS ✓")
    except Exception as e:
        print(f"  Status   : FAIL ✗ — {e}")

    print("\n[TEST 3] Multi-turn conversation...")
    try:
        history = [
            {"role": "system",    "content": "You are a helpful assistant. Be brief."},
            {"role": "user",      "content": "My name is Tony."},
            {"role": "assistant", "content": "Hello Tony, how can I help you?"},
            {"role": "user",      "content": "What is my name?"},
        ]
        reply = client.multi_turn(history)
        print(f"  Response : {reply}")
        print(f"  Status   : PASS ✓")
    except Exception as e:
        print(f"  Status   : FAIL ✗ — {e}")

    print("\n[TEST 4] Model pool info...")
    info = client.available_models()
    print(f"  Text models   : {info['total_text']}")
    print(f"  Vision models : {info['total_vision']}")
    print(f"  Rate limited  : {info['rate_limited'] or 'none'}")
    print(f"  Status        : PASS ✓")

    print("\n" + "=" * 55)
    print("  All tests complete.")
    print("=" * 55)
