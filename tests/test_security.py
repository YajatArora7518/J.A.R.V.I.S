# tests/test_security.py
# SecurityManager Unit & Policy Test Suite

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.security import SecurityManager, default_security_manager, RiskLevel, ActionConfirmationNeeded
from core.tool_registry import Tool, ToolRegistry


def test_security_classification() -> tuple[bool, str]:
    try:
        # 1. Risk Classification Checks
        risk_search = default_security_manager.classify_risk("web_search", {"query": "test"})
        risk_app = default_security_manager.classify_risk("open_app", {"app_name": "notepad"})
        risk_del = default_security_manager.classify_risk("file_controller", {"action": "delete", "path": "c:\\test"})
        risk_fmt = default_security_manager.classify_risk("system", {"action": "format_drive"})

        if risk_search != RiskLevel.LOW:
            return False, f"web_search expected LOW risk, got {risk_search}"
        if risk_app != RiskLevel.MEDIUM:
            return False, f"open_app expected MEDIUM risk, got {risk_app}"
        if risk_del != RiskLevel.HIGH:
            return False, f"file_controller delete expected HIGH risk, got {risk_del}"
        if risk_fmt != RiskLevel.CRITICAL:
            return False, f"system format_drive expected CRITICAL risk, got {risk_fmt}"

        # 2. Confirmation Enforcement Checks
        confirmed = False
        try:
            default_security_manager.check_permission("file_controller", {"action": "delete", "path": "c:\\test"})
        except ActionConfirmationNeeded:
            confirmed = True
        except Exception as e:
            return False, f"Unexpected exception on HIGH risk check: {e}"

        if not confirmed:
            return False, "HIGH risk operation did not trigger ActionConfirmationNeeded"

        # 3. Registry must honor a tool's declared risk level and fail closed.
        registry = ToolRegistry(security_manager=SecurityManager())
        registry.register(Tool(
            name="declared_high_risk",
            description="Test high-risk tool",
            parameters={},
            handler=lambda: "should not run",
            risk_level=RiskLevel.HIGH,
        ))
        denied = registry.execute_tool("declared_high_risk", {})
        if denied.success or "confirmation" not in denied.message.lower():
            return False, "Registry allowed a declared HIGH-risk tool without confirmation"

        return True, "Risk classification, registry risk propagation, and fail-closed security verified"
    except Exception as e:
        return False, f"Security test exception: {e}"


if __name__ == "__main__":
    passed, msg = test_security_classification()
    print(f"Security Test: {'PASS' if passed else 'FAIL'} - {msg}")
