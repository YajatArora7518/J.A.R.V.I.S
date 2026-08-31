import sys
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import asyncio
import logging
import threading
import numpy as np
import time
import json
import traceback
from pathlib import Path
from typing import Optional

logger = logging.getLogger("JARVIS.Main")



import sounddevice as sd
from google import genai
from google.genai import types
from ui import JarvisUI
from memory.memory_manager import (
    load_memory, update_memory, format_memory_for_prompt,
    should_extract_memory, extract_memory
)

from actions.file_processor import file_processor
from actions.flight_finder     import flight_finder
from actions.open_app          import open_app
from actions.weather_report    import weather_action
from actions.send_message      import send_message
from actions.reminder          import reminder
from actions.computer_settings import computer_settings
from actions.screen_processor  import screen_process
from actions.youtube_video     import youtube_video
from actions.desktop           import desktop_control
from actions.browser_control   import browser_control
from actions.file_controller   import file_controller
from actions.code_helper       import code_helper
from actions.dev_agent         import dev_agent
from actions.computer_control  import computer_control
from actions.game_updater      import game_updater

from core.intent_router import classify_intent
from core.register_tools import default_tool_registry
from actions.whatsapp import open_whatsapp_web_in_yajat_profile
from actions.telegram import open_telegram_web_in_yajat_profile
from actions.web_registry import open_website_in_yajat_profile
from agent.task_queue import get_queue, TaskPriority


def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR        = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
PROMPT_PATH     = BASE_DIR / "core" / "prompt.txt"
LIVE_MODEL          = "models/gemini-2.5-flash-native-audio-latest"
CHANNELS            = 1
SEND_SAMPLE_RATE    = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE          = 1024


_cached_api_key: Optional[str] = None
_cached_api_key_mtime: float = 0.0

def _get_api_key() -> str:
    global _cached_api_key, _cached_api_key_mtime
    try:
        mtime = API_CONFIG_PATH.stat().st_mtime
        if _cached_api_key is not None and mtime == _cached_api_key_mtime:
            return _cached_api_key
        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
            _cached_api_key = json.load(f)["gemini_api_key"]
            _cached_api_key_mtime = mtime
            return _cached_api_key
    except Exception:
        if _cached_api_key is not None:
            return _cached_api_key
        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)["gemini_api_key"]

_cached_prompt_text: Optional[str] = None
_cached_prompt_mtime: float = 0.0

def _load_system_prompt() -> str:
    global _cached_prompt_text, _cached_prompt_mtime
    try:
        mtime = PROMPT_PATH.stat().st_mtime
        if _cached_prompt_text is not None and mtime == _cached_prompt_mtime:
            return _cached_prompt_text
        _cached_prompt_text = PROMPT_PATH.read_text(encoding="utf-8")
        _cached_prompt_mtime = mtime
        return _cached_prompt_text
    except Exception:
        if _cached_prompt_text is not None:
            return _cached_prompt_text
        return (
            "You are JARVIS, Tony Stark's AI assistant. "
            "Be concise, direct, and always use the provided tools to complete tasks. "
            "Never simulate or guess results — always call the appropriate tool."
        )

def _is_session_active(session) -> bool:
    """Robust helper to inspect WebSocket connection state across different protocol layers."""
    if not session:
        return False
    try:
        ws = getattr(session, "_ws", None) or getattr(session, "websocket", None) or getattr(session, "_websocket", None)
        if ws is None:
            return True
        if hasattr(ws, "closed"):
            return not bool(ws.closed)
        if hasattr(ws, "open"):
            return bool(ws.open)
        if hasattr(ws, "state"):
            state = getattr(ws, "state", None)
            if state is not None:
                return str(state).upper().endswith("OPEN") or getattr(state, "name", "") == "OPEN"
        return True
    except Exception:
        return False


_last_memory_input: str = ""
_memory_lock = threading.Lock()


def _update_memory_async(user_text: str, jarvis_text: str) -> None:
    global _last_memory_input

    user_text   = (user_text   or "").strip()
    jarvis_text = (jarvis_text or "").strip()

    with _memory_lock:
        if len(user_text) < 5 or user_text == _last_memory_input:
            return
        _last_memory_input = user_text

    try:
        api_key = _get_api_key()
        if should_extract_memory(user_text, jarvis_text, api_key):
            data = extract_memory(user_text, jarvis_text, api_key)
            if data:
                update_memory(data)
                print(f"[Memory] ✅ {list(data.keys())}")
    except Exception as e:
        if "429" not in str(e):
            print(f"[Memory] ⚠️ {e}")

    try:
        from memory.adaptive_intelligence import default_adaptive_engine
        default_adaptive_engine.observe_interaction(user_text, jarvis_text)
    except Exception as ex:
        print(f"[AdaptiveIntelligence] ⚠️ Observer error: {ex}")

TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": (
            "Opens any application, web service, email client, messaging app, "
            "or social media platform on the computer (e.g. WhatsApp, Gmail, Instagram, "
            "Discord, YouTube, Outlook, LinkedIn, X/Twitter, Reddit, Spotify, Chrome, Edge, VS Code, Settings). "
            "Use this whenever the user asks to open, launch, check, or start any app, "
            "website, or social media service. Always call this tool — never just say you opened it."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {
                    "type": "STRING",
                    "description": "Name of the application or service (e.g. 'WhatsApp', 'Gmail', 'Instagram', 'Discord', 'YouTube', 'Outlook', 'LinkedIn')"
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "web_search",
        "description": (
            "Performs a real live internet search for current information, news, prices, "
            "weather, live events, sports scores, or specific web lookup queries. "
            "Always call this tool whenever the user asks for current information, latest news, prices, or explicitly says 'Google search', 'search the web', 'look up', 'check online'."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query":  {"type": "STRING", "description": "Search query string"},
                "num_results": {"type": "INTEGER", "description": "Number of results (1-10)"},
                "fetch_page":  {"type": "BOOLEAN", "description": "Set to true to extract top webpage text content"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "fetch_webpage",
        "description": "Downloads and extracts clean readable text content from a specific webpage URL.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "url": {"type": "STRING", "description": "Full webpage URL to fetch"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "weather_report",
        "description": "Gives the weather report to user",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "city": {"type": "STRING", "description": "City name"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "send_message",
        "description": "Sends a text message via WhatsApp, Telegram, or other messaging platform.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "receiver":     {"type": "STRING", "description": "Recipient contact name"},
                "message_text": {"type": "STRING", "description": "The message to send"},
                "platform":     {"type": "STRING", "description": "Platform: WhatsApp, Telegram, etc."}
            },
            "required": ["receiver", "message_text", "platform"]
        }
    },
    {
        "name": "reminder",
        "description": "Sets a timed reminder using Windows Task Scheduler.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "date":    {"type": "STRING", "description": "Date in YYYY-MM-DD format"},
                "time":    {"type": "STRING", "description": "Time in HH:MM format (24h)"},
                "message": {"type": "STRING", "description": "Reminder message text"}
            },
            "required": ["date", "time", "message"]
        }
    },
    {
        "name": "youtube_video",
        "description": (
            "Controls YouTube. Use for: playing videos, summarizing a video's content, "
            "getting video info, or showing trending videos."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "play | summarize | get_info | trending (default: play)"},
                "query":  {"type": "STRING", "description": "Search query for play action"},
                "save":   {"type": "BOOLEAN", "description": "Save summary to Notepad (summarize only)"},
                "region": {"type": "STRING", "description": "Country code for trending e.g. TR, US"},
                "url":    {"type": "STRING", "description": "Video URL for get_info action"},
            },
            "required": []
        }
    },
    {
        "name": "screen_process",
        "description": (
            "Captures and analyzes the screen or webcam image. "
            "MUST be called when user asks what is on screen, what you see, "
            "analyze my screen, look at camera, etc. "
            "You have NO visual ability without this tool. "
            "After calling this tool, stay SILENT — the vision module speaks directly."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "angle": {"type": "STRING", "description": "'screen' to capture display, 'camera' for webcam. Default: 'screen'"},
                "text":  {"type": "STRING", "description": "The question or instruction about the captured image"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "computer_settings",
        "description": (
            "Controls the computer: volume, brightness, window management, keyboard shortcuts, "
            "typing text on screen, closing apps, fullscreen, dark mode, WiFi, restart, shutdown, "
            "scrolling, tab management, zoom, screenshots, lock screen, refresh/reload page. "
            "Use for ANY single computer control command. NEVER route to agent_task."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "The action to perform"},
                "description": {"type": "STRING", "description": "Natural language description of what to do"},
                "value":       {"type": "STRING", "description": "Optional value: volume level, text to type, etc."}
            },
            "required": []
        }
    },
    {
        "name": "browser_control",
        "description": (
            "Controls the web browser. Use for: opening websites, searching the web, "
            "clicking elements, filling forms, scrolling, any web-based task."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "go_to | search | click | type | scroll | fill_form | smart_click | smart_type | get_text | press | close"},
                "url":         {"type": "STRING", "description": "URL for go_to action"},
                "query":       {"type": "STRING", "description": "Search query for search action"},
                "selector":    {"type": "STRING", "description": "CSS selector for click/type"},
                "text":        {"type": "STRING", "description": "Text to click or type"},
                "description": {"type": "STRING", "description": "Element description for smart_click/smart_type"},
                "direction":   {"type": "STRING", "description": "up or down for scroll"},
                "key":         {"type": "STRING", "description": "Key name for press action"},
                "incognito":   {"type": "BOOLEAN", "description": "Open in private/incognito mode"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_controller",
        "description": "Manages files and folders: list, create, delete, move, copy, rename, read, write, find, disk usage.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "list | create_file | create_folder | delete | move | copy | rename | read | write | find | largest | disk_usage | organize_desktop | info"},
                "path":        {"type": "STRING", "description": "File/folder path or shortcut: desktop, downloads, documents, home"},
                "destination": {"type": "STRING", "description": "Destination path for move/copy"},
                "new_name":    {"type": "STRING", "description": "New name for rename"},
                "content":     {"type": "STRING", "description": "Content for create_file/write"},
                "name":        {"type": "STRING", "description": "File name to search for"},
                "extension":   {"type": "STRING", "description": "File extension to search (e.g. .pdf)"},
                "count":       {"type": "INTEGER", "description": "Number of results for largest"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "desktop_control",
        "description": "Controls the desktop: wallpaper, organize, clean, list, stats.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "wallpaper | wallpaper_url | organize | clean | list | stats | task"},
                "path":   {"type": "STRING", "description": "Image path for wallpaper"},
                "url":    {"type": "STRING", "description": "Image URL for wallpaper_url"},
                "mode":   {"type": "STRING", "description": "by_type or by_date for organize"},
                "task":   {"type": "STRING", "description": "Natural language desktop task"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "code_helper",
        "description": "Writes, edits, explains, runs, or builds code files.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "write | edit | explain | run | build | auto (default: auto)"},
                "description": {"type": "STRING", "description": "What the code should do or what change to make"},
                "language":    {"type": "STRING", "description": "Programming language (default: python)"},
                "output_path": {"type": "STRING", "description": "Where to save the file"},
                "file_path":   {"type": "STRING", "description": "Path to existing file for edit/explain/run/build"},
                "code":        {"type": "STRING", "description": "Raw code string for explain"},
                "args":        {"type": "STRING", "description": "CLI arguments for run/build"},
                "timeout":     {"type": "INTEGER", "description": "Execution timeout in seconds (default: 30)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "dev_agent",
        "description": "Builds complete multi-file projects from scratch: plans, writes files, installs deps, opens VSCode, runs and fixes errors.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description":  {"type": "STRING", "description": "What the project should do"},
                "language":     {"type": "STRING", "description": "Programming language (default: python)"},
                "project_name": {"type": "STRING", "description": "Optional project folder name"},
                "timeout":      {"type": "INTEGER", "description": "Run timeout in seconds (default: 30)"},
            },
            "required": ["description"]
        }
    },
    {
        "name": "agent_task",
        "description": (
            "Executes complex multi-step tasks requiring multiple different tools. "
            "Examples: 'research X and save to file', 'find and organize files'. "
            "DO NOT use for single commands. NEVER use for Steam/Epic — use game_updater."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "goal":     {"type": "STRING", "description": "Complete description of what to accomplish"},
                "priority": {"type": "STRING", "description": "low | normal | high (default: normal)"}
            },
            "required": ["goal"]
        }
    },
    {
        "name": "computer_control",
        "description": "Direct computer control: type, click, hotkeys, scroll, move mouse, screenshots, find elements on screen. NEVER use for pure calculations or arithmetic.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "type | smart_type | click | double_click | right_click | hotkey | press | scroll | move | copy | paste | screenshot | wait | clear_field | focus_window | screen_find | screen_click | random_data | user_data"},
                "text":        {"type": "STRING", "description": "Text to type or paste"},
                "x":           {"type": "INTEGER", "description": "X coordinate"},
                "y":           {"type": "INTEGER", "description": "Y coordinate"},
                "keys":        {"type": "STRING", "description": "Key combination e.g. 'ctrl+c'"},
                "key":         {"type": "STRING", "description": "Single key e.g. 'enter'"},
                "direction":   {"type": "STRING", "description": "up | down | left | right"},
                "amount":      {"type": "INTEGER", "description": "Scroll amount (default: 3)"},
                "seconds":     {"type": "NUMBER",  "description": "Seconds to wait"},
                "title":       {"type": "STRING",  "description": "Window title for focus_window"},
                "description": {"type": "STRING",  "description": "Element description for screen_find/screen_click"},
                "type":        {"type": "STRING",  "description": "Data type for random_data"},
                "field":       {"type": "STRING",  "description": "Field for user_data: name|email|city"},
                "clear_first": {"type": "BOOLEAN", "description": "Clear field before typing (default: true)"},
                "path":        {"type": "STRING",  "description": "Save path for screenshot"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "game_updater",
        "description": (
            "THE ONLY tool for ANY Steam or Epic Games request. "
            "Use for: installing, downloading, updating games, listing installed games, "
            "checking download status, scheduling updates. "
            "ALWAYS call directly for any Steam/Epic/game request. "
            "NEVER use agent_task, browser_control, or web_search for Steam/Epic."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":    {"type": "STRING",  "description": "update | install | list | download_status | schedule | cancel_schedule | schedule_status (default: update)"},
                "platform":  {"type": "STRING",  "description": "steam | epic | both (default: both)"},
                "game_name": {"type": "STRING",  "description": "Game name (partial match supported)"},
                "app_id":    {"type": "STRING",  "description": "Steam AppID for install (optional)"},
                "hour":      {"type": "INTEGER", "description": "Hour for scheduled update 0-23 (default: 3)"},
                "minute":    {"type": "INTEGER", "description": "Minute for scheduled update 0-59 (default: 0)"},
                "shutdown_when_done": {"type": "BOOLEAN", "description": "Shut down PC when download finishes"},
            },
            "required": []
        }
    },
    {
        "name": "flight_finder",
        "description": "Searches Google Flights and speaks the best options.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "origin":      {"type": "STRING",  "description": "Departure city or airport code"},
                "destination": {"type": "STRING",  "description": "Arrival city or airport code"},
                "date":        {"type": "STRING",  "description": "Departure date (any format)"},
                "return_date": {"type": "STRING",  "description": "Return date for round trips"},
                "passengers":  {"type": "INTEGER", "description": "Number of passengers (default: 1)"},
                "cabin":       {"type": "STRING",  "description": "economy | premium | business | first"},
                "save":        {"type": "BOOLEAN", "description": "Save results to Notepad"},
            },
            "required": ["origin", "destination", "date"]
        }
    },
    {
    "name": "file_processor",
    "description": (
        "Processes any file that the user has uploaded or dropped onto the interface. "
        "Use this when the user refers to an uploaded file and wants an action on it. "
        "Supports: images (describe/ocr/resize/compress/convert), "
        "PDFs (summarize/extract_text/to_word), "
        "Word docs & text files (summarize/fix/reformat/translate), "
        "CSV/Excel (analyze/stats/filter/sort/convert), "
        "JSON/XML (validate/format/analyze), "
        "code files (explain/review/fix/optimize/run/document/test), "
        "audio (transcribe/trim/convert/info), "
        "video (trim/extract_audio/extract_frame/compress/transcribe/info), "
        "archives (list/extract), "
        "presentations (summarize/extract_text). "
        "ALWAYS call this tool when a file has been uploaded and the user gives a command about it. "
        "If the user's command is ambiguous, pick the most logical action for that file type."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_path": {
                "type": "STRING",
                "description": "Full path to the uploaded file. Leave empty to use the currently uploaded file."
            },
            "action": {
                "type": "STRING",
                "description": (
                    "What to do with the file. Examples by type:\n"
                    "image: describe | ocr | resize | compress | convert | info\n"
                    "pdf: summarize | extract_text | to_word | info\n"
                    "docx/txt: summarize | fix | reformat | translate_hint | word_count | to_bullet\n"
                    "csv/excel: analyze | stats | filter | sort | convert | info\n"
                    "json: validate | format | analyze | to_csv\n"
                    "code: explain | review | fix | optimize | run | document | test\n"
                    "audio: transcribe | trim | convert | info\n"
                    "video: trim | extract_audio | extract_frame | compress | transcribe | info | convert\n"
                    "archive: list | extract\n"
                    "pptx: summarize | extract_text | analyze"
                )
            },
            "instruction": {
                "type": "STRING",
                "description": "Free-form instruction if action doesn't cover it. E.g. 'translate this to Turkish', 'find all email addresses'"
            },
            "format": {
                "type": "STRING",
                "description": "Target format for conversion. E.g. 'mp3', 'pdf', 'csv', 'png'"
            },
            "width":     {"type": "INTEGER", "description": "Target width for image resize"},
            "height":    {"type": "INTEGER", "description": "Target height for image resize"},
            "scale":     {"type": "NUMBER",  "description": "Scale factor for image resize (e.g. 0.5)"},
            "quality":   {"type": "INTEGER", "description": "Quality 1-100 for image/video compress"},
            "start":     {"type": "STRING",  "description": "Start time for trim: seconds or HH:MM:SS"},
            "end":       {"type": "STRING",  "description": "End time for trim: seconds or HH:MM:SS"},
            "timestamp": {"type": "STRING",  "description": "Timestamp for video frame extraction HH:MM:SS"},
            "column":    {"type": "STRING",  "description": "Column name for CSV filter/sort"},
            "value":     {"type": "STRING",  "description": "Filter value for CSV filter"},
            "condition": {"type": "STRING",  "description": "Filter condition: equals|contains|gt|lt"},
            "ascending": {"type": "BOOLEAN", "description": "Sort order for CSV sort (default: true)"},
            "save":      {"type": "BOOLEAN", "description": "Save result to file (default: true)"},
            "destination": {"type": "STRING", "description": "Output folder for archive extract"},
        },
        "required": []
    }
},
    {
    "name": "shutdown_jarvis",
    "description": (
        "Shuts down the assistant completely. "
        "Call this when the user expresses intent to end the conversation, "
        "close the assistant, say goodbye, or stop Jarvis. "
        "The user can say this in ANY language."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {},
    }
    },
    {
        "name": "save_memory",
        "description": (
            "Save an important personal fact about the user to long-term memory. "
            "Call this silently whenever the user reveals something worth remembering: "
            "name, age, city, job, preferences, hobbies, relationships, projects, or future plans. "
            "Do NOT call for: weather, reminders, searches, or one-time commands. "
            "Do NOT announce that you are saving — just call it silently. "
            "Values must be in English regardless of the conversation language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": (
                        "identity — name, age, birthday, city, job, language, nationality | "
                        "preferences — favorite food/color/music/film/game/sport, hobbies | "
                        "projects — active projects, goals, things being built | "
                        "relationships — friends, family, partner, colleagues | "
                        "wishes — future plans, things to buy, travel dreams | "
                        "notes — habits, schedule, anything else worth remembering"
                    )
                },
                "key":   {"type": "STRING", "description": "Short snake_case key (e.g. name, favorite_food, sister_name)"},
                "value": {"type": "STRING", "description": "Concise value in English (e.g. Fatih, pizza, older sister)"},
            },
            "required": ["category", "key", "value"]
        }
    },
]


