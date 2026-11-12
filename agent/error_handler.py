import json
import re
import sys
import time
import logging
from pathlib import Path
from enum import Enum
from typing import Dict, Any, Optional

logger = logging.getLogger("JARVIS.ErrorHandler")


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR        = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

# Natural error messages for user-facing responses
NATURAL_ERROR_MESSAGES: Dict[str, str] = {
    "ConnectionError": "Boss, network connection problem hai. Internet check karo.",
    "TimeoutError": "Boss, response aane mein zyada time lag raha hai. Fir se try karta hoon.",
    "FileNotFoundError": "Boss, wo file mil nahi rahi. Path check karo.",
    "PermissionError": "Boss, permission denied. Admin access required ho sakta hai.",
    "ModuleNotFoundError": "Boss, ek required library install nahi hai.",
    "json.JSONDecodeError": "Boss, response format mein problem thi. Fir se try karta hoon.",
    "WebSocketError": "Boss, Gemini connection drop ho gaya. Reconnect kar raha hoon.",
    "OllamaError": "Boss, local AI server respond nahi kar raha. Ollama running check karo.",
    "ChromeError": "Boss, Chrome response nahi de raha. Chrome restart karna padega.",
    "default": "Boss, ek unexpected issue aaya hai. Working on a fix.",
}


class CircuitBreaker:
    """Simple circuit breaker to prevent repeated failing calls."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self._failure_count: int = 0
        self._failure_threshold: int = failure_threshold
        self._recovery_timeout: float = recovery_timeout
        self._last_failure_time: float = 0.0
        self._state: str = "CLOSED"  # CLOSED | OPEN | HALF_OPEN

    def record_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self._failure_threshold:
            self._state = "OPEN"
            logger.warning(f"[CircuitBreaker] OPEN — {self._failure_count} consecutive failures.")

    def record_success(self):
        self._failure_count = 0
        self._state = "CLOSED"

    def is_open(self) -> bool:
        if self._state == "OPEN":
            if time.time() - self._last_failure_time > self._recovery_timeout:
                self._state = "HALF_OPEN"
                logger.info("[CircuitBreaker] HALF_OPEN — testing recovery.")
                return False
            return True
        return False

    def get_state(self) -> Dict[str, Any]:
        return {
            "state": self._state,
            "failure_count": self._failure_count,
            "last_failure": self._last_failure_time,
        }


# Global circuit breakers per subsystem
_CIRCUIT_BREAKERS: Dict[str, CircuitBreaker] = {}

def get_circuit_breaker(subsystem: str = "default") -> CircuitBreaker:
    if subsystem not in _CIRCUIT_BREAKERS:
        _CIRCUIT_BREAKERS[subsystem] = CircuitBreaker()
    return _CIRCUIT_BREAKERS[subsystem]


def get_natural_error_message(error: Exception) -> str:
    """Convert a Python exception into a natural, user-friendly message."""
    error_type = type(error).__name__
    msg = NATURAL_ERROR_MESSAGES.get(error_type)
    if msg:
        return msg
    error_str = str(error).lower()
    if "connection" in error_str or "network" in error_str:
        return NATURAL_ERROR_MESSAGES["ConnectionError"]
    if "timeout" in error_str:
        return NATURAL_ERROR_MESSAGES["TimeoutError"]
    if "permission" in error_str:
        return NATURAL_ERROR_MESSAGES["PermissionError"]
    if "chrome" in error_str:
        return NATURAL_ERROR_MESSAGES["ChromeError"]
    if "ollama" in error_str:
        return NATURAL_ERROR_MESSAGES["OllamaError"]
    return NATURAL_ERROR_MESSAGES["default"]


class ErrorDecision(Enum):
    RETRY       = "retry"      
    SKIP        = "skip"       
    REPLAN      = "replan"     
    ABORT       = "abort"    


ERROR_ANALYST_PROMPT = """You are the error recovery module of JARVIS AI assistant.

A task step has failed. Analyze the error and decide what to do.

DECISIONS:
- retry   : Transient error (network timeout, temporary file lock, race condition).
             The same step can succeed if tried again.
- skip    : This step is not critical and the task can succeed without it.
- replan  : The approach was wrong. A different tool or method should be tried.
- abort   : The task is fundamentally impossible or unsafe to continue.

