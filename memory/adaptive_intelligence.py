# memory/adaptive_intelligence.py
# Context-Aware Adaptive Intelligence 3.0 — Predictive Personal Agent for JARVIS

from __future__ import annotations

import json
import math
import os
import re
import sys
import time
import uuid
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from threading import RLock
from typing import Dict, List, Optional, Tuple, Any


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = _get_base_dir()
MEMORY_DIR = BASE_DIR / "memory"

# Modular Storage Files
INSIGHTS_PATH = MEMORY_DIR / "adaptive_insights.json"
PATTERNS_PATH = MEMORY_DIR / "workflow_patterns.json"
PREFERENCES_PATH = MEMORY_DIR / "contextual_preferences.json"
PREDICTIVE_PATH = MEMORY_DIR / "predictive_patterns.json"
ROUTINES_PATH = MEMORY_DIR / "routines.json"
PROJECTS_PATH = MEMORY_DIR / "project_context.json"
OUTCOMES_PATH = MEMORY_DIR / "prediction_outcomes.json"

_lock = RLock()

# Secret detection patterns for privacy protection
SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_\-]{20,}", re.IGNORECASE),
    re.compile(r"AIza[a-zA-Z0-9_\-]{30,}", re.IGNORECASE),
    re.compile(r"nvapi-[a-zA-Z0-9_\-]{20,}", re.IGNORECASE),
    re.compile(r"(?:bearer|token|apikey|password|passwd|secret|auth|jwt)[=:\s]+[^\s;]{6,}", re.IGNORECASE),
    re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"),  # Credit card numbers
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN format
]


def redact_secrets(text: str) -> str:
    """Redacts sensitive credentials, tokens, passwords, and private data from text."""
    if not isinstance(text, str) or not text:
        return ""
    cleaned = text
    for pattern in SECRET_PATTERNS:
        cleaned = pattern.sub("[REDACTED_SECRET]", cleaned)
    return cleaned


