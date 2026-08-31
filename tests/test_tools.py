# tests/test_tools.py
# ToolRegistry Unit & Schema Test Suite

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.tool_registry import ToolRegistry, Tool, ToolResult
from core.security import RiskLevel


def dummy_handler(args: dict) -> str:
    return f"Success: {args.get('val', '')}"


def test_tool_registry_unit() -> tuple[bool, str]:
    try:
        reg = ToolRegistry()

        # 1. Registration
        tool = Tool(
            name="test_dummy",
            description="Dummy tool for testing",
            parameters={"val": {"type": "string", "required": True}},
            risk_level=RiskLevel.LOW,
            handler=dummy_handler
        )
        reg.register(tool)

        if "test_dummy" not in reg.list_tools():
            return False, "Tool registration failed"

        # 2. Schema Lookup
        fetched = reg.get_tool("test_dummy")
        if not fetched or fetched.name != "test_dummy":
            return False, "Tool lookup failed"

        # 3. Execution Success
        res = reg.execute_tool("test_dummy", {"val": "hello"})
        if not res.success or res.message != "Success: hello":
            return False, f"Tool execution failed: {res.message}"

        # 4. Parameter Validation Error (missing required param)
        res_err = reg.execute_tool("test_dummy", {})
        if res_err.success:
            return False, "Expected parameter validation error for missing required param"

        return True, "Tool registration, lookup, execution, and validation verified"
    except Exception as e:
        return False, f"ToolRegistry test exception: {e}"


if __name__ == "__main__":
    passed, msg = test_tool_registry_unit()
    print(f"Tool Test: {'PASS' if passed else 'FAIL'} - {msg}")
