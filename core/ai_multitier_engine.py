# core/ai_multitier_engine.py
# Universal Multi-Tier AI Brain for J.A.R.V.I.S
# Tier 1: Local Ollama (fotiecodes/jarvis:latest) — Primary brain for conversations, Hinglish, intent, memory
# Tier 2: Cloud Gemini (gemini-3.6-flash) — Resilient fallback when local model is offline/times out
# Tier 3: OpenRouter — Optional tertiary fallback
# Strict Privacy Guard: Never silently sends camera frames, private files, or credentials to cloud providers.

import os
import sys
import json
import time
import logging
import threading
from core.conversation_style import get_conversation_style
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger("JARVIS.AIBrain")

_GLOBAL_AI_ENGINE: Optional['MultiTierAIEngine'] = None
_AI_ENGINE_LOCK = threading.Lock()
_EXHAUSTED_GEMINI_MODELS: Dict[str, float] = {}


def get_ai_engine() -> 'MultiTierAIEngine':
    """Thread-safe accessor for the MultiTierAIEngine singleton."""
    global _GLOBAL_AI_ENGINE
    with _AI_ENGINE_LOCK:
        if _GLOBAL_AI_ENGINE is None:
            _GLOBAL_AI_ENGINE = MultiTierAIEngine()
        return _GLOBAL_AI_ENGINE


class MultiTierAIEngine:
    """
    Universal Multi-Tier Intelligence Coordinator.
    Implements:
    - Tier 1: Local Ollama with keep_alive="30m" and startup prewarming.
    - Tier 2: Google GenAI gemini-3.6-flash fallback.
    - Tier 3: OpenRouter fallback.
    - Charismatic Stark-inspired Hinglish & English personality.
    - Context injection (time, battery, memories, active window).
    - Privacy protection against sending private/sensitive files to cloud.
    """

    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent.parent
        self.config_path = self.base_dir / "config" / "api_keys.json"
        self.memory_path = self.base_dir / "memory" / "long_term.json"
        
        self.gemini_api_key: Optional[str] = None
        self.openrouter_api_key: Optional[str] = None
        self.ollama_model: str = "fotiecodes/jarvis:latest"
        self.cloud_model: str = "gemini-3.5-flash-lite"

        self._load_config()
        self._prewarmed = False

        # Conversational Sliding Window (Max 6 meaningful turns)
        self._history_lock = threading.Lock()
        self._conversation_history: List[Dict[str, Any]] = []
        self._max_history_turns = 6

    def redact_sensitive_content(self, text: str) -> str:
        """Redacts API keys, tokens, passwords, and credentials from context and logs."""
        import re
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

    def add_turn(self, role: str, content: str):
        """Safely records a conversational turn into sliding window memory."""
        if not content or not isinstance(content, str) or not content.strip():
            return
        cleaned = self.redact_sensitive_content(content.strip())
        with self._history_lock:
            # Prevent duplicate insertion of the same message
            same_role_turns = [t for t in self._conversation_history if t.get("role") == role]
            if same_role_turns and same_role_turns[-1].get("content") == cleaned:
                same_role_turns[-1]["timestamp"] = time.time()
                return
            self._conversation_history.append({
                "role": role,
                "content": cleaned,
                "timestamp": time.time()
            })
            if len(self._conversation_history) > self._max_history_turns:
                self._conversation_history = self._conversation_history[-self._max_history_turns:]

    def clear_history(self):
        """Clears recent conversational turns."""
        with self._history_lock:
            self._conversation_history.clear()

    def get_history_formatted(self) -> str:
        """Returns formatted sliding-window dialogue turns."""
        with self._history_lock:
            if not self._conversation_history:
                return ""
            lines = []
            for turn in self._conversation_history:
                speaker = "User" if turn.get("role") == "user" else "JARVIS"
                lines.append(f"{speaker}: {turn.get('content')}")
            return "\n".join(lines)

    def _load_config(self):
        """Loads API keys and provider preferences."""
        from config import get_api_key, get_model_name, get_runtime_config
        self.gemini_api_key = get_api_key("gemini_api_key")
        self.openrouter_api_key = get_api_key("openrouter_api_key")
        self.cloud_model = get_model_name()
        self.prefer_cloud = bool(get_runtime_config().get("prefer_cloud", False))
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                model_cfg = cfg.get("ollama_model", "fotiecodes/jarvis")
                self.ollama_model = f"{model_cfg}:latest" if ":" not in model_cfg else model_cfg
            except Exception as e:
                logger.warning(f"[AIBrain] Failed to read api_keys.json: {e}")

    def prewarm_background(self):
        """Runs non-blocking pre-warming of Ollama model in a daemon thread."""
        if self._prewarmed:
            return
        t = threading.Thread(target=self._prewarm_worker, daemon=True, name="JARVIS_Ollama_Prewarm")
        t.start()

    def _prewarm_worker(self):
        """Internal prewarm worker sending a lightweight ping with keep_alive to Ollama."""
        try:
            from core.ollama_provider import is_ollama_available, generate_ollama_response
            if not is_ollama_available():
                logger.info("[AIBrain] Ollama server offline during prewarm; skipping.")
                return
            
            logger.info(f"[AIBrain] 🚀 Pre-warming Tier 1 local model '{self.ollama_model}' into memory...")
            t0 = time.time()
            res = generate_ollama_response(
                prompt="System check. Ready?",
                system_prompt="You are JARVIS. Reply in 2 words.",
                model=self.ollama_model,
                timeout=15.0
            )
            elapsed = round(time.time() - t0, 1)
            if res.get("success"):
                self._prewarmed = True
                logger.info(f"[AIBrain] ✅ Tier 1 model pre-warmed in {elapsed}s: '{res.get('text', '').strip()}'")
            else:
                logger.warning(f"[AIBrain] ⚠️ Pre-warm did not complete: {res.get('error')}")
        except Exception as ex:
            logger.debug(f"[AIBrain] Pre-warm exception (non-fatal): {ex}")

    def _build_contextual_prompt(self, user_prompt: str) -> str:
        """Injects dynamic context (current time, memory facts, user preferences)."""
        now = time.strftime("%A, %d %B %Y, %I:%M %p")
        memory_snippets = []

        if self.memory_path.exists():
            try:
                with open(self.memory_path, "r", encoding="utf-8") as f:
                    mem = json.load(f)
                
                # Extract key user attributes
                identity = mem.get("identity", {})
                prefs = mem.get("preferences", {})
                projects = mem.get("projects", {})
                
                if "language" in prefs:
                    memory_snippets.append(f"Preferred Language: {prefs['language'].get('value')}")
                if "college_plan" in projects:
                    memory_snippets.append(f"College: {projects['college_plan'].get('value')}")
            except Exception:
                pass

        mem_text = " | ".join(memory_snippets) if memory_snippets else "None"
        history_str = self.get_history_formatted()
        history_block = f"\nRecent Dialogue History:\n{history_str}\n" if history_str else ""

        system_instructions = (
            "You are JARVIS, Yajat's practical personal laptop assistant.\n"
            f"Current Time: {now}\n"
            f"User Context: {mem_text}\n"
            f"{history_block}"
            "Personality Guidelines:\n"
            "- Be calm, direct and useful. No movie roleplay, invented protocols, theatrical jokes or repeated introductions.\n"
            "- Default to short everyday Hinglish (Hindi written in Latin script) unless the user asks for English or another language. Use normal phrases such as 'Haan, bolo', 'Chrome khol diya', 'Ye command samajh nahi aayi'.\n"
            "- Never bring up coffee, lectures, college or old personal facts unless they answer the current request.\n"
            "- Never invent missing phone numbers, contacts or unavailable tools. If no tool checked them, you do not know their state; ask for the missing command detail instead of claiming laptop access is unavailable.\n"
            "- You are generating a conversation response, not executing laptop controls. Never claim to change volume, open an app, create a reminder, make coffee or perform any action. Only an actual verified tool result can establish those actions. If a requested action reached this chat fallback, state that it has not executed and ask for the needed detail.\n"
            "- Use familiar, natural address such as an occasional 'bhai'; do not repeat a title in every reply.\n"
            "- Deliver one useful response. Use lists when they help a plan or requested explanation.\n"
            "- Keep ordinary conversation brief; provide complete writing drafts and explanations. No unrelated suggestions.\n"
            "- Explicit current user instructions MUST always override remembered context.\n"
            "- Never say robotic phrases like 'As an AI model'. Never invent fake system statuses."
        )
        from agent.emotional_context import get_emotional_context
        emotional = get_emotional_context()
        emotional.detect_state(user_prompt)
        from agent.daily_planner import get_daily_planner
        return system_instructions + '\n' + get_conversation_style() + '\n' + emotional.get_response_modifier() + '\n' + get_daily_planner().prompt_context()

    def _contains_sensitive_content(self, text: str) -> bool:
        """Checks if text contains private credentials or local security data."""
        lower = text.lower()
        triggers = ["password", "private key", "auth_token", "api_key", "secret_key", "credentials", "credit card"]
        return any(t in lower for t in triggers)

    def generate_response(
        self,
        prompt: str,
        system_override: Optional[str] = None,
        prefer_cloud: Optional[bool] = None,
        allow_sensitive_cloud: bool = False,
        _local_fallback: bool = False,
        response_tokens: int = 512,
        record_history: bool = True,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Executes multi-tier AI inference:
        Tier 1: Local Ollama (unless prefer_cloud is True or Ollama fails)
        Tier 2: Cloud Gemini (gemini-3.6-flash)
        Tier 3: OpenRouter Fallback
        """
        # Record user turn in conversational memory
        if record_history and not _local_fallback:
            self.add_turn("user", prompt)

        system_prompt = system_override or self._build_contextual_prompt(prompt)
        is_sensitive = self._contains_sensitive_content(prompt)
        import core.ai_policy as ai_policy
        if prefer_cloud is None:
            prefer_cloud = self.prefer_cloud
        prefer_cloud = bool(prefer_cloud and ai_policy.is_cloud_ai_allowed()
                            and (self.gemini_api_key or self.openrouter_api_key)
                            and (not is_sensitive or allow_sensitive_cloud))

        # -------------------------------------------------------------
        # TIER 1: Local Ollama (100% Local AI)
        # -------------------------------------------------------------
        if not prefer_cloud:
            from core.ollama_provider import is_ollama_available, generate_ollama_response
            if is_ollama_available():
                try:
                    logger.info(f"[AIBrain] [Tier 1: Ollama] Invoking model '{self.ollama_model}'...")
                    t0 = time.time()
                    res = generate_ollama_response(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        model=self.ollama_model,
                        timeout=15.0,
                        num_predict=response_tokens,
                        temperature=temperature
                    )
                    if res.get("success") and res.get("text", "").strip():
                        duration_ms = int((time.time() - t0) * 1000)
                        reply = res["text"].strip()
                        if record_history: self.add_turn("assistant", reply)
                        logger.info(f"[AIBrain] [Tier 1: Ollama] Generated response in {duration_ms}ms")
                        try:
                            from core.runtime_supervisor import get_runtime_supervisor
                            get_runtime_supervisor().record_success("OLLAMA", provider=f"Tier 1: {self.ollama_model}", latency_ms=duration_ms)
                        except Exception:
                            pass
                        try:
                            import core.ai_policy as ai_policy
                            ai_policy.record_local_ai_call(self.ollama_model)
                        except Exception:
                            pass
                        return {
                            "success": True,
                            "tier": "TIER_1_OLLAMA",
                            "model": res.get("model_used", self.ollama_model),
                            "text": reply,
                            "duration_ms": duration_ms
                        }
                    else:
                        err_msg = str(res.get('error', 'empty_response'))
                        logger.warning(f"[AIBrain] [Tier 1: Ollama] Failed or empty: {err_msg}. Falling back to Tier 2...")
                        try:
                            from core.runtime_supervisor import get_runtime_supervisor
                            get_runtime_supervisor().record_failure("OLLAMA", offline=False, error_msg=err_msg, category="OLLAMA_DEGRADED")
                        except Exception:
                            pass
                except Exception as oe:
                    logger.warning(f"[AIBrain] [Tier 1: Ollama] Exception: {oe}. Falling back to Tier 2...")
                    try:
                        from core.runtime_supervisor import get_runtime_supervisor
                        get_runtime_supervisor().record_failure("OLLAMA", offline=True, error_msg=str(oe), category="OLLAMA_EXCEPTION")
                    except Exception:
                        pass
            else:
                logger.info("[AIBrain] [Tier 1: Ollama] Offline. Escalating to Tier 2 Cloud Fallback...")
                try:
                    from core.runtime_supervisor import get_runtime_supervisor
                    get_runtime_supervisor().record_failure("OLLAMA", offline=True, error_msg="Ollama server unreachable", category="OLLAMA_OFFLINE")
                except Exception:
                    pass

        # Guard: Check sensitive content before sending to cloud
        if is_sensitive and not allow_sensitive_cloud:
            return {
                "success": False,
                "tier": "PRIVACY_GUARD",
                "text": "Boss, this query contains sensitive credentials or private tokens. I cannot upload this to cloud AI without your confirmation.",
                "error": "SENSITIVE_CONTENT_CLOUD_BLOCKED"
            }

        # -------------------------------------------------------------
        # TIER 2 & 3: Cloud Fallbacks (Guarded by AI Policy Gate)
        # -------------------------------------------------------------
        if _local_fallback:
            return {"success": False, "tier": "FAILED_ALL_TIERS",
                    "text": "AI connection unavailable hai. Apps aur basic laptop commands phir bhi chala sakta hoon.",
                    "error": "ALL_AI_TIERS_UNAVAILABLE"}
        if not ai_policy.is_cloud_ai_allowed():
            try:
                ai_policy.assert_cloud_ai_allowed("Gemini Cloud Fallback")
            except ai_policy.CloudAIBlocked as cb:
                logger.info(f"[AIBrain] Cloud AI blocked by policy: {cb}")
                return {
                    "success": False,
                    "tier": "LOCAL_ZERO_CLOUD_GATE",
                    "text": "Sir, cloud AI is disabled by security policy (100% Local Mode). Local reasoning was unable to complete this query.",
                    "error": "CLOUD_AI_BLOCKED"
                }

        # TIER 2: Cloud Gemini
        if self.gemini_api_key:
            from google import genai
            from google.genai import types
            
            gemini_candidates = [
                self.cloud_model,
            ]
            
            # Prioritize models not currently rate-limited (429 circuit-breaker)
            now_t = time.time()
            gemini_candidates.sort(key=lambda m: 1 if _EXHAUSTED_GEMINI_MODELS.get(m, 0) > now_t else 0)

            for model_name in gemini_candidates:
                if _EXHAUSTED_GEMINI_MODELS.get(model_name, 0) > time.time():
                    continue
                try:
                    ai_policy.assert_cloud_ai_allowed("Gemini Conversation")
                    logger.info(f"[AIBrain] [Tier 2: Gemini] Querying '{model_name}'...")
                    t0 = time.time()
                    client = genai.Client(api_key=self.gemini_api_key, http_options=types.HttpOptions(timeout=10000))
                    
                    config = types.GenerateContentConfig(
                        temperature=temperature,
                        max_output_tokens=response_tokens,
                        system_instruction=system_prompt
                    )
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config
                    )
                    
                    if response and response.text:
                        reply = response.text.strip()
                        if record_history: self.add_turn("assistant", reply)
                        duration_ms = int((time.time() - t0) * 1000)
                        logger.info(f"[AIBrain] [Tier 2: Gemini] Generated response with '{model_name}' in {duration_ms}ms")
                        _EXHAUSTED_GEMINI_MODELS.pop(model_name, None)
                        try:
                            from core.runtime_supervisor import get_runtime_supervisor
                            get_runtime_supervisor().record_success("CLOUD_PROVIDER", provider=f"Tier 2: {model_name}", latency_ms=duration_ms)
                        except Exception:
                            pass
                        return {
                            "success": True,
                            "tier": "TIER_2_GEMINI",
                            "model": model_name,
                            "text": reply,
                            "duration_ms": duration_ms
                        }
                except Exception as ge:
                    ge_str = str(ge)
                    if "429" in ge_str or "RESOURCE_EXHAUSTED" in ge_str:
                        _EXHAUSTED_GEMINI_MODELS[model_name] = time.time() + 60.0
                    logger.warning(f"[AIBrain] [Tier 2: Gemini] Model '{model_name}' failed: {ge}. Trying fallback candidate...")
                    try:
                        from core.runtime_supervisor import get_runtime_supervisor
                        get_runtime_supervisor().record_failure("CLOUD_PROVIDER", offline=False, error_msg=str(ge), category="GEMINI_FAILOVER")
                    except Exception:
                        pass

        # -------------------------------------------------------------
        # TIER 3: OpenRouter Fallback
        # -------------------------------------------------------------
        if self.openrouter_api_key:
            try:
                ai_policy.assert_cloud_ai_allowed("OpenRouter Conversation")
                logger.info("[AIBrain] [Tier 3: OpenRouter] Querying fallback provider...")
                import urllib.request
                t0 = time.time()
                payload = {
                    "model": "meta-llama/llama-3.3-70b-instruct:free",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": response_tokens,
                    "temperature": temperature
                }
                req = urllib.request.Request(
                    "https://openrouter.ai/api/v1/chat/completions",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {self.openrouter_api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/jarvis",
                        "X-Title": "JARVIS Personal Assistant"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=20.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    choices = data.get("choices", [])
                    if choices:
                        reply = choices[0].get("message", {}).get("content", "").strip()
                        if record_history: self.add_turn("assistant", reply)
                        duration_ms = int((time.time() - t0) * 1000)
                        logger.info(f"[AIBrain] [Tier 3: OpenRouter] Generated response in {duration_ms}ms")
                        return {
                            "success": True,
                            "tier": "TIER_3_OPENROUTER",
                            "model": "openrouter-free",
                            "text": reply,
                            "duration_ms": duration_ms
                        }
            except Exception as ore:
                logger.error(f"[AIBrain] [Tier 3: OpenRouter] Call failed: {ore}")



        # Cloud-first mode still has a bounded local fallback; never recurse twice.
        if prefer_cloud:
            return self.generate_response(prompt, system_override=system_prompt,
                                          prefer_cloud=False, _local_fallback=True,
                                           response_tokens=response_tokens, record_history=record_history,
                                           temperature=temperature)
        # All tiers failed
        return {
            "success": False,
            "tier": "FAILED_ALL_TIERS",
            "text": "Boss, mere AI systems respond nahi kar rahe hain. Local Ollama check kar lijiye.",
            "error": "ALL_AI_TIERS_UNAVAILABLE"
        }