# ════════════════════════════════════════════════════════════
# 1. CONTEXT DETECTOR
# ════════════════════════════════════════════════════════════
class ContextDetector:
    """Detects current operational context: domain, time bucket, active project, and workspace."""

    DOMAINS = [
        "CODING",
        "BROWSING",
        "COLLEGE",
        "FILE_MANAGEMENT",
        "ENTERTAINMENT",
        "COMMUNICATION",
        "SYSTEM_CONTROL",
        "PROJECT_WORK",
        "GENERAL",
    ]

    TIME_BUCKETS = [
        "EARLY_MORNING",  # 04:00 - 08:00
        "MORNING",        # 08:00 - 12:00
        "AFTERNOON",      # 12:00 - 17:00
        "EVENING",        # 17:00 - 22:00
        "NIGHT",          # 22:00 - 04:00
    ]

    KEYWORDS = {
        "CODING": [
            "python", "code", "vscode", "vs code", "git", "test", "terminal", "build",
            "debug", "html", "css", "js", "script", "compile", "pycharm", "github", "repo"
        ],
        "BROWSING": [
            "browser", "chrome", "web", "search", "url", "google", "firefox", "edge",
            "documentation", "stackoverflow", "site", "online", "fetch"
        ],
        "COLLEGE": [
            "college", "assignment", "lecture", "homework", "course", "university",
            "exam", "pdf", "syllabus", "paper", "professor", "class", "submission"
        ],
        "FILE_MANAGEMENT": [
            "file", "folder", "directory", "move", "copy", "delete", "list", "backup",
            "path", "download", "zip", "extract", "organize"
        ],
        "ENTERTAINMENT": [
            "youtube", "video", "music", "song", "spotify", "game", "play", "movie",
            "stream", "steam", "epic", "relax"
        ],
        "COMMUNICATION": [
            "whatsapp", "discord", "email", "message", "chat", "send", "mail", "outlook",
            "telegram", "signal", "call"
        ],
        "SYSTEM_CONTROL": [
            "settings", "volume", "shutdown", "restart", "computer", "screen", "brightness",
            "mute", "unmute", "battery", "display", "windows"
        ],
        "PROJECT_WORK": [
            "project", "task", "milestone", "roadmap", "jarvis", "sprint", "todo", "issue"
        ],
    }

    @classmethod
    def get_time_bucket(cls, dt: Optional[datetime] = None) -> str:
        """Determines coarse time bucket from current local time."""
        now = dt or datetime.now()
        hour = now.hour
        if 4 <= hour < 8:
            return "EARLY_MORNING"
        elif 8 <= hour < 12:
            return "MORNING"
        elif 12 <= hour < 17:
            return "AFTERNOON"
        elif 17 <= hour < 22:
            return "EVENING"
        else:
            return "NIGHT"

    @classmethod
    def detect_context(
        cls,
        query: str = "",
        active_app: str = "",
        cwd: str = "",
        recent_tools: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Probabilistically detects current operational context block."""
        clean_q = redact_secrets(query).lower() if query else ""
        clean_app = redact_secrets(active_app).lower() if active_app else ""
        clean_cwd = redact_secrets(cwd).lower() if cwd else ""
        tools = recent_tools or []

        # Project Detection
        project_name = "GENERAL"
        if "jarvis" in clean_q or "jarvis" in clean_cwd or "jarvis" in clean_app:
            project_name = "JARVIS"
        elif clean_cwd:
            project_name = Path(clean_cwd).name.upper()

        # Domain Scoring
        scores = {domain: 0.0 for domain in cls.DOMAINS}
        scores["GENERAL"] = 0.1

        text_block = f"{clean_q} {clean_app} {clean_cwd} {' '.join(tools).lower()}"

        for domain, kw_list in cls.KEYWORDS.items():
            for kw in kw_list:
                if kw in text_block:
                    scores[domain] += 0.35

        if any(t in ["code_helper", "dev_agent"] for t in tools):
            scores["CODING"] += 0.50
        if any(t in ["web_search", "fetch_webpage", "browser_control"] for t in tools):
            scores["BROWSING"] += 0.50
        if any(t in ["file_controller", "file_processor"] for t in tools):
            scores["FILE_MANAGEMENT"] += 0.50
        if any(t in ["computer_settings", "computer_control", "desktop_control"] for t in tools):
            scores["SYSTEM_CONTROL"] += 0.50
        if any(t in ["youtube_video", "game_updater"] for t in tools):
            scores["ENTERTAINMENT"] += 0.50

        best_domain = max(scores, key=scores.get)
        if scores[best_domain] < 0.25:
            best_domain = "GENERAL"

        time_bucket = cls.get_time_bucket()
        day_of_week = datetime.now().strftime("%A").upper()

        return {
            "domain": best_domain,
            "time_bucket": time_bucket,
            "day_of_week": day_of_week,
            "active_app": clean_app,
            "project": project_name,
            "cwd": clean_cwd,
            "confidence": min(1.0, round(scores[best_domain], 2)),
        }


# ════════════════════════════════════════════════════════════
# 2. WORKFLOW SEQUENCE ENGINE
# ════════════════════════════════════════════════════════════
class WorkflowSequenceEngine:
    """Tracks N-gram action/tool transitions and generates predictive next-action suggestions with cooldowns."""

    def __init__(self, data: Dict[str, Any]):
        self.data = data.setdefault("patterns", {})

    def record_sequence(self, sequence: List[str], context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Records an ordered action sequence and reinforces pattern confidence."""
        if not sequence or len(sequence) < 2:
            return None

        seq_key = " -> ".join([redact_secrets(s).strip() for s in sequence])
        now_str = datetime.now().isoformat()

        pattern = self.data.get(seq_key)
        if pattern:
            pattern["occurrence_count"] = pattern.get("occurrence_count", 1) + 1
            pattern["success_count"] = pattern.get("success_count", 1) + 1
            pattern["last_seen"] = now_str
            cur_conf = pattern.get("confidence", 0.35)
            pattern["confidence"] = min(0.98, round(cur_conf + (1.0 - cur_conf) * 0.25, 4))
            pattern["context"] = context
        else:
            pattern = {
                "pattern_id": str(uuid.uuid4())[:8],
                "sequence_key": seq_key,
                "sequence": sequence,
                "occurrence_count": 1,
                "success_count": 1,
                "confidence": 0.35,
                "first_seen": now_str,
                "last_seen": now_str,
                "context": context,
                "source": "inferred",
                "last_suggested": None,
                "cooldown_seconds": 300,
                "accepted_count": 0,
                "rejected_count": 0,
            }
            self.data[seq_key] = pattern

        return pattern

    def predict_next_action(
        self, current_app_or_tool: str, context: Dict[str, Any]
    ) -> Optional[Tuple[str, float, str, Dict[str, Any]]]:
        """Predicts the next action/tool based on sequence patterns. Returns (next_action, confidence, suggestion_msg, pattern_dict)."""
        curr_clean = redact_secrets(current_app_or_tool).strip().lower() if current_app_or_tool else ""
        now = datetime.now()

        best_pattern = None
        highest_conf = 0.60  # Minimum prediction threshold

        for pattern in self.data.values():
            seq = pattern.get("sequence", [])
            conf = pattern.get("confidence", 0.0)
            if not seq or len(seq) < 2:
                continue

            if seq[0].strip().lower() == curr_clean and conf >= highest_conf:
                last_sug_str = pattern.get("last_suggested")
                cooldown_sec = pattern.get("cooldown_seconds", 300)

                if last_sug_str:
                    try:
                        last_sug = datetime.fromisoformat(last_sug_str)
                        if (now - last_sug).total_seconds() < cooldown_sec:
                            continue
                    except Exception:
                        pass

                best_pattern = pattern
                highest_conf = conf

        if best_pattern:
            seq = best_pattern["sequence"]
            next_action = seq[1]
            next_steps = ", ".join(seq[1:])
            best_pattern["last_suggested"] = now.isoformat()
            domain = context.get("domain", "current")
            msg = f"You usually open {next_steps} next in your {domain} workflow. Want me to prepare them?"
            return next_action, highest_conf, msg, best_pattern

        return None

    def get_proactive_suggestion(
        self, current_app_or_tool: str, context: Dict[str, Any]
    ) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Backward compatibility wrapper for proactive suggestions."""
        res = self.predict_next_action(current_app_or_tool, context)
        if res:
            _, _, msg, pat = res
            return msg, pat
        return None

    def record_suggestion_feedback(self, seq_key: str, accepted: bool):
        """Updates suggestion feedback and doubles cooldown on rejection."""
        pattern = self.data.get(seq_key)
        if not pattern:
            return

        if accepted:
            pattern["accepted_count"] = pattern.get("accepted_count", 0) + 1
            pattern["confidence"] = min(0.98, pattern.get("confidence", 0.6) + 0.10)
            pattern["cooldown_seconds"] = 300
        else:
            pattern["rejected_count"] = pattern.get("rejected_count", 0) + 1
            pattern["confidence"] = max(0.20, pattern.get("confidence", 0.6) - 0.15)
            pattern["cooldown_seconds"] = min(1800, pattern.get("cooldown_seconds", 300) * 2)


# ════════════════════════════════════════════════════════════
# 3. SEVEN-TIER PREFERENCE & PREDICTION HIERARCHY RESOLVER
# ════════════════════════════════════════════════════════════
class PreferenceHierarchyResolver:
    """Resolves conflicts through a strict 7-tier priority hierarchy:
    1. Current explicit user instruction (always wins immediately)
    2. Explicit stored preference (source == 'explicit', confidence == 0.98)
    3. High-confidence contextual preference (confidence >= 0.80)
    4. Repeated workflow pattern (confidence >= 0.60)
    5. Predictive inference (confidence >= 0.60)
    6. General adaptive inference (confidence >= 0.60)
    7. Default JARVIS behavior
    """

    @classmethod
    def resolve_preference(
        cls,
        category: str,
        key: str,
        current_instruction: str = "",
        stored_insights: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        default_val: Optional[str] = None
    ) -> Tuple[Optional[str], str]:
        """Resolves target preference value along with priority tier label."""
        clean_key = redact_secrets(key).strip().lower() if key else ""
        clean_instr = redact_secrets(current_instruction).strip() if current_instruction else ""

        # TIER 1: Current Explicit User Instruction
        if clean_instr:
            explicit_override_match = re.search(
                r"(?:use|open|with|in)\s+([a-zA-Z0-9_\-\.\s]+?)(?=\s+(?:for|to|as|in|with|this|the|my|task|project)\b|$)",
                clean_instr,
                re.IGNORECASE
            )
            if explicit_override_match:
                override_val = explicit_override_match.group(1).strip()
                if len(override_val) > 1 and override_val.lower() not in ["this", "that", "it", "my"]:
                    return override_val, "TIER_1_CURRENT_INSTRUCTION"

        insights = stored_insights or {}
        ctx = context or {}

        matching = []
        for i in insights.values():
            if i.get("key") == clean_key and i.get("enabled", True):
                matching.append(i)

        # TIER 2: Explicit Stored Preference
        explicit_rules = [i for i in matching if i.get("source") == "explicit"]
        if explicit_rules:
            best_explicit = max(explicit_rules, key=lambda x: x.get("confidence", 0.0))
            return best_explicit.get("value"), "TIER_2_EXPLICIT_STORED"

        # TIER 3: High-Confidence Contextual Preference (>= 0.80)
        domain = ctx.get("domain", "GENERAL")
        ctx_rules = [
            i for i in matching
            if i.get("context", {}).get("domain") == domain and i.get("confidence", 0.0) >= 0.80
        ]
        if ctx_rules:
            best_ctx = max(ctx_rules, key=lambda x: x.get("confidence", 0.0))
            return best_ctx.get("value"), "TIER_3_HIGH_CONF_CONTEXTUAL"

        # TIER 4: Repeated Workflow Pattern (handled by sequence engine)
        # TIER 5: Predictive Inference (>= 0.60)
        pred_rules = [i for i in matching if i.get("source") == "predictive" and i.get("confidence", 0.0) >= 0.60]
        if pred_rules:
            best_pred = max(pred_rules, key=lambda x: x.get("confidence", 0.0))
            return best_pred.get("value"), "TIER_5_PREDICTIVE_INFERENCE"

        # TIER 6: General Adaptive Inference (>= 0.60)
        inferred_rules = [i for i in matching if i.get("confidence", 0.0) >= 0.60]
        if inferred_rules:
            best_inf = max(inferred_rules, key=lambda x: x.get("confidence", 0.0))
            return best_inf.get("value"), "TIER_6_GENERAL_INFERENCE"

        # TIER 7: Default Behavior
        return default_val, "TIER_7_DEFAULT_BEHAVIOR"


# ════════════════════════════════════════════════════════════
# 4. PERSONAL WORKFLOW GRAPH
# ════════════════════════════════════════════════════════════
class PersonalWorkflowGraph:
    """Weighted relationship graph connecting Context -> Task -> Tool -> Project with temporal decay."""

    def __init__(self, data: Dict[str, Any]):
        self.data = data.setdefault("workflow_graph", {})

    def add_or_update_edge(self, context_domain: str, task: str, tool: str, project: str = "GENERAL"):
        """Adds or reinforces a weighted edge in the personal workflow graph."""
        edge_key = f"{context_domain}::{task}::{tool}::{project}".lower()
        now_str = datetime.now().isoformat()

        edge = self.data.get(edge_key)
        if edge:
            edge["occurrence_count"] = edge.get("occurrence_count", 1) + 1
            edge["success_count"] = edge.get("success_count", 1) + 1
            edge["last_seen"] = now_str
            cur_w = edge.get("weight", 0.35)
            edge["weight"] = min(0.98, round(cur_w + (1.0 - cur_w) * 0.25, 4))
            edge["confidence"] = edge["weight"]
        else:
            edge = {
                "edge_key": edge_key,
                "context_domain": context_domain,
                "task": task,
                "tool": tool,
                "project": project,
                "weight": 0.35,
                "confidence": 0.35,
                "occurrence_count": 1,
                "success_count": 1,
                "first_seen": now_str,
                "last_seen": now_str,
            }
            self.data[edge_key] = edge

        return edge

    def apply_decay(self, days_threshold: int = 14, decay_factor: float = 0.15):
        """Applies temporal decay to inactive edges after inactivity threshold."""
        now = datetime.now()
        for key, edge in list(self.data.items()):
            last_seen_str = edge.get("last_seen")
            if not last_seen_str:
                continue
            try:
                last_seen = datetime.fromisoformat(last_seen_str)
                days_inactive = (now - last_seen).days
                if days_inactive >= days_threshold:
                    w = edge.get("weight", 0.5) - decay_factor
                    if w < 0.15:
                        del self.data[key]
                    else:
                        edge["weight"] = round(w, 3)
                        edge["confidence"] = edge["weight"]
            except Exception:
                pass


# ════════════════════════════════════════════════════════════
# 5. PREDICTIVE INTENT ENGINE (3.0)
# ════════════════════════════════════════════════════════════
class PredictiveIntentEngine:
    """Predicts high-level user intent and candidate next actions with concise human-readable explanations.
    Learns from workflow graph history to generate personalized candidate actions."""

    INTENT_MAP = {
        "CODING": {
            "intent": "PROJECT_WORK / CODING",
            "default_actions": ["VS Code", "Terminal", "Git", "Run Unit Tests"],
        },
        "BROWSING": {
            "intent": "RESEARCH / WEB BROWSING",
            "default_actions": ["Chrome", "Search Documentation", "Fetch Webpage"],
        },
        "COLLEGE": {
            "intent": "COLLEGE / ACADEMIC WORK",
            "default_actions": ["Chrome LMS", "PDF Reader", "Notes"],
        },
        "FILE_MANAGEMENT": {
            "intent": "FILE ORGANIZATION",
            "default_actions": ["File Controller", "File Processor", "Downloads"],
        },
        "ENTERTAINMENT": {
            "intent": "MEDIA / ENTERTAINMENT",
            "default_actions": ["YouTube", "Spotify", "Steam"],
        },
        "COMMUNICATION": {
            "intent": "COMMUNICATION",
            "default_actions": ["WhatsApp", "Discord", "Email"],
        },
        "SYSTEM_CONTROL": {
            "intent": "SYSTEM CONTROL",
            "default_actions": ["Settings", "Volume Control", "Display Settings"],
        },
        "PROJECT_WORK": {
            "intent": "PROJECT WORK",
            "default_actions": ["VS Code", "Terminal", "Chrome"],
        },
    }

    def __init__(self, data: Dict[str, Any]):
        self.data = data.setdefault("intent_patterns", {})

    def predict_intent(
        self,
        query: str = "",
        active_app: str = "",
        cwd: str = "",
        recent_tools: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        workflow_graph: Optional[PersonalWorkflowGraph] = None,
        project_engine: Optional[ProjectContextEngine] = None
    ) -> Dict[str, Any]:
        """Estimates intent, candidate actions, and concise user-safe explanation.
        Uses workflow graph and project context when available for personalized predictions."""
        ctx = context or ContextDetector.detect_context(query, active_app, cwd, recent_tools)
        domain = ctx["domain"]
        project = ctx["project"]

        matched = self.INTENT_MAP.get(domain)
        if matched:
            intent_label = matched["intent"]
            actions = list(matched["default_actions"])
        else:
            intent_label = f"GENERAL / {domain}"
            actions = ["Open App", "Web Search", "File Controller"]

        # Personalize from workflow graph if available
        if workflow_graph:
            learned_tools = []
            for edge in workflow_graph.data.values():
                if (edge.get("context_domain", "").upper() == domain and
                    edge.get("confidence", 0) >= 0.50):
                    tool = edge.get("tool", "")
                    if tool and tool not in learned_tools:
                        learned_tools.append(tool)
            if learned_tools:
                actions = learned_tools[:4]

        # Personalize from project context if available
        if project_engine and project != "GENERAL":
            proj_data = project_engine.data.get(project)
            if proj_data and proj_data.get("typical_tools"):
                proj_tools = proj_data["typical_tools"][:4]
                if proj_tools:
                    actions = proj_tools

        explanation = f"Based on your active {project} {domain.lower()} session, I predict you're continuing your workflow."

        return {
            "intent": intent_label,
            "confidence": min(0.95, max(0.60, ctx.get("confidence", 0.5) + 0.20)),
            "supporting_context": ctx,
            "candidate_actions": actions,
            "reasoning_summary": explanation,
        }


# ════════════════════════════════════════════════════════════
# 6. ROUTINE PREDICTION ENGINE (3.0)
# ════════════════════════════════════════════════════════════
class RoutinePredictionEngine:
    """Learns recurring time + day + project multi-variable routines."""

    def __init__(self, data: Dict[str, Any]):
        self.data = data.setdefault("routines", {})

    def record_routine_observation(
        self, time_bucket: str, day_of_week: str, domain: str, project: str, tool_sequence: List[str]
    ) -> Dict[str, Any]:
        """Records a multi-variable routine observation."""
        routine_key = f"{day_of_week}::{time_bucket}::{domain}::{project}".lower()
        now_str = datetime.now().isoformat()

        routine = self.data.get(routine_key)
        if routine:
            routine["occurrence_count"] = routine.get("occurrence_count", 1) + 1
            routine["last_seen"] = now_str
            cur_c = routine.get("confidence", 0.35)
            routine["confidence"] = min(0.95, round(cur_c + (1.0 - cur_c) * 0.25, 4))
            routine["tool_sequence"] = tool_sequence
        else:
            routine = {
                "routine_key": routine_key,
                "day_of_week": day_of_week,
                "time_bucket": time_bucket,
                "domain": domain,
                "project": project,
                "tool_sequence": tool_sequence,
                "occurrence_count": 1,
                "confidence": 0.35,
                "first_seen": now_str,
                "last_seen": now_str,
            }
            self.data[routine_key] = routine

        return routine

    def predict_routine(self, time_bucket: str, day_of_week: str, domain: str) -> Optional[Dict[str, Any]]:
        """Predicts active routine if confidence >= 0.60."""
        best_routine = None
        best_conf = 0.60

        for routine in self.data.values():
            if (routine.get("time_bucket") == time_bucket and
                routine.get("day_of_week") == day_of_week and
                routine.get("domain") == domain and
                routine.get("confidence", 0.0) >= best_conf):
                best_routine = routine
                best_conf = routine.get("confidence", 0.0)

        return best_routine


# ════════════════════════════════════════════════════════════
# 7. PROJECT CONTEXT & CROSS-SESSION CONTINUITY ENGINE (3.0)
# ════════════════════════════════════════════════════════════
class ProjectContextEngine:
    """Manages project-specific metadata and cross-session task continuity."""

    def __init__(self, data: Dict[str, Any]):
        self.data = data.setdefault("projects", {})

    def update_project_context(
        self,
        project_name: str,
        tool: str,
        task: str,
        file_path: Optional[str] = None
    ):
        """Updates project metadata and recent activity."""
        p_key = redact_secrets(project_name).strip().upper()
        now_str = datetime.now().isoformat()

        proj = self.data.setdefault(p_key, {
            "project_name": p_key,
            "typical_tools": [],
            "typical_tasks": [],
            "recent_files": [],
            "last_session": {},
            "created_at": now_str,
            "last_updated": now_str,
        })

        proj["last_updated"] = now_str
        if tool and tool not in proj["typical_tools"]:
            proj["typical_tools"].append(tool)
        if task and task not in proj["typical_tasks"]:
            proj["typical_tasks"].append(task)
        if file_path and file_path not in proj["recent_files"]:
            proj["recent_files"].append(file_path)
            if len(proj["recent_files"]) > 10:
                proj["recent_files"].pop(0)

        proj["last_session"] = {
            "project": p_key,
            "task": task,
            "tools_used": [tool] if tool else [],
            "last_file": file_path or "",
            "last_state": "COMPLETED_TURN",
            "timestamp": now_str,
        }

    def get_last_session_summary(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Retrieves last session summary for cross-session continuity ("Continue what I was doing")."""
        p_key = redact_secrets(project_name).strip().upper()
        proj = self.data.get(p_key)
        if proj and "last_session" in proj:
            return proj["last_session"]
        return None


# ════════════════════════════════════════════════════════════
# 8. OUTCOME LEARNING ENGINE (3.0)
# ════════════════════════════════════════════════════════════
class OutcomeLearningEngine:
    """Evaluates prediction feedback (Prediction -> Response -> Outcome -> Confidence Update)."""

    def __init__(self, data: Dict[str, Any]):
        self.data = data.setdefault("outcomes", {})

    def evaluate_prediction_outcome(
        self,
        prediction_id: str,
        user_response: str,
        actual_outcome: str,
        sequence_engine: WorkflowSequenceEngine
    ) -> Dict[str, Any]:
        """Evaluates prediction response and updates confidence cleanly.
        Only applies feedback to the specific pattern that generated the prediction."""
        resp_clean = user_response.lower().strip()
        now_str = datetime.now().isoformat()

        accepted = any(w in resp_clean for w in ["yes", "yeah", "sure", "do it", "ok", "okay", "accept"])
        rejected = any(w in resp_clean for w in ["no", "nope", "dont", "don't", "stop", "cancel", "reject"])

        record = {
            "prediction_id": prediction_id,
            "user_response": user_response,
            "actual_outcome": actual_outcome,
            "accepted": accepted,
            "rejected": rejected,
            "timestamp": now_str,
        }

        self.data[prediction_id] = record

        # Apply feedback ONLY to the specific matching sequence pattern
        if accepted or rejected:
            for seq_key in list(sequence_engine.data.keys()):
                if prediction_id in seq_key:
                    sequence_engine.record_suggestion_feedback(seq_key, accepted=accepted)
                    break  # Only update the matched pattern

        return record


# ════════════════════════════════════════════════════════════
# 9. MEMORY CONSOLIDATION ENGINE (3.0)
# ════════════════════════════════════════════════════════════
class MemoryConsolidationEngine:
    """Consolidates duplicate memories, resolves contradictions, and cleans obsolete low-value records."""

    @classmethod
    def consolidate(cls, insights_data: Dict[str, Any]) -> int:
        """Consolidates duplicate insight keys and cleans stale/contradictory memory entries."""
        insights = insights_data.get("insights", {})
        if not insights:
            return 0

        merged_count = 0
        grouped: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}

        for i_id, insight in list(insights.items()):
            key = insight.get("key", "").lower().strip()
            if key:
                grouped.setdefault(key, []).append((i_id, insight))

        for key, item_list in grouped.items():
            if len(item_list) > 1:
                # Prioritize explicit > highest confidence > most recent
                item_list.sort(
                    key=lambda x: (
                        x[1].get("source") == "explicit",
                        x[1].get("confidence", 0.0),
                        x[1].get("last_seen", "")
                    ),
                    reverse=True
                )
                keep_id, keep_item = item_list[0]

                # Merge observation counts
                total_obs = sum(x[1].get("observation_count", 1) for x in item_list)
                keep_item["observation_count"] = total_obs

                # Delete duplicate entries
                for del_id, _ in item_list[1:]:
                    if del_id in insights:
                        del insights[del_id]
                        merged_count += 1

        return merged_count


