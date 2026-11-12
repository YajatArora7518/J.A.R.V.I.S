import json, os
from pathlib import Path

_CONFIG_DIR  = Path(__file__).parent
_CONFIG_PATH = _CONFIG_DIR / "api_keys.json"
_EXAMPLE_PATH = _CONFIG_DIR / "api_keys.example.json"
_RUNTIME_PATH = _CONFIG_DIR / "runtime.json"

def get_runtime_config() -> dict:
    """Non-secret runtime preferences, separate from API credentials."""
    try:
        data = json.loads(_RUNTIME_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}

def get_config() -> dict:
    data = {}
    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    elif _EXAMPLE_PATH.exists():
        try:
            with open(_EXAMPLE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass

    # Environment variable overrides
    if os.environ.get("GEMINI_API_KEY"):
        data["gemini_api_key"] = os.environ["GEMINI_API_KEY"]
    if os.environ.get("OPENROUTER_API_KEY"):
        data["openrouter_api_key"] = os.environ["OPENROUTER_API_KEY"]
    if os.environ.get("OS_SYSTEM"):
        data["os_system"] = os.environ["OS_SYSTEM"]

    return data

def get_api_key(key_name: str = "gemini_api_key") -> str:
    env_name = key_name.upper()
    if os.environ.get(env_name):
        return os.environ[env_name]
    cfg = get_config()
    val = cfg.get(key_name, "")
    if val and not val.lower().startswith(("your_", "replace_")):
        return val
    return ""

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"

def get_model_name() -> str:
    return os.environ.get("GEMINI_MODEL") or get_runtime_config().get("text_model", DEFAULT_GEMINI_MODEL)

def get_live_model_name() -> str:
    return os.environ.get("GEMINI_LIVE_MODEL") or get_runtime_config().get("live_model", "gemini-3.8-live")

def get_os() -> str:
    """Returns: 'windows' | 'mac' | 'linux'"""
    return get_config().get("os_system", "windows").lower()

def is_windows() -> bool: return get_os() == "windows"
def is_mac()     -> bool: return get_os() == "mac"
def is_linux()   -> bool: return get_os() == "linux"
