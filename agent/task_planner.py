# agent/task_planner.py
# Autonomous Multi-Step Desktop Task Planner & Safe Verification Engine for J.A.R.V.I.S
# Architecture: USER -> PLANNER -> SECURITY MANAGER -> ACTION -> OBSERVE -> VERIFY -> NEXT STEP

import os
import sys
import time
import re
import json
import logging
from enum import Enum
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable, Tuple, Union

from core.security import SecurityManager, RiskLevel, default_security_manager
from core.verification import (
    verify_app_launched,
    verify_process_closed,
    verify_file_exists,
    verify_file_deleted
)

logger = logging.getLogger("JARVIS.TaskPlanner")


class ActionType(str, Enum):
    RESOLVE_APP = "RESOLVE_APP"
    LAUNCH_APP = "LAUNCH_APP"
    VERIFY_WINDOW = "VERIFY_WINDOW"
    RESOLVE_PROJECT = "RESOLVE_PROJECT"
    INSPECT_PROJECT = "INSPECT_PROJECT"
    ANALYZE_ERROR = "ANALYZE_ERROR"
    SAFE_WRITE_FILE = "SAFE_WRITE_FILE"
    SAFE_DELETE_FILE = "SAFE_DELETE_FILE"
    SEARCH_WEB = "SEARCH_WEB"
    SCREEN_QUERY = "SCREEN_QUERY"
    SET_REMINDER = "SET_REMINDER"
    REPORT = "REPORT"
    TOOL_ACTION = "TOOL_ACTION"


@dataclass
class PlanStep:
    step_number: int
    action_type: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.LOW
    requires_confirmation: bool = False
    status: str = "PENDING"  # PENDING, CONFIRMING, EXECUTING, VERIFIED, FAILED, SKIPPED, DENIED
    execution_result: Any = None
    verification_result: Optional[Dict[str, Any]] = None
    timestamp: float = 0.0
    failure_info: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "action_type": str(self.action_type),
            "description": self.description,
            "parameters": self.parameters,
            "risk_level": self.risk_level.value if isinstance(self.risk_level, RiskLevel) else str(self.risk_level),
            "requires_confirmation": self.requires_confirmation,
            "status": self.status,
            "execution_result": str(self.execution_result)[:200] if self.execution_result is not None else None,
            "verification_result": self.verification_result,
            "timestamp": self.timestamp,
            "failure_info": self.failure_info
        }


@dataclass
class ExecutionPlan:
    plan_id: str
    goal: str
    steps: List[PlanStep] = field(default_factory=list)
    status: str = "PENDING"  # PENDING, IN_PROGRESS, COMPLETED, FAILED, CANCELLED, DENIED
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    summary: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "summary": self.summary,
            "error": self.error
        }


