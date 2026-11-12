# core/tool_registry.py
# Unified Tool Registry & Deterministic Dispatcher for JARVIS

import time
import inspect
from core.tool_invocation import invoke_tool
import logging
import traceback
from dataclasses import dataclass, field
from typing import Dict, Any, Callable, Optional, List, Tuple

from core.security import SecurityManager, RiskLevel, default_security_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("JARVIS.ToolRegistry")


@dataclass
class ToolResult:
    success: bool
    tool: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    verification: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "tool": self.tool,
            "message": self.message,
            "data": self.data,
            "verification": self.verification,
            "error": self.error,
            "execution_time_ms": round(self.execution_time_ms, 2),
        }

    def __str__(self) -> str:
        if self.success:
            verif_str = " (Verified)" if self.verification.get("verified") else ""
            return f"[{self.tool}] [OK] {self.message}{verif_str}"
        return f"[{self.tool}] [ERROR]: {self.error or self.message}"


class Tool:
    """
    Encapsulates a callable JARVIS capability.
    """
    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        execute_func: Optional[Callable[..., Any]] = None,
        verify_func: Optional[Callable[..., Dict[str, Any]]] = None,
        risk_level: RiskLevel = RiskLevel.LOW,
        timeout: float = 30.0,
        required_permissions: Optional[List[str]] = None,
        handler: Optional[Callable[..., Any]] = None,
        category: str = "general",
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.execute_func = execute_func or handler
        self.verify_func = verify_func
        self.risk_level = risk_level
        self.timeout = timeout
        self.required_permissions = required_permissions or []
        self.category = category

        # Pre-compute and cache signature + call strategy at registration time
        # to avoid expensive inspect.signature() on every execution hot-path
        self._cached_accepts_parameters: Optional[bool] = None
        self._cache_signature()

    def _cache_signature(self) -> None:
        """Pre-compute call strategy from function signature at registration time."""
        if self.execute_func is None:
            self._cached_accepts_parameters = None
            return
        try:
            fn = self.execute_func
            while hasattr(fn, "__wrapped__"):
                fn = fn.__wrapped__
            sig = inspect.signature(fn)
            self._cached_accepts_parameters = (
                "parameters" in sig.parameters or
                any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
            )
        except (ValueError, TypeError):
            # Built-in or wrapped callable without introspectable signature
            self._cached_accepts_parameters = None

    def execute(self, args: Dict[str, Any], player: Any = None, **kwargs) -> ToolResult:
        start_time = time.time()
        logger.info(f"Executing tool '{self.name}' with args: {args}")

        try:
            raw_output = invoke_tool(self.execute_func, args, player=player, **kwargs)

            exec_time = (time.time() - start_time) * 1000

            # Convert string or dict output to standard format
            if isinstance(raw_output, dict) and "message" in raw_output:
                msg = str(raw_output["message"])
            elif raw_output is not None:
                msg = str(raw_output)
            else:
                msg = "Operation completed."

            data = raw_output if isinstance(raw_output, dict) else {"output": raw_output}

            # 2. Run post-execution verification if defined
            verif_res = {"verified": bool(raw_output.get("verified", raw_output.get("success", True)))} if isinstance(raw_output, dict) else {"verified": True}
            if self.verify_func:
                try:
                    verif_res = self.verify_func(args=args, output=raw_output)
                except Exception as ve:
                    verif_res = {"verified": False, "reason": f"Verification function error: {ve}"}

            if isinstance(raw_output, dict) and "success" in raw_output:
                success = bool(raw_output["success"]) and (not self.verify_func or verif_res.get("verified", True))
            else:
                success = verif_res.get("verified", True)

            if not success:
                logger.warning(f"Tool '{self.name}' execution failed or verification failed: {verif_res}")

            return ToolResult(
                success=success,
                tool=self.name,
                message=msg if success or not verif_res.get("reason") else f"{msg} Verification: {verif_res['reason']}",
                data=data,
                verification=verif_res,
                error=None if success else (verif_res.get("reason") or msg),
                execution_time_ms=exec_time,
            )

        except Exception as e:
            exec_time = (time.time() - start_time) * 1000
            err_msg = f"Tool '{self.name}' failed with exception: {e}"
            logger.error(err_msg, exc_info=True)
            return ToolResult(
                success=False,
                tool=self.name,
                message=f"Failed to execute {self.name}: {e}",
                data={},
                verification={"verified": False, "reason": str(e)},
                error=str(e),
                execution_time_ms=exec_time,
            )


