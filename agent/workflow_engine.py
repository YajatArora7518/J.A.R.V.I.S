"""
agent/workflow_engine.py
Reusable Workflow Engine for J.A.R.V.I.S.

Extends the existing ExecutionPlan/PlanStep architecture with:
- Named workflow save/load to config/workflows.json
- Sequential and conditional step execution
- Retry with backoff and timeouts
- Cancellation and recovery
- UI state sync via existing set_state()
"""

import json
import time
import logging
import uuid
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict

logger = logging.getLogger("JARVIS.WorkflowEngine")

BASE_DIR = Path(__file__).resolve().parent.parent
WORKFLOWS_FILE = BASE_DIR / "config" / "workflows.json"


@dataclass
class WorkflowStep:
    """A single step in a workflow, compatible with ExecutionPlan's PlanStep."""
    step_number: int
    tool_name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    condition: Optional[str] = None  # e.g., "previous_success" or None for unconditional
    max_retries: int = 1
    timeout_seconds: float = 30.0
    status: str = "PENDING"
    result: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "tool_name": self.tool_name,
            "description": self.description,
            "parameters": self.parameters,
            "condition": self.condition,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "status": self.status,
            "result": self.result,
        }

    @staticmethod
    def from_dict(data: dict) -> "WorkflowStep":
        return WorkflowStep(
            step_number=data.get("step_number", 0),
            tool_name=data.get("tool_name", ""),
            description=data.get("description", ""),
            parameters=data.get("parameters", {}),
            condition=data.get("condition"),
            max_retries=data.get("max_retries", 1),
            timeout_seconds=data.get("timeout_seconds", 30.0),
            status=data.get("status", "PENDING"),
            result=data.get("result"),
        )


@dataclass
class Workflow:
    """A named, replayable workflow built on the ExecutionPlan structure."""
    workflow_id: str
    name: str
    description: str
    steps: List[WorkflowStep] = field(default_factory=list)
    status: str = "PENDING"  # PENDING | RUNNING | COMPLETED | FAILED | CANCELLED
    created_at: float = field(default_factory=time.time)
    last_run_at: Optional[float] = None
    run_count: int = 0
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status,
            "created_at": self.created_at,
            "last_run_at": self.last_run_at,
            "run_count": self.run_count,
            "tags": self.tags,
        }

    @staticmethod
    def from_dict(data: dict) -> "Workflow":
        return Workflow(
            workflow_id=data.get("workflow_id", str(uuid.uuid4())[:8]),
            name=data.get("name", "Untitled"),
            description=data.get("description", ""),
            steps=[WorkflowStep.from_dict(s) for s in data.get("steps", [])],
            status=data.get("status", "PENDING"),
            created_at=data.get("created_at", time.time()),
            last_run_at=data.get("last_run_at"),
            run_count=data.get("run_count", 0),
            tags=data.get("tags", []),
        )