Also provide:
- A brief explanation of WHY it failed (1 sentence)
- A fix suggestion if decision is replan (what to try instead)
- Max retries: how many times to retry if decision is retry (1 or 2)

Return ONLY valid JSON:
{
  "decision": "retry|skip|replan|abort",
  "reason": "why it failed",
  "fix_suggestion": "what to try instead (for replan)",
  "max_retries": 1,
  "user_message": "Short message to tell the user (max 15 words)"
}
"""


def _get_api_key() -> str:
    from config import get_api_key
    return get_api_key("gemini_api_key")


def analyze_error(
    step: dict,
    error: str,
    attempt: int = 1,
    max_attempts: int = 2
) -> dict:
    import google.generativeai as genai

    if attempt >= max_attempts:
        print(f"[ErrorHandler] ⚠️ Max attempts reached for step {step.get('step')} — forcing replan")
        return {
            "decision":      ErrorDecision.REPLAN,
            "reason":        f"Failed {attempt} times: {error[:100]}",
            "fix_suggestion": "Try a completely different approach or tool",
            "max_retries":   0,
            "user_message":  "Trying a different approach, sir."
        }

    genai.configure(api_key=_get_api_key())
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=ERROR_ANALYST_PROMPT
    )


    prompt = f"""Failed step:
Tool: {step.get('tool')}
Description: {step.get('description')}
Parameters: {json.dumps(step.get('parameters', {}), indent=2)}
Critical: {step.get('critical', False)}

Error:
{error[:500]}

Attempt number: {attempt}"""

    try:
        response = model.generate_content(prompt)
        text     = response.text.strip()
        text     = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()

        result = json.loads(text)
        decision_str = result.get("decision", "replan").lower()
        decision_map = {
            "retry":  ErrorDecision.RETRY,
            "skip":   ErrorDecision.SKIP,
            "replan": ErrorDecision.REPLAN,
            "abort":  ErrorDecision.ABORT,
        }
        result["decision"] = decision_map.get(decision_str, ErrorDecision.REPLAN)


        if step.get("critical") and result["decision"] == ErrorDecision.SKIP:
            result["decision"]     = ErrorDecision.REPLAN
            result["user_message"] = "This step is critical — finding alternative approach, sir."

        print(f"[ErrorHandler] Decision: {result['decision'].value} — {result.get('reason', '')}")
        return result

    except Exception as e:
        print(f"[ErrorHandler] ⚠️ Analysis failed: {e} — defaulting to replan")
        return {
            "decision":       ErrorDecision.REPLAN,
            "reason":         str(e),
            "fix_suggestion": "Try alternative approach",
            "max_retries":    1,
            "user_message":   "Encountered an issue, adjusting approach, sir."
        }


def generate_fix(step: dict, error: str, fix_suggestion: str) -> dict:
    """
    When decision is REPLAN and a fix suggestion exists,
    generates a replacement step using generated_code as fallback.

    Returns a modified step dict.
    """
    import google.generativeai as genai

    genai.configure(api_key=_get_api_key())
    model = genai.GenerativeModel(model_name="gemini-3.5-flash-lite")

    prompt = f"""A task step failed. Generate a replacement step.

Original step:
Tool: {step.get('tool')}
Description: {step.get('description')}
Parameters: {json.dumps(step.get('parameters', {}), indent=2)}

Error: {error[:300]}
Fix suggestion: {fix_suggestion}

Write a Python script that accomplishes the same goal differently.
Return ONLY the Python code, no explanation."""

    try:
        response = model.generate_content(prompt)
        code = response.text.strip()
        code = re.sub(r"```(?:python)?", "", code).strip().rstrip("`").strip()

        return {
            "step":        step.get("step"),
            "tool":        "code_helper",
            "description": f"Auto-fix for: {step.get('description')}",
            "parameters": {
                "action":      "run",
                "description": fix_suggestion,
                "code":        code,
                "language":    "python"
            },
            "depends_on": step.get("depends_on", []),
            "critical":   step.get("critical", False)
        }

    except Exception as e:
        print(f"[ErrorHandler] ⚠️ Fix generation failed: {e}")
        return {
            "step":        step.get("step"),
            "tool":        "generated_code",
            "description": f"Fallback for: {step.get('description')}",
            "parameters":  {"description": step.get("description", "")},
            "depends_on":  step.get("depends_on", []),
            "critical":    step.get("critical", False)
        }