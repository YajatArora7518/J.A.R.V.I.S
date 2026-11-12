# core/local_ai_provider.py
# Authoritative Local AI Provider for JARVIS
# Strictly 100% Local Inference via Ollama (No Cloud AI, No Gemini Fallback)

import os
import re
import json
import time
import logging
import threading
from core.conversation_style import CONVERSATION_STYLE
import urllib.request
from typing import Dict, Any, List, Optional, Type, TypeVar, Union
from pydantic import BaseModel, Field

import core.ai_policy as ai_policy
from core.ollama_health_manager import get_health_manager, MAX_BOUNDED_TIMEOUT_SEC
from core.ollama_provider import (
    OllamaProvider,
    get_ollama_provider,
    is_ollama_available,
    get_available_ollama_models,
    OLLAMA_BASE_URL,
    DEFAULT_STARK_MODEL,
    DEFAULT_TOOL_MODEL,
    DEFAULT_KEEP_ALIVE,
    OLLAMA_READY
)

logger = logging.getLogger("JARVIS.LocalAI")

T = TypeVar("T", bound=BaseModel)

# ==============================================================================
# 1. Pydantic Validation Schemas
# ==============================================================================

class IntentResult(BaseModel):
    intent: str = Field(description="The primary classified intent")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Classification confidence score")
    slots: Dict[str, Any] = Field(default_factory=dict, description="Extracted entity slots")
    raw_query: str = Field(default="", description="Original user query")

class ToolCall(BaseModel):
    tool: str = Field(description="Target tool / capability name")
    action: str = Field(default="execute", description="Action to perform")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")

class ToolArguments(BaseModel):
    tool: str = Field(description="Target tool name")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Key-value arguments for tool")

class PlanStep(BaseModel):
    step_number: int = Field(description="Sequential step order (1-indexed)")
    description: str = Field(description="Natural language summary of the step")
    tool: str = Field(description="Tool to invoke")
    action: str = Field(default="execute", description="Tool action name")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments for tool execution")
    expected_outcome: str = Field(default="", description="Expected result for verification")

class ExecutionResult(BaseModel):
    success: bool = Field(description="Whether execution succeeded")
    tool: str = Field(description="Executed tool")
    action: str = Field(description="Executed action")
    output: Any = Field(default=None, description="Tool output payload")
    error: Optional[str] = Field(default=None, description="Error message if failed")

class VerificationResult(BaseModel):
    verified: bool = Field(description="Whether outcome matches expectation")
    details: str = Field(default="", description="Verification explanation")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Verification confidence")

class FinalResponse(BaseModel):
    text: str = Field(description="Final conversational response to user")
    spoken: bool = Field(default=True, description="Whether response should be spoken via TTS")
    visual_summary: Optional[str] = Field(default=None, description="Optional text for HUD display")

# ==============================================================================
# 2. JSON Repair Utility
# ==============================================================================

def repair_json_string(raw: str) -> Optional[Dict[str, Any]]:
    """Extracts and parses JSON from raw LLM output, handling markdown fences and surrounding text."""
    if not raw or not raw.strip():
        return None
    cleaned = raw.strip()

    # Strip thinking tags if present
    if "</thought>" in cleaned:
        cleaned = cleaned.split("</thought>")[-1].strip()

    # Strip markdown code blocks
    if "```" in cleaned:
        cleaned = re.sub(r"```(?:json)?", "", cleaned)
        cleaned = cleaned.replace("```", "").strip()

    # Try direct parse
    try:
        data = json.loads(cleaned)
        if isinstance(data, (dict, list)):
            return data
    except Exception:
        pass

    # Extract outermost JSON object
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass

    # Extract outermost JSON array
    match_arr = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if match_arr:
        try:
            return json.loads(match_arr.group(0))
        except Exception:
            pass

    return None

# ==============================================================================
# 3. LocalAIProvider Implementation
# ==============================================================================

