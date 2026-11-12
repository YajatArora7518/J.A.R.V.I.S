"""
agent/emotional_context.py
Lightweight Conversational Context Detector for J.A.R.V.I.S.

Detects emotional/conversational states from interaction patterns:
- States: neutral, happy, excited, frustrated, sad, stressed, tired, quiet, confused, angry, busy
- Detects from: tone keywords, repeated failures, interaction patterns
- Cooldowns to prevent over-asking
- Respects dismissal ("chhod", "leave it")
- Never diagnoses mental health conditions
"""

import time
import logging
import re
from typing import Dict, Any, Optional, List

logger = logging.getLogger("JARVIS.EmotionalContext")

# Keyword → state mapping
STATE_KEYWORDS = {
    "happy": ["awesome", "great", "amazing", "perfect", "love it", "nice", "khush", "maza aa gaya", "bahut accha", "excellent", "fantastic"],
    "excited": ["wow", "yay", "omg", "let's go", "finally", "exciting", "can't wait", "hype"],
    "frustrated": ["ugh", "not working", "kaam nahi kar raha", "broken", "hate this", "stupid", "annoying", "irritating", "again", "fir se"],
    "sad": ["sad", "upset", "lonely", "miss you", "dukhi", "udaas", "mood off", "mann nahi", "मन उदास", "मूड ऑफ"],
    "stressed": ["stressed", "deadline", "tension", "pressure", "overwhelmed", "too much", "bahut kaam"],
    "tired": ["tired", "thak gaya", "sleepy", "exhausted", "neend", "sone do", "goodnight"],
    "confused": ["confused", "samajh nahi aa raha", "kya karu", "help", "don't understand", "what should i", "kaise karu"],
    "angry": ["angry", "gussa", "pissed", "what the", "wtf", "stupid"],
    "busy": ["busy", "not now", "baad mein", "later", "abhi nahi", "occupied"],
    "quiet": ["hmm", "ok", "k", "fine", "thik hai", "acha"],
}

DISMISSAL_WORDS = ["chhod", "chhodo", "leave it", "jane do", "bas", "enough", "stop asking", "rehne do"]

def _contains_phrase(text, phrase):
    return bool(re.search(r'(?<!\w)' + re.escape(phrase) + r'(?!\w)', text))


class EmotionalContext:
    """Tracks conversational emotional context without diagnosis."""

    def __init__(self):
        self._current_state: str = "neutral"
        self._state_confidence: float = 0.0
        self._state_history: List[Dict[str, Any]] = []
        self._last_state_change: float = 0.0
        self._consecutive_failures: int = 0
        self._cooldown_until: float = 0.0  # Don't re-detect until this time
        self._dismissed: bool = False

    def detect_state(self, text: str, was_failure: bool = False) -> str:
        """Analyze text and interaction outcome to update emotional state."""
        now = time.time()

        # Respect cooldown
        if now < self._cooldown_until:
            return self._current_state

        # Respect dismissal
        lower = (text or "").lower().strip()
        if any(_contains_phrase(lower, w) for w in DISMISSAL_WORDS):
            self._dismissed = True
            self._cooldown_until = now + 300  # 5 min cooldown
            return self._current_state

        if self._dismissed and (now - self._last_state_change) < 300:
            return self._current_state

        self._dismissed = False

        # Track failures
        if was_failure:
            self._consecutive_failures += 1
        else:
            self._consecutive_failures = max(0, self._consecutive_failures - 1)

        # Detect from repeated failures
        if self._consecutive_failures >= 3:
            new_state = "frustrated"
            confidence = min(1.0, self._consecutive_failures * 0.25)
        else:
            # Detect from keywords
            new_state = "neutral"
            confidence = 0.0
            for state, keywords in STATE_KEYWORDS.items():
                matches = sum(1 for k in keywords if _contains_phrase(lower, k))
                if matches > 0:
                    state_conf = min(1.0, matches * 0.4)
                    if state_conf > confidence:
                        new_state = state
                        confidence = state_conf

        # Only update if confident enough
        if confidence >= 0.3 and new_state != self._current_state:
            old = self._current_state
            self._current_state = new_state
            self._state_confidence = confidence
            self._last_state_change = now
            self._state_history.append({
                "from": old,
                "to": new_state,
                "confidence": confidence,
                "timestamp": now,
                "trigger": lower[:60],
            })
            # Keep only last 20 transitions
            self._state_history = self._state_history[-20:]
            logger.info(f"[EmotionalContext] State: {old} → {new_state} (conf={confidence:.2f})")

        return self._current_state

    def get_state(self) -> Dict[str, Any]:
        """Return current emotional context state."""
        return {
            "state": self._current_state,
            "confidence": self._state_confidence,
            "last_change": self._last_state_change,
            "consecutive_failures": self._consecutive_failures,
        }

    def get_response_modifier(self) -> str:
        """Return a tone modifier hint for response generation based on current state."""
        if time.time() - self._last_state_change > 1200:
            return ''
        modifiers = {
            "neutral": "",
            "happy": "The user's words suggest positive energy. Match it without claiming to know their mood.",
            "excited": "The user's words suggest excitement. Be enthusiastic without claiming certainty about their mood.",
            "frustrated": "The user seems frustrated. Be patient, empathetic, and solution-focused. Avoid long explanations.",
            "sad": "The user's words suggest they may be down. Ask gently; no roasting or diagnosis.",
            "stressed": "The user's words suggest stress. Listen first; be practical, gentle and avoid roasting.",
            "tired": "The user seems tired. Keep responses short and don't suggest unnecessary tasks.",
            "confused": "The user seems confused. Explain clearly with simple steps.",
            "angry": "The user seems upset. Be calm, direct, and helpful. Don't be defensive.",
            "busy": "The user is busy. Be extremely concise.",
            "quiet": "The user is being brief. Match their energy — short responses only.",
        }
        return modifiers.get(self._current_state, "")

    def reset(self):
        """Reset emotional context."""
        self._current_state = "neutral"
        self._state_confidence = 0.0
        self._consecutive_failures = 0
        self._dismissed = False
        self._cooldown_until = 0.0
        self._last_state_change = 0.0


# Global singleton
_EMOTIONAL_CONTEXT: Optional[EmotionalContext] = None

def get_emotional_context() -> EmotionalContext:
    global _EMOTIONAL_CONTEXT
    if _EMOTIONAL_CONTEXT is None:
        _EMOTIONAL_CONTEXT = EmotionalContext()
    return _EMOTIONAL_CONTEXT
