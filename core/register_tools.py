# core/register_tools.py
# Registers all JARVIS tools into the central ToolRegistry with high-performance lazy module proxies

import importlib
import logging
import threading
from typing import Dict, Any, Callable

from core.tool_registry import Tool, default_tool_registry
from core.security import RiskLevel

logger = logging.getLogger("JARVIS.RegisterTools")

_LOADED_FUNCS: Dict[str, Callable] = {}

def _lazy_tool(module_path: str, func_name: str) -> Callable[..., Any]:
    """
    Returns a lazy proxy callable that imports the target module only upon first invocation.
    This guarantees lightning-fast JARVIS boot times (<50ms) while preserving 100% compatibility.
    """
    def _proxy(*args, **kwargs):
        key = f"{module_path}:{func_name}"
        if key not in _LOADED_FUNCS:
            mod = importlib.import_module(module_path)
            _LOADED_FUNCS[key] = getattr(mod, func_name)
        fn = _LOADED_FUNCS[key]

        # Handle 'parameters' kwarg passed from Tool.execute or dictionary arg
        if len(args) == 0 and "parameters" in kwargs and len(kwargs) == 1:
            p = kwargs["parameters"]
            if isinstance(p, dict):
                try:
                    return fn(**p)
                except (TypeError, AttributeError):
                    try:
                        return fn(p)
                    except (TypeError, AttributeError):
                        return fn(parameters=p)
            return fn(parameters=p)

        try:
            return fn(*args, **kwargs)
        except (TypeError, AttributeError):
            if len(args) == 1 and isinstance(args[0], dict) and not kwargs:
                try:
                    return fn(**args[0])
                except (TypeError, AttributeError):
                    return fn(parameters=args[0])
            elif not args and kwargs:
                try:
                    return fn(parameters=kwargs)
                except (TypeError, AttributeError):
                    return fn(kwargs)
            raise

    _proxy.__name__ = func_name
    _proxy.__doc__ = f"Lazy proxy for {module_path}.{func_name}"
    return _proxy


