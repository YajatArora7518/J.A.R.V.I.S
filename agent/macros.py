"""
agent/macros.py
Reusable Macro System for J.A.R.V.I.S.

Provides pre-built and user-defined macros for common desktop automation sequences.
Macros are stored in config/macros.json and executed through the ToolRegistry/SecurityManager.
"""

import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("JARVIS.Macros")

BASE_DIR = Path(__file__).resolve().parent.parent
MACROS_FILE = BASE_DIR / "config" / "macros.json"

# Built-in macros that are always available
BUILTIN_MACROS = {
    "study_mode": {
        "name": "Study Mode",
        "description": "Opens coding environment and study tools",
        "steps": [
            {"tool": "open_app", "params": {"app_name": "VS Code"}, "description": "Open VS Code"},
            {"tool": "open_app", "params": {"app_name": "Google Chrome"}, "description": "Open Chrome"},
        ],
        "tags": ["productivity", "study"],
    },
    "morning_routine": {
        "name": "Morning Routine",
        "description": "Opens daily productivity apps",
        "steps": [
            {"tool": "open_app", "params": {"app_name": "Google Chrome"}, "description": "Open Chrome"},
            {"tool": "web_search", "params": {"query": "weather today"}, "description": "Check weather"},
        ],
        "tags": ["routine", "morning"],
    },
    "coding_setup": {
        "name": "Coding Setup",
        "description": "Opens VS Code and terminal for coding session",
        "steps": [
            {"tool": "open_app", "params": {"app_name": "VS Code"}, "description": "Open VS Code"},
            {"tool": "open_app", "params": {"app_name": "Windows Terminal"}, "description": "Open Terminal"},
        ],
        "tags": ["coding", "productivity"],
    },
}


class MacroManager:
    """Manages reusable macro sequences."""

    def __init__(self):
        self._macros: Dict[str, Dict[str, Any]] = {}
        self._load_macros()

    def _load_macros(self):
        """Load user macros from config/macros.json, then overlay builtins."""
        # Start with builtins
        self._macros = dict(BUILTIN_MACROS)

        # Load user-defined macros
        try:
            if MACROS_FILE.exists():
                data = json.loads(MACROS_FILE.read_text(encoding="utf-8"))
                for key, macro_data in data.get("macros", {}).items():
                    self._macros[key.lower()] = macro_data
                logger.info(f"[Macros] Loaded {len(data.get('macros', {}))} user macros.")
        except Exception as e:
            logger.warning(f"[Macros] Could not load macros file: {e}")

    def _save_macros(self):
        """Save user-defined macros (excluding builtins) to config/macros.json."""
        try:
            MACROS_FILE.parent.mkdir(parents=True, exist_ok=True)
            user_macros = {k: v for k, v in self._macros.items() if k not in BUILTIN_MACROS}
            data = {"macros": user_macros}
            MACROS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error(f"[Macros] Save failed: {e}")

    def create_macro(self, name: str, description: str, steps: List[Dict[str, Any]], tags: List[str] = None) -> Dict[str, Any]:
        """Create a new named macro."""
        key = name.lower().replace(" ", "_")
        self._macros[key] = {
            "name": name,
            "description": description,
            "steps": steps,
            "tags": tags or [],
            "created_at": time.time(),
        }
        self._save_macros()
        return {"success": True, "message": f"Macro '{name}' created with {len(steps)} steps."}

    def list_macros(self) -> List[Dict[str, Any]]:
        """Return all available macros."""
        return [
            {"key": k, "name": v.get("name", k), "description": v.get("description", ""), "steps": len(v.get("steps", [])), "tags": v.get("tags", [])}
            for k, v in self._macros.items()
        ]

    def get_macro(self, name: str) -> Optional[Dict[str, Any]]:
        key = name.lower().replace(" ", "_")
        return self._macros.get(key)

    def delete_macro(self, name: str) -> bool:
        key = name.lower().replace(" ", "_")
        if key in BUILTIN_MACROS:
            return False  # Cannot delete builtins
        if key in self._macros:
            del self._macros[key]
            self._save_macros()
            return True
        return False

    def run_macro(self, name: str, player=None, speak_fn=None) -> Dict[str, Any]:
        """Execute a macro by name."""
        macro = self.get_macro(name)
        if not macro:
            return {"success": False, "message": f"Macro '{name}' not found."}

        steps = macro.get("steps", [])
        results = []

        for i, step in enumerate(steps):
            tool_name = step.get("tool", "")
            params = step.get("params", step.get("parameters", {}))
            desc = step.get("description", f"Step {i + 1}")

            try:
                from core.register_tools import default_tool_registry
                tool = default_tool_registry.get_tool(tool_name)
                if tool:
                    res = default_tool_registry.execute_tool(tool_name, params, player=player, speak=speak_fn)
                    result_msg = res.message if hasattr(res, "message") else str(res)
                    results.append({"step": i + 1, "tool": tool_name, "status": "COMPLETED", "message": result_msg[:200]})
                else:
                    results.append({"step": i + 1, "tool": tool_name, "status": "FAILED", "message": f"Tool '{tool_name}' not found"})
            except Exception as e:
                results.append({"step": i + 1, "tool": tool_name, "status": "FAILED", "message": str(e)[:200]})

        completed = sum(1 for r in results if r["status"] == "COMPLETED")
        summary = f"Macro '{macro.get('name', name)}': {completed}/{len(results)} steps completed."
        if speak_fn:
            speak_fn(summary)

        return {"success": completed == len(results), "message": summary, "steps": results}


# Global singleton
_MACRO_MANAGER: Optional[MacroManager] = None

def get_macro_manager() -> MacroManager:
    global _MACRO_MANAGER
    if _MACRO_MANAGER is None:
        _MACRO_MANAGER = MacroManager()
    return _MACRO_MANAGER


def macro_executor(
    parameters: Optional[Dict[str, Any]] = None,
    response: Any = None,
    player: Any = None,
    session_memory: Any = None,
    speak: Any = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Standard tool entry point for the Macro system."""
    params = dict(parameters) if isinstance(parameters, dict) else {}
    if kwargs:
        for k, v in kwargs.items():
            if k not in ("speak", "player", "response", "session_memory") and k not in params:
                params[k] = v

    action = params.get("action", "list").lower()
    mgr = get_macro_manager()

    if action == "run":
        name = params.get("name", params.get("macro_name", ""))
        return mgr.run_macro(name, player=player, speak_fn=speak)

    elif action == "create":
        name = params.get("name", "Untitled Macro")
        desc = params.get("description", "")
        steps = params.get("steps", [])
        tags = params.get("tags", [])
        return mgr.create_macro(name, desc, steps, tags)

    elif action == "list":
        macros = mgr.list_macros()
        if not macros:
            return {"success": True, "message": "No macros available."}
        msg = "Available macros:\n" + "\n".join(f"- {m['name']}: {m['description']} ({m['steps']} steps)" for m in macros)
        return {"success": True, "message": msg}

    elif action == "delete":
        name = params.get("name", "")
        ok = mgr.delete_macro(name)
        return {"success": ok, "message": f"Deleted macro '{name}'." if ok else f"Macro '{name}' not found or is built-in."}

    return {"success": False, "message": f"Unknown macro action: {action}"}
