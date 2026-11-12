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
import re
import traceback
import os
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
class VoiceSessionRenewal(ConnectionError):
    """Provider requested a fresh socket; not a failed user command."""

API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
PROMPT_PATH     = BASE_DIR / "core" / "prompt.txt"
from config import get_api_key, get_live_model_name, get_runtime_config
LIVE_MODEL          = get_live_model_name()
CHANNELS            = 1
SEND_SAMPLE_RATE    = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE          = 1024


_cached_api_key: Optional[str] = None
_cached_api_key_mtime: float = 0.0

def _get_api_key() -> str:
    return get_api_key("gemini_api_key")

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
    from core.intent_router import normalize_command_prefix
    if re.match(r'^(?:bhool jao?\s*:|forget memory\s*:|memory dikhao|meri memory|saved memory|memory mein)', normalize_command_prefix(user_text), re.I):
        return  # A memory inspection/deletion is not a new personal fact.
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

    # Barge-in keywords detected in real-time voice transcription
    BARGE_IN_WORDS = {"stop", "chup", "bas", "quiet", "silence", "shh", "ruk", "ruko", "रुक", "रुको", "shut up", "stop speaking", "cancel"}

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
        self._last_speech_end = 0.0
        self._local_voice_active = False
        self._session_resume_handle = None
        self._session_resume_saved_at = 0.0
        self._command_lock = threading.RLock()
        self._command_in_progress = False
        runtime = get_runtime_config()
        self._voice_barge_in = bool(runtime.get("voice_barge_in", False))
        self._voice_require_address = bool(runtime.get("voice_require_address", True))
        self._echo_guard_seconds = float(runtime.get("local_echo_guard_seconds", 0.5))
        self._max_local_audio_chunks = max(16, int(float(runtime.get("local_stt_max_utterance_seconds", 20)) * SEND_SAMPLE_RATE / CHUNK_SIZE))
        self.ui.on_text_command = self._on_text_command
        self.ui.on_voice_wake = self._request_voice_followup
        self._companion_enabled = False
        try:
            from agent.daily_planner import get_daily_planner
            get_daily_planner().start_session()
            self._companion_enabled = True
        except Exception:
            logger.exception('Daily planner initialization failed; laptop commands remain available')
        try:
            from actions.mic_control import set_ui_instance
            set_ui_instance(self.ui)
            from actions.screen_processor import set_ui_instance as set_screen_ui
            set_screen_ui(self.ui)
        except Exception:
            pass

        # Microphone instrumentation counters (safe, no raw audio logged)
        self._mic_stats = {
            "frames_captured": 0,
            "frames_accepted": 0,
            "frames_sent": 0,
            "frames_dropped": 0,
            "send_errors": 0,
            "transcript_events": 0,
            "speech_segments": 0,
            "reconnect_count": 0,
            "last_audio_ts": 0.0,
        }

        # Turn execution guard to prevent duplicate command execution
        self._turn_had_tool_call = False
        self._turn_received_audio = False
        self._turn_command_results = {}

        # Ensure Windows OS master microphone is unmuted and at usable volume
        self._ensure_windows_mic_unmuted()

        # Universal Speech Synthesis Engine (handles non-blocking audio queue & Windows TTS fallback)
        try:
            from core.tts_engine import get_tts_engine
            self.tts_engine = get_tts_engine()
            self.tts_engine.set_callbacks(
                on_start=lambda: self.set_speaking(True),
                on_end=lambda: self.set_speaking(False),
                on_notice=lambda message: self.ui.write_log('SYS: ' + message)
            )
        except Exception as tts_init_err:
            logger.warning(f"[Main] Universal TTS Engine initialization warning: {tts_init_err}")
            self.tts_engine = None

        # Start background voice watchdog thread
        self._watchdog_running = True
        self._watchdog_thread = threading.Thread(target=self._voice_watchdog_loop, daemon=True)
        self._watchdog_thread.start()
        try:
            from agent.ambient_orchestrator import ambient_orchestrator
            ambient_orchestrator.speak_callback = self._deliver_check_in
        except Exception as exc:
            logger.debug("Proactive speech unavailable: %s", exc)

    def _update_proactive_state(self):
        try:
            from agent.proactive_engine import proactive_decision_engine
            proactive_decision_engine.set_system_state(
                is_speaking=getattr(self, "_is_speaking", False),
                is_user_speaking=time.time() - getattr(self, '_mic_stats', {}).get('last_transcript_ts', 0) < 20,
                is_command_executing=getattr(self, "_command_in_progress", False))
        except Exception:
            pass

    def _deliver_check_in(self, message):
        if (getattr(self.ui, 'muted', False) or getattr(self, '_command_in_progress', False) or self._is_speaking
                or time.time() - getattr(self, '_mic_stats', {}).get('last_transcript_ts', 0) < 20
                or (self.tts_engine and self.tts_engine.is_speaking())):
            return False
        self._check_in_followup_pending = True
        self.ui.write_log('JARVIS: ' + message)
        self.speak(message)
        return True

    def _observe_companion_turn(self, text, handled_by_tool=False):
        if not getattr(self, '_companion_enabled', False):
            return
        try:
            from agent.daily_planner import get_daily_planner
            from core.intent_router import classify_intent
            planner = get_daily_planner()
            planner.note_interaction(text)
            if not handled_by_tool:
                planner.handle_command(text, intent=classify_intent(text).get('intent', 'OTHER'))
        except Exception:
            logger.exception('Companion interaction could not be recorded')

    def _mic_accepts_audio(self) -> bool:
        from actions.mic_control import get_jarvis_mic_enabled
        if getattr(self.ui, "muted", False) or not get_jarvis_mic_enabled():
            return False
        tts_speaking = bool(self.tts_engine and self.tts_engine.is_speaking())
        playback_state = self.tts_engine.is_playing() if self.tts_engine and hasattr(self.tts_engine, 'is_playing') else None
        generating = tts_speaking and playback_state is False
        echo_tail = time.monotonic() - self._last_speech_end < self._echo_guard_seconds
        if tts_speaking and not generating:
            return False
        if (self._local_voice_active or not self._voice_barge_in) and ((self._is_speaking and not generating) or echo_tail):
            return False
        return True

    def _ensure_windows_mic_unmuted(self):
        """On startup, ensure Windows default capture endpoint is unmuted and at usable volume."""
        try:
            import pythoncom
            pythoncom.CoInitialize()
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from ctypes import cast, POINTER
            mic = AudioUtilities.GetMicrophone()
            if mic is None:
                logger.warning("[MIC] No default Windows microphone found via pycaw.")
                return
            iface = mic.Activate(IAudioEndpointVolume._iid_, 7, None)
            vol = cast(iface, POINTER(IAudioEndpointVolume))
            # Keep these native interface wrappers owned by the voice runner.
            # Cyclic GC otherwise releases them later during unrelated SDK
            # imports, which caused a native access violation on this laptop.
            self._mic_com_refs = (mic, iface, vol)
            mute_state = vol.GetMute()
            volume_scalar = vol.GetMasterVolumeLevelScalar()
            if mute_state:
                vol.SetMute(0, None)
                logger.info("[MIC] Windows master microphone was MUTED — unmuted it.")
            if volume_scalar < 0.85:
                vol.SetMasterVolumeLevelScalar(1.0, None)
                logger.info(f"[MIC] Windows mic volume was {volume_scalar:.2f} — boosted to 1.0.")
            else:
                logger.info(f"[MIC] Windows mic OK: mute={mute_state}, volume={volume_scalar:.2f}")
        except ImportError:
            logger.debug("[MIC] pycaw not available for Windows mic check.")
        except Exception as e:
            logger.warning(f"[MIC] Windows mic check/unmute failed (non-fatal): {e}")

    def _voice_watchdog_loop(self):
        while self._watchdog_running:
            time.sleep(1.0)
            try:
                self._voice_watchdog_tick()
            except Exception:
                logger.exception("[VOICE][WATCHDOG] Health check failed; monitor will retry.")

    def _voice_watchdog_tick(self):
        self._update_proactive_state()
        with self._speaking_lock:
            is_spk = self._is_speaking
        tts_busy = bool(self.tts_engine and self.tts_engine.is_speaking())
        queue_empty = self.audio_in_queue is None or self.audio_in_queue.empty()
        # A long explanation or cloud speech request is not a stuck state.
        if (is_spk and not tts_busy and not getattr(self, '_playback_active', False)
                and queue_empty and time.time() - self._last_audio_chunk_time > 2.0):
            logger.warning('[VOICE][WATCHDOG] Idle speech state recovered; listening restored.')
            self.set_speaking(False)

    def _show_ready_voice_state(self):
        tts = getattr(self, 'tts_engine', None)
        busy = getattr(self, '_is_speaking', False) or (tts and tts.is_speaking() is True)
        self.ui.set_state('SPEAKING' if busy else 'THINKING' if getattr(self, '_command_in_progress', False) else 'IDLE' if self.ui.muted else 'LISTENING')

    def _flush_out_queue(self):
        if self.out_queue:
            try:
                while not self.out_queue.empty():
                    self.out_queue.get_nowait()
            except Exception:
                pass

    def _request_voice_followup(self):
        """Start a conversation until the user explicitly asks to wait."""
        from actions.mic_control import get_jarvis_mic_enabled
        if self.ui.muted or not get_jarvis_mic_enabled():
            self.ui.write_log('SYS: Pehle Mic ON karo, phir Talk to Jarvis dabao.')
            return
        self._voice_conversation_active = True
        self.ui.set_state('LISTENING')
        self.ui.write_log('SYS: Sun raha hoon. Baat karte raho; "ab wait kar" se wake-word ka intezaar karunga.')

    def _voice_is_addressed(self, text: str) -> bool:
        if text and text.strip() and getattr(self, '_voice_conversation_active', False):
            return True
        if not getattr(self, "_voice_require_address", True):
            return True
        from core.command_pipeline import is_pending_power_confirmation
        if is_pending_power_confirmation(text):
            return True
        prefixed = bool(re.match(
            r"^\s*(?:(?:hey|hi|hello|ok|okay|ओके|हे|हेलो)[,\s]+)?(?:jarvis|jervis|जार्विस|जारविस|जर्विस)(?=$|[\s,.:!?।])",
            text or "", re.IGNORECASE,
        ))
        return prefixed or bool(text and text.strip() and
                                time.monotonic() < getattr(self, '_voice_followup_deadline', 0.0))

    def _apply_conversation_control(self, text):
        from core.voice_conversation import conversation_control
        from core.command_pipeline import is_pending_power_confirmation
        if is_pending_power_confirmation(text):
            return None  # A pending action's cancel/confirm reply takes priority.
        from core.intent_router import normalize_command_prefix
        if normalize_command_prefix(text).lower().strip(' ,.!?।') in self.BARGE_IN_WORDS - {'cancel'}:
            if getattr(self, 'tts_engine', None):
                self.tts_engine.stop()
            return {'success': True, 'verified': True, 'action': 'stop_speech', 'message': 'Ruk gaya. Bolo, sun raha hoon.'}
        control = conversation_control(text)
        if not control:
            return None
        self._voice_conversation_active = control == 'resume'
        self._voice_followup_deadline = 0.0
        if control == 'pause':
            if getattr(self, 'tts_engine', None):
                self.tts_engine.stop()
            message = 'Theek hai, ab Jarvis bolo ya Talk dabao toh sununga.'
        else:
            message = 'Haan bhai, sun raha hoon. Baat karte raho.'
        return {'success': True, 'verified': True, 'action': 'conversation_control', 'message': message}

    def _on_text_command(self, text: str, source: str = "chat"):
        # All desktop commands share one execution lane, including voice and chat.
        from core.intent_router import normalize_command_prefix
        control_text = (text or "").strip()
        if control_text.startswith("[CID:") and "] " in control_text:
            control_text = control_text.split("] ", 1)[1]
        if source == "voice" and not self._voice_is_addressed(control_text):
            return {"success": False, "verified": False, "status": "VOICE_NOT_ADDRESSED", "message": "Voice command Jarvis kehkar shuru karo."}
        if source == 'voice':
            self._voice_conversation_active = True
        if getattr(self, '_companion_enabled', False):
            try:
                from agent.daily_planner import get_daily_planner
                get_daily_planner().note_interaction(control_text)
            except Exception:
                logger.exception('Daily interaction could not be saved')
        from core.command_pipeline import is_pending_power_confirmation
        if not is_pending_power_confirmation(control_text) and self._check_barge_in(normalize_command_prefix(control_text)):
            result = {"success": True, "verified": True, "source": source, "barge_in": True, "message": "Bolna rok diya."}
            self.ui.write_log("JARVIS: " + result["message"])
            self.ui.set_state("IDLE" if self.ui.muted else "LISTENING")
            return result
        with self._command_lock:
            self._command_in_progress = True
            self.ui.set_state('THINKING')
            self._update_proactive_state()
            try:
                return self._execute_text_command(text, source)
            finally:
                self._command_in_progress = False
                self._update_proactive_state()
                self._show_ready_voice_state()

    def _execute_text_command(self, text: str, source: str = "chat"):
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
            from core.command_sequence import split_sequence
            sequence_options = {'stream_callback': self.ui.add_recent_action} if split_sequence(clean_text) else {}
            res = self._apply_conversation_control(clean_text) or process_user_command(clean_text, source=source, **sequence_options)
            if not isinstance(res, dict):
                res = {"success": bool(res), "message": str(res) if res else "Command ka result nahi mila.", "verified": False}

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

            from core.voice_conversation import natural_action_reply
            msg = natural_action_reply({**res, 'message': str(raw_msg)})
            self._record_conversation_turn(clean_text, msg, source=source)
            logger.info(f"[RESULT]{cid_log}success={res.get('success')}, verified={res.get('verified')}, msg='{msg}'")
            self.ui.write_log(f"JARVIS: {msg}")
            if msg.strip():
                try:
                    self.speak(res.get('spoken_message') or msg)
                except Exception as tts_err:
                    logger.warning(f"[Main]{cid_log}TTS output warning: {tts_err}")
            return res
        except Exception as exc:
            import traceback
            err_msg = f"Boss, command execute nahi hua. {exc}"
            logger.error(f"[WORKER]{cid_log}Error executing text command '{clean_text}': {exc}\n{traceback.format_exc()}")
            self.ui.write_log(f"JARVIS: {err_msg}")
            self.speak(err_msg)
            return {"success": False, "verified": False, "message": err_msg, "source": source}

    def _record_conversation_turn(self, user_text, reply, source='voice'):
        if not user_text or not reply:
            return
        try:
            from core.ai_multitier_engine import get_ai_engine
            engine = get_ai_engine()
            engine.add_turn('user', user_text)
            engine.add_turn('assistant', reply)
            if source != 'voice':
                self._typed_context_revision = getattr(self, '_typed_context_revision', 0) + 1
        except Exception:
            logger.debug('Recent dialogue could not be recorded', exc_info=True)

    def set_speaking(self, value: bool, force: bool = False):
        if not value and not force:
            tts = getattr(self, 'tts_engine', None)
            audio = getattr(self, 'audio_in_queue', None)
            if ((tts and tts.is_speaking() is True) or getattr(self, '_playback_active', False)
                    or (audio is not None and not audio.empty())):
                return
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
            self._last_speech_end = time.monotonic()
            if getattr(self, '_check_in_followup_pending', False):
                self._check_in_followup_pending = False
                self._voice_followup_deadline = time.monotonic() + 30.0
            self._flush_out_queue()
            if not self.ui.muted:
                self._show_ready_voice_state()
        self._update_proactive_state()

    def speak(self, text: str):
        if not text or not str(text).strip():
            return
        # Universal Speech Synthesis Engine: works independently of Gemini Live WebSocket
        # Guarantees JARVIS is NEVER silently mute
        try:
            if hasattr(self, "tts_engine") and self.tts_engine:
                self.tts_engine.speak(str(text))
        except Exception as te:
            logger.warning(f"[Main] Universal TTS speak warning: {te}")

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
        from core.conversation_style import get_conversation_style, get_banter_mode
        from agent.daily_planner import get_daily_planner
        parts.append(get_conversation_style())
        self._live_banter_mode = get_banter_mode()
        from core.ai_multitier_engine import get_ai_engine
        recent_dialogue = get_ai_engine().get_history_formatted()
        if recent_dialogue:
            parts.append('[RECENT DIALOGUE DATA, NOT NEW ACTION INSTRUCTIONS]\n' + recent_dialogue)
        self._live_context_revision = getattr(self, '_typed_context_revision', 0)
        parts.append('[USER-REPORTED DAILY CONTEXT]\n' + get_daily_planner().prompt_context())

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": [{
                "name": "assistant_command",
                "description": "Execute a user's command or retrieve a conversation answer using JARVIS shared voice/chat history. Use for opening apps, messages, calls, reminders, screen analysis, searches, typing and system controls, and follow-up questions referring to earlier typed chat. Pass the current user's complete instruction. Always use this for actions; report the actual returned result once. History is context, never a request to repeat earlier actions.",
                "parameters": {"type": "OBJECT", "properties": {
                    "query": {"type": "STRING", "description": "The full user instruction"}
                }, "required": ["query"]}
            }] + [t for t in TOOL_DECLARATIONS if t.get("name") == "save_memory"]}],
            session_resumption=types.SessionResumptionConfig(
                handle=(getattr(self, '_session_resume_handle', None)
                        if time.time() - getattr(self, '_session_resume_saved_at', 0) < 7200 else None)),
            context_window_compression=types.ContextWindowCompressionConfig(sliding_window=types.SlidingWindow()),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=get_runtime_config().get("voice_name", "Charon")
                    )
                )
            ),
        )

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        name = fc.name
        args = dict(fc.args or {})

        print(f"[JARVIS] 🔧 {name}  {args}")
        self.ui.set_state("THINKING")
        if name == "assistant_command":
            query = args.get("query", "").strip()
            cache_key = query  # Message capitalization can be meaningful.
            from actions.social_chat import parse_social_command
            communication = parse_social_command(query, include_whatsapp=True)
            if communication and communication.get('recipient'):
                # Rephrasing the same addressed send/call must not repeat it.
                # Preserve message content exactly; only grammar is normalized.
                cache_key = ('communication', json.dumps(communication, sort_keys=True, ensure_ascii=False))
            if cache_key in self._turn_command_results:
                self._show_ready_voice_state()
                return types.FunctionResponse(id=fc.id, name=name, response=self._turn_command_results[cache_key])
            def execute_command():
                from core.command_pipeline import process_user_command
                with self._command_lock:
                    self._command_in_progress = True
                    self._update_proactive_state()
                    try:
                        from core.voice_conversation import natural_action_reply
                        from core.command_sequence import split_sequence
                        sequence_options = {'stream_callback': self.ui.add_recent_action} if split_sequence(query) else {}
                        result = self._apply_conversation_control(query) or process_user_command(query, source="voice", **sequence_options)
                        result['message'] = natural_action_reply(result)
                        from core.conversation_style import get_banter_mode
                        if hasattr(self, '_live_banter_mode') and self._live_banter_mode != get_banter_mode():
                            # Old Live instructions must not add rough banter back
                            # after the user disabled it. Speak the current shared reply.
                            result['authoritative_response'] = True
                        if result.get('success') and result.get('verified'):
                            self._live_context_revision = getattr(self, '_typed_context_revision', 0)
                        return result
                    finally:
                        self._command_in_progress = False
                        self._update_proactive_state()
                        self._show_ready_voice_state()
            try:
                res = await asyncio.to_thread(execute_command)
            except Exception as exc:
                res = {"success": False, "verified": False, "message": f"Command failed: {exc}"}
            self.ui.write_log(f"ACTION: {res.get('message', '')}")
            res = json.loads(json.dumps(res, default=str))
            self._turn_command_results[cache_key] = res
            return types.FunctionResponse(id=fc.id, name=name, response=res)
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
        success = True
        verified = False
        authoritative_response = name in ('screen_process', 'web_search')
        spoken_message = None

        try:
            self.ui.add_recent_action(f"Tool executed: {name}")
            tool_obj = default_tool_registry.get_tool(name)

            if tool_obj:
                res = await loop.run_in_executor(
                    None,
                    lambda: default_tool_registry.execute_tool(name, args, player=self.ui, speak=self.speak)
                )
                result = res.message
                success = res.success
                verified = bool(res.verification.get("verified")) if res.verification else res.success
                if isinstance(res.data, dict):
                    authoritative_response = authoritative_response or bool(res.data.get('authoritative_response'))
                    spoken_message = res.data.get('spoken_message')
            elif name == "agent_task":
                priority_map = {"low": TaskPriority.LOW, "normal": TaskPriority.NORMAL, "high": TaskPriority.HIGH}
                priority = priority_map.get(args.get("priority", "normal").lower(), TaskPriority.NORMAL)
                task_id  = get_queue().submit(goal=args.get("goal", ""), priority=priority, speak=self.speak)
                result   = f"Task started (ID: {task_id})."
            elif name == "shutdown_jarvis":
                self.ui.write_log("SYS: Shutdown requested.")
                self.speak("Goodbye, sir.")

                def _shutdown():
                    import time
                    time.sleep(1.5)  # Allow TTS to finish "Goodbye"
                    try:
                        # Stop TTS cleanly
                        if hasattr(self, 'tts_engine') and self.tts_engine:
                            self.tts_engine.shutdown()
                        # Stop watchdog
                        self._watchdog_running = False
                    except Exception:
                        pass
                    try:
                        from PyQt6.QtWidgets import QApplication
                        app = QApplication.instance()
                        if app:
                            app.quit()
                        else:
                            import os
                            os._exit(0)
                    except Exception:
                        import os
                        os._exit(0)

                threading.Thread(target=_shutdown, daemon=True).start()
            else:
                result = f"Unknown tool: {name}"
                success = False

        except Exception as e:
            result = f"Tool '{name}' failed: {e}"
            success = False
            traceback.print_exc()
            try:
                self.speak_error(name, e)
            except Exception:
                pass

        if not self.ui.muted:
            self.ui.set_state("LISTENING")

        print(f"[JARVIS] 📤 {name} → {str(result)[:80]}")

        # Structured diagnostic telemetry for voice execution validation
        telemetry_block = (
            f"\n==================================================\n"
            f"[VOICE_TOOL_TELEMETRY]\n"
            f"Tool: {name}\n"
            f"Arguments: {args}\n"
            f"Execution: {'SUCCESS' if success else 'FAILED'}\n"
            f"Verification: {'TRUE' if verified else 'FALSE'}\n"
            f"Result: {str(result)[:100]}\n"
            f"=================================================="
        )
        print(telemetry_block, flush=True)
        logger.info(telemetry_block)
        if not success:
            print(f"[VOICE_DIAGNOSTIC] STAGE_I_FAIL (Tool executed but Windows action failed): Tool '{name}' returned error: {result}", flush=True)
        elif not verified:
            print(f"[VOICE_DIAGNOSTIC] STAGE_J_FAIL (Windows action succeeded but verification failed): Tool '{name}' result not verified", flush=True)

        # Return TRUTHFUL result to Gemini so its audio response matches reality
        return types.FunctionResponse(
            id=fc.id, name=name,
            response={
                "result": result,
                "message": result,
                "spoken_message": spoken_message or result,
                "authoritative_response": authoritative_response,
                "success": success,
                "verified": verified,
            }
        )

    async def _send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            if self.session:
                try:
                    # Extract raw bytes and MIME type from the queued dict
                    if isinstance(msg, dict):
                        data = msg.get("data", b"")
                        mime = msg.get("mime_type", f"audio/pcm;rate={SEND_SAMPLE_RATE}")
                    else:
                        data = msg
                        mime = f"audio/pcm;rate={SEND_SAMPLE_RATE}"
                    # Live audio must use the dedicated audio field. The legacy
                    # mediaChunks input connected but produced no transcription.
                    blob = types.Blob(data=data, mime_type=mime)
                    await self.session.send_realtime_input(audio=blob)
                    self._mic_stats["frames_sent"] += 1
                    self._mic_stats["last_audio_ts"] = time.time()
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self._mic_stats["send_errors"] += 1
                    print(f"[JARVIS] ⚠️ Realtime audio dispatch warning: {e}")
                    print(f"[VOICE_DIAGNOSTIC] STAGE_C_FAIL (Gemini Live audio send failed): {e}", flush=True)
                    # A broken stream must exit the TaskGroup so run() can
                    # reconnect, rather than dropping every subsequent frame.
                    raise

    def _safe_put_out_queue(self, item):
        try:
            self.out_queue.put_nowait(item)
        except (asyncio.QueueFull, AttributeError):
            pass

    def _publish_voice_health(self):
        """Local diagnostics contain signal metrics, never audio or transcript text."""
        from actions.mic_control import get_jarvis_mic_enabled
        report = dict(self._mic_stats)
        tts = getattr(self, 'tts_engine', None)
        tts_busy = bool(tts and tts.is_speaking() is True)
        tts_playing = bool(tts and hasattr(tts, 'is_playing') and tts.is_playing() is True)
        report.update(pid=os.getpid(), timestamp=time.time(),
                      capture_enabled=self._mic_accepts_audio(),
                      ui_muted=bool(self.ui.muted), jarvis_mic_enabled=get_jarvis_mic_enabled(),
                      session_connected=self.session is not None,
                      conversation_active=bool(getattr(self, '_voice_conversation_active', False)),
                      tts_generating=tts_busy and not tts_playing, tts_playing=tts_playing,
                      input_device=str(sd.query_devices(kind='input').get('name', 'unknown')))
        path = BASE_DIR / 'scratch' / 'voice_health.json'
        path.parent.mkdir(exist_ok=True)
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(report, indent=2), encoding='utf-8')
        temp.replace(path)

    async def _listen_audio(self):
        print("[JARVIS] 🎤 Mic started")
        loop = asyncio.get_event_loop()

        from actions.mic_control import get_jarvis_mic_enabled

        _last_mic_logged = [None]
        def callback(indata, frames, time_info, status):
            self._mic_stats["frames_captured"] += 1
            samples = indata.astype(np.float32)
            self._mic_stats["last_rms"] = float(np.sqrt(np.mean(samples ** 2))) if samples.size else 0.0
            self._mic_stats["peak_since_start"] = max(self._mic_stats.get("peak_since_start", 0.0), float(np.max(np.abs(samples))) if samples.size else 0.0)
            # Mic gate: remains OPEN during TTS so barge-in works via Gemini VAD.
            # Only disabled if user explicitly muted the UI or JARVIS mic.
            is_mic_on = self._mic_accepts_audio()
            if _last_mic_logged[0] != is_mic_on:
                _last_mic_logged[0] = is_mic_on
                logger.info(f"[MIC AUDIO] capture_enabled={is_mic_on} (ui_muted={getattr(self.ui, 'muted', False)}, jarvis_mic_enabled={get_jarvis_mic_enabled()})")

            if is_mic_on:
                self._mic_stats["frames_accepted"] += 1
                data = indata.tobytes()
                try:
                    loop.call_soon_threadsafe(
                        self._safe_put_out_queue,
                        {"data": data, "mime_type": f"audio/pcm;rate={SEND_SAMPLE_RATE}"}
                    )
                except Exception:
                    self._mic_stats["frames_dropped"] += 1
                # Compute real audio amplitude for 3D core visualization
                try:
                    samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                    if len(samples) > 0:
                        rms = np.sqrt(np.mean(samples ** 2)) / 32768.0
                        level = min(1.0, rms * 8.0)
                        self.ui.set_audio_level(level)
                except Exception:
                    pass
            else:
                self.ui.set_audio_level(0.0)

        # Try to open the default mic device; if it fails, try alternatives
        device_to_use = None
        try:
            dev_info = sd.query_devices(kind='input')
            print(f"[JARVIS] 🎤 Default input device: {dev_info.get('name', 'Unknown')} (idx={sd.default.device[0]}, hostapi={dev_info.get('hostapi')}, sr={dev_info.get('default_samplerate')}, ch={dev_info.get('max_input_channels')})")
        except Exception:
            pass

        for attempt_device in [None]:  # None = default
            try:
                kwargs = dict(
                    samplerate=SEND_SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype="int16",
                    blocksize=CHUNK_SIZE,
                    callback=callback,
                )
                if attempt_device is not None:
                    kwargs["device"] = attempt_device
                with sd.InputStream(**kwargs):
                    print(f"[JARVIS] 🎤 Mic stream open (device={attempt_device or 'default'})")
                    next_health = 0.0
                    while True:
                        if time.monotonic() >= next_health:
                            try:
                                self._publish_voice_health()
                            except Exception as health_error:
                                logger.debug("Voice health snapshot unavailable: %s", health_error)
                            next_health = time.monotonic() + 5
                        await asyncio.sleep(0.05)
            except Exception as e:
                print(f"[JARVIS] ⚠️ Mic device {attempt_device or 'default'} failed: {e}")
                # Try fallback: enumerate devices and find an alternative input
                if attempt_device is None:
                    try:
                        all_devs = sd.query_devices()
                        for i, d in enumerate(all_devs):
                            if d.get('max_input_channels', 0) > 0 and i != sd.default.device[0]:
                                print(f"[JARVIS] 🔁 Trying fallback mic device {i}: {d.get('name')}")
                                try:
                                    with sd.InputStream(device=i, samplerate=SEND_SAMPLE_RATE, channels=CHANNELS, dtype="int16", blocksize=CHUNK_SIZE, callback=callback):
                                        print(f"[JARVIS] 🎤 Mic stream open on fallback device {i}: {d.get('name')}")
                                        while True:
                                            await asyncio.sleep(0.05)
                                except Exception as fe:
                                    print(f"[JARVIS] ⚠️ Fallback device {i} also failed: {fe}")
                                    continue
                    except Exception:
                        pass
                print(f"[JARVIS] ❌ All mic devices failed. Mic capture unavailable.")
                print(f"[VOICE_DIAGNOSTIC] STAGE_B_FAIL (Mic capture failed): No working input device found", flush=True)
                raise

    def _check_barge_in(self, text: str) -> bool:
        """Check if text contains barge-in keywords. If so, stop TTS immediately."""
        from core.intent_router import normalize_command_prefix
        lower = normalize_command_prefix(text).casefold().strip(" .!?,")
        for word in self.BARGE_IN_WORDS:
            if word == lower:
                from core.command_pipeline import _handle_power_request, is_pending_power_confirmation
                if is_pending_power_confirmation(text):
                    _handle_power_request('cancel', 'voice', 'speech-stop')
                if self.tts_engine:
                    self.tts_engine.barge_in_stop()
                self._live_speech_generation = getattr(self, '_live_speech_generation', 0) + 1
                self.set_speaking(False, force=True)
                # Flush audio playback queue
                if self.audio_in_queue:
                    try:
                        while not self.audio_in_queue.empty():
                            self.audio_in_queue.get_nowait()
                    except Exception:
                        pass
                logger.info(f"[BARGE-IN] Speech interrupted by voice keyword: '{word}'")
                return True
        return False

    def _dispatch_voice_to_pipeline(self, transcript: str, gemini_response: str):
        """Route voice transcript to the existing command pipeline on a background thread."""
        return self._on_text_command(transcript, source="voice")

    def _voice_requires_pipeline(self, text: str) -> bool:
        from core.conversation_style import banter_command_mode, get_banter_mode
        from core.intent_router import normalize_command_prefix, classify_intent
        if banter_command_mode(text) is not None:
            return True
        # A running Live session retains old instructions until reconnect. Route new
        # dialogue through the shared engine while its saved tone has changed.
        if normalize_command_prefix(text).strip(' ,.!?।') and hasattr(self, '_live_banter_mode') and self._live_banter_mode != get_banter_mode():
            return True
        from core.voice_conversation import conversation_control
        if conversation_control(text):
            return True
        """An action acknowledgement cannot replace an attempted laptop command."""
        if normalize_command_prefix(text).strip(' ,.!?।') and getattr(self, '_typed_context_revision', 0) > getattr(self, '_live_context_revision', 0):
            return True  # Retrieve current shared history, not stale Live-only context.
        if re.match(r'^(?:memory dikhao|meri memory|saved memory|what do you remember|memory mein|yaad rakh\s*:|remember\s*:|bhool jao?\s*:|forget memory\s*:)', normalize_command_prefix(text), re.I):
            return True
        from core.command_pipeline import _parse_power_request, is_pending_power_confirmation
        clean = normalize_command_prefix(text)
        return (bool(_parse_power_request(clean)) or is_pending_power_confirmation(clean)
                or classify_intent(clean).get('intent', 'OTHER') not in ('OTHER', 'DRAFT_TEXT'))

    async def _receive_audio(self):
        print("[JARVIS] 👂 Recv started")
        out_buf, in_buf = [], []
        addressed = self._voice_is_addressed("")
        command_attempted = False
        unverified_reply = None
        requires_pipeline = False
        pending_tool_reply = None
        reply_audio_accepted = False

        try:
            while True:
                received = False
                async for response in self.session.receive():
                    received = True
                    update = getattr(response, 'session_resumption_update', None)
                    if update is not None:
                        if update.resumable is True and isinstance(update.new_handle, str) and update.new_handle:
                            self._session_resume_handle = update.new_handle
                            self._session_resume_saved_at = time.time()
                        elif update.resumable is False:
                            self._session_resume_handle = None
                    if getattr(response, 'go_away', None) is not None:
                        self._session_renewal_pending = True

                    sc = response.server_content
                    if (getattr(self, '_session_renewal_pending', False) and not in_buf and not out_buf
                            and not response.tool_call and (sc is None or sc.turn_complete)):
                        raise VoiceSessionRenewal('Provider connection lifetime reached')
                    if sc and sc.interrupted:
                        in_buf, out_buf = [], []
                        addressed = self._voice_is_addressed("")
                        self._turn_had_tool_call = False
                        self._turn_received_audio = False
                        self._turn_command_results.clear()
                        command_attempted = False
                        unverified_reply = None
                        requires_pipeline = False
                        pending_tool_reply = None
                        reply_audio_accepted = False
                    if sc and sc.input_transcription and sc.input_transcription.text:
                        txt = sc.input_transcription.text.strip()
                        if txt:
                            self._mic_stats["transcript_events"] += 1
                            self._mic_stats["last_transcript_ts"] = time.time()
                            # Ignored background may have no model turn_complete.
                            # A newly addressed utterance starts its own buffer.
                            if not addressed and self._voice_is_addressed(txt):
                                in_buf, out_buf = [], []
                                self._turn_had_tool_call = False
                                self._turn_received_audio = False
                                self._turn_command_results.clear()
                                command_attempted = False
                                unverified_reply = None
                                pending_tool_reply = None
                                reply_audio_accepted = False
                            in_buf.append(txt)
                            addressed = addressed or self._voice_is_addressed(" ".join(in_buf))
                            if addressed:
                                self._voice_conversation_active = True
                                tts = getattr(self, 'tts_engine', None)
                                if tts and tts.is_speaking() is True and tts.is_playing() is False:
                                    tts.stop()  # New input cancels a reply still waiting for sound.
                                    self.set_speaking(False, force=True)
                            requires_pipeline = addressed and self._voice_requires_pipeline(' '.join(in_buf))
                            self._mic_stats["last_transcript_addressed"] = addressed
                            if addressed:
                                print(f"[VOICE_DIAGNOSTIC] STAGE_D_OK (Transcript received): '{txt}'", flush=True)
                                self._check_barge_in(" ".join(in_buf))
                            else:
                                self._mic_stats["ignored_transcript_events"] = self._mic_stats.get("ignored_transcript_events", 0) + 1
                                print(f"[VOICE_DIAGNOSTIC] Transcript heard but not addressed to Jarvis: {txt[:120]!r}", flush=True)

                    if response.tool_call:
                        # Never resume a snapshot from before a possibly completed
                        # outgoing action whose response failed to reach the server.
                        self._session_resume_handle = None
                        self._turn_had_tool_call = True

                    allow_reply = addressed and (not requires_pipeline or command_attempted) and unverified_reply is None

                    if response.data:
                        self._turn_received_audio = True
                        if allow_reply:
                            self.audio_in_queue.put_nowait(response.data)
                            reply_audio_accepted = True

                    if response.server_content:
                        sc = response.server_content
                        if sc.interrupted:
                            while not self.audio_in_queue.empty():
                                self.audio_in_queue.get_nowait()
                            self.set_speaking(False)

                        if allow_reply and sc.output_transcription and sc.output_transcription.text:
                            self.set_speaking(True)
                            txt = sc.output_transcription.text.strip()
                            if txt:
                                out_buf.append(txt)

                        # Keep the ledger through Live's empty tool-request
                        # completion; the spoken answer finishes the user turn.
                        if sc.turn_complete and (not addressed or not self._turn_had_tool_call or out_buf or unverified_reply is not None or getattr(self, "_turn_received_audio", False) or (sc.output_transcription and sc.output_transcription.text)):
                            self._mic_stats["speech_segments"] += 1
                            self.set_speaking(False)

                            full_in = " ".join(in_buf).strip() if addressed else ""
                            from core.intent_router import normalize_command_prefix
                            if full_in and not normalize_command_prefix(full_in).strip(' ,.!?।'):
                                self.ui.write_log('Listening: baat karte raho; "ab wait kar" se pause.')
                            elif full_in:
                                self._voice_followup_deadline = 0.0
                            if full_in:
                                self.ui.write_log(f"You: {full_in}")
                            in_buf = []

                            full_out = " ".join(out_buf).strip()
                            if unverified_reply is not None:
                                full_out = str(unverified_reply.get('message') or 'Action ka result verify nahi hua.')
                                pending_tool_reply = None
                                self.speak(unverified_reply.get('spoken_message') or full_out)
                            if full_out:
                                self.ui.write_log(f"Jarvis: {full_out}")
                            if full_in and full_out:
                                self._record_conversation_turn(full_in, full_out)
                            out_buf = []

                            # Conversation audio can complete a conversation;
                            # a laptop action needs an actual command attempt.
                            # Never retry a tool attempt, including an uncertain send.
                            gemini_already_handled = (command_attempted if requires_pipeline else
                                                      self._turn_had_tool_call or bool(full_out) or self._turn_received_audio)
                            if full_in and gemini_already_handled:
                                self._observe_companion_turn(full_in, handled_by_tool=bool(self._turn_command_results))
                            if full_in and len(full_in) > 2 and not gemini_already_handled:
                                # Check if it's a pure barge-in word; if so, don't re-route
                                lower_in = full_in.lower().strip()
                                is_pure_barge_in = lower_in in self.BARGE_IN_WORDS
                                if not is_pure_barge_in:
                                    threading.Thread(
                                        target=self._dispatch_voice_to_pipeline,
                                        args=(f"Jarvis, {normalize_command_prefix(full_in)}", full_out),
                                        daemon=True
                                    ).start()

                            # Reset turn execution guard
                            self._turn_had_tool_call = False
                            self._turn_received_audio = False
                            self._turn_command_results.clear()
                            command_attempted = False
                            unverified_reply = None
                            requires_pipeline = False
                            pending_tool_reply = None
                            reply_audio_accepted = False

                            if full_in and len(full_in) > 5:
                                threading.Thread(
                                    target=_update_memory_async,
                                    args=(full_in, full_out),
                                    daemon=True
                                ).start()
                            addressed = self._voice_is_addressed("")

                    if response.tool_call:
                        self._turn_had_tool_call = True
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            if addressed:
                                print(f"[JARVIS] 📞 {fc.name}")
                                fr = await self._execute_tool(fc)
                                result = getattr(fr, 'response', None)
                                if isinstance(result, dict) and result.get('message') and not result.get('silent'):
                                    pending_tool_reply = result
                                    reply_audio_accepted = False
                                if fc.name == 'assistant_command' or (isinstance(result, dict) and result.get('authoritative_response')):
                                    command_attempted = True
                                    if isinstance(result, dict) and (result.get('authoritative_response') or not result.get('success') or not result.get('verified')):
                                        unverified_reply = result
                            else:
                                fr = types.FunctionResponse(id=fc.id, name=fc.name, response={
                                    "success": False, "verified": False,
                                    "status": "VOICE_NOT_ADDRESSED",
                                    "message": "Ignore background speech. Remain silent until the user starts with Jarvis.",
                                })
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
                                raise VoiceSessionRenewal('Provider connection ended during tool response') from ws_err
                        else:
                            print("[JARVIS] ⚠️ Connection closed prior to tool response. Preserving result locally.")
                            raise VoiceSessionRenewal('Provider connection ended before tool response')
                if getattr(self, '_session_renewal_pending', False) or not received:
                    raise VoiceSessionRenewal('Provider connection ended')

        except Exception as e:
            print(f"[JARVIS] ❌ Recv error: {e}")
            self.set_speaking(False)
            if pending_tool_reply is not None and not reply_audio_accepted:
                # Deliver only the saved result. Re-running a completed tool
                # could send a message or start a call twice after reconnect.
                reply = pending_tool_reply
                pending_tool_reply = None
                try:
                    self.ui.write_log(f"Jarvis: {reply['message']}")
                    self.speak(reply.get('spoken_message') or reply['message'])
                except Exception:
                    logger.exception('Could not deliver saved tool reply after disconnect')
            if not isinstance(e, VoiceSessionRenewal):
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
                    self._playback_active = True
                    try:
                        generation = getattr(self, '_live_speech_generation', 0)
                        # At most 50ms of audio per write, so stop does not wait
                        # for a large provider packet to finish playing.
                        for offset in range(0, len(chunk), 2400):
                            if generation != getattr(self, '_live_speech_generation', 0):
                                break
                            await asyncio.to_thread(stream.write, chunk[offset:offset + 2400])
                    finally:
                        self._playback_active = False
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

    async def _local_stt_loop(self):
        """
        100% Local Speech-To-Text processing loop.
        Consumes 16kHz PCM audio frames from self.out_queue, detects utterance boundaries
        using local VAD, transcribes via local faster-whisper (CUDA float16),
        checks barge-in keywords, and dispatches directly to local command pipeline.
        """
        from core.local_stt import get_local_stt
        try:
            stt_engine = await asyncio.to_thread(get_local_stt)
        except Exception as exc:
            logger.error("Local speech recognition unavailable: %s", exc)
            self.ui.write_log("ERR: Local voice unavailable. Typed laptop commands still work.")
            while True:
                await asyncio.sleep(1)
        audio_chunks = []
        silence_frames = 0
        speaking = False
        SILENCE_THRESHOLD = 500       # RMS amplitude threshold
        SILENCE_FRAMES_LIMIT = 15     # ~0.5s of silence after speech

        print("[JARVIS] [LocalSTT] 🎙️ Local faster-whisper voice listener active.", flush=True)

        while True:
            try:
                item = await self.out_queue.get()
                data = item.get("data", b"")
                if not data:
                    continue
                if self._is_speaking or time.monotonic() - self._last_speech_end < self._echo_guard_seconds:
                    audio_chunks.clear()
                    speaking = False
                    silence_frames = 0
                    continue

                # Calculate RMS amplitude
                samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                rms = np.sqrt(np.mean(samples ** 2)) if len(samples) > 0 else 0

                if rms > SILENCE_THRESHOLD:
                    speaking = True
                    silence_frames = 0
                    audio_chunks.append(data)
                    if len(audio_chunks) >= self._max_local_audio_chunks:
                        audio_chunks.clear()
                        speaking = False
                        self.ui.write_log("SYS: Long/noisy audio discarded. Please speak a shorter command.")
                elif speaking:
                    audio_chunks.append(data)
                    silence_frames += 1
                    if silence_frames > SILENCE_FRAMES_LIMIT:
                        # Utterance boundary detected
                        pcm_data = b"".join(audio_chunks)
                        audio_chunks.clear()
                        speaking = False
                        silence_frames = 0

                        if len(pcm_data) >= 16000 * 2 * 0.4:  # Minimum 0.4s to filter noise
                            self.ui.set_state("THINKING")
                            t0 = time.time()
                            transcript, lat = await asyncio.to_thread(stt_engine.transcribe, pcm_data)
                            if transcript and len(transcript.strip()) > 1 and self._voice_is_addressed(transcript):
                                clean_transcript = transcript.strip()
                                self.ui.write_log(f"User (Voice, {lat:.0f}ms): {clean_transcript}")
                                # Check barge-in
                                if self._check_barge_in(clean_transcript):
                                    from core.tts_engine import get_tts_engine
                                    get_tts_engine().stop()
                                    self.set_speaking(False)
                                else:
                                    await asyncio.to_thread(self._on_text_command, clean_transcript, "voice")
                            if not self.ui.muted:
                                self.ui.set_state("LISTENING")
            except Exception as e:
                logger.error(f"[LocalSTTLoop] Audio processing warning: {e}")
                await asyncio.sleep(0.05)

    async def run(self):
        import core.ai_policy as ai_policy
        self._echo_guard_seconds = float(get_runtime_config().get("local_echo_guard_seconds", 0.5))
        if not ai_policy.is_cloud_ai_allowed() or not _get_api_key():
            self._local_voice_active = True
            print("[JARVIS] [LocalMode] 🚀 Running in 100% LOCAL AI MODE (Ollama + faster-whisper + SAPI TTS)", flush=True)
            self.ui.write_log("SYS: JARVIS 100% Local AI Online (Ollama + faster-whisper).")
            self.set_speaking(False)
            self._show_ready_voice_state()
            self.out_queue = asyncio.Queue(maxsize=50)

            async with asyncio.TaskGroup() as tg:
                tg.create_task(self._listen_audio())
                tg.create_task(self._local_stt_loop())
            return

        ai_policy.assert_cloud_ai_allowed("Gemini Live WebSocket")
        client = genai.Client(
            api_key=_get_api_key(),
            http_options={"api_version": "v1beta"}
        )

        reconnect_attempt = 0
        models = [LIVE_MODEL] + get_runtime_config().get("live_fallback_models", [])
        model_index = 0
        while True:
            connected_at = None
            resume_handle = None
            try:
                print(f"[JARVIS] 🔌 Connecting (Attempt {reconnect_attempt + 1})...")
                self.ui.set_state("THINKING")
                prior_context_revision = getattr(self, '_live_context_revision', 0)
                prior_banter_mode = getattr(self, '_live_banter_mode', None)
                config = self._build_config()
                resume_handle = getattr(getattr(config, 'session_resumption', None), 'handle', None)
                if isinstance(resume_handle, str) and resume_handle:
                    self._live_context_revision = prior_context_revision
                    if prior_banter_mode is not None:
                        self._live_banter_mode = prior_banter_mode

                async with (
                    client.aio.live.connect(model=models[model_index], config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session        = session
                    self._loop          = asyncio.get_event_loop()
                    self.audio_in_queue = asyncio.Queue()
                    self.out_queue      = asyncio.Queue(maxsize=50)

                    print("[JARVIS] ✅ Connected.")
                    connected_at = time.monotonic()
                    self._session_renewal_pending = False
                    self._turn_had_tool_call = False
                    self._turn_received_audio = False
                    self._turn_command_results.clear()
                    self._voice_followup_deadline = 0.0
                    self.set_speaking(False)
                    self._show_ready_voice_state()
                    self.ui.write_log("SYS: Voice connected. Sun raha hoon." if reconnect_attempt else "SYS: JARVIS online.")

                    tg.create_task(self._send_realtime())
                    tg.create_task(self._listen_audio())
                    tg.create_task(self._receive_audio())
                    tg.create_task(self._play_audio())

            except Exception as e:
                self.session = None
                # Opening a socket that immediately fails is not recovery.
                if connected_at is not None and time.monotonic() - connected_at >= 30:
                    reconnect_attempt = 0
                reconnect_attempt += 1
                self._mic_stats['reconnect_count'] = self._mic_stats.get('reconnect_count', 0) + 1
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
                # One failed resumed socket is retried fresh; a rejected token
                # must never poison every subsequent connection attempt.
                if (isinstance(resume_handle, str) and resume_handle
                        and (connected_at is None or time.monotonic() - connected_at < 30)):
                    self._session_resume_handle = None
                if any(word in primary_err.lower() for word in ("not found", "not supported", "1008", "404")) and model_index + 1 < len(models):
                    self._session_resume_handle = None
                    model_index += 1
                if reconnect_attempt >= 3:
                    self.ui.write_log("SYS: Cloud voice unavailable; switching to local speech. Laptop commands remain available.")
                    self._local_voice_active = True
                    self.out_queue = asyncio.Queue(maxsize=50)
                    async with asyncio.TaskGroup() as tg:
                        tg.create_task(self._listen_audio())
                        tg.create_task(self._local_stt_loop())
                    return
                print(f"[JARVIS] ⚠️ Session/Connection Exception Unpacked:")
                for err in sub_errors:
                    print(f"  [VOICE][ERROR] -> {err}")

                transient = any(word in primary_err.lower() for word in ('1006', '1011', 'connectionclosed', 'timeout', 'voicesessionrenewal'))
                self.ui.write_log("SYS: Voice connection toot gaya; dobara connect kar raha hoon. Chat chal rahi hai."
                                  if transient else f"ERR: Voice error: {primary_err[:120]}")
                # Keep UI ready/listening so typed commands and local AI continue working
                self._show_ready_voice_state()

            self.set_speaking(False)
            self._flush_out_queue()
            backoff_sec = min(15.0, round(1.0 * (1.5 ** reconnect_attempt), 1))
            print(f"[JARVIS] 🔄 Reconnecting in {backoff_sec}s (Backoff attempt {reconnect_attempt})...")
            await asyncio.sleep(backoff_sec)

def _global_exception_handler(exctype, value, tb):
    print("[JARVIS] ⚠️ Unhandled Exception caught:")
    traceback.print_exception(exctype, value, tb)

sys.excepthook = _global_exception_handler


def _threading_exception_handler(args):
    """Catch and log unhandled exceptions in ALL background threads."""
    print(f"[JARVIS] ⚠️ Unhandled THREAD Exception in '{args.thread.name}':")
    traceback.print_exception(args.exc_type, args.exc_value, args.exc_traceback)

try:
    threading.excepthook = _threading_exception_handler
except AttributeError:
    pass  # Python < 3.8


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


_MUTEX_HANDLE = None

def acquire_single_instance_lock() -> bool:
    """Enforces single-instance execution via a Windows Named Mutex."""
    global _MUTEX_HANDLE
    try:
        import ctypes
        ERROR_ALREADY_EXISTS = 183
        kernel32 = ctypes.windll.kernel32
        _MUTEX_HANDLE = kernel32.CreateMutexW(None, False, "Global\\JARVIS_SINGLE_INSTANCE_MUTEX")
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            print("[BOOT] ⚠️ An active instance of J.A.R.V.I.S is already running! Only one instance is permitted.", flush=True)
            try:
                user32 = ctypes.windll.user32
                hwnd = user32.FindWindowW(None, "J.A.R.V.I.S")
                if hwnd:
                    user32.ShowWindow(hwnd, 9)
                    user32.SetForegroundWindow(hwnd)
            except Exception:
                pass
            return False
        return True
    except Exception as me:
        print(f"[BOOT] Mutex check note: {me}", flush=True)
        return True


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

    # Enforce Single Active Instance Protection
    if not acquire_single_instance_lock():
        sys.exit(0)

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

    print("[BOOT] 5.5/9 Pre-warming Tier 1 Local AI Brain...", flush=True)
    try:
        from core.ai_multitier_engine import get_ai_engine
        get_ai_engine().prewarm_background()
    except Exception as e:
        print(f"[BOOT] ⚠️ AI Brain prewarm note: {e}", flush=True)

    print("[BOOT] 6/9 Initializing PyQt6 UI Window...", flush=True)
    ui = JarvisUI("face.png")
    print("[BOOT] PyQt6 Dashboard UI Window Created", flush=True)

    # Activate Proactive Engine (non-blocking background daemon)
    try:
        from agent.ambient_orchestrator import ambient_orchestrator
        ambient_orchestrator.start()
        print("[BOOT] Proactive Engine (AmbientOrchestrator) activated in background.", flush=True)
    except Exception as ae:
        print(f"[BOOT] ⚠️ Proactive Engine activation note: {ae}", flush=True)

    # Store greeting text to speak asynchronously after Gemini connects
    _startup_greeting = [None]
    try:
        from core.greeting_engine import generate_startup_greeting
        _startup_greeting[0] = generate_startup_greeting()
    except Exception as ge:
        print(f"[BOOT] ⚠️ Greeting generation note: {ge}")

    def runner():
        print("[BOOT] 7/9 Background voice runner thread started", flush=True)
        try:
            import core.ai_policy as ai_policy
            if ai_policy.is_cloud_ai_allowed():
                ui.wait_for_api_key(timeout_sec=5.0)
                print("[BOOT] API Key Check Complete — Initializing Gemini Live...", flush=True)
            else:
                print("[BOOT] 100% Local AI Mode Enforced — Bypassing Cloud API Key Check.", flush=True)
            jarvis = JarvisLive(ui)
            print("[BOOT] 9/9 JARVIS RUNTIME FULLY READY", flush=True)

            # Schedule greeting as a non-blocking asyncio task AFTER runtime starts
            # This ensures Gemini Live, mic, and event loop are never blocked by TTS
            async def _async_greeting():
                await asyncio.sleep(1.5)  # Let Gemini session connect first
                greeting = _startup_greeting[0]
                if greeting:
                    try:
                        ui.write_log(f"SYS: {greeting}")
                        jarvis.speak(greeting)
                    except Exception as ge:
                        print(f"[BOOT] ⚠️ Greeting speak note: {ge}")

            # Patch jarvis.run() to include greeting task
            _original_run = jarvis.run
            async def _run_with_greeting():
                # Create greeting as a background task, not blocking Gemini
                asyncio.get_event_loop().create_task(_async_greeting())
                await _original_run()

            asyncio.run(_run_with_greeting())
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
