# core/security.py
# Security & Confirmation Manager for JARVIS Tools

import sys
import enum
from typing import Dict, Any, Callable, Optional, Tuple


class RiskLevel(enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ActionConfirmationNeeded(Exception):
    """Raised when a HIGH or CRITICAL risk operation requires explicit user confirmation."""
    pass


class SecurityManager:
    """
    SecurityManager enforces tool classification, parameter sanitization,
    and user confirmation for high-risk or destructive actions.
    """

    def __init__(self, confirmation_callback: Optional[Callable[[str], bool]] = None):
        self.confirmation_callback = confirmation_callback

    def set_confirmation_callback(self, callback: Callable[[str], bool]) -> None:
        self.confirmation_callback = callback

    def classify_risk(self, tool_name: str, parameters: Dict[str, Any]) -> RiskLevel:
        name = tool_name.lower()
        action = str(parameters.get("action", "")).lower()
        elevated = bool(parameters.get("elevated", False))

        # Critical actions: drive formatting, system destruction, security bypass
        if action in ["format_drive", "delete_all", "disable_defender", "disable_firewall"] or "format" in action:
            return RiskLevel.CRITICAL

        # Elevated executions are HIGH risk
        if elevated:
            return RiskLevel.HIGH

        # High-risk actions: deleting files/dirs, service modification, shutdown/restart, closing apps/killing processes
        if name in ["shutdown_jarvis"]:
            return RiskLevel.HIGH
        if name in ["file_controller", "windows_system_controller"] and action in ["delete_file", "delete_directory", "delete", "remove"]:
            return RiskLevel.HIGH
        if name in ["computer_settings", "computer_control", "windows_system_controller"] and action in ["shutdown", "restart", "close_app", "kill_process", "terminate_process"]:
            return RiskLevel.HIGH
        if name in ["windows_service_control", "windows_services"] and action in ["start_service", "stop_service", "restart_service"]:
            return RiskLevel.HIGH

        # Medium-risk actions: create/write files, create scripts, move/copy/rename files, launch programs, start/stop non-critical processes, open applications
        if name in ["open_app", "open_application"]:
            return RiskLevel.MEDIUM
        if name in ["script_executor", "create_script", "run_script"]:
            if action in ["create_script", "run_script"]:
                return RiskLevel.MEDIUM
        if name in ["computer_settings", "browser_control", "desktop_control", "game_updater", "windows_system_controller"]:
            if action in ["create_file", "write_file", "append_file", "move_file", "copy_file", "rename_file", "create_directory"]:
                return RiskLevel.MEDIUM

        # Low-risk actions: read system info, list files, inspect processes, inspect services, web search
        return RiskLevel.LOW

    def validate_and_authorize(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        player: Any = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates parameters and requests confirmation for HIGH/CRITICAL risk actions.
        Returns (authorized, reason_if_denied).
        """
        risk = self.classify_risk(tool_name, parameters)

        # Parameter sanitization
        if "path" in parameters:
            path_str = str(parameters["path"]).lower()
            # Prevent accidental target of system root/windows system32 deletion
            if risk in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                if any(sys_dir in path_str for sys_dir in ["system32", "windows\\system", "c:\\windows"]):
                    return False, f"Action blocked: Operation on protected system path '{parameters['path']}' is strictly forbidden."

        if risk in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            prompt_msg = self._build_confirmation_prompt(tool_name, parameters, risk)

            if player and hasattr(player, "write_log"):
                player.write_log(f"SECURITY ALERT [{risk.value}]: {prompt_msg}")

            # If a UI/voice confirmation callback exists, ask
            if self.confirmation_callback:
                confirmed = self.confirmation_callback(prompt_msg)
                if not confirmed:
                    return False, f"Operation cancelled by user security prompt: {prompt_msg}"

        return True, None

    def check_permission(self, tool_name: str, parameters: Dict[str, Any]) -> None:
        risk = self.classify_risk(tool_name, parameters)
        if risk in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            if not self.confirmation_callback:
                raise ActionConfirmationNeeded(f"Explicit user confirmation required for {risk.value}-risk tool '{tool_name}'.")

    def _build_confirmation_prompt(self, tool_name: str, parameters: Dict[str, Any], risk: RiskLevel) -> str:
        action = parameters.get("action", tool_name)
        target = parameters.get("path") or parameters.get("app_name") or parameters.get("value") or ""
        return f"Confirm {risk.value}-risk action '{tool_name}' ({action} {target})?"


# Global singleton instance
default_security_manager = SecurityManager()
