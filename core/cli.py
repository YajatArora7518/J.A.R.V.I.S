# core/cli.py
# Command Line Entrypoints & CLI Parser for JARVIS Platform

import sys
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from jarvis_api.version import __version__


def cli_main():
    """
    Main CLI entrypoint for 'jarvis'.
    Supports subcommands (status, tools, execute, task) and flags (--version, --help).
    Launches desktop GUI assistant by default if no subcommand is passed.
    """
    parser = argparse.ArgumentParser(
        prog="jarvis",
        description="JARVIS — Personal AI Desktop Assistant & Developer Platform CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  jarvis                          Launch desktop HUD assistant UI
  jarvis --version                Display installed JARVIS package version
  jarvis status                   Run diagnostic system health check
  jarvis tools                    List all registered tools and risk levels
  jarvis execute "Open Notepad"   Execute natural language command
  jarvis task "Find all PDFs"     Submit autonomous planner task
"""
    )
    parser.add_argument("-v", "--version", action="version", version=f"JARVIS v{__version__}")

    subparsers = parser.add_subparsers(dest="subcommand", help="JARVIS CLI Subcommands")

    # Subcommand: status
    subparsers.add_parser("status", help="Run diagnostic health check")

    # Subcommand: tools
    subparsers.add_parser("tools", help="List all registered tools and risk levels")

    # Subcommand: execute
    exec_parser = subparsers.add_parser("execute", help="Execute natural language command")
    exec_parser.add_argument("command", type=str, help="Command text to execute (e.g. 'Open Notepad')")

    # Subcommand: task
    task_parser = subparsers.add_parser("task", help="Submit autonomous multi-step planner task")
    task_parser.add_argument("goal", type=str, help="Goal description for autonomous planner")

    args = parser.parse_args()

    if args.subcommand == "status":
        cli_status()
    elif args.subcommand == "tools":
        from jarvis_api import JarvisAPI
        jarvis = JarvisAPI()
        tools = jarvis.list_tools()
        print(f"\nRegistered Tools ({len(tools)}):")
        print("-" * 55)
        for t in tools:
            print(f" - {t['name']:<20} [{t['risk_level']:<6}] : {t['description']}")
        print("-" * 55 + "\n")
    elif args.subcommand == "execute":
        from jarvis_api import JarvisAPI
        jarvis = JarvisAPI()
        print(f"[*] Executing command: '{args.command}'...")
        res = jarvis.execute(args.command)
        print(f"[*] Result: {res.message}")
        if res.verification.get("verified"):
            print(f"[✓] Verification: {res.verification}")
    elif args.subcommand == "task":
        from jarvis_api import JarvisAPI
        jarvis = JarvisAPI()
        print(f"[*] Submitting task goal: '{args.goal}'...")
        t_res = jarvis.run_task(args.goal)
        print(f"[*] Task Created: ID={t_res.task_id}, Status={t_res.status}")
    else:
        # Default: Launch GUI HUD desktop assistant
        try:
            from main import main
        except ImportError:
            import importlib.util
            main_path = BASE_DIR / "main.py"
            spec = importlib.util.spec_from_file_location("main", str(main_path))
            mod = importlib.util.module_from_spec(spec)
            sys.modules["main"] = mod
            spec.loader.exec_module(mod)
            main = mod.main
        main()


def cli_api():
    """CLI entrypoint: 'jarvis-api' -> Launches REST API server."""
    from jarvis_api.server import main as api_main
    api_main()


def cli_status():
    """CLI entrypoint: 'jarvis-status' -> Displays diagnostic system health check."""
    from core.health_check import run_startup_health_check
    all_passed, summary = run_startup_health_check(BASE_DIR)
    sys.exit(0 if all_passed else 1)


def cli_test():
    """CLI entrypoint: 'jarvis-test' -> Runs automated platform test suite."""
    from tests.run_tests import run_all_tests
    report = run_all_tests()
    all_pass = all(status in ("PASS", "UNAVAILABLE") for status, _ in report.values())
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    cli_main()
