# jarvis_api/client.py
# Public Python Client SDK for JARVIS

import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from jarvis_api.config import JarvisConfig
from jarvis_api.models import ToolResultModel, TaskResultModel, HealthStatusModel, MemoryResultModel
from jarvis_api.exceptions import JarvisError, ToolNotFoundError, ValidationError

from core.register_tools import default_tool_registry
from core.health_check import run_startup_health_check
from memory.memory_manager import load_memory, update_memory


class JarvisAPI:
    """
    Public Python Client SDK providing programmatic control over JARVIS.
    Connects directly to the unified JARVIS execution pipeline.
    """
    def __init__(self, config: Optional[JarvisConfig] = None):
        self.config = config or JarvisConfig()
        self.base_dir = self.config.base_dir

    def get_status(self) -> HealthStatusModel:
        """
        Runs diagnostic system check and returns operational health status.
        """
        all_passed, summary = run_startup_health_check(self.base_dir)
        status_str = "online" if all_passed else "degraded"
        return HealthStatusModel(
            status=status_str,
            version="1.0.0",
            all_systems_operational=all_passed,
            diagnostics={"summary": summary}
        )

    def list_tools(self) -> List[Dict[str, Any]]:
        """
        Returns registered tool definitions and metadata.
        """
        result = []
        for name in default_tool_registry.list_tools():
            tool = default_tool_registry.get_tool(name)
            if tool:
                result.append({
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                    "risk_level": tool.risk_level.value,
                    "timeout": tool.timeout,
                })
        return result

    def call_tool(self, tool_name: str, args: Optional[Dict[str, Any]] = None) -> ToolResultModel:
        """
        Executes a registered tool through ToolRegistry parameter validation,
        SecurityManager authorization, execution, and verification.
        """
        args = args or {}
        tool = default_tool_registry.get_tool(tool_name)
        if not tool:
            raise ToolNotFoundError(f"Tool '{tool_name}' is not registered in ToolRegistry.")

        res = default_tool_registry.execute_tool(tool_name, args)
        return ToolResultModel(
            success=res.success,
            tool=res.tool,
            message=res.message,
            data=res.data,
            verification=res.verification,
            error=res.error,
            execution_time_ms=res.execution_time_ms
        )

    def execute(self, command_text: str) -> ToolResultModel:
        """
        Executes a natural language command by detecting intent or launching open_app/computer_settings.
        """
        cmd = command_text.strip().lower()

        # Command intent resolution
        if cmd.startswith("open ") or cmd.startswith("launch "):
            app_name = cmd.replace("open ", "").replace("launch ", "").strip()
            return self.call_tool("open_app", {"app_name": app_name})

        if "volume" in cmd or "mute" in cmd or "close " in cmd:
            return self.call_tool("computer_settings", {"description": command_text})

        if "screenshot" in cmd:
            return self.call_tool("computer_control", {"action": "screenshot"})

        # Fallback to web search if query-like
        return self.call_tool("web_search", {"query": command_text})

    def run_task(self, goal_description: str, priority: str = "normal") -> TaskResultModel:
        """
        Submits an autonomous multi-step planner task to the task queue.
        """
        from agent.task_queue import get_queue, TaskPriority
        pmap = {"low": TaskPriority.LOW, "normal": TaskPriority.NORMAL, "high": TaskPriority.HIGH}
        p_val = pmap.get(priority.lower(), TaskPriority.NORMAL)

        task_id = get_queue().submit(goal=goal_description, priority=p_val)
        return TaskResultModel(
            task_id=str(task_id),
            status="RUNNING",
            goal=goal_description,
            created_at=time.time(),
            result=f"Task submitted with ID: {task_id}",
            steps=[]
        )

    def remember(self, key: str, value: Any, category: str = "notes") -> MemoryResultModel:
        """
        Saves a persistent fact to JARVIS long-term memory.
        """
        update_memory({category: {key: {"value": str(value)}}})
        return MemoryResultModel(
            success=True,
            category=category,
            key=key,
            value=value
        )

    def get_memory(self, category: Optional[str] = None, key: Optional[str] = None) -> Any:
        """
        Retrieves facts from persistent memory.
        """
        mem = load_memory()
        if category and key:
            return mem.get(category, {}).get(key, {}).get("value")
        if category:
            return mem.get(category, {})
        return mem

    def delete_memory(self, category: str, key: str) -> bool:
        """
        Deletes a fact from long-term memory.
        """
        mem = load_memory()
        if category in mem and key in mem[category]:
            del mem[category][key]
            from memory.memory_manager import save_memory
            save_memory(mem)
            return True
        return False

    def analyze_screen(self, question: str = "What is visible on screen?") -> ToolResultModel:
        """
        Runs vision analysis on the current display screen.
        """
        return self.call_tool("computer_control", {"action": "screenshot"})