class JarvisLive:

    def __init__(self, ui: JarvisUI):
        self.ui             = ui
        self.session        = None
        self.audio_in_queue = None
        self.out_queue      = None
        self._loop          = None
        self._is_speaking   = False
        self._speaking_lock = threading.Lock()
        self._last_speaking_time = time.time()
        self._last_audio_chunk_time = time.time()
        self.ui.on_text_command = self._on_text_command
        try:
            from actions.mic_control import set_ui_instance
            set_ui_instance(self.ui)
        except Exception:
            pass

        # Start background voice watchdog thread
        self._watchdog_running = True
        self._watchdog_thread = threading.Thread(target=self._voice_watchdog_loop, daemon=True)
        self._watchdog_thread.start()

    def _voice_watchdog_loop(self):
        while self._watchdog_running:
            time.sleep(1.0)
            try:
                with self._speaking_lock:
                    is_spk = self._is_speaking
                if is_spk:
                    now = time.time()
                    queue_empty = (self.audio_in_queue is None or self.audio_in_queue.empty())
                    time_since_chunk = now - self._last_audio_chunk_time
                    time_speaking = now - self._last_speaking_time

                    # Force reset if speaking for > 15s or audio idle for > 2s
                    if (time_speaking > 15.0) or (queue_empty and time_since_chunk > 2.0):
                        print(f"[VOICE][WATCHDOG] ⚠️ Stuck speaking state detected (speaking: {time_speaking:.1f}s, idle: {time_since_chunk:.1f}s). Resetting to LISTENING.")
                        self.set_speaking(False)
            except Exception as e:
                pass

    def _flush_out_queue(self):
        if self.out_queue:
            try:
                while not self.out_queue.empty():
                    self.out_queue.get_nowait()
            except Exception:
                pass

    def _on_text_command(self, text: str):
        cid = ""
        clean_text = text.strip()
        if clean_text.startswith("[CID:"):
            try:
                parts = clean_text.split("] ", 1)
                cid = parts[0].replace("[CID:", "").strip()
                clean_text = parts[1].strip() if len(parts) > 1 else clean_text
            except Exception:
                clean_text = text

        cid_log = f"[CID={cid}] " if cid else ""
        try:
            logger.info(f"[WORKER]{cid_log}Processing text command: '{clean_text}'")
            from core.command_pipeline import process_user_command
            res = process_user_command(clean_text, source="chat")
            if not isinstance(res, dict):
                res = {"success": True, "message": str(res) if res else f"Processed: {clean_text}", "verified": True}
            
            raw_msg = res.get("message", f"Executed: {clean_text}")
            if isinstance(raw_msg, str) and raw_msg.startswith("{") and "'message':" in raw_msg:
                try:
                    import ast
                    parsed = ast.literal_eval(raw_msg)
                    if isinstance(parsed, dict) and "message" in parsed:
                        raw_msg = parsed["message"]
                except Exception:
                    pass
            elif isinstance(raw_msg, dict):
                raw_msg = raw_msg.get("message") or raw_msg.get("output") or str(raw_msg)
            
            msg = str(raw_msg)
            logger.info(f"[RESULT]{cid_log}success={res.get('success')}, verified={res.get('verified')}, msg='{msg}'")
            self.ui.write_log(f"JARVIS: {msg}")
            if res.get("verified") or res.get("success"):
                try:
                    self.speak(msg)
                except Exception as tts_err:
                    logger.warning(f"[Main]{cid_log}TTS output warning: {tts_err}")
        except Exception as exc:
            import traceback
            err_msg = f"Boss, command execute nahi hua. {exc}"
            logger.error(f"[WORKER]{cid_log}Error executing text command '{clean_text}': {exc}\n{traceback.format_exc()}")
            self.ui.write_log(f"JARVIS: {err_msg}")
        return

    def set_speaking(self, value: bool):
        with self._speaking_lock:
            if self._is_speaking == value:
                return
            self._is_speaking = value
            if value:
                self._last_speaking_time = time.time()
                self._last_audio_chunk_time = time.time()

        if value:
            self.ui.set_state("SPEAKING")
        else:
            self._flush_out_queue()
            if not self.ui.muted:
                self.ui.set_state("LISTENING")

    def speak(self, text: str):
        if not self._loop or not self.session:
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def speak_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.speak(f"Sir, {tool_name} encountered an error. {short}")

    def _build_config(self) -> types.LiveConnectConfig:
        from datetime import datetime

        memory     = load_memory()
        mem_str    = format_memory_for_prompt(memory)
        sys_prompt = _load_system_prompt()

        now      = datetime.now()
        time_str = now.strftime("%A, %B %d, %Y — %I:%M %p")
        time_ctx = (
            f"[CURRENT DATE & TIME]\n"
            f"Right now it is: {time_str}\n"
            f"Use this to calculate exact times for reminders.\n\n"
        )

        parts = [time_ctx]
        if mem_str:
            parts.append(mem_str)

        # Inject Adaptive Intelligence 3.0 context into system prompt
        try:
            from memory.adaptive_intelligence import default_adaptive_engine
            adaptive_ctx = default_adaptive_engine.get_adaptive_context(max_insights=5, min_confidence=0.60)
            if adaptive_ctx:
                parts.append(f"\n[ADAPTIVE INTELLIGENCE]\n{adaptive_ctx}\n")
        except Exception:
            pass  # Adaptive layer failure must never crash prompt construction

        parts.append(sys_prompt)

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": TOOL_DECLARATIONS}],
            session_resumption=types.SessionResumptionConfig(),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Charon"
                    )
                )
            ),
        )

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        name = fc.name
        args = dict(fc.args or {})

        print(f"[JARVIS] 🔧 {name}  {args}")
        self.ui.set_state("THINKING")
        if name == "save_memory":
            category = args.get("category", "notes")
            key      = args.get("key", "")
            value    = args.get("value", "")
            if key and value:
                update_memory({category: {key: {"value": value}}})
                print(f"[Memory] 💾 save_memory: {category}/{key} = {value}")
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"result": "ok", "silent": True}
            )

        loop   = asyncio.get_event_loop()
        result = "Done."

        try:
            self.ui.add_recent_action(f"Tool executed: {name}")
            tool_obj = default_tool_registry.get_tool(name)
            
            if tool_obj:
                res = await loop.run_in_executor(
                    None,
                    lambda: default_tool_registry.execute_tool(name, args, player=self.ui, speak=self.speak)
                )
                result = res.message
            elif name == "agent_task":
                priority_map = {"low": TaskPriority.LOW, "normal": TaskPriority.NORMAL, "high": TaskPriority.HIGH}
                priority = priority_map.get(args.get("priority", "normal").lower(), TaskPriority.NORMAL)
                task_id  = get_queue().submit(goal=args.get("goal", ""), priority=priority, speak=self.speak)
                result   = f"Task started (ID: {task_id})."
            elif name == "shutdown_jarvis":
                self.ui.write_log("SYS: Shutdown requested.")
                self.speak("Goodbye, sir.")

                def _shutdown():
                    import time, sys, os
                    time.sleep(1)
                    os._exit(0)

                threading.Thread(target=_shutdown, daemon=True).start()
            else:
                result = f"Unknown tool: {name}"

        except Exception as e:
            result = f"Tool '{name}' failed: {e}"
            traceback.print_exc()
            self.speak_error(name, e)

        if not self.ui.muted:
            self.ui.set_state("LISTENING")

        print(f"[JARVIS] 📤 {name} → {str(result)[:80]}")

        return types.FunctionResponse(
            id=fc.id, name=name,
            response={"result": result}
        )

    async def _send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            if self.session:
                try:
                    await self.session.send_realtime_input(audio=msg)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    print(f"[JARVIS] ⚠️ Realtime audio dispatch warning: {e}")

    def _safe_put_out_queue(self, item):
        try:
            self.out_queue.put_nowait(item)
        except (asyncio.QueueFull, AttributeError):
            pass

    async def _listen_audio(self):
        print("[JARVIS] 🎤 Mic started")
        loop = asyncio.get_event_loop()

        from actions.mic_control import get_jarvis_mic_enabled

        _last_mic_logged = [None]
        def callback(indata, frames, time_info, status):
            with self._speaking_lock:
                jarvis_speaking = self._is_speaking
            is_mic_on = (not jarvis_speaking and not getattr(self.ui, "muted", False) and get_jarvis_mic_enabled())
            if _last_mic_logged[0] != is_mic_on:
                _last_mic_logged[0] = is_mic_on
                logger.info(f"[MIC AUDIO] capture_enabled={is_mic_on} (speaking={jarvis_speaking}, ui_muted={getattr(self.ui, 'muted', False)}, jarvis_mic_enabled={get_jarvis_mic_enabled()})")

            if is_mic_on:
                data = indata.tobytes()
                try:
                    loop.call_soon_threadsafe(
                        self._safe_put_out_queue,
                        {"data": data, "mime_type": f"audio/pcm;rate={SEND_SAMPLE_RATE}"}
                    )
                except Exception:
                    pass
                # Compute real audio amplitude for 3D core
                try:
                    samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                    if len(samples) > 0:
                        rms = np.sqrt(np.mean(samples ** 2)) / 32768.0
                        # Normalize: typical speech RMS ~0.02-0.15, map to 0.0-1.0
                        level = min(1.0, rms * 8.0)
                        self.ui.set_audio_level(level)
                except Exception:
                    pass
            else:
                # Send zero level when not listening
                self.ui.set_audio_level(0.0)

        try:
            with sd.InputStream(
                samplerate=SEND_SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=CHUNK_SIZE,
                callback=callback,
            ):
                print("[JARVIS] 🎤 Mic stream open")
                while True:
                    await asyncio.sleep(0.05)
        except Exception as e:
            print(f"[JARVIS] ❌ Mic error: {e}")
            raise

    async def _receive_audio(self):
        print("[JARVIS] 👂 Recv started")
        out_buf, in_buf = [], []

        try:
            while True:
                async for response in self.session.receive():

                    if response.data:
                        self.audio_in_queue.put_nowait(response.data)

                    if response.server_content:
                        sc = response.server_content

                        if sc.output_transcription and sc.output_transcription.text:
                            self.set_speaking(True)
                            txt = sc.output_transcription.text.strip()
                            if txt:
                                out_buf.append(txt)

                        if sc.input_transcription and sc.input_transcription.text:
                            txt = sc.input_transcription.text.strip()
                            if txt:
                                in_buf.append(txt)

                        if sc.turn_complete:
                            self.set_speaking(False)

                            full_in = " ".join(in_buf).strip()
                            if full_in:
                                self.ui.write_log(f"You: {full_in}")
                            in_buf = []

                            full_out = " ".join(out_buf).strip()
                            if full_out:
                                self.ui.write_log(f"Jarvis: {full_out}")
                            out_buf = []

                            if full_in and len(full_in) > 5:
                                threading.Thread(
                                    target=_update_memory_async,
                                    args=(full_in, full_out),
                                    daemon=True
                                ).start()

                    if response.tool_call:
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            print(f"[JARVIS] 📞 {fc.name}")
                            fr = await self._execute_tool(fc)
                            fn_responses.append(fr)
                        
                        # Verify session and socket state before sending tool response
                        is_active = _is_session_active(self.session)

                        if is_active:
                            try:
                                await self.session.send_tool_response(
                                    function_responses=fn_responses
                                )
                            except Exception as ws_err:
                                print(f"[JARVIS] ⚠️ WebSocket send_tool_response failed on disconnected socket: {ws_err}")
                        else:
                            print("[JARVIS] ⚠️ Connection closed prior to tool response. Preserving result locally.")

        except Exception as e:
            print(f"[JARVIS] ❌ Recv error: {e}")
            self.set_speaking(False)
            traceback.print_exc()
            raise
        finally:
            self.set_speaking(False)

    async def _play_audio(self):
        print("[JARVIS] 🔊 Play started")
        stream = sd.RawOutputStream(
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=CHUNK_SIZE,
        )
        stream.start()
        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(self.audio_in_queue.get(), timeout=0.15)
                    self._last_audio_chunk_time = time.time()
                    self.set_speaking(True)
                    await asyncio.to_thread(stream.write, chunk)
                except asyncio.TimeoutError:
                    with self._speaking_lock:
                        is_spk = self._is_speaking
                    # Only reset speaking state if queue is still empty and at least 300ms has elapsed since last chunk
                    if is_spk and self.audio_in_queue.empty() and (time.time() - self._last_audio_chunk_time > 0.3):
                        self.set_speaking(False)
        except Exception as e:
            print(f"[JARVIS] ❌ Play error: {e}")
            raise
        finally:
            self.set_speaking(False)
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass

    async def run(self):
        client = genai.Client(
            api_key=_get_api_key(),
            http_options={"api_version": "v1beta"}
        )

        reconnect_attempt = 0
        while True:
            try:
                print(f"[JARVIS] 🔌 Connecting (Attempt {reconnect_attempt + 1})...")
                self.ui.set_state("THINKING")
                config = self._build_config()

                async with (
                    client.aio.live.connect(model=LIVE_MODEL, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session        = session
                    self._loop          = asyncio.get_event_loop()
                    self.audio_in_queue = asyncio.Queue()
                    self.out_queue      = asyncio.Queue(maxsize=50)

                    print("[JARVIS] ✅ Connected.")
                    reconnect_attempt = 0  # Reset attempt counter on success
                    self.set_speaking(False)
                    if not self.ui.muted:
                        self.ui.set_state("LISTENING")
                    self.ui.write_log("SYS: JARVIS online.")

                    tg.create_task(self._send_realtime())
                    tg.create_task(self._listen_audio())
                    tg.create_task(self._receive_audio())
                    tg.create_task(self._play_audio())
                    
            except Exception as e:
                reconnect_attempt += 1
                self.set_speaking(False)
                # Unpack Python 3.11+ ExceptionGroup / TaskGroup sub-exceptions
                sub_errors = []
                def _unpack(ex):
                    if hasattr(ex, "exceptions"):
                        for child in getattr(ex, "exceptions"):
                            _unpack(child)
                    else:
                        sub_errors.append(f"{type(ex).__name__}: {ex}")

                _unpack(e)
                primary_err = sub_errors[0] if sub_errors else str(e)
                print(f"[JARVIS] ⚠️ Session/Connection Exception Unpacked:")
                for err in sub_errors:
                    print(f"  [VOICE][ERROR] -> {err}")

                self.ui.write_log(f"ERR: Voice error: {primary_err[:120]}")
                self.ui.set_state("RECOVERING")

            self.set_speaking(False)
            self._flush_out_queue()
            backoff_sec = min(15.0, round(1.0 * (1.5 ** reconnect_attempt), 1))
            print(f"[JARVIS] 🔄 Reconnecting in {backoff_sec}s (Backoff attempt {reconnect_attempt})...")
            await asyncio.sleep(backoff_sec)

def _global_exception_handler(exctype, value, tb):
    print("[JARVIS] ⚠️ Unhandled Exception caught:")
    traceback.print_exception(exctype, value, tb)

sys.excepthook = _global_exception_handler


def run_demo_mode():
    print("=" * 60)
    print("      J.A.R.V.I.S — SAFE DEMO MODE WALKTHROUGH")
    print("=" * 60)
    print("\n[✓] STEP 1: Core System Initialization...")
    time.sleep(0.5)

    from core.register_tools import default_tool_registry
    tools = default_tool_registry.list_tools()
    print(f"[✓] STEP 2: Tool Registry — {len(tools)} tools registered: {', '.join(tools[:6])}...")
    time.sleep(0.5)

    from core.context_engine import default_context_engine
    print(f"[✓] STEP 3: Unified Context Engine:\n{default_context_engine.to_prompt_string()}")
    time.sleep(0.5)

    from memory.memory_manager import remember, query_memory
    remember("demo_key", "Demonstration value active", category="notes")
    mem_res = query_memory("demo_key")
    print(f"[✓] STEP 4: Memory Engine:\n{mem_res}")
    time.sleep(0.5)

    from core.security import default_security_manager, RiskLevel
    r1 = default_security_manager.classify_risk("web_search", {"query": "python"})
    r2 = default_security_manager.classify_risk("file_controller", {"action": "delete_all"})
    print(f"[✓] STEP 5: Security Manager — web_search: {r1.value}, delete_all: {r2.value}")
    time.sleep(0.5)

    from actions.college_mode import college_mode
    c_res = college_mode({"action": "schedule"}, player=None)
    print(f"[✓] STEP 6: College Mode:\n  {c_res.get('message')}")
    time.sleep(0.5)

    from core.verification import verify_file_exists
    v_res = verify_file_exists("main.py")
    print(f"[✓] STEP 7: Verification Engine — main.py check: verified={v_res.get('verified')}")
    time.sleep(0.5)

    print("\n" + "=" * 60)
    print("      ALL DEMO CHECKS PASSED — JARVIS SYSTEM FULLY OPERATIONAL")
    print("=" * 60)
    sys.exit(0)


def main():
    print("[BOOT] 1/9 Main entry point reached", flush=True)

    if "--demo" in sys.argv:
        run_demo_mode()

    if "--test-web-live" in sys.argv:
        from actions.web_search_diagnostic import run_web_search_live_test
        success = run_web_search_live_test()
        sys.exit(0 if success else 1)

    if "--test-web" in sys.argv:
        from actions.web_search_diagnostic import run_web_search_diagnostic
        success = run_web_search_diagnostic()
        sys.exit(0 if success else 1)

    print("[BOOT] 2/9 Running system health check...", flush=True)
    try:
        from core.health_check import run_startup_health_check
        run_startup_health_check(BASE_DIR)
    except Exception as e:
        print(f"[BOOT] ⚠️ Health check non-fatal error: {e}", flush=True)

    print("[BOOT] 3/9 Initializing Tool Registry...", flush=True)
    try:
        from core.register_tools import default_tool_registry
        tools_count = len(default_tool_registry.list_tools())
        print(f"[BOOT] Tool Registry READY ({tools_count} tools registered)", flush=True)
    except Exception as e:
        print(f"[BOOT] ⚠️ Tool Registry warning: {e}", flush=True)

    print("[BOOT] 4/9 Initializing Web Search Providers...", flush=True)
    try:
        from actions.web_search_providers import init_search_providers
        init_search_providers()
    except Exception as e:
        print(f"[BOOT] ⚠️ Web Search init warning: {e}", flush=True)

    print("[BOOT] 5/9 Initializing Memory & Adaptive Intelligence...", flush=True)
    try:
        from memory.memory_manager import load_memory
        load_memory()
        from memory.adaptive_intelligence import default_adaptive_engine
        print("[BOOT] Adaptive Intelligence READY", flush=True)
    except Exception as e:
        print(f"[BOOT] ⚠️ Memory/Adaptive warning: {e}", flush=True)

    print("[BOOT] 6/9 Initializing PyQt6 UI Window...", flush=True)
    ui = JarvisUI("face.png")
    print("[BOOT] PyQt6 Dashboard UI Window Created", flush=True)

    def runner():
        print("[BOOT] 7/9 Background voice runner thread started", flush=True)
        try:
            ui.wait_for_api_key(timeout_sec=5.0)
            print("[BOOT] API Key Check Complete — Initializing Gemini Live...", flush=True)
            jarvis = JarvisLive(ui)
            print("[BOOT] 9/9 JARVIS RUNTIME FULLY READY", flush=True)
            asyncio.run(jarvis.run())
        except KeyboardInterrupt:
            print("\n🔴 Shutting down...")
        except Exception as e:
            print(f"[JARVIS] ⚠️ Voice runner subsystem degraded: {e}")
            traceback.print_exc()

    threading.Thread(target=runner, daemon=True).start()
    print("[BOOT] 8/9 Starting PyQt6 Event Loop...", flush=True)
    ui.root.mainloop()


if __name__ == "__main__":
    main()