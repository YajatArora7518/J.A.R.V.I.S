# core/context_retriever.py
# Smart Context Retrieval Engine for J.A.R.V.I.S (Domain-Specific Bounded Context Assembly)

import os
import sys
import re
import time
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional

from memory.memory_manager import retrieve_relevant_memories

# Common sensitive regex patterns to redact before LLM prompt injection
SECRET_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z-_]{35}"),                         # Google API Keys
    re.compile(r"sk-[0-9A-Za-z]{32,}"),                          # OpenAI / Generic Secret keys
    re.compile(r"(?:api_key|apikey|secret|token|password|passwd|pwd)[\"'\s]*[:=][\"'\s]*([a-zA-Z0-9_\-\.]{8,})", re.IGNORECASE),
    re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]{15,}", re.IGNORECASE)
]


class ContextDomain(str, Enum):
    PROJECT = "PROJECT"
    COLLEGE = "COLLEGE"
    SCREEN = "SCREEN"
    GENERAL = "GENERAL"


class SmartContextRetriever:
    """
    Selectively retrieves and bounds domain-relevant context for LLM prompts.
    Prevents complete database dumping and redacts private secrets.
    """

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path(__file__).resolve().parent.parent

    def classify_domain(self, query: str) -> ContextDomain:
        """Determines the active operational domain of the user request."""
        lower = (query or "").lower()

        # 1. Screen domain
        if any(w in lower for w in [
            "screen", "window", "display", "screenshot", "dekho", "kya chal raha",
            "active window", "click karo", "error solve karo"
        ]):
            return ContextDomain.SCREEN

        # 2. College / Academic domain
        if any(w in lower for w in [
            "class", "schedule", "timetable", "lecture", "assignment", "deadline",
            "exam", "professor", "college", "submit", "homework", "subject"
        ]):
            return ContextDomain.COLLEGE

        # 3. Project / Code domain
        if any(w in lower for w in [
            "project", "code", "python", "build", "git", "repo", "repository",
            "file", "script", "terminal", "antigravity", "ide", "bug", "traceback",
            "regression", "function", "class", "tests"
        ]):
            return ContextDomain.PROJECT

        # 4. Default: General conversation
        return ContextDomain.GENERAL

    def retrieve_context(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        active_window: str = ""
    ) -> Dict[str, Any]:
        """
        Assembles bounded context specific to the classified domain.
        """
        domain = self.classify_domain(query)
        base_ctx = {
            "domain": domain.value,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "query": query
        }

        if domain == ContextDomain.PROJECT:
            base_ctx.update(self._get_project_context(query, active_window, conversation_history))

        elif domain == ContextDomain.COLLEGE:
            base_ctx.update(self._get_college_context(query))

        elif domain == ContextDomain.SCREEN:
            base_ctx.update(self._get_screen_context(query, active_window, conversation_history))

        else:
            base_ctx.update(self._get_general_context(query, conversation_history))

        return base_ctx

    def format_prompt_context(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        active_window: str = ""
    ) -> str:
        """
        Formats retrieved domain-specific context into a clean, bounded prompt block.
        Applies secret redaction.
        """
        ctx = self.retrieve_context(query, conversation_history, active_window)
        domain = ctx.get("domain", ContextDomain.GENERAL.value)
        blocks = [f"=== SMART CONTEXT [{domain}] ==="]
        blocks.append(f"Current Time: {ctx.get('timestamp')}")

        if domain == ContextDomain.PROJECT:
            if "project_name" in ctx:
                blocks.append(f"Project: {ctx['project_name']} ({ctx.get('project_dir', '')})")
            if "recent_files" in ctx and ctx["recent_files"]:
                blocks.append(f"Relevant Files: {', '.join(ctx['recent_files'][:5])}")
            if "active_window" in ctx and ctx["active_window"]:
                blocks.append(f"Active App/Window: {ctx['active_window']}")
            if "relevant_memories" in ctx and ctx["relevant_memories"]:
                blocks.append("Relevant Code Memory:")
                for m in ctx["relevant_memories"]:
                    blocks.append(f"  • {m['key']}: {m['value']}")

        elif domain == ContextDomain.COLLEGE:
            if "timetable" in ctx and ctx["timetable"]:
                blocks.append("Academic Timetable:")
                for item in ctx["timetable"][:5]:
                    blocks.append(f"  • {item}")
            if "assignments" in ctx and ctx["assignments"]:
                blocks.append("Upcoming Deadlines & Assignments:")
                for a in ctx["assignments"][:4]:
                    blocks.append(f"  • {a}")
            if "relevant_memories" in ctx and ctx["relevant_memories"]:
                blocks.append("Relevant Notes:")
                for m in ctx["relevant_memories"]:
                    blocks.append(f"  • {m['key']}: {m['value']}")

        elif domain == ContextDomain.SCREEN:
            blocks.append(f"Active Foreground Window: {ctx.get('active_window') or 'Unknown/Desktop'}")
            if "screen_summary" in ctx and ctx["screen_summary"]:
                blocks.append(f"Screen Observation: {ctx['screen_summary']}")
            if "recent_conversation" in ctx and ctx["recent_conversation"]:
                blocks.append("Recent Conversation Context:")
                for turn in ctx["recent_conversation"][-2:]:
                    blocks.append(f"  {turn.get('role', 'User')}: {turn.get('text', '')}")

        else:
            # General Domain
            if "relevant_memories" in ctx and ctx["relevant_memories"]:
                blocks.append("User Preferences & Facts:")
                for m in ctx["relevant_memories"]:
                    blocks.append(f"  • {m['key']}: {m['value']}")
            if "recent_conversation" in ctx and ctx["recent_conversation"]:
                blocks.append("Recent Conversation:")
                for turn in ctx["recent_conversation"][-3:]:
                    blocks.append(f"  {turn.get('role', 'User')}: {turn.get('text', '')}")

        raw_block = "\n".join(blocks)
        return self._redact_secrets(raw_block)

    def _get_project_context(
        self,
        query: str,
        active_window: str,
        conversation_history: Optional[List[Dict[str, str]]]
    ) -> Dict[str, Any]:
        """Project context: includes only project files, active app, code memory."""
        recent_files = []
        try:
            # Gather relevant modified python files
            candidates = list(self.base_dir.glob("*.py")) + list((self.base_dir / "core").glob("*.py"))
            sorted_files = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)
            recent_files = [f.name for f in sorted_files[:5]]
        except Exception:
            pass

        memories = retrieve_relevant_memories(f"project code {query}", limit=3)

        return {
            "project_name": self.base_dir.name,
            "project_dir": str(self.base_dir),
            "recent_files": recent_files,
            "active_window": active_window or "VS Code / Antigravity",
            "relevant_memories": memories,
            "recent_conversation": (conversation_history or [])[-3:]
        }

    def _get_college_context(self, query: str) -> Dict[str, Any]:
        """College context: timetable, assignments, deadlines, relevant memory."""
        timetable_items = []
        assignments_items = []

        try:
            from actions.college_schedule import schedule_query_engine
            day_name = time.strftime("%A")
            classes = schedule_query_engine.store.get_day_classes(day_name)
            for c in classes:
                timetable_items.append(f"{c.get('time')}: {c.get('course_name')} ({c.get('course_code')}) - {c.get('room')}")
        except Exception:
            pass

        try:
            from actions.college_mode import load_college_config
            cfg = load_college_config()
            for asg in cfg.get("assignments", []):
                due = asg.get("due_date", "Soon")
                assignments_items.append(f"[{asg.get('course_code', '')}] {asg.get('title', '')} (Due: {due})")
        except Exception:
            pass

        memories = retrieve_relevant_memories(f"college assignment deadline {query}", limit=3)

        return {
            "timetable": timetable_items,
            "assignments": assignments_items,
            "relevant_memories": memories
        }

    def _get_screen_context(
        self,
        query: str,
        active_window: str,
        conversation_history: Optional[List[Dict[str, str]]]
    ) -> Dict[str, Any]:
        """Screen context: active window, screen context, recent conversation."""
        if not active_window:
            try:
                import pygetwindow as gw
                win = gw.getActiveWindow()
                if win and win.title:
                    active_window = win.title.strip()
            except Exception:
                active_window = "Desktop"

        return {
            "active_window": active_window or "Desktop",
            "screen_summary": f"User is inspecting active window '{active_window}'.",
            "recent_conversation": (conversation_history or [])[-3:]
        }

    def _get_general_context(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]]
    ) -> Dict[str, Any]:
        """General context: identity, user preferences, time, recent conversation."""
        memories = retrieve_relevant_memories(query, limit=3)
        return {
            "relevant_memories": memories,
            "recent_conversation": (conversation_history or [])[-4:]
        }

    def _redact_secrets(self, text: str) -> str:
        """Sanitizes text by masking secret API keys, tokens, and passwords."""
        redacted = text
        for pattern in SECRET_PATTERNS:
            redacted = pattern.sub("[REDACTED_SECRET]", redacted)
        return redacted


# Default singleton instance
default_context_retriever = SmartContextRetriever()