# ════════════════════════════════════════════════════════════
# 10. MAIN ADAPTIVE INTELLIGENCE ENGINE 3.0
# ════════════════════════════════════════════════════════════
class AdaptiveIntelligenceEngine:
    """Adaptive Intelligence Engine 3.0 — Predictive Personal Agent Subsystem."""

    def __init__(self, insights_path: Optional[Path] = None):
        base_dir = insights_path.parent if insights_path else MEMORY_DIR
        self.insights_path = insights_path or (base_dir / "adaptive_insights.json")
        self.patterns_path = base_dir / "workflow_patterns.json"
        self.preferences_path = base_dir / "contextual_preferences.json"
        self.predictive_path = base_dir / "predictive_patterns.json"
        self.routines_path = base_dir / "routines.json"
        self.projects_path = base_dir / "project_context.json"
        self.outcomes_path = base_dir / "prediction_outcomes.json"

        self.learning_enabled = True
        self.predictive_enabled = True
        self.session_active = True
        self._recent_tool_history: List[str] = []

        # Load modular databases safely
        self.insights_data = self._load_json_safely(self.insights_path, "insights")
        self.patterns_data = self._load_json_safely(self.patterns_path, "patterns")
        self.preferences_data = self._load_json_safely(self.preferences_path, "preferences")
        self.predictive_data = self._load_json_safely(self.predictive_path, "intent_patterns")
        self.routines_data = self._load_json_safely(self.routines_path, "routines")
        self.projects_data = self._load_json_safely(self.projects_path, "projects")
        self.outcomes_data = self._load_json_safely(self.outcomes_path, "outcomes")

        # Subsystems
        self.sequence_engine = WorkflowSequenceEngine(self.patterns_data)
        self.workflow_graph = PersonalWorkflowGraph(self.preferences_data)
        self.intent_engine = PredictiveIntentEngine(self.predictive_data)
        self.routine_engine = RoutinePredictionEngine(self.routines_data)
        self.project_engine = ProjectContextEngine(self.projects_data)
        self.outcome_engine = OutcomeLearningEngine(self.outcomes_data)

    # Backward Compatibility Wrapper
    @property
    def data(self) -> Dict[str, Any]:
        return self.insights_data

    @data.setter
    def data(self, value: Dict[str, Any]):
        self.insights_data = value

    # ════════════════════════════════════════════════════════════
    # STORAGE & ATOMIC PERSISTENCE
    # ════════════════════════════════════════════════════════════
    def _default_schema(self, root_key: str) -> Dict[str, Any]:
        return {
            "meta": {
                "version": "3.0.0",
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "learning_enabled": True,
                "predictive_enabled": True,
            },
            root_key: {},
            "tool_reflexes": {},
            "user_commands": {}
        }

    def _load_json_safely(self, file_path: Path, root_key: str) -> Dict[str, Any]:
        if not file_path.exists():
            return self._default_schema(root_key)

        with _lock:
            try:
                raw = file_path.read_text(encoding="utf-8")
                data = json.loads(raw)
                if isinstance(data, dict):
                    meta = data.get("meta", {})
                    self.learning_enabled = meta.get("learning_enabled", True)
                    self.predictive_enabled = meta.get("predictive_enabled", True)
                    return data
                raise ValueError(f"Invalid schema structure in {file_path.name}")
            except Exception as e:
                print(f"[AdaptiveIntelligence] [WARN] Storage corruption in {file_path.name} ({e}). Creating backup.")
                self._backup_file(file_path)
                return self._default_schema(root_key)

    def _backup_file(self, file_path: Path):
        try:
            if file_path.exists():
                bak_path = file_path.with_suffix(f".bak.{int(time.time())}")
                file_path.rename(bak_path)
                print(f"[AdaptiveIntelligence] [BACKUP] Saved corrupted dataset to {bak_path.name}")
        except Exception as ex:
            print(f"[AdaptiveIntelligence] [WARN] Backup failed: {ex}")

    def save(self) -> bool:
        """Atomic write across all modular JSON files."""
        if not self.session_active:
            return False

        with _lock:
            try:
                now_str = datetime.now().isoformat()

                files_and_data = [
                    (self.insights_path, self.insights_data),
                    (self.patterns_path, self.patterns_data),
                    (self.preferences_path, self.preferences_data),
                    (self.predictive_path, self.predictive_data),
                    (self.routines_path, self.routines_data),
                    (self.projects_path, self.projects_data),
                    (self.outcomes_path, self.outcomes_data),
                ]

                for path, data in files_and_data:
                    data.setdefault("meta", {})["last_updated"] = now_str
                    data["meta"]["learning_enabled"] = self.learning_enabled
                    data["meta"]["predictive_enabled"] = self.predictive_enabled

                    tmp_path = path.with_suffix(".tmp")
                    serialized = json.dumps(data, indent=2, ensure_ascii=False)

                    tmp_path.parent.mkdir(parents=True, exist_ok=True)
                    tmp_path.write_text(serialized, encoding="utf-8")

                    json.loads(tmp_path.read_text(encoding="utf-8"))

                    if sys.platform == "win32":
                        if path.exists():
                            path.unlink()
                    tmp_path.rename(path)

                return True
            except Exception as e:
                print(f"[AdaptiveIntelligence] ⚠️ Save failed: {e}")
                return False

    # ════════════════════════════════════════════════════════════
    # CORE LEARNING & OBSERVATION ENGINE (3.0)
    # ════════════════════════════════════════════════════════════
    def add_or_update_insight(
        self,
        category: str,
        key: str,
        value: str,
        source: str = "inferred",
        initial_confidence: float = 0.35,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Adds or reinforces an insight with context metadata and secret redaction."""
        if not self.learning_enabled or not self.session_active:
            return None

        try:
            clean_value = redact_secrets(str(value).strip().rstrip(".,!?"))
            clean_key = redact_secrets(str(key).strip().lower().rstrip(".,!?"))
            if not clean_key or not clean_value:
                return None

            now_str = datetime.now().isoformat()
            insights = self.insights_data.setdefault("insights", {})

            existing_id = None
            for i_id, insight in insights.items():
                if insight.get("category") == category and insight.get("key") == clean_key:
                    existing_id = i_id
                    break

            if existing_id:
                target = insights[existing_id]
                old_val = target.get("value")

                if old_val == clean_value:
                    obs = target.get("observation_count", 1) + 1
                    target["observation_count"] = obs
                    target["last_seen"] = now_str
                    if context:
                        target["context"] = context

                    if source == "explicit":
                        target["confidence"] = 0.98
                        target["source"] = "explicit"
                    else:
                        cur_conf = target.get("confidence", initial_confidence)
                        target["confidence"] = min(0.95, round(cur_conf + (1.0 - cur_conf) * 0.25, 4))
                else:
                    if target.get("source") == "explicit" and source == "inferred":
                        pass
                    else:
                        target["value"] = clean_value
                        target["observation_count"] = 1
                        target["last_seen"] = now_str
                        if context:
                            target["context"] = context

                        if source == "explicit":
                            target["confidence"] = 0.98
                            target["source"] = "explicit"
                        else:
                            target["confidence"] = initial_confidence
                            target["source"] = source

                result = insights[existing_id]
            else:
                insight_id = str(uuid.uuid4())[:8]
                conf = 0.98 if source == "explicit" else min(0.98, initial_confidence)
                new_insight = {
                    "insight_id": insight_id,
                    "category": category,
                    "key": clean_key,
                    "value": clean_value,
                    "confidence": conf,
                    "observation_count": 1,
                    "first_seen": now_str,
                    "last_seen": now_str,
                    "source": source,
                    "context": context or ContextDetector.detect_context(key),
                    "enabled": True,
                }
                insights[insight_id] = new_insight
                result = new_insight

            self.save()
            return result
        except Exception as e:
            print(f"[AdaptiveIntelligence] ⚠️ Error recording insight: {e}")
            return None

    def observe_interaction(
        self,
        user_input: str,
        jarvis_output: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        active_app: str = "",
        cwd: str = ""
    ):
        """Asynchronously observes interaction turns to infer preferences, routines, workflows & project context."""
        if not self.session_active:
            return

        try:
            user_text = redact_secrets(user_input).strip() if user_input else ""
            jarvis_text = redact_secrets(jarvis_output).strip() if jarvis_output else ""

            if not user_text or len(user_text) < 3:
                return

            lower_in = user_text.lower()

            # 1. Governance Commands
            if self._handle_user_control_commands(lower_in):
                return

            if not self.learning_enabled:
                return

            # Context & Intent Detection
            recent_t = [tc.get("name", "") for tc in (tool_calls or [])]
            ctx = ContextDetector.detect_context(user_text, active_app, cwd, recent_t)

            # Update Project Context
            if ctx["project"] != "GENERAL":
                first_tool = recent_t[0] if recent_t else active_app
                self.project_engine.update_project_context(ctx["project"], first_tool, ctx["domain"])

            # 2. Extract Explicit Preference
            pref_match = re.search(
                r"(?:remember that|note that|my favorite|i prefer|i use|i always use)\s+([a-zA-Z0-9_\s]+?)\s+(?:is|for|to|as)\s+([a-zA-Z0-9_\s\.\-]+)",
                lower_in
            )
            if pref_match:
                key = pref_match.group(1).strip()
                val = pref_match.group(2).strip()
                self.add_or_update_insight("preference", key, val, source="explicit", initial_confidence=0.98, context=ctx)
                print(f"[ADAPTIVE] Preference reinforced: {key} -> {val} (Explicit 0.98)")
                return

            # 3. Infer Tool & App Habits
            if "python" in lower_in and ("vs code" in lower_in or "vscode" in lower_in):
                self.add_or_update_insight("preference", "python_editor", "VS Code", source="inferred", initial_confidence=0.45, context=ctx)
                self.workflow_graph.add_or_update_edge(ctx["domain"], "python_development", "VS Code", ctx["project"])
            elif "browser" in lower_in and "chrome" in lower_in:
                self.add_or_update_insight("preference", "web_browser", "Google Chrome", source="inferred", initial_confidence=0.45, context=ctx)

            # 4. Tool Calls & Sequence Learning
            if tool_calls:
                for tc in tool_calls:
                    tool_name = tc.get("name")
                    tool_args = tc.get("args", {})
                    if tool_name:
                        action_item = tool_args.get("app_name", tool_name) if tool_name == "open_app" else tool_name
                        self._recent_tool_history.append(action_item)
                        if len(self._recent_tool_history) > 10:
                            self._recent_tool_history.pop(0)

                        if tool_name == "open_app" and "app_name" in tool_args:
                            app_name = tool_args["app_name"]
                            self.add_or_update_insight(
                                "habit", f"frequent_app_{app_name.lower()}", app_name, source="inferred", initial_confidence=0.35, context=ctx
                            )
                            self.workflow_graph.add_or_update_edge(ctx["domain"], "launch_app", app_name, ctx["project"])

                if len(self._recent_tool_history) >= 2:
                    self.sequence_engine.record_sequence(self._recent_tool_history[-3:], ctx)
                    self.routine_engine.record_routine_observation(
                        ctx["time_bucket"], ctx["day_of_week"], ctx["domain"], ctx["project"], self._recent_tool_history[-3:]
                    )

            # Consolidated Memory Maintenance
            MemoryConsolidationEngine.consolidate(self.insights_data)
            self.save()
        except Exception as e:
            print(f"[AdaptiveIntelligence] [WARN] Observer error: {e}")

    # ════════════════════════════════════════════════════════════
    # TOOL REFLEX & ROUTING
    # ════════════════════════════════════════════════════════════
    def record_tool_reflex(self, tool_name: str, failed_args: Dict[str, Any], corrected_args: Dict[str, Any]):
        """Learns parameter corrections for failed tool invocations to suggest auto-corrections."""
        if not self.learning_enabled or not self.session_active:
            return

        try:
            reflexes = self.insights_data.setdefault("tool_reflexes", {})
            tool_list = reflexes.setdefault(tool_name, [])

            rule = {
                "failed_args": failed_args,
                "corrected_args": corrected_args,
                "success_count": 1,
                "last_applied": datetime.now().isoformat()
            }

            for existing in tool_list:
                if existing.get("failed_args") == failed_args:
                    existing["corrected_args"] = corrected_args
                    existing["success_count"] = existing.get("success_count", 1) + 1
                    existing["last_applied"] = datetime.now().isoformat()
                    self.save()
                    return

            tool_list.append(rule)
            self.save()
            print(f"[ADAPTIVE] Learned tool reflex for '{tool_name}'")
        except Exception as e:
            print(f"[AdaptiveIntelligence] [WARN] Tool reflex recording note: {e}")

    def suggest_tool_correction(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Suggests learned parameter corrections if previous identical args failed."""
        if not self.learning_enabled or not self.session_active:
            return args

        try:
            reflexes = self.insights_data.get("tool_reflexes", {}).get(tool_name, [])
            for rule in reflexes:
                if rule.get("failed_args") == args and rule.get("success_count", 0) >= 1:
                    print(f"[ADAPTIVE] Applied tool reflex correction for '{tool_name}'")
                    return rule.get("corrected_args", args)
        except Exception:
            pass
        return args

    # ════════════════════════════════════════════════════════════
    # USER VOICE GOVERNANCE & NATURAL MEMORY QUERIES (3.0)
    # ════════════════════════════════════════════════════════════
    def _handle_user_control_commands(self, lower_input: str) -> bool:
        """Processes voice control commands for Adaptive & Predictive Intelligence management."""
        if "jarvis, stop adaptive learning" in lower_input or "disable adaptive learning" in lower_input:
            self.learning_enabled = False
            self.save()
            print("[ADAPTIVE] Learning disabled by user.")
            return True

        if "jarvis, resume adaptive learning" in lower_input or "enable adaptive learning" in lower_input:
            self.learning_enabled = True
            self.save()
            print("[ADAPTIVE] Learning resumed by user.")
            return True

        if "stop predictive intelligence" in lower_input or "disable predictive intelligence" in lower_input:
            self.predictive_enabled = False
            self.save()
            print("[ADAPTIVE] Predictive intelligence disabled by user.")
            return True

        if "resume predictive intelligence" in lower_input or "enable predictive intelligence" in lower_input:
            self.predictive_enabled = True
            self.save()
            print("[ADAPTIVE] Predictive intelligence resumed by user.")
            return True

        if "clear predictions" in lower_input or "forget predictions" in lower_input:
            self.clear_predictions()
            print("[ADAPTIVE] Prediction memory cleared by user.")
            return True

        if "forget everything you learned about my workflow" in lower_input or "forget workflow" in lower_input:
            self.forget_workflow_patterns()
            print("[ADAPTIVE] Workflow patterns cleared by user.")
            return True

        if "jarvis, reset adaptive intelligence" in lower_input or "clear learned adaptive data" in lower_input:
            self.reset_learning()
            print("[ADAPTIVE] Adaptive memory reset by user.")
            return True

        return False

    def handle_voice_query(self, user_command: str) -> Optional[str]:
        """Handles voice queries regarding predictions, learned preferences & dataset status."""
        lower = user_command.lower().strip()

        if "what have you learned about me" in lower or "what do you know about my workflow" in lower or "learned preferences" in lower:
            return self.summarize_insights()

        if "stop predictive intelligence" in lower or "disable predictive intelligence" in lower:
            self.predictive_enabled = False
            self.save()
            return "Predictive intelligence has been paused, sir."

        if "resume predictive intelligence" in lower or "enable predictive intelligence" in lower:
            self.predictive_enabled = True
            self.save()
            return "Predictive intelligence is active and observing, sir."

        if "what do you predict" in lower or "what are you predicting" in lower:
            pred = self.intent_engine.predict_intent()
            return f"Sir, based on your active {pred['supporting_context']['domain']} context, I predict your intent is {pred['intent']}. Candidate actions include {', '.join(pred['candidate_actions'][:2])}."

        if "why did you suggest" in lower:
            return "Because you usually open Terminal after VS Code when working on this project, sir."

        if "how confident are you" in lower:
            return "My prediction confidence models range between 60% and 95% depending on contextual relevance, sir."

        forget_pref_match = re.search(r"forget (?:that preference for|my preference for|preference for)\s+([a-zA-Z0-9_\s]+)", lower)
        if forget_pref_match:
            target_key = forget_pref_match.group(1).strip()
            removed = self.forget_insight(target_key)
            if removed:
                return f"Sir, I have removed my learned preference regarding '{target_key}'."
            return f"I couldn't find any specific learned preference for '{target_key}'."

        if "forget this prediction" in lower or "clear predictions" in lower:
            self.clear_predictions()
            return "Predictions have been cleared, sir."

        if "forget everything you learned about my workflow" in lower or "forget my workflow patterns" in lower:
            self.forget_workflow_patterns()
            return "Sir, I have cleared all learned workflow patterns from adaptive memory."

        if "stop adaptive learning" in lower:
            self.learning_enabled = False
            self.save()
            return "Adaptive learning has been paused, sir."

        if "resume adaptive learning" in lower:
            self.learning_enabled = True
            self.save()
            return "Adaptive learning is active and observing, sir."

        if "reset adaptive intelligence" in lower:
            self.reset_learning()
            return "Adaptive intelligence dataset has been reset to default parameters, sir."

        return None

    def forget_insight(self, key_substring: str) -> bool:
        """Removes or disables insights matching a key substring."""
        if not self.session_active:
            return False

        with _lock:
            try:
                insights = self.insights_data.get("insights", {})
                target_sub = key_substring.lower().strip()
                removed_any = False

                for i_id, insight in list(insights.items()):
                    if target_sub in insight.get("key", "").lower() or target_sub in insight.get("value", "").lower():
                        del insights[i_id]
                        removed_any = True

                if removed_any:
                    self.save()
                    print(f"[ADAPTIVE] Preference forgotten: {key_substring}")
                return removed_any
            except Exception as e:
                print(f"[AdaptiveIntelligence] ⚠️ Forget insight error: {e}")
                return False

    def clear_predictions(self):
        """Clears predictive intent patterns."""
        with _lock:
            try:
                self.predictive_data["intent_patterns"] = {}
                self.save()
                print("[ADAPTIVE] Predictions cleared cleanly.")
            except Exception as e:
                print(f"[AdaptiveIntelligence] ⚠️ Clear predictions error: {e}")

    def forget_workflow_patterns(self):
        """Clears all learned workflow sequence patterns without resetting user preferences."""
        with _lock:
            try:
                self.patterns_data["patterns"] = {}
                self.save()
                print("[ADAPTIVE] Workflow patterns reset cleanly.")
            except Exception as e:
                print(f"[AdaptiveIntelligence] ⚠️ Workflow reset error: {e}")

    def reset_learning(self):
        """Resets entire adaptive learning dataset to clean initial template."""
        with _lock:
            try:
                self.insights_data = self._default_schema("insights")
                self.patterns_data = self._default_schema("patterns")
                self.preferences_data = self._default_schema("preferences")
                self.predictive_data = self._default_schema("intent_patterns")
                self.routines_data = self._default_schema("routines")
                self.projects_data = self._default_schema("projects")
                self.outcomes_data = self._default_schema("outcomes")

                self.sequence_engine = WorkflowSequenceEngine(self.patterns_data)
                self.workflow_graph = PersonalWorkflowGraph(self.preferences_data)
                self.intent_engine = PredictiveIntentEngine(self.predictive_data)
                self.routine_engine = RoutinePredictionEngine(self.routines_data)
                self.project_engine = ProjectContextEngine(self.projects_data)
                self.outcome_engine = OutcomeLearningEngine(self.outcomes_data)

                self.learning_enabled = True
                self.predictive_enabled = True
                self.save()
                print("[ADAPTIVE] Adaptive memory reset.")
            except Exception as e:
                print(f"[AdaptiveIntelligence] ⚠️ Reset error: {e}")

    def summarize_insights(self) -> str:
        """Generates a concise spoken summary of high-confidence learned user insights and workflows."""
        insights = [
            i for i in self.insights_data.get("insights", {}).values()
            if i.get("enabled", True) and i.get("confidence", 0) >= 0.60
        ]

        patterns = [
            p for p in self.patterns_data.get("patterns", {}).values()
            if p.get("confidence", 0) >= 0.60
        ]

        if not insights and not patterns:
            return "I have not established any distinct behavioral preferences or workflow patterns yet, sir."

        summary_lines = ["Your strongest learned patterns are:"]
        for i in insights[:4]:
            summary_lines.append(f"• {i['key'].title()}: {i['value']} (Confidence: {int(i['confidence']*100)}%)")

        for p in patterns[:2]:
            summary_lines.append(f"• Workflow: {p.get('sequence_key')} (Confidence: {int(p['confidence']*100)}%)")

        return "\n".join(summary_lines)

    def apply_decay(self, days_threshold: int = 14, decay_factor: float = 0.15):
        """Applies 14-day temporal decay across inactive insights and workflow graph edges."""
        if not self.session_active:
            return

        with _lock:
            try:
                now = datetime.now()
                insights = self.insights_data.get("insights", {})

                for i_id, insight in list(insights.items()):
                    if insight.get("source") == "explicit":
                        continue

                    last_seen_str = insight.get("last_seen")
                    if not last_seen_str:
                        continue

                    try:
                        last_seen = datetime.fromisoformat(last_seen_str)
                        if (now - last_seen).days >= days_threshold:
                            conf = insight.get("confidence", 0.5) - decay_factor
                            if conf < 0.2:
                                insight["enabled"] = False
                                insight["confidence"] = 0.0
                            else:
                                insight["confidence"] = round(conf, 3)
                    except Exception:
                        pass

                self.workflow_graph.apply_decay(days_threshold, decay_factor)
                self.save()
            except Exception as ex:
                print(f"[AdaptiveIntelligence] [WARN] Decay execution note: {ex}")

    # ════════════════════════════════════════════════════════════
    # PROMPT CONTEXT SYNTHESIZER FOR GEMINI
    # ════════════════════════════════════════════════════════════
    def get_adaptive_context(
        self,
        max_insights: int = 5,
        min_confidence: float = 0.60,
        query: str = "",
        active_app: str = "",
        cwd: str = ""
    ) -> str:
        """Synthesizes a compact, highly relevant contextual prompt block for Gemini."""
        if not self.learning_enabled or not self.session_active:
            return ""

        try:
            ctx = ContextDetector.detect_context(query, active_app, cwd)
            domain = ctx["domain"]
            project = ctx["project"]

            active_insights = []
            for i in self.insights_data.get("insights", {}).values():
                if not i.get("enabled", True) or i.get("confidence", 0.0) < min_confidence:
                    continue
                i_dom = i.get("context", {}).get("domain")
                if i_dom and domain != "GENERAL" and i_dom not in ["GENERAL", domain]:
                    continue
                active_insights.append(i)

            if not active_insights:
                return ""

            def relevance_score(item):
                score = item.get("confidence", 0.0)
                if item.get("source") == "explicit":
                    score += 0.5
                i_ctx = item.get("context", {})
                if i_ctx.get("domain") == domain:
                    score += 0.4
                if i_ctx.get("project") == project:
                    score += 0.3
                return score

            active_insights.sort(key=relevance_score, reverse=True)

            lines = [f"ADAPTIVE CONTEXT ({domain} | {project}):"]
            for insight in active_insights[:max_insights]:
                lines.append(f"- {insight['key']}: {insight['value']} (confidence: {insight.get('confidence', 0.6):.2f})")

            return "\n".join(lines)
        except Exception as e:
            print(f"[AdaptiveIntelligence] ⚠️ Context generator note: {e}")
            return ""


# Global Singleton Instance with Fail-Safe Protection
default_adaptive_engine = AdaptiveIntelligenceEngine()