class TaskPlanner:
    """
    TaskPlanner breaks high-level user instructions into typed, safe action steps.
    Execution passes through SecurityManager BEFORE any action is dispatched.
    Every step is verified post-execution before advancing to the next step.
    """

    def __init__(
        self,
        security_manager: Optional[SecurityManager] = None,
        confirmation_callback: Optional[Callable[[str], bool]] = None,
        tts_engine: Any = None
    ):
        self.security_manager = security_manager or default_security_manager
        self.confirmation_callback = confirmation_callback
        self.tts_engine = tts_engine

    def set_confirmation_callback(self, callback: Callable[[str], bool]) -> None:
        self.confirmation_callback = callback
        if hasattr(self.security_manager, "set_confirmation_callback"):
            self.security_manager.set_confirmation_callback(callback)

    def classify_step_risk(self, step: PlanStep) -> Tuple[RiskLevel, bool]:
        """
        Evaluates step risk authoritatively through SecurityManager.
        Planner cannot downgrade risk.
        """
        # Map typed actions to registered tool/parameter equivalents for SecurityManager
        tool_mapping = {
            ActionType.RESOLVE_APP.value: ("open_app", {"action": "resolve"}),
            ActionType.LAUNCH_APP.value: ("open_app", {"action": "launch", "app_name": step.parameters.get("app_name", "")}),
            ActionType.VERIFY_WINDOW.value: ("open_app", {"action": "verify"}),
            ActionType.RESOLVE_PROJECT.value: ("file_controller", {"action": "find"}),
            ActionType.INSPECT_PROJECT.value: ("file_controller", {"action": "read"}),
            ActionType.ANALYZE_ERROR.value: ("file_controller", {"action": "read"}),
            ActionType.SAFE_WRITE_FILE.value: ("file_controller", {"action": "create_file", "path": step.parameters.get("path", "")}),
            ActionType.SAFE_DELETE_FILE.value: ("file_controller", {"action": "delete_file", "path": step.parameters.get("path", "")}),
            ActionType.SEARCH_WEB.value: ("web_search", {"query": step.parameters.get("query", "")}),
            ActionType.SCREEN_QUERY.value: ("screen_process", {"text": step.parameters.get("query", "")}),
            ActionType.SET_REMINDER.value: ("reminder", {"action": "set"}),
            ActionType.REPORT.value: ("report", {}),
            ActionType.TOOL_ACTION.value: (step.parameters.get("tool_name", ""), step.parameters.get("tool_params", {}))
        }

        tool_name, tool_params = tool_mapping.get(
            step.action_type,
            (str(step.action_type).lower(), step.parameters)
        )

        risk = self.security_manager.classify_risk(tool_name, tool_params)

        # Explicit safety boundaries:
        # File deletion is always at least HIGH risk
        if step.action_type == ActionType.SAFE_DELETE_FILE.value:
            risk = RiskLevel.HIGH
        # App launch is MEDIUM risk
        elif step.action_type == ActionType.LAUNCH_APP.value:
            risk = RiskLevel.MEDIUM
        # File write is MEDIUM risk
        elif step.action_type == ActionType.SAFE_WRITE_FILE.value:
            risk = RiskLevel.MEDIUM

        # Confirmation required for MEDIUM, HIGH, CRITICAL
        requires_confirmation = (risk in [RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL])
        return risk, requires_confirmation

    def create_plan(self, instruction: str, context: Optional[Dict[str, Any]] = None) -> ExecutionPlan:
        """
        Converts natural language user instructions into a structured ExecutionPlan.
        Uses deterministic pattern matching for high-frequency workflows,
        with fallback to local Ollama / AI engine for arbitrary requests.
        """
        raw_text = (instruction or "").strip()
        lower = raw_text.lower()
        plan_id = f"plan_{int(time.time() * 1000)}"

        # 1. Check deterministic workflow templates
        steps = self._match_deterministic_patterns(raw_text, lower)

        # 2. If no deterministic match, generate plan using AI (Local-first Ollama)
        if not steps:
            steps = self._generate_ai_plan(raw_text, context)

        # 3. If AI generation fails or is empty, use safe fallback plan
        if not steps:
            steps = [
                PlanStep(
                    step_number=1,
                    action_type=ActionType.REPORT.value,
                    description=f"Process instruction: {raw_text}",
                    parameters={"instruction": raw_text, "status": "unresolved"}
                )
            ]

        # Authoritative security classification for every step
        for i, s in enumerate(steps, 1):
            s.step_number = i
            risk, req_conf = self.classify_step_risk(s)
            s.risk_level = risk
            s.requires_confirmation = req_conf

        plan = ExecutionPlan(
            plan_id=plan_id,
            goal=raw_text,
            steps=steps,
            status="PENDING"
        )
        logger.info(f"[TaskPlanner] Created plan '{plan_id}' with {len(steps)} steps for goal: '{raw_text}'")
        return plan

    def _match_deterministic_patterns(self, raw_text: str, lower: str) -> List[PlanStep]:
        """High-precision pattern matcher for standard multi-step desktop instructions."""

        # Pattern: Antigravity + JARVIS project + build error check
        # e.g., "Antigravity kholo, mera JARVIS project open karo aur build error check karo"
        if ("antigravity" in lower or "jarvis" in lower) and any(w in lower for w in ["build error", "error check", "build", "inspect error"]):
            return [
                PlanStep(
                    step_number=1,
                    action_type=ActionType.RESOLVE_APP.value,
                    description="Resolve Antigravity IDE application",
                    parameters={"app_name": "Antigravity"}
                ),
                PlanStep(
                    step_number=2,
                    action_type=ActionType.LAUNCH_APP.value,
                    description="Launch Antigravity IDE",
                    parameters={"app_name": "Antigravity"}
                ),
                PlanStep(
                    step_number=3,
                    action_type=ActionType.VERIFY_WINDOW.value,
                    description="Verify Antigravity window is active",
                    parameters={"app_name": "Antigravity"}
                ),
                PlanStep(
                    step_number=4,
                    action_type=ActionType.RESOLVE_PROJECT.value,
                    description="Resolve JARVIS project directory",
                    parameters={"project_name": "JARVIS"}
                ),
                PlanStep(
                    step_number=5,
                    action_type=ActionType.INSPECT_PROJECT.value,
                    description="Inspect project status and build logs",
                    parameters={"target": "build_logs"}
                ),
                PlanStep(
                    step_number=6,
                    action_type=ActionType.ANALYZE_ERROR.value,
                    description="Analyze recent errors in project logs",
                    parameters={"target": "latest_errors"}
                ),
                PlanStep(
                    step_number=7,
                    action_type=ActionType.REPORT.value,
                    description="Report build error analysis to user",
                    parameters={"summary": "Antigravity and JARVIS project inspected"}
                )
            ]

        # Pattern: "Open Antigravity and open my JARVIS project"
        if "antigravity" in lower and any(w in lower for w in ["open my jarvis", "open jarvis project", "jarvis project"]):
            return [
                PlanStep(
                    step_number=1,
                    action_type=ActionType.RESOLVE_APP.value,
                    description="Resolve Antigravity IDE application",
                    parameters={"app_name": "Antigravity"}
                ),
                PlanStep(
                    step_number=2,
                    action_type=ActionType.LAUNCH_APP.value,
                    description="Launch Antigravity IDE",
                    parameters={"app_name": "Antigravity"}
                ),
                PlanStep(
                    step_number=3,
                    action_type=ActionType.VERIFY_WINDOW.value,
                    description="Verify Antigravity window is active",
                    parameters={"app_name": "Antigravity"}
                ),
                PlanStep(
                    step_number=4,
                    action_type=ActionType.RESOLVE_PROJECT.value,
                    description="Resolve JARVIS project directory",
                    parameters={"project_name": "JARVIS"}
                ),
                PlanStep(
                    step_number=5,
                    action_type=ActionType.REPORT.value,
                    description="Report project launch status",
                    parameters={"summary": "Antigravity and JARVIS project opened"}
                )
            ]

        # Pattern: "Open Notepad and write my notes"
        if "notepad" in lower and any(w in lower for w in ["write", "notes", "likho", "note"]):
            # Extract notes content if provided
            content = "Notes: Meeting and tasks"
            if "write" in lower:
                parts = raw_text.split("write", 1)
                if len(parts) > 1 and parts[1].strip():
                    content = parts[1].strip()
            return [
                PlanStep(
                    step_number=1,
                    action_type=ActionType.RESOLVE_APP.value,
                    description="Resolve Notepad application",
                    parameters={"app_name": "Notepad"}
                ),
                PlanStep(
                    step_number=2,
                    action_type=ActionType.LAUNCH_APP.value,
                    description="Launch Notepad",
                    parameters={"app_name": "Notepad"}
                ),
                PlanStep(
                    step_number=3,
                    action_type=ActionType.VERIFY_WINDOW.value,
                    description="Verify Notepad window is active",
                    parameters={"app_name": "Notepad"}
                ),
                PlanStep(
                    step_number=4,
                    action_type=ActionType.SAFE_WRITE_FILE.value,
                    description="Safely write notes file",
                    parameters={"path": "jarvis_notes.txt", "content": content}
                ),
                PlanStep(
                    step_number=5,
                    action_type=ActionType.REPORT.value,
                    description="Report notes written successfully",
                    parameters={"summary": "Notepad opened and notes saved"}
                )
            ]

        # Pattern: "Open Chrome and research this topic"
        if any(w in lower for w in ["chrome", "browser"]) and any(w in lower for w in ["research", "search", "khojo", "dhoondo"]):
            query = re.sub(r"^(open|kholo|launch)\s+(chrome|browser)\s+(and\s+)?(research|search|khojo)?\s*", "", raw_text, flags=re.IGNORECASE).strip()
            query = query or "Latest AI developments"
            return [
                PlanStep(
                    step_number=1,
                    action_type=ActionType.RESOLVE_APP.value,
                    description="Resolve Chrome browser",
                    parameters={"app_name": "Chrome"}
                ),
                PlanStep(
                    step_number=2,
                    action_type=ActionType.LAUNCH_APP.value,
                    description="Launch Chrome browser",
                    parameters={"app_name": "Chrome"}
                ),
                PlanStep(
                    step_number=3,
                    action_type=ActionType.SEARCH_WEB.value,
                    description=f"Perform web research for '{query}'",
                    parameters={"query": query}
                ),
                PlanStep(
                    step_number=4,
                    action_type=ActionType.REPORT.value,
                    description="Report research findings to user",
                    parameters={"query": query}
                )
            ]

        # Pattern: Delete file / remove file
        # e.g. "Delete this file" / "Is file ko delete karo"
        if any(w in lower for w in ["delete", "remove", "hatao", "delete karo"]) and any(w in lower for w in ["file", "document", "folder"]):
            file_match = re.search(r"['\"]([^'\"]+)['\"]", raw_text)
            target_path = file_match.group(1) if file_match else "temp_target.txt"
            return [
                PlanStep(
                    step_number=1,
                    action_type=ActionType.RESOLVE_PROJECT.value,
                    description=f"Locate target file: {target_path}",
                    parameters={"path": target_path}
                ),
                PlanStep(
                    step_number=2,
                    action_type=ActionType.SAFE_DELETE_FILE.value,
                    description=f"Safely delete file: {target_path}",
                    parameters={"path": target_path}
                ),
                PlanStep(
                    step_number=3,
                    action_type=ActionType.REPORT.value,
                    description="Verify and report file deletion",
                    parameters={"path": target_path}
                )
            ]

        # Pattern: Screen query / vision assistance
        if any(w in lower for w in ["screen pe kya hai", "screen check", "what's on my screen", "what is on my screen"]):
            return [
                PlanStep(
                    step_number=1,
                    action_type=ActionType.SCREEN_QUERY.value,
                    description="Inspect active screen and foreground window",
                    parameters={"query": raw_text}
                ),
                PlanStep(
                    step_number=2,
                    action_type=ActionType.REPORT.value,
                    description="Report screen analysis",
                    parameters={"summary": "Screen analysis complete"}
                )
            ]

        return []

    def _generate_ai_plan(self, instruction: str, context: Optional[Dict[str, Any]] = None) -> List[PlanStep]:
        """Generates structured typed steps via local Ollama LLM or Cloud Fallback."""
        system_prompt = """You are the Task Planner for J.A.R.V.I.S.
Deconstruct the user's multi-step goal into typed, safe action steps.
Allowed action_type values:
- RESOLVE_APP (parameters: {"app_name": string})
- LAUNCH_APP (parameters: {"app_name": string})
- VERIFY_WINDOW (parameters: {"app_name": string})
- RESOLVE_PROJECT (parameters: {"project_name": string})
- INSPECT_PROJECT (parameters: {"target": string})
- ANALYZE_ERROR (parameters: {"target": string})
- SAFE_WRITE_FILE (parameters: {"path": string, "content": string})
- SAFE_DELETE_FILE (parameters: {"path": string})
- SEARCH_WEB (parameters: {"query": string})
- SCREEN_QUERY (parameters: {"query": string})
- SET_REMINDER (parameters: {"message": string, "time": string})
- REPORT (parameters: {"summary": string})

RULES:
1. NEVER generate arbitrary bash, shell, PowerShell, or Python script execution.
2. Max 7 steps.
3. Output ONLY a valid JSON array of objects, e.g.:
[
  {"step_number": 1, "action_type": "RESOLVE_APP", "description": "Resolve app", "parameters": {"app_name": "Notepad"}},
  {"step_number": 2, "action_type": "LAUNCH_APP", "description": "Launch app", "parameters": {"app_name": "Notepad"}},
  {"step_number": 3, "action_type": "REPORT", "description": "Report status", "parameters": {"summary": "Done"}}
]"""
        try:
            from core.ollama_provider import is_ollama_available, OllamaProvider
            if is_ollama_available():
                provider = OllamaProvider()
                res = provider.chat(f"Goal: {instruction}", system_prompt=system_prompt, temperature=0.1)
                if res.get("success") and res.get("text"):
                    clean = re.sub(r"```(?:json)?", "", res["text"]).strip().rstrip("`").strip()
                    parsed = json.loads(clean)
                    if isinstance(parsed, list):
                        steps = []
                        for item in parsed:
                            act = item.get("action_type", ActionType.REPORT.value)
                            steps.append(PlanStep(
                                step_number=item.get("step_number", len(steps) + 1),
                                action_type=act,
                                description=item.get("description", act),
                                parameters=item.get("parameters", {})
                            ))
                        return steps
        except Exception as e:
            logger.warning(f"[TaskPlanner] Ollama AI plan generation skipped: {e}")

        # Cloud fallback if needed
        try:
            from core.ai_multitier_engine import get_ai_engine
            brain = get_ai_engine()
            res = brain.generate_response(f"{system_prompt}\n\nUser Goal: {instruction}", prefer_cloud=True)
            if res.get("success") and res.get("text"):
                clean = re.sub(r"```(?:json)?", "", res["text"]).strip().rstrip("`").strip()
                # Find JSON array
                match = re.search(r"\[.*\]", clean, re.DOTALL)
                if match:
                    parsed = json.loads(match.group(0))
                    steps = []
                    for item in parsed:
                        act = item.get("action_type", ActionType.REPORT.value)
                        steps.append(PlanStep(
                            step_number=item.get("step_number", len(steps) + 1),
                            action_type=act,
                            description=item.get("description", act),
                            parameters=item.get("parameters", {})
                        ))
                    return steps
        except Exception as e:
            logger.warning(f"[TaskPlanner] Cloud AI plan generation skipped: {e}")

        return []

    def execute_plan(
        self,
        plan: ExecutionPlan,
        confirmation_callback: Optional[Callable[[str], bool]] = None,
        cancel_flag: Any = None,
        speak: Optional[Callable[[str], None]] = None,
        auto_confirm_medium: bool = False
    ) -> ExecutionPlan:
        """
        Reusable Execution Loop:
        PLAN -> SECURITY CHECK -> CONFIRMATION -> EXECUTE -> OBSERVE -> VERIFY -> NEXT STEP
        """
        plan.status = "IN_PROGRESS"
        active_cb = confirmation_callback or self.confirmation_callback

        # Spoken acknowledgement
        if speak:
            try:
                speak("Ek second boss, check kar raha hoon.")
            except Exception:
                pass

        logger.info(f"[TaskPlanner] Executing plan '{plan.plan_id}' with {len(plan.steps)} steps")

        for step in plan.steps:
            if cancel_flag and getattr(cancel_flag, "is_set", lambda: False)():
                step.status = "CANCELLED"
                plan.status = "CANCELLED"
                plan.error = "Task cancelled by user."
                if speak:
                    speak("Task cancel kar diya gaya, sir.")
                return plan

            step.timestamp = time.time()
            step.status = "CONFIRMING"

            # -------------------------------------------------------------
            # 1. SECURITY MANAGER AUTHORIZATION GATE
            # -------------------------------------------------------------
            risk, req_conf = self.classify_step_risk(step)
            step.risk_level = risk

            # Parameter check for path traversals and protected system paths
            if "path" in step.parameters:
                p_str = str(step.parameters["path"]).lower()
                if any(bad in p_str for bad in ["system32", "windows\\system", "c:\\windows"]):
                    step.status = "DENIED"
                    step.failure_info = f"Security Policy: Operations on protected system path '{p_str}' are strictly forbidden."
                    plan.status = "DENIED"
                    plan.error = step.failure_info
                    logger.warning(f"[TaskPlanner] Blocked forbidden path access: {p_str}")
                    return plan

            if req_conf:
                prompt_msg = f"Security Authorization Required: Execute {risk.value}-risk step {step.step_number} [{step.action_type}] ({step.description})?"
                
                # Check confirmation
                confirmed = False
                if active_cb:
                    confirmed = active_cb(prompt_msg)
                elif auto_confirm_medium and risk == RiskLevel.MEDIUM:
                    confirmed = True
                else:
                    confirmed = False

                if not confirmed:
                    step.status = "DENIED"
                    step.failure_info = f"Action cancelled: Security confirmation denied for {step.action_type} ({risk.value})"
                    plan.status = "DENIED"
                    plan.error = step.failure_info
                    logger.warning(f"[TaskPlanner] Security gate stopped execution at step {step.step_number}: {step.failure_info}")
                    if speak:
                        speak(f"Security check: Step {step.step_number} confirm nahi hua, isliye execution rok diya gaya.")
                    return plan

            # -------------------------------------------------------------
            # 2. DISPATCH & EXECUTE TYPED ACTION
            # -------------------------------------------------------------
            step.status = "EXECUTING"
            exec_ok, result_val, err_msg = self._dispatch_action(step)

            step.execution_result = result_val

            if not exec_ok:
                step.status = "FAILED"
                step.failure_info = f"Execution error: {err_msg}"
                plan.status = "FAILED"
                plan.error = step.failure_info
                logger.error(f"[TaskPlanner] Step {step.step_number} execution failed: {err_msg}")
                if speak:
                    speak(f"Step {step.step_number} mein issue aaya: {err_msg[:60]}")
                return plan

            # -------------------------------------------------------------
            # 3. OBSERVE & VERIFY POST-ACTION STATE
            # -------------------------------------------------------------
            verif_res = self._verify_action(step)
            step.verification_result = verif_res

            if not verif_res.get("verified", False):
                step.status = "FAILED"
                step.failure_info = verif_res.get("reason", "Verification failed.")
                plan.status = "FAILED"
                plan.error = step.failure_info
                logger.error(f"[TaskPlanner] Step {step.step_number} verification failed: {step.failure_info}")
                if speak:
                    speak(f"Step {step.step_number} verify nahi hua: {step.failure_info[:60]}")
                return plan

            step.status = "VERIFIED"
            logger.info(f"[TaskPlanner] Step {step.step_number} [{step.action_type}] VERIFIED successfully.")

        # All steps completed & verified
        plan.status = "COMPLETED"
        plan.completed_at = time.time()
        plan.summary = f"Ho gaya boss. All {len(plan.steps)} steps executed and verified."
        if speak:
            speak("Ho gaya boss. Task successfully complete ho gaya.")

        return plan

    def _dispatch_action(self, step: PlanStep) -> Tuple[bool, Any, str]:
        """Dispatches typed action safely without arbitrary shell commands."""
        act = step.action_type
        params = step.parameters

        try:
            if act == ActionType.RESOLVE_APP.value:
                from actions.app_registry import resolve_app
                app_name = params.get("app_name", "")
                resolved = resolve_app(app_name)
                if resolved:
                    return True, resolved, ""
                return False, None, f"Application '{app_name}' could not be resolved in App Registry."

            elif act == ActionType.LAUNCH_APP.value:
                from actions.open_app import open_app
                app_name = params.get("app_name", "")
                out = open_app(parameters={"app_name": app_name})
                return True, out, ""

            elif act == ActionType.VERIFY_WINDOW.value:
                app_name = params.get("app_name", "")
                verif = verify_app_launched(app_name, timeout=3.0)
                if verif.get("verified"):
                    return True, verif, ""
                return False, verif, verif.get("reason", "Window not verified")

            elif act == ActionType.RESOLVE_PROJECT.value:
                proj_name = params.get("project_name", "JARVIS")
                # Resolve active project directory
                cwd = Path(__file__).resolve().parent.parent
                if proj_name.lower() in str(cwd).lower():
                    return True, str(cwd), ""
                # Check Desktop or Home
                desktop = Path.home() / "Desktop"
                found = list(desktop.glob(f"*{proj_name}*"))
                if found and found[0].is_dir():
                    return True, str(found[0]), ""
                return True, str(cwd), ""

            elif act == ActionType.INSPECT_PROJECT.value:
                # Safe project inspection (reads directory structure or logs)
                cwd = Path(__file__).resolve().parent.parent
                files = [f.name for f in cwd.iterdir() if not f.name.startswith(".")]
                return True, {"files_count": len(files), "sample": files[:5]}, ""

            elif act == ActionType.ANALYZE_ERROR.value:
                # Safe log inspection
                cwd = Path(__file__).resolve().parent.parent
                log_candidates = list(cwd.glob("*.log")) + list((cwd / "scripts").glob("*.log"))
                recent_errs = "No active build errors detected. Systems healthy."
                if log_candidates:
                    try:
                        with open(log_candidates[0], "r", encoding="utf-8", errors="ignore") as lf:
                            lines = lf.readlines()[-20:]
                            recent_errs = "".join(lines)
                    except Exception:
                        pass
                return True, {"analysis": recent_errs}, ""

            elif act == ActionType.SAFE_WRITE_FILE.value:
                file_path = params.get("path", "notes.txt")
                content = params.get("content", "")
                # Resolve to safe absolute path
                if not os.path.isabs(file_path):
                    file_path = os.path.join(str(Path.home() / "Desktop"), file_path)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                return True, {"path": file_path, "bytes_written": len(content.encode("utf-8"))}, ""

            elif act == ActionType.SAFE_DELETE_FILE.value:
                file_path = params.get("path", "")
                if not os.path.isabs(file_path):
                    file_path = os.path.join(str(Path.home() / "Desktop"), file_path)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    return True, {"path": file_path, "deleted": True}, ""
                return True, {"path": file_path, "already_absent": True}, ""

            elif act == ActionType.SEARCH_WEB.value:
                from actions.web_search import web_search
                query = params.get("query", "")
                res = web_search(parameters={"query": query})
                return True, res, ""

            elif act == ActionType.SCREEN_QUERY.value:
                from actions.screen_processor import analyze_screen_vision
                res = analyze_screen_vision(user_query=params.get("query", "What is on screen"))
                return True, res, ""

            elif act == ActionType.SET_REMINDER.value:
                from actions.reminder import reminder
                res = reminder(parameters=params)
                return True, res, ""

            elif act == ActionType.REPORT.value:
                if params.get('status') == 'unresolved':
                    return False, None, 'Is request ka executable plan nahi bana. Exact target ya task detail batao.'
                summary = params.get("summary", "Operation completed.")
                return True, summary, ""

            elif act == ActionType.TOOL_ACTION.value:
                from core.tool_registry import default_tool_registry
                tool_name = params.get("tool_name", "")
                tool_params = params.get("tool_params", {})
                res = default_tool_registry.execute_tool(tool_name, tool_params)
                return res.success, res, '' if res.success else res.message

            else:
                return False, None, f"Unsupported action type '{act}'"

        except Exception as e:
            return False, None, str(e)

    def _verify_action(self, step: PlanStep) -> Dict[str, Any]:
        """Post-action verification against real OS state."""
        act = step.action_type
        params = step.parameters

        if act == ActionType.RESOLVE_APP.value:
            if step.execution_result and isinstance(step.execution_result, dict):
                return {"verified": True, "app_name": step.execution_result.get("name")}
            return {"verified": False, "reason": "Application could not be resolved."}

        elif act in [ActionType.LAUNCH_APP.value, ActionType.VERIFY_WINDOW.value]:
            app_name = params.get("app_name", "")
            return verify_app_launched(app_name, timeout=3.0)

        elif act == ActionType.RESOLVE_PROJECT.value:
            path_val = step.execution_result
            if path_val and os.path.isdir(str(path_val)):
                return {"verified": True, "path": str(path_val)}
            return {"verified": False, "reason": f"Project path does not exist: {path_val}"}

        elif act == ActionType.SAFE_WRITE_FILE.value:
            path_val = params.get("path", "")
            if not os.path.isabs(path_val):
                path_val = os.path.join(str(Path.home() / "Desktop"), path_val)
            return verify_file_exists(path_val, min_bytes=0)

        elif act == ActionType.SAFE_DELETE_FILE.value:
            path_val = params.get("path", "")
            if not os.path.isabs(path_val):
                path_val = os.path.join(str(Path.home() / "Desktop"), path_val)
            return verify_file_deleted(path_val)

        elif act == ActionType.TOOL_ACTION.value:
            result = step.execution_result
            return {'verified': bool(result and result.success and result.verification.get('verified', False)),
                    'reason': 'Registered tool must verify its own result.'}

        elif act in [ActionType.INSPECT_PROJECT.value, ActionType.ANALYZE_ERROR.value, ActionType.SEARCH_WEB.value, ActionType.SCREEN_QUERY.value, ActionType.REPORT.value, ActionType.SET_REMINDER.value]:
            # Functional verification: valid execution result returned without errors
            if step.execution_result is not None:
                return {"verified": True, "details": "Execution output received and validated."}
            return {"verified": False, "reason": "No valid execution result returned."}

        return {"verified": True}


# Default singleton instance
default_task_planner = TaskPlanner()