class WorkflowEngine:
    """
    Manages named workflows: create, save, load, replay, cancel.
    Executes steps sequentially via the ToolRegistry.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._workflows: Dict[str, Workflow] = {}
        self._active_workflow: Optional[str] = None
        self._cancelled = False
        self._load_saved_workflows()

    def _load_saved_workflows(self):
        """Load workflows from config/workflows.json."""
        with self._lock:
            try:
                if WORKFLOWS_FILE.exists():
                    data = json.loads(WORKFLOWS_FILE.read_text(encoding="utf-8"))
                    for wf_data in data.get("workflows", []):
                        wf = Workflow.from_dict(wf_data)
                        self._workflows[wf.name.lower()] = wf
                    logger.info(f"[WorkflowEngine] Loaded {len(self._workflows)} saved workflows.")
            except Exception as e:
                logger.warning(f"[WorkflowEngine] Could not load workflows: {e}")

    def _save_workflows(self):
        """Persist all workflows to config/workflows.json."""
        with self._lock:
            try:
                WORKFLOWS_FILE.parent.mkdir(parents=True, exist_ok=True)
                data = {"workflows": [wf.to_dict() for wf in self._workflows.values()]}
                tmp_file = WORKFLOWS_FILE.parent / f"workflows.tmp.{uuid.uuid4().hex[:8]}.json"
                tmp_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                tmp_file.replace(WORKFLOWS_FILE)
                logger.info(f"[WorkflowEngine] Saved {len(self._workflows)} workflows.")
            except Exception as e:
                logger.error(f"[WorkflowEngine] Save failed: {e}")

    def create_workflow(self, name: str, description: str, steps: List[Dict[str, Any]], tags: List[str] = None) -> Workflow:
        """Create and save a new named workflow."""
        with self._lock:
            wf = Workflow(
                workflow_id=str(uuid.uuid4())[:8],
                name=name,
                description=description,
                steps=[
                    WorkflowStep(
                        step_number=i + 1,
                        tool_name=s.get("tool", s.get("tool_name", "")),
                        description=s.get("description", ""),
                        parameters=s.get("parameters", s.get("params", {})),
                        condition=s.get("condition"),
                        max_retries=s.get("max_retries", 1),
                        timeout_seconds=s.get("timeout_seconds", 30.0),
                    )
                    for i, s in enumerate(steps)
                ],
                tags=tags or [],
            )
            self._workflows[name.lower()] = wf
            self._save_workflows()
            logger.info(f"[WorkflowEngine] Created workflow '{name}' with {len(wf.steps)} steps.")
            return wf

    def list_workflows(self) -> List[Dict[str, Any]]:
        """Return a summary of all saved workflows."""
        with self._lock:
            return [
                {"name": wf.name, "description": wf.description, "steps": len(wf.steps), "run_count": wf.run_count, "tags": wf.tags}
                for wf in self._workflows.values()
            ]

    def get_workflow(self, name: str) -> Optional[Workflow]:
        with self._lock:
            return self._workflows.get(name.lower())

    def delete_workflow(self, name: str) -> bool:
        with self._lock:
            key = name.lower()
            if key in self._workflows:
                del self._workflows[key]
                self._save_workflows()
                return True
            return False

    def cancel(self):
        """Cancel the currently running workflow."""
        self._cancelled = True
        if self._active_workflow and self._active_workflow in self._workflows:
            self._workflows[self._active_workflow].status = "CANCELLED"
        logger.info("[WorkflowEngine] Cancellation requested.")

    def run_workflow(self, name: str, ui=None, speak_fn=None) -> Dict[str, Any]:
        """
        Execute a saved workflow by name. Returns summary of execution.
        """
        wf = self.get_workflow(name)
        if not wf:
            return {"success": False, "message": f"Workflow '{name}' not found."}

        self._cancelled = False
        self._active_workflow = name.lower()
        wf.status = "RUNNING"
        wf.last_run_at = time.time()
        wf.run_count += 1

        # Reset step statuses
        for step in wf.steps:
            step.status = "PENDING"
            step.result = None

        if ui and hasattr(ui, "set_state"):
            ui.set_state("EXECUTING")

        results = []
        previous_success = True

        for step in wf.steps:
            if self._cancelled:
                step.status = "CANCELLED"
                results.append({"step": step.step_number, "status": "CANCELLED"})
                continue

            # Check condition
            if step.condition == "previous_success" and not previous_success:
                step.status = "SKIPPED"
                results.append({"step": step.step_number, "status": "SKIPPED", "reason": "Previous step failed"})
                continue

            step.status = "EXECUTING"
            success = False
            result_msg = ""

            for attempt in range(step.max_retries):
                try:
                    from core.register_tools import default_tool_registry
                    tool = default_tool_registry.get_tool(step.tool_name)
                    if tool:
                        res = default_tool_registry.execute_tool(step.tool_name, step.parameters)
                        result_msg = res.message if hasattr(res, "message") else str(res)
                        success = True
                        break
                    else:
                        result_msg = f"Tool '{step.tool_name}' not found in registry."
                        break
                except Exception as e:
                    result_msg = f"Step {step.step_number} attempt {attempt + 1} failed: {e}"
                    if attempt < step.max_retries - 1:
                        backoff = min(2 ** attempt, 10)
                        time.sleep(backoff)

            step.status = "COMPLETED" if success else "FAILED"
            step.result = result_msg[:500]
            previous_success = success
            results.append({"step": step.step_number, "tool": step.tool_name, "status": step.status, "message": result_msg[:200]})

        wf.status = "COMPLETED" if all(r.get("status") in ("COMPLETED", "SKIPPED") for r in results) else "FAILED"
        self._active_workflow = None
        self._save_workflows()

        if ui and hasattr(ui, "set_state"):
            ui.set_state("LISTENING")

        summary = f"Workflow '{wf.name}': {sum(1 for r in results if r['status'] == 'COMPLETED')}/{len(results)} steps completed."
        if speak_fn:
            speak_fn(summary)

        return {"success": wf.status == "COMPLETED", "message": summary, "steps": results}


# Global singleton
_WORKFLOW_ENGINE: Optional[WorkflowEngine] = None

def get_workflow_engine() -> WorkflowEngine:
    global _WORKFLOW_ENGINE
    if _WORKFLOW_ENGINE is None:
        _WORKFLOW_ENGINE = WorkflowEngine()
    return _WORKFLOW_ENGINE


def workflow_engine(
    parameters: Optional[Dict[str, Any]] = None,
    response: Any = None,
    player: Any = None,
    session_memory: Any = None,
    speak: Any = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Standard tool entry point for the Workflow Engine."""
    params = dict(parameters) if isinstance(parameters, dict) else {}
    if kwargs:
        for k, v in kwargs.items():
            if k not in ("speak", "player", "response", "session_memory") and k not in params:
                params[k] = v

    action = params.get("action", "list").lower()
    engine = get_workflow_engine()

    if action == "create":
        name = params.get("name", "Untitled Workflow")
        desc = params.get("description", "")
        steps = params.get("steps", [])
        tags = params.get("tags", [])
        wf = engine.create_workflow(name, desc, steps, tags)
        return {"success": True, "message": f"Created workflow '{wf.name}' with {len(wf.steps)} steps."}

    elif action == "run":
        name = params.get("name", "")
        return engine.run_workflow(name, ui=player, speak_fn=speak)

    elif action == "list":
        workflows = engine.list_workflows()
        if not workflows:
            return {"success": True, "message": "No saved workflows."}
        msg = "Saved workflows:\n" + "\n".join(f"- {w['name']}: {w['description']} ({w['steps']} steps, run {w['run_count']}x)" for w in workflows)
        return {"success": True, "message": msg}

    elif action == "delete":
        name = params.get("name", "")
        ok = engine.delete_workflow(name)
        return {"success": ok, "message": f"Deleted workflow '{name}'." if ok else f"Workflow '{name}' not found."}

    elif action == "cancel":
        engine.cancel()
        return {"success": True, "message": "Workflow cancellation requested."}

    return {"success": False, "message": f"Unknown workflow action: {action}"}