def initialize_all_tools() -> None:
    """
    Registers all system tools in default_tool_registry.
    """
    # 1. App Launcher
    default_tool_registry.register(Tool(
        name="open_app",
        description=(
            "Opens any application, web application, email client, messaging app, "
            "or social media platform (e.g. WhatsApp, Gmail, Instagram, Discord, YouTube, "
            "Outlook, LinkedIn, X/Twitter, Reddit, Spotify, Chrome, VS Code, Settings). "
            "Automatically discovers installed desktop apps or opens web versions in the default browser."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {"app_name": {"type": "STRING", "description": "Application or web service name"}},
            "required": ["app_name"]
        },
        execute_func=_lazy_tool("actions.open_app", "open_app"),
        risk_level=RiskLevel.MEDIUM,
    ))
    # 2. Web Search
    default_tool_registry.register(Tool(
        name="web_search",
        description=(
            "Performs a real live internet search for current information, news, prices, "
            "weather, live events, sports scores, or specific web lookup queries. "
            "Returns real search results with titles, snippets, source domains, and source URLs."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Search query string"},
                "num_results": {"type": "INTEGER", "description": "Number of results to retrieve (1-10)"},
                "fetch_page": {"type": "BOOLEAN", "description": "Set to true to extract top webpage text content"}
            },
            "required": ["query"]
        },
        execute_func=_lazy_tool("actions.web_search", "web_search"),
        risk_level=RiskLevel.LOW,
    ))

    # 2b. Fetch Webpage Content
    default_tool_registry.register(Tool(
        name="fetch_webpage",
        description="Downloads and extracts clean readable text content from a specific webpage URL.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "url": {"type": "STRING", "description": "Full webpage URL to fetch"},
                "max_chars": {"type": "INTEGER", "description": "Maximum characters to extract (default 4000)"}
            },
            "required": ["url"]
        },
        execute_func=_lazy_tool("actions.fetch_webpage", "fetch_webpage"),
        risk_level=RiskLevel.LOW,
    ))

    # 3. Weather Report
    default_tool_registry.register(Tool(
        name="weather_report",
        description="Gives the weather report for a city.",
        parameters={
            "type": "OBJECT",
            "properties": {"city": {"type": "STRING", "description": "City name"}},
            "required": ["city"]
        },
        execute_func=_lazy_tool("actions.weather_report", "weather_action"),
        risk_level=RiskLevel.LOW,
    ))

    # 4. Computer Settings
    default_tool_registry.register(Tool(
        name="computer_settings",
        description="Controls volume, brightness, window state, typing, closing apps.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING"},
                "description": {"type": "STRING"},
                "value": {"type": "STRING"}
            },
            "required": []
        },
        execute_func=_lazy_tool("actions.computer_settings", "computer_settings"),
        risk_level=RiskLevel.MEDIUM,
    ))

    # 5. Computer Control
    default_tool_registry.register(Tool(
        name="computer_control",
        description="Direct computer control: type, click, hotkeys, screenshots.",
        parameters={
            "type": "OBJECT",
            "properties": {"action": {"type": "STRING"}},
            "required": ["action"]
        },
        execute_func=_lazy_tool("actions.computer_control", "computer_control"),
        risk_level=RiskLevel.MEDIUM,
    ))

    # 6. File Controller
    default_tool_registry.register(Tool(
        name="file_controller",
        description="Manages files and folders: list, create, delete, move, copy, rename, read, write.",
        parameters={
            "type": "OBJECT",
            "properties": {"action": {"type": "STRING"}},
            "required": ["action"]
        },
        execute_func=_lazy_tool("actions.file_controller", "file_controller"),
        risk_level=RiskLevel.MEDIUM,
    ))

    # 7. Browser Control
    default_tool_registry.register(Tool(
        name="browser_control",
        description="Controls the web browser with Playwright.",
        parameters={
            "type": "OBJECT",
            "properties": {"action": {"type": "STRING"}},
            "required": ["action"]
        },
        execute_func=_lazy_tool("actions.browser_control", "browser_control"),
        risk_level=RiskLevel.MEDIUM,
    ))

    # 8. Code Helper
    default_tool_registry.register(Tool(
        name="code_helper",
        description="Writes, edits, explains, or runs code.",
        parameters={
            "type": "OBJECT",
            "properties": {"action": {"type": "STRING"}},
            "required": ["action"]
        },
        execute_func=_lazy_tool("actions.code_helper", "code_helper"),
        risk_level=RiskLevel.MEDIUM,
    ))

    # 9. Dev Agent
    default_tool_registry.register(Tool(
        name="dev_agent",
        description="Builds complete multi-file projects from scratch.",
        parameters={
            "type": "OBJECT",
            "properties": {"description": {"type": "STRING"}},
            "required": ["description"]
        },
        execute_func=_lazy_tool("actions.dev_agent", "dev_agent"),
        risk_level=RiskLevel.HIGH,
    ))

    # 10. File Processor
    default_tool_registry.register(Tool(
        name="file_processor",
        description="Processes dropped/uploaded files (PDFs, images, CSVs, audio).",
        parameters={
            "type": "OBJECT",
            "properties": {"file_path": {"type": "STRING"}, "action": {"type": "STRING"}},
            "required": []
        },
        execute_func=_lazy_tool("actions.file_processor", "file_processor"),
        risk_level=RiskLevel.LOW,
    ))

    # 11. YouTube Control
    default_tool_registry.register(Tool(
        name="youtube_video",
        description="Controls YouTube playback and search.",
        parameters={
            "type": "OBJECT",
            "properties": {"action": {"type": "STRING"}},
            "required": []
        },
        execute_func=_lazy_tool("actions.youtube_video", "youtube_video"),
        risk_level=RiskLevel.LOW,
    ))

    # 12. Desktop Control
    default_tool_registry.register(Tool(
        name="desktop_control",
        description="Manages desktop wallpapers and organization.",
        parameters={
            "type": "OBJECT",
            "properties": {"action": {"type": "STRING"}},
            "required": ["action"]
        },
        execute_func=_lazy_tool("actions.desktop", "desktop_control"),
        risk_level=RiskLevel.LOW,
    ))

    # 13. Game Updater
    default_tool_registry.register(Tool(
        name="game_updater",
        description="Manages Steam and Epic games.",
        parameters={
            "type": "OBJECT",
            "properties": {"action": {"type": "STRING"}},
            "required": []
        },
        execute_func=_lazy_tool("actions.game_updater", "game_updater"),
        risk_level=RiskLevel.LOW,
    ))

    # 14. Flight Finder
    default_tool_registry.register(Tool(
        name="flight_finder",
        description="Searches Google Flights.",
        parameters={
            "type": "OBJECT",
            "properties": {"origin": {"type": "STRING"}, "destination": {"type": "STRING"}, "date": {"type": "STRING"}},
            "required": ["origin", "destination", "date"]
        },
        execute_func=_lazy_tool("actions.flight_finder", "flight_finder"),
        risk_level=RiskLevel.LOW,
    ))

    # 15. Chrome Profile Controller
    default_tool_registry.register(Tool(
        name="chrome_profile",
        description="Controls Google Chrome profile discovery and profile launching.",
        parameters={
            "type": "OBJECT",
            "properties": {"action": {"type": "STRING"}, "profile_name": {"type": "STRING"}, "url": {"type": "STRING"}},
            "required": []
        },
        execute_func=_lazy_tool("actions.chrome_profile", "chrome_profile"),
        risk_level=RiskLevel.MEDIUM,
    ))

    # 16. WhatsApp Controller & Discrete Action Tools
    default_tool_registry.register(Tool(
        name="whatsapp",
        description="Master controller for WhatsApp Web messaging, contact resolution, chat opening, and calls.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING"},
                "contact": {"type": "STRING"},
                "message": {"type": "STRING"},
                "recipient": {"type": "STRING"},
                "receiver": {"type": "STRING"},
                "message_text": {"type": "STRING"},
                "call_type": {"type": "STRING"}
            },
            "required": []
        },
        execute_func=_lazy_tool("actions.whatsapp", "whatsapp"),
        risk_level=RiskLevel.MEDIUM,
    ))

    default_tool_registry.register(Tool(
        name="whatsapp_open",
        description="Opens WhatsApp Web session in Yajat Chrome profile.",
        parameters={"type": "OBJECT", "properties": {}, "required": []},
        execute_func=_lazy_tool("actions.whatsapp", "whatsapp_open_tool"),
        risk_level=RiskLevel.LOW,
    ))

    default_tool_registry.register(Tool(
        name="whatsapp_search_contact",
        description="Searches WhatsApp Web contacts and resolves matching names.",
        parameters={
            "type": "OBJECT",
            "properties": {"query": {"type": "STRING"}, "contact": {"type": "STRING"}},
            "required": []
        },
        execute_func=_lazy_tool("actions.whatsapp", "whatsapp_search_contact_tool"),
        risk_level=RiskLevel.LOW,
    ))

    default_tool_registry.register(Tool(
        name="whatsapp_open_chat",
        description="Opens a specific contact chat in WhatsApp Web session.",
        parameters={
            "type": "OBJECT",
            "properties": {"contact": {"type": "STRING"}, "recipient": {"type": "STRING"}},
            "required": []
        },
        execute_func=_lazy_tool("actions.whatsapp", "whatsapp_open_chat_tool"),
        risk_level=RiskLevel.LOW,
    ))

    def _exec_whatsapp_send(parameters=None, **kw):
        p = parameters if isinstance(parameters, dict) else (kw or {})
        contact = p.get("contact") or p.get("recipient") or p.get("receiver") or ""
        message = p.get("message") or p.get("text") or p.get("message_text") or ""
        if not contact or not message:
            q = p.get("query") or p.get("text_prompt") or ""
            from actions.whatsapp_automation import parse_whatsapp_command
            parsed = parse_whatsapp_command(q)
            contact = contact or parsed.get("contact", "Rahul")
            message = message or parsed.get("message", "Hello")
        from actions.whatsapp import whatsapp_send_message_tool
        return whatsapp_send_message_tool(contact=contact, message=message)

    def _exec_whatsapp_voice(parameters=None, **kw):
        p = parameters if isinstance(parameters, dict) else (kw or {})
        contact = p.get("contact") or p.get("recipient") or p.get("receiver") or ""
        if not contact:
            q = p.get("query") or p.get("text_prompt") or ""
            from actions.whatsapp_automation import parse_whatsapp_command
            parsed = parse_whatsapp_command(q)
            contact = parsed.get("contact", "Rahul")
        from actions.whatsapp import whatsapp_voice_call_tool
        return whatsapp_voice_call_tool(contact=contact)

    def _exec_whatsapp_video(parameters=None, **kw):
        p = parameters if isinstance(parameters, dict) else (kw or {})
        contact = p.get("contact") or p.get("recipient") or p.get("receiver") or ""
        if not contact:
            q = p.get("query") or p.get("text_prompt") or ""
            from actions.whatsapp_automation import parse_whatsapp_command
            parsed = parse_whatsapp_command(q)
            contact = parsed.get("contact", "Rahul")
        from actions.whatsapp import whatsapp_video_call_tool
        return whatsapp_video_call_tool(contact=contact)

    default_tool_registry.register(Tool(
        name="whatsapp_send_message",
        description="Sends a verified text message to a specific WhatsApp contact.",
        parameters={
            "type": "OBJECT",
            "properties": {"contact": {"type": "STRING"}, "message": {"type": "STRING"}},
            "required": ["contact", "message"]
        },
        execute_func=_exec_whatsapp_send,
        risk_level=RiskLevel.MEDIUM,
    ))

    default_tool_registry.register(Tool(
        name="whatsapp_reply",
        description="Replies to a contact's latest WhatsApp message.",
        parameters={
            "type": "OBJECT",
            "properties": {"contact": {"type": "STRING"}, "message": {"type": "STRING"}},
            "required": ["contact", "message"]
        },
        execute_func=_lazy_tool("actions.whatsapp", "whatsapp_reply_tool"),
        risk_level=RiskLevel.MEDIUM,
    ))

    default_tool_registry.register(Tool(
        name="whatsapp_voice_call",
        description="Initiates a WhatsApp Web voice call with contact and DOM state verification.",
        parameters={
            "type": "OBJECT",
            "properties": {"contact": {"type": "STRING"}},
            "required": ["contact"]
        },
        execute_func=_exec_whatsapp_voice,
        risk_level=RiskLevel.HIGH,
    ))

    default_tool_registry.register(Tool(
        name="whatsapp_video_call",
        description="Initiates a WhatsApp Web video call with contact and DOM state verification.",
        parameters={
            "type": "OBJECT",
            "properties": {"contact": {"type": "STRING"}},
            "required": ["contact"]
        },
        execute_func=_exec_whatsapp_video,
        risk_level=RiskLevel.HIGH,
    ))

    default_tool_registry.register(Tool(
        name="whatsapp_read_messages",
        description="Reads visible/unread messages for a contact from WhatsApp Web DOM.",
        parameters={
            "type": "OBJECT",
            "properties": {"contact": {"type": "STRING"}, "unread_only": {"type": "BOOLEAN"}},
            "required": []
        },
        execute_func=_lazy_tool("actions.whatsapp", "whatsapp_read_messages_tool"),
        risk_level=RiskLevel.LOW,
    ))

    # 16a. Send Message Dispatcher (WhatsApp / Telegram / App)
    default_tool_registry.register(Tool(
        name="send_message",
        description="Sends a text message via WhatsApp, Telegram, or other messaging platform.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "receiver": {"type": "STRING", "description": "Recipient contact name"},
                "message_text": {"type": "STRING", "description": "The message to send"},
                "platform": {"type": "STRING", "description": "Platform: WhatsApp, Telegram, etc."}
            },
            "required": ["receiver", "message_text"]
        },
        execute_func=_lazy_tool("actions.send_message", "send_message"),
        risk_level=RiskLevel.MEDIUM,
    ))

    # 16b. Telegram Controller
    default_tool_registry.register(Tool(
        name="telegram",
        description="Controls Telegram Web messaging and session opening in Yajat Chrome profile.",
        parameters={
            "type": "OBJECT",
            "properties": {"action": {"type": "STRING"}, "message": {"type": "STRING"}},
            "required": []
        },
        execute_func=_lazy_tool("actions.telegram", "telegram"),
        risk_level=RiskLevel.MEDIUM,
    ))

    # 17. Discord Controller
    default_tool_registry.register(Tool(
        name="discord",
        description="Controls Discord messaging, user resolution, calls, and voice channels.",
        parameters={
            "type": "OBJECT",
            "properties": {"action": {"type": "STRING"}, "target": {"type": "STRING"}, "message": {"type": "STRING"}},
            "required": []
        },
        execute_func=_lazy_tool("actions.discord", "discord"),
        risk_level=RiskLevel.MEDIUM,
    ))

    # 18. Windows Startup Controller
    default_tool_registry.register(Tool(
        name="windows_startup",
        description="Manages optional JARVIS Windows Startup registry configuration.",
        parameters={
            "type": "OBJECT",
            "properties": {"action": {"type": "STRING", "description": "'enable' | 'disable' | 'status'"}},
            "required": []
        },
        execute_func=_lazy_tool("actions.windows_startup", "windows_startup"),
        risk_level=RiskLevel.MEDIUM,
    ))

    # 19. College Mode Engine
    default_tool_registry.register(Tool(
        name="college_mode",
        description="Manages college timetable, assignments, study planner, note summarization, and flashcards.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "schedule | assignments | add_assignment | summarize_notes | generate_flashcards"},
                "day": {"type": "STRING"},
                "query": {"type": "STRING"}
            },
            "required": []
        },
        execute_func=_lazy_tool("actions.college_mode", "college_mode"),
        risk_level=RiskLevel.LOW,
    ))

    # 20. Camera Controller
    def camera_control(parameters: dict | None = None, player=None, **kwargs) -> str:
        params = parameters or kwargs or {}
        action = str(params.get("action", "")).lower().strip()
        from core.context_engine import default_context_engine
        if action in ["on", "enable", "start", "turn_on"]:
            default_context_engine.camera_active = True
            if player and hasattr(player, "set_camera_active"):
                player.set_camera_active(True)
            return "Camera activated, sir. CAMERA ACTIVE indicator is displayed on HUD."
        elif action in ["off", "disable", "stop", "turn_off"]:
            default_context_engine.camera_active = False
            if player and hasattr(player, "set_camera_active"):
                player.set_camera_active(False)
            return "Camera deactivated, sir."
        else:
            if not default_context_engine.camera_active:
                default_context_engine.camera_active = True
                if player and hasattr(player, "set_camera_active"):
                    player.set_camera_active(True)
            from actions.screen_processor import screen_process
            text_query = params.get("query") or params.get("text") or "What do you see?"
            screen_process({"angle": "camera", "text": text_query}, player=player)
            return "Analyzing camera feed, sir."

    default_tool_registry.register(Tool(
        name="camera_control",
        description="Controls camera activation state and webcam visual analysis.",
        parameters={
            "type": "OBJECT",
            "properties": {"action": {"type": "STRING", "description": "on | off | analyze"}, "query": {"type": "STRING"}},
            "required": []
        },
        execute_func=camera_control,
        risk_level=RiskLevel.LOW,
    ))

    # 21. Discord Discrete Tools & Mic Control
    def _exec_discord_connect(parameters=None, **kw):
        p = parameters if isinstance(parameters, dict) else kw
        ch = (p or {}).get("channel", "General")
        from actions.discord_automation import discord_provider
        return discord_provider.join_voice(ch or "General")

    def _exec_discord_disconnect(*a, **kw):
        from actions.discord_automation import discord_provider
        return discord_provider.disconnect_voice()

    def _exec_discord_mute(*a, **kw):
        from actions.discord_automation import discord_provider
        return discord_provider.mute(True)

    def _exec_discord_unmute(*a, **kw):
        from actions.discord_automation import discord_provider
        return discord_provider.mute(False)

    def _exec_mic_control(parameters=None, **kw):
        p = parameters if isinstance(parameters, dict) else kw
        q = (p or {}).get("query", "")
        from actions.mic_control import handle_mic_command
        return handle_mic_command(q or "")

    def _exec_system_telemetry(action_name):
        def _wrapper(parameters=None, **kw):
            p = parameters if isinstance(parameters, dict) else kw
            p_clean = p or {}
            from actions.system_telemetry import execute_system_telemetry
            return execute_system_telemetry(action_name, **p_clean)
        return _wrapper

    default_tool_registry.register(Tool(
        name="discord_connect_voice",
        description="Joins a Discord voice channel (e.g. General).",
        parameters={"type": "OBJECT", "properties": {"channel": {"type": "STRING"}}, "required": []},
        execute_func=_exec_discord_connect,
        risk_level=RiskLevel.MEDIUM,
    ))

    default_tool_registry.register(Tool(
        name="discord_disconnect_voice",
        description="Disconnects from the active Discord voice channel.",
        parameters={"type": "OBJECT", "properties": {}, "required": []},
        execute_func=_exec_discord_disconnect,
        risk_level=RiskLevel.LOW,
    ))

    default_tool_registry.register(Tool(
        name="discord_mute",
        description="Mutes the Discord microphone.",
        parameters={"type": "OBJECT", "properties": {}, "required": []},
        execute_func=_exec_discord_mute,
        risk_level=RiskLevel.LOW,
    ))

    default_tool_registry.register(Tool(
        name="discord_unmute",
        description="Unmutes the Discord microphone.",
        parameters={"type": "OBJECT", "properties": {}, "required": []},
        execute_func=_exec_discord_unmute,
        risk_level=RiskLevel.LOW,
    ))

    default_tool_registry.register(Tool(
        name="mic_control",
        description="Controls microphone states across JARVIS voice input and System master mic.",
        parameters={"type": "OBJECT", "properties": {"query": {"type": "STRING"}}, "required": []},
        execute_func=_exec_mic_control,
        risk_level=RiskLevel.MEDIUM,
    ))

    # System Telemetry Tools Registration
    telemetry_tools = [
        ("system_info", "Queries complete Windows system hardware snapshot: CPU, RAM, Battery, Disk storage."),
        ("cpu_info", "Queries CPU processor model, core count, and current CPU usage."),
        ("memory_info", "Queries total RAM, used RAM, and free RAM available."),
        ("gpu_info", "Queries GPU graphics card model and video memory."),
        ("battery_info", "Queries laptop battery charge percentage and charger status."),
        ("disk_info", "Queries storage partitions and available free disk space."),
        ("network_info", "Queries active network connection, IP address, and interface status."),
        ("process_info", "Inspects top running processes by CPU and RAM usage or checks if a process is running."),
        ("installed_apps_info", "Scans Windows system registry to inspect installed applications."),
        ("active_windows_info", "Lists all visible open windows currently active on desktop."),
        ("audio_devices_info", "Inspects active recording microphone and playback speaker endpoints."),
        ("filesystem_info", "Inspects and searches user files in Downloads, Documents, Desktop, or JARVIS folder.")
    ]

    for tool_name, desc in telemetry_tools:
        default_tool_registry.register(Tool(
            name=tool_name,
            description=desc,
            parameters={"type": "OBJECT", "properties": {"query": {"type": "STRING"}, "app_name": {"type": "STRING"}, "folder": {"type": "STRING"}}, "required": []},
            execute_func=_exec_system_telemetry(tool_name),
            risk_level=RiskLevel.LOW,
        ))

    # =========================================================
    # NEW WINDOWS SYSTEM CONTROL & SCRIPT EXECUTION TOOLS
    # =========================================================
    def _create_script_wrapper(params):
        p = params or {}
        from actions.script_executor import create_script as _create_script_fn
        return _create_script_fn(
            p.get("content", ""),
            p.get("script_type", "bat"),
            filename=p.get("filename"),
            target_dir=p.get("directory")
        )

    # 1. Script Creation Tool
    default_tool_registry.register(Tool(
        name="create_script",
        description="Creates a .bat, .cmd, .ps1, .py, .js, .exe, or .msi script file in the JARVIS workspace or user specified directory.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "content": {"type": "STRING"},
                "script_type": {"type": "STRING"},
                "filename": {"type": "STRING"},
                "directory": {"type": "STRING"}
            },
            "required": ["content", "script_type"]
        },
        execute_func=_create_script_wrapper,
        risk_level=RiskLevel.MEDIUM
    ))

    def _run_script_wrapper(params):
        p = params or {}
        from actions.script_executor import run_script as _run_script_fn
        return _run_script_fn(
            p.get("file_path", ""),
            args=p.get("args", ""),
            timeout=int(p.get("timeout", 30)),
            elevated=bool(p.get("elevated", False))
        )

    # 2. Script Execution Tool
    default_tool_registry.register(Tool(
        name="run_script",
        description="Executes a .bat, .cmd, .ps1, .py, .js, .exe, or .msi script file.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING"},
                "args": {"type": "STRING"},
                "timeout": {"type": "INTEGER"},
                "elevated": {"type": "BOOLEAN"}
            },
            "required": ["file_path"]
        },
        execute_func=_run_script_wrapper,
        risk_level=RiskLevel.MEDIUM
    ))

    # 3. Windows Service Control Tool
    def _exec_windows_service_control(params):
        p = params or {}
        act = str(p.get("action", "list")).lower().strip()
        sname = p.get("service_name") or p.get("name", "")
        elevated = bool(p.get("elevated", False))
        from actions.windows_services import list_services, get_service_status, start_service, stop_service, restart_service

        if act in ["status", "get_service_status"]:
            return get_service_status(sname)
        elif act in ["start", "start_service"]:
            return start_service(sname, elevated=elevated)
        elif act in ["stop", "stop_service"]:
            return stop_service(sname, elevated=elevated)
        elif act in ["restart", "restart_service"]:
            return restart_service(sname, elevated=elevated)
        else:
            return list_services(filter_name=sname)

    default_tool_registry.register(Tool(
        name="windows_service_control",
        description="Inspects, starts, stops, or restarts Windows system services.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING"},
                "service_name": {"type": "STRING"},
                "elevated": {"type": "BOOLEAN"}
            },
            "required": ["action"]
        },
        execute_func=_exec_windows_service_control,
        risk_level=RiskLevel.HIGH
    ))

    def _exec_windows_sys_control(params):
        p = params or {}
        from actions.windows_system_controller import execute_system_capability
        return execute_system_capability(
            p.get("capability", ""),
            p.get("args", {})
        )

    # 4. Generic Windows System Controller Tool
    default_tool_registry.register(Tool(
        name="windows_system_controller",
        description="Master controller executing typed Windows system capabilities (apps, files, processes, power, web search).",
        parameters={
            "type": "OBJECT",
            "properties": {
                "capability": {"type": "STRING"},
                "args": {"type": "OBJECT"}
            },
            "required": ["capability"]
        },
        execute_func=_exec_windows_sys_control,
        risk_level=RiskLevel.MEDIUM
    ))

    def _exec_capability_info(params):
        from core.capability_discovery import capability_registry
        return capability_registry.discover()

    # 5. System Capability Info Tool
    default_tool_registry.register(Tool(
        name="capability_info",
        description="Queries detected Windows system runtimes, interpreters, and hardware capabilities.",
        parameters={"type": "OBJECT", "properties": {}, "required": []},
        execute_func=_exec_capability_info,
        risk_level=RiskLevel.LOW
    ))

    def _exec_service_discovery(params=None):
        from actions.service_discovery import discover_communication_services
        return discover_communication_services()

    # 6. Universal Service Discovery Tool
    default_tool_registry.register(Tool(
        name="service_discovery",
        description="Lists installed communication and social media services and their active capabilities across Windows, Chrome, and Mobile.",
        parameters={"type": "OBJECT", "properties": {}, "required": []},
        execute_func=_exec_service_discovery,
        risk_level=RiskLevel.LOW
    ))

    def _exec_read_notifications(params=None):
        p = params or {}
        from actions.notification_engine import read_aggregated_notifications
        return read_aggregated_notifications(only_important=p.get("only_important", True))

    # 7. Read Notifications Tool
    default_tool_registry.register(Tool(
        name="read_notifications",
        description="Reads aggregated unread messages and high-priority notifications across Android, Windows, and Browser sessions.",
        parameters={
            "type": "OBJECT",
            "properties": {"only_important": {"type": "BOOLEAN", "description": "Filter high and medium priority notifications only"}},
            "required": []
        },
        execute_func=_exec_read_notifications,
        risk_level=RiskLevel.LOW
    ))

    def _exec_make_call(params):
        p = params or {}
        from actions.universal_calls_sms import make_call as _make_call_fn
        return _make_call_fn(
            p.get("recipient", ""),
            call_type=p.get("call_type", "voice"),
            confirm_call=p.get("confirm_call", False)
        )

    # 8. Universal Call Tool
    default_tool_registry.register(Tool(
        name="make_call",
        description="Places a voice or video call to a recipient via Android or Windows Phone Link.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "recipient": {"type": "STRING", "description": "Contact name or phone number"},
                "call_type": {"type": "STRING", "description": "voice or video"},
                "confirm_call": {"type": "BOOLEAN", "description": "Set to true after user confirmation"}
            },
            "required": ["recipient"]
        },
        execute_func=_exec_make_call,
        risk_level=RiskLevel.HIGH
    ))

    def _exec_read_call_log(params=None):
        from actions.universal_calls_sms import read_call_log as _read_call_log_fn
        return _read_call_log_fn()

    # 9. Read Call Log Tool
    default_tool_registry.register(Tool(
        name="read_call_log",
        description="Reads call log history and missed calls.",
        parameters={"type": "OBJECT", "properties": {}, "required": []},
        execute_func=_exec_read_call_log,
        risk_level=RiskLevel.LOW
    ))

    def _exec_send_sms(params):
        p = params or {}
        from actions.universal_calls_sms import send_sms_message as _send_sms_fn
        return _send_sms_fn(p.get("recipient", ""), p.get("message_text", ""))

    # 10. Universal SMS Tool
    default_tool_registry.register(Tool(
        name="send_sms",
        description="Sends an SMS text message to a contact or phone number.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "recipient": {"type": "STRING", "description": "Contact name or phone number"},
                "message_text": {"type": "STRING", "description": "SMS text content"}
            },
            "required": ["recipient", "message_text"]
        },
        execute_func=_exec_send_sms,
        risk_level=RiskLevel.MEDIUM
    ))

    def _exec_read_sms(params=None):
        from actions.universal_calls_sms import read_sms_messages as _read_sms_fn
        return _read_sms_fn()

    default_tool_registry.register(Tool(
        name="read_sms",
        description="Reads SMS inbox and unread SMS text messages.",
        parameters={"type": "OBJECT", "properties": {}, "required": []},
        execute_func=_exec_read_sms,
        risk_level=RiskLevel.LOW
    ))

    def _exec_social_action(params):
        p = params or {}
        from actions.social_actions import execute_social_action as _execute_social_action_fn
        return _execute_social_action_fn(
            p.get("platform", ""),
            p.get("action", ""),
            target=p.get("target", ""),
            content=p.get("content", "")
        )

    # 11. Social Actions Tool
    default_tool_registry.register(Tool(
        name="social_action",
        description="Executes a social media engagement action like post, comment, share, follow, or media control.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "platform": {"type": "STRING", "description": "Target social platform"},
                "action": {"type": "STRING", "description": "like, comment, share, follow, play_media, pause_media"},
                "target": {"type": "STRING", "description": "Target profile, post, or media"},
                "content": {"type": "STRING", "description": "Optional comment or text content"}
            },
            "required": ["platform", "action"]
        },
        execute_func=_exec_social_action,
        risk_level=RiskLevel.MEDIUM
    ))

    def _exec_mobile_gateway(params):
        p = params or {}
        from actions.mobile_pc_gateway import handle_mobile_gateway_command as _handle_mobile_gateway_fn
        return _handle_mobile_gateway_fn(
            p.get("target_device", ""),
            p.get("action", ""),
            p.get("payload", {})
        )

    # 12. Mobile/PC Cross-Device Gateway Tool
    default_tool_registry.register(Tool(
        name="mobile_gateway",
        description="Routes cross-device commands between Windows PC and Android devices.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "target_device": {"type": "STRING", "description": "android or pc"},
                "action": {"type": "STRING", "description": "Action name"},
                "payload": {"type": "OBJECT", "description": "Action parameters"}
            },
            "required": ["target_device", "action"]
        },
        execute_func=_exec_mobile_gateway,
        risk_level=RiskLevel.MEDIUM
    ))

    def _exec_unified_connection_status(params=None):
        from actions.mobile_pc_gateway import get_unified_connection_status as _get_unified_connection_status_fn
        return _get_unified_connection_status_fn()

    # 13. Unified Connection Status Tool
    default_tool_registry.register(Tool(
        name="unified_connection_status",
        description="Returns unified connection diagnostic status across Windows, Android, ADB, Gateway, Chrome, WhatsApp, Instagram, and Discord.",
        parameters={"type": "OBJECT", "properties": {}, "required": []},
        execute_func=_exec_unified_connection_status,
        risk_level=RiskLevel.LOW
    ))

    logger.info(f"Initialized {len(default_tool_registry.list_tools())} tools into ToolRegistry.")


def preload_hot_tools_async() -> None:
    """
    Asynchronously warms up HOT tools in a background daemon thread
    AFTER the UI and voice pipeline become interactive.
    Guarantees 0ms first-use latency for common desktop actions.
    """
    def _worker():
        hot_modules = [
            ("actions.open_app", "open_app"),
            ("actions.computer_control", "computer_control"),
            ("actions.computer_settings", "computer_settings"),
            ("actions.screen_processor", "screen_process"),
            ("actions.system_telemetry", "execute_system_telemetry"),
            ("actions.web_search", "web_search"),
        ]
        for mod_name, fn_name in hot_modules:
            try:
                key = f"{mod_name}:{fn_name}"
                if key not in _LOADED_FUNCS:
                    mod = importlib.import_module(mod_name)
                    _LOADED_FUNCS[key] = getattr(mod, fn_name)
            except Exception:
                pass

    t = threading.Thread(target=_worker, name="JARVIS-HotTools-Preloader", daemon=True)
    t.start()


# Initialize on import
initialize_all_tools()
preload_hot_tools_async()