class LocalAIProvider:
    """
    Authoritative Local AI Provider for JARVIS.
    Wraps local Ollama models (fotiecodes/jarvis:latest & gemma4:12b).
    Strictly 100% offline, zero cloud calls, zero Gemini fallbacks.
    """
    def __init__(self, base_url: str = OLLAMA_BASE_URL):
        self.base_url = base_url
        self._provider: OllamaProvider = get_ollama_provider(base_url)
        self._health_mgr = get_health_manager(base_url)
        logger.info(f"[LocalAIProvider] Ready on {base_url}. Persona: {self._provider.persona_model}, Tool: {self._provider.tool_model}")

    def health_check(self) -> Dict[str, Any]:
        """Returns diagnostic health and model status."""
        return self._provider.health_check()

    def model_info(self) -> Dict[str, Any]:
        """Returns metadata about current local models."""
        health = self.health_check()
        hud = self._health_mgr.get_hud_status()
        return {
            "provider": "Ollama (100% Local)",
            "base_url": self.base_url,
            "persona_model": self._provider.persona_model,
            "tool_model": self._provider.tool_model,
            "available_models": health.get("models", []),
            "status": hud.get("status", "UNKNOWN"),
            "cloud_ai_blocked": not ai_policy.is_cloud_ai_allowed(),
            "latency": hud.get("latency", {})
        }

    def chat(
        self,
        prompt: str,
        context: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.7,
        timeout: float = 15.0,
        model: Optional[str] = None
    ) -> str:
        """Synchronous chat response generation via local Ollama persona model."""
        ai_policy.record_local_ai_call("ollama_chat")
        bounded_timeout = self._health_mgr.get_bounded_timeout(timeout)
        sys_prompt = system or (
            "You are JARVIS, Yajat's practical laptop assistant. "
            "Use short, natural Hinglish unless another language is requested. "
            "No movie roleplay, invented protocols or unrelated coffee jokes. "
            "Never claim an action happened without its verified tool result.\n" + CONVERSATION_STYLE
        )
        if context:
            sys_prompt += f"\nContext:\n{context}"

        t0 = time.time()
        res = self._provider.chat(
            prompt=prompt,
            system_prompt=sys_prompt,
            model=model or self._provider.persona_model,
            temperature=temperature,
            timeout=bounded_timeout
        )
        latency_ms = (time.time() - t0) * 1000.0

        if res.get("success"):
            self._health_mgr.record_latency(latency_ms)
            return res.get("text", "").strip()

        logger.warning(f"[LocalAIProvider] Chat generation warning: {res.get('error')}")
        return res.get("text", "") or f"I encountered a local inference issue: {res.get('error', 'unknown')}"

    def stream_chat(
        self,
        prompt: str,
        context: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.7,
        timeout: float = 15.0,
        model: Optional[str] = None
    ):
        """Streaming token generator via local Ollama persona model."""
        ai_policy.record_local_ai_call("ollama_stream")
        bounded_timeout = self._health_mgr.get_bounded_timeout(timeout)
        sys_prompt = system or CONVERSATION_STYLE
        if context:
            sys_prompt += f"\nContext:\n{context}"

        for chunk in self._provider.chat_stream(
            prompt=prompt,
            system_prompt=sys_prompt,
            model=model or self._provider.persona_model,
            temperature=temperature,
            timeout=bounded_timeout
        ):
            yield chunk

    def _call_ollama_json(self, prompt: str, system: str, model: str, timeout: float) -> str:
        """Direct low-level invocation of Ollama with format='json' for guaranteed schema enforcement."""
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": 256
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
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            return res_json.get("response", "").strip()

    def generate_structured(
        self,
        prompt: str,
        schema_class: Type[T],
        system: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 15.0
    ) -> T:
        """
        Generates structured output strictly adhering to a Pydantic schema class.
        Forces format='json' at the Ollama engine level, applies repair, and 1 retry.
        """
        ai_policy.record_local_ai_call("ollama_structured")
        bounded_timeout = self._health_mgr.get_bounded_timeout(timeout)
        target_model = model or self._provider.persona_model or DEFAULT_STARK_MODEL
        schema_json = json.dumps(schema_class.model_json_schema())

        sys_prompt = (
            system or
            "You are the structured reasoning engine of JARVIS. Output ONLY a valid JSON object strictly matching this schema."
        )
        sys_prompt += f"\nREQUIRED JSON SCHEMA:\n{schema_json}\nCRITICAL: Output ONLY the valid JSON object, no thinking, no markdown, no other keys."

        t0 = time.time()
        try:
            raw_text = self._call_ollama_json(prompt, sys_prompt, target_model, bounded_timeout)
        except Exception as e:
            logger.warning(f"[LocalAIProvider] Primary structured call failed: {e}")
            raw_text = ""

        latency_ms = (time.time() - t0) * 1000.0
        parsed = repair_json_string(raw_text)

        if parsed is not None:
            try:
                if isinstance(parsed, dict):
                    self._health_mgr.record_latency(latency_ms)
                    return schema_class.model_validate(parsed)
            except Exception as val_err:
                logger.debug(f"[LocalAIProvider] Schema validation failed on attempt 1: {val_err}")

        # Attempt 2: Constrained 1-retry repair prompt
        logger.info("[LocalAIProvider] Attempting 1-retry JSON repair prompt with local model...")
        retry_prompt = (
            f"Fix this invalid JSON response so it strictly matches the schema {schema_json}:\n"
            f"{raw_text}\n"
            f"Output ONLY the corrected raw JSON object."
        )
        try:
            raw_retry = self._call_ollama_json(retry_prompt, "You are a JSON fixer. Return ONLY the valid JSON object.", target_model, bounded_timeout)
            parsed_retry = repair_json_string(raw_retry)
            if parsed_retry is not None and isinstance(parsed_retry, dict):
                self._health_mgr.record_latency((time.time() - t0) * 1000.0)
                return schema_class.model_validate(parsed_retry)
        except Exception as e:
            logger.error(f"[LocalAIProvider] Schema validation failed after repair retry: {e}")

        # Safe fallback instance if all else fails (never crash, never cloud)
        try:
            return schema_class.model_validate({})
        except Exception:
            raise ValueError(f"Failed to generate valid structured output for schema {schema_class.__name__}. Raw: {raw_text[:200]}")

    def classify_intent(self, user_input: str, available_intents: Optional[List[str]] = None) -> IntentResult:
        """Classifies user query intent using local Ollama model."""
        intents_str = ", ".join(available_intents) if available_intents else "CHAT, SYSTEM_COMMAND, APP_CONTROL, WHATSAPP, WEB_SEARCH, SCREEN_ANALYSIS, CODE, REASONING"
        prompt = (
            f"Classify the user intent for query: \"{user_input}\"\n"
            f"Available intents: [{intents_str}]\n"
            f"Format response as: {{\"intent\": \"<INTENT>\", \"confidence\": 0.95, \"slots\": {{}}, \"raw_query\": \"{user_input}\"}}"
        )
        try:
            return self.generate_structured(prompt, IntentResult)
        except Exception as e:
            logger.warning(f"[LocalAIProvider] Local intent classification fallback: {e}")
            return IntentResult(intent="CHAT", confidence=0.5, raw_query=user_input)

    def plan(self, user_goal: str, available_tools: Optional[List[str]] = None) -> List[PlanStep]:
        """Generates an atomic multi-step plan using local Ollama model."""
        tools_str = ", ".join(available_tools) if available_tools else "system_control, app_launcher, whatsapp_desktop, web_search, file_operations, code_agent"
        example_json = '{\"steps\": [{\"step_number\": 1, \"description\": \"Open application\", \"tool\": \"app_launcher\", \"action\": \"open\", \"arguments\": {\"target\": \"app\"}, \"expected_outcome\": \"App is open\"}]}'
        prompt = (
            f"Generate an atomic execution plan for user goal: \"{user_goal}\"\n"
            f"Available tools: [{tools_str}]\n"
            f"Provide sequential steps. Example format: {example_json}"
        )

        class PlanContainer(BaseModel):
            steps: List[PlanStep] = Field(default_factory=list)

        try:
            container = self.generate_structured(prompt, PlanContainer)
            if container.steps:
                return container.steps
            return [
                PlanStep(
                    step_number=1,
                    description=f"Execute goal: {user_goal}",
                    tool="app_launcher",
                    action="execute",
                    arguments={"query": user_goal}
                )
            ]
        except Exception as e:
            logger.warning(f"[LocalAIProvider] Plan generation fallback: {e}")
            return [
                PlanStep(
                    step_number=1,
                    description=f"Execute goal directly: {user_goal}",
                    tool="app_launcher",
                    action="execute",
                    arguments={"query": user_goal}
                )
            ]

    def summarize(self, text: str, max_words: int = 50) -> str:
        """Summarizes text using local Ollama model in max_words."""
        prompt = f"Summarize the following text in under {max_words} words. Be direct and factual:\n\n{text}"
        return self.chat(prompt, system="You are a concise summarizer.", temperature=0.3)

    def extract_action(
        self,
        user_input: str,
        context: Optional[str] = None,
        allowed_tools: Optional[List[str]] = None
    ) -> ToolCall:
        """Extracts a structured tool call from user input."""
        tools_str = ", ".join(allowed_tools) if allowed_tools else "app_launcher, whatsapp_desktop, system_volume, web_search, screen_capture"
        prompt = (
            f"Extract the best tool call for request: \"{user_input}\"\n"
            f"Allowed tools: [{tools_str}]\n"
            f"Context: {context or 'None'}\n"
            f"Format response as: {{\"tool\": \"<tool_name>\", \"action\": \"<action>\", \"parameters\": {{}}}}"
        )
        try:
            return self.generate_structured(prompt, ToolCall)
        except Exception as e:
            logger.warning(f"[LocalAIProvider] Action extraction fallback: {e}")
            return ToolCall(tool="app_launcher", action="open", parameters={"target": user_input})


# ==============================================================================
# 4. Thread-Safe Singleton Accessor
# ==============================================================================

_LOCAL_AI_LOCK = threading.Lock()
_GLOBAL_LOCAL_AI_INSTANCE: Optional[LocalAIProvider] = None

def get_local_ai_provider(base_url: str = OLLAMA_BASE_URL) -> LocalAIProvider:
    """Thread-safe singleton accessor for LocalAIProvider."""
    global _GLOBAL_LOCAL_AI_INSTANCE
    with _LOCAL_AI_LOCK:
        if _GLOBAL_LOCAL_AI_INSTANCE is None:
            _GLOBAL_LOCAL_AI_INSTANCE = LocalAIProvider(base_url=base_url)
        return _GLOBAL_LOCAL_AI_INSTANCE