class ToolRegistry:
    """
    Central Tool Registry managing registration, validation, security checks, and execution.
    """
    def __init__(self, security_manager: Optional[SecurityManager] = None):
        self._tools: Dict[str, Tool] = {}
        self.security_manager = security_manager or default_security_manager
        # Cache for pre-computed required parameter lists per tool
        self._required_cache: Dict[str, List[str]] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool
        # Invalidate cached required params on re-registration
        self._required_cache.pop(tool.name, None)
        logger.info(f"Registered tool: {tool.name} (Risk: {tool.risk_level.value})")

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def list_tools(self) -> List[str]:
        return list(self._tools.keys())

    def list_tool_names(self) -> List[str]:
        """Explicit alias — returns tool name strings."""
        return list(self._tools.keys())

    def validate_parameters(self, tool: Tool, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        # Use cached required-params list to avoid repeated dict traversal
        if tool.name in self._required_cache:
            required = self._required_cache[tool.name]
        else:
            required = list(tool.parameters.get("required", [])) if isinstance(tool.parameters.get("required"), list) else []
            for p_name, p_spec in tool.parameters.items():
                if isinstance(p_spec, dict) and p_spec.get("required") is True:
                    if p_name not in required:
                        required.append(p_name)
            self._required_cache[tool.name] = required

        # Fast-path: skip validation when no parameters are required
        if not required:
            return True, None

        for req in required:
            if req not in args or args[req] is None or str(args[req]).strip() == "":
                return False, f"Missing required parameter '{req}' for tool '{tool.name}'."
        return True, None

    def execute_tool(self, name: str, args: Any, player: Any = None, **kwargs) -> ToolResult:
        tool = self.get_tool(name)
        if not tool:
            return ToolResult(
                success=False,
                tool=name,
                message=f"Tool '{name}' is not registered in ToolRegistry.",
                error=f"Unregistered tool: '{name}'"
            )

        # Normalize args if string or non-dict was passed
        if isinstance(args, str):
            if name in ["open_app", "open_application"]:
                args = {"app_name": args.strip(" '\"`.,")}
            elif name == "web_search":
                args = {"query": args}
            elif name == "fetch_webpage":
                args = {"url": args}
            else:
                args = {"query": args}
        elif not isinstance(args, dict):
            args = {}
        else:
            args = dict(args)

        # Tool-specific parameter alias resolution (e.g. target/app/name -> app_name for open_app)
        if name in ["open_app", "open_application"]:
            if "app_name" not in args or not str(args.get("app_name", "")).strip():
                for alias in ["target", "app", "name", "application", "query"]:
                    if alias in args and args[alias]:
                        args["app_name"] = str(args[alias]).strip(" '\"`.,")
                        break
            if "app_name" in args and isinstance(args["app_name"], str):
                args["app_name"] = args["app_name"].strip(" '\"`.,")

        # Parameter validation
        valid, val_err = self.validate_parameters(tool, args)
        if not valid:
            return ToolResult(
                success=False,
                tool=name,
                message=val_err or "Parameter validation failed.",
                error=val_err
            )

        # Security check
        authorized, sec_err = self.security_manager.validate_and_authorize(
            name,
            args,
            player=player,
            risk_level=tool.risk_level,
        )
        if not authorized:
            return ToolResult(
                success=False,
                tool=name,
                message=sec_err or "Security authorization denied.",
                error=sec_err
            )

        # Execute
        return tool.execute(args=args, player=player, **kwargs)


# Global singleton instance
default_tool_registry = ToolRegistry()
