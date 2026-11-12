import sys
import traceback
from core.command_pipeline import process_user_command
from core.register_tools import default_tool_registry

commands = [
    'open Notepad',
    'open "Notepad"',
    'open Chrome',
    'open Calculator',
    'open File Explorer',
    'Jarvis, open Notepad',
    'Jarvis open Notepad',
    'please open Notepad',
    'Notepad kholo',
    'Chrome kholo',
    'open SomeApplicationThatDefinitelyDoesNotExist123'
]

print("=== TESTING PROCESS_USER_COMMAND ===")
for cmd in commands:
    print(f"\n--- Testing: {cmd} ---")
    try:
        res = process_user_command(cmd, source="voice")
        print("RESULT:", res)
    except Exception as e:
        print("EXCEPTION CAUGHT IN TEST RUNNER:", type(e), e)
        traceback.print_exc()

print("\n=== TESTING DIRECT TOOL_REGISTRY EXECUTE_TOOL ===")
tool_args_tests = [
    {"app_name": "Notepad"},
    {"target": "Notepad"},
    {"app": "Notepad"},
    {"name": "Notepad"},
    {"application": "Notepad"},
    {"app_name": '"Notepad"'},
    {"target": '"Notepad"'},
    "Notepad", # string instead of dict
    {"app_name": "SomeApplicationThatDefinitelyDoesNotExist123"}
]

for args in tool_args_tests:
    print(f"\n--- Testing tool args: {args!r} ---")
    try:
        res = default_tool_registry.execute_tool("open_app", args)
        print("ToolResult:", res)
    except Exception as e:
        print("EXCEPTION CAUGHT IN EXECUTE_TOOL:", type(e), e)
        traceback.print_exc()

print("\n=== TESTING DIRECT open_app CALL ===")
from actions.open_app import open_app
direct_tests = [
    ("positional str", ("Notepad",), {}),
    ("dict in parameters", ({"app_name": "Notepad"},), {}),
    ("target in parameters", ({"target": "Notepad"},), {}),
    ("target in kwargs", (), {"target": "Notepad"}),
    ("app_name in kwargs", (), {"app_name": "Notepad"}),
    ("name in kwargs", (), {"name": "Notepad"}),
    ("quotes", ({"app_name": '"Notepad"'},), {}),
]

for name, args, kwargs in direct_tests:
    print(f"\n--- Testing open_app {name}: args={args}, kwargs={kwargs} ---")
    try:
        res = open_app(*args, **kwargs)
        print("open_app result:", res)
    except Exception as e:
        print("EXCEPTION IN open_app:", type(e), e)
        traceback.print_exc()
