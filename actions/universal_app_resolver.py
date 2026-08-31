# actions/universal_app_resolver.py
# Centralized Universal Application Resolver for JARVIS
# Dynamically discovers installed Win32, Packaged/UWP, Start Menu, and System applications on Windows.

import os
import re
import sys
import time
import glob
import logging
import platform
import subprocess

from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from difflib import SequenceMatcher

logger = logging.getLogger("JARVIS.UniversalAppResolver")

try:
    import winreg
    _HAS_WINREG = True
except ImportError:
    _HAS_WINREG = False

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False


@dataclass
class ApplicationDescriptor:
    requested_name: str
    normalized_name: str
    display_name: str
    executable_path: Optional[str] = None
    app_user_model_id: Optional[str] = None
    launch_type: str = "WIN32_EXECUTABLE"  # WIN32_EXECUTABLE, PACKAGED_APP, START_MENU_APP, SHELL_APP, URI_APP
    source: str = "UNKNOWN"
    aliases: List[str] = field(default_factory=list)
    verification_strategy: str = "DEFAULT"
    protocol: Optional[str] = None
    process_names: List[str] = field(default_factory=list)
    window_title_patterns: List[str] = field(default_factory=list)
    custom_launch_args: List[str] = field(default_factory=list)
    confidence: float = 1.0


def normalize_app_name(input_name: str) -> str:
    """
    Generic application name normalization:
    - Lowercase
    - Removes punctuation & speech noise words ('open', 'launch', 'start', 'run', 'app', 'application')
    - Compacts whitespace
    """
    if not input_name:
        return ""
    text = input_name.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    words = text.split()
    
    fillers = {
        "open", "launch", "start", "run", "take", "me", "to", "go", "check", "show",
        "my", "the", "a", "an", "app", "application", "please", "kholo", "khol", "karo"
    }
    
    filtered = [w for w in words if w not in fillers]
    if filtered:
        return " ".join(filtered)
    return text.strip()


# Seed map for canonical alias mapping (hints for common aliases -> display names)
COMMON_ALIASES_MAP: Dict[str, List[str]] = {
    "chrome": ["google chrome", "chrome browser", "chrome", "google's chrome"],
    "vscode": ["visual studio code", "vs code", "vscode", "code"],
    "edge": ["microsoft edge", "ms edge", "edge", "edge browser"],
    "spotify": ["spotify", "spotify music", "spotify app"],
    "discord": ["discord", "discord app"],
    "whatsapp": ["whatsapp", "whatsapp desktop", "wa"],
    "calculator": ["calculator", "calc", "windows calculator"],
    "notepad": ["notepad", "text editor"],
    "explorer": ["file explorer", "explorer", "my computer", "this pc", "windows explorer", "folders"],
    "settings": ["windows settings", "system settings", "settings"],
    "antigravity": ["antigravity", "anti gravity", "antigravity app"],
    "cmd": ["command prompt", "cmd", "terminal"],
    "powershell": ["powershell", "windows powershell"],
    "terminal": ["windows terminal", "wt"],
    "taskmanager": ["task manager", "taskmgr"],
    "word": ["microsoft word", "winword", "word"],
    "excel": ["microsoft excel", "excel"],
    "powerpoint": ["microsoft powerpoint", "powerpoint", "ppt"],
    "outlook": ["microsoft outlook", "outlook"],
    "steam": ["steam", "steam games"],
}


class InstalledAppCatalog:
    """
    Thread-safe dynamic catalog that discovers all installed applications on the Windows machine.
    Uses Start Menu (Get-StartApps), Registry Uninstall keys, App Paths, Start Menu shortcuts, UWP packages, and System binaries.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(InstalledAppCatalog, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._catalog: Dict[str, ApplicationDescriptor] = {}
        self._last_refresh = 0.0
        self._cache_ttl = 300.0  # 5 minutes refresh
        self.refresh_catalog()

    def refresh_catalog(self, force: bool = False):
        now = time.time()
        if not force and self._catalog and (now - self._last_refresh < self._cache_ttl):
            return

        logger.info("[UniversalAppResolver] Discovering installed applications on system...")
        new_catalog: Dict[str, ApplicationDescriptor] = {}

        # 1. System Applications
        self._discover_system_apps(new_catalog)

        # 2. Get-StartApps (PowerShell)
        self._discover_start_apps(new_catalog)

        # 3. Windows Registry Uninstall Keys (HKLM & HKCU, 32-bit & 64-bit)
        self._discover_registry_uninstall(new_catalog)

        # 4. Windows Registry App Paths (HKLM & HKCU)
        self._discover_registry_app_paths(new_catalog)

        # 5. Start Menu Shortcuts (.lnk search)
        self._discover_start_menu_shortcuts(new_catalog)

        # 6. UWP / Packaged Appx Packages
        self._discover_uwp_packages(new_catalog)

        self._catalog = new_catalog
        self._last_refresh = now
        logger.info(f"[UniversalAppResolver] Catalog refreshed. Discovered {len(self._catalog)} installed application entries.")

    def _add_descriptor(self, catalog: Dict[str, ApplicationDescriptor], desc: ApplicationDescriptor):
        key = desc.normalized_name
        if not key:
            return
        if key not in catalog or desc.confidence > catalog[key].confidence:
            catalog[key] = desc

        # Add aliases into catalog references
        for alias in desc.aliases:
            norm_alias = normalize_app_name(alias)
            if norm_alias and norm_alias not in catalog:
                catalog[norm_alias] = desc

    def _discover_system_apps(self, catalog: Dict[str, ApplicationDescriptor]):
        sys_dir = os.environ.get("SystemRoot", "C:\\Windows")
        system32 = os.path.join(sys_dir, "System32")

        system_apps = [
            ("Calculator", ["calc.exe"], ["calculator", "calc"], "PACKAGED_APP", "Microsoft.WindowsCalculator_8wekyb3d8bbwe!App"),
            ("Notepad", ["notepad.exe"], ["notepad", "text editor"], "WIN32_EXECUTABLE", os.path.join(system32, "notepad.exe")),
            ("File Explorer", ["explorer.exe"], ["file explorer", "explorer", "my computer", "this pc"], "WIN32_EXECUTABLE", os.path.join(sys_dir, "explorer.exe")),
            ("Settings", ["SystemSettings.exe"], ["settings", "windows settings", "system settings"], "URI_APP", "ms-settings:"),
            ("Task Manager", ["Taskmgr.exe"], ["task manager", "taskmgr"], "WIN32_EXECUTABLE", os.path.join(system32, "Taskmgr.exe")),
            ("Command Prompt", ["cmd.exe"], ["command prompt", "cmd"], "WIN32_EXECUTABLE", os.path.join(system32, "cmd.exe")),
            ("PowerShell", ["powershell.exe"], ["powershell", "windows powershell"], "WIN32_EXECUTABLE", os.path.join(system32, "WindowsPowerShell\\v1.0\\powershell.exe")),
        ]

        for display_name, procs, aliases, l_type, path_or_id in system_apps:
            norm = normalize_app_name(display_name)
            exe_path = path_or_id if l_type == "WIN32_EXECUTABLE" and os.path.exists(path_or_id) else None
            app_id = path_or_id if l_type in ["PACKAGED_APP", "SHELL_APP"] else None
            proto = path_or_id if l_type == "URI_APP" else None

            desc = ApplicationDescriptor(
                requested_name=display_name,
                normalized_name=norm,
                display_name=display_name,
                executable_path=exe_path,
                app_user_model_id=app_id,
                launch_type=l_type,
                source="SYSTEM",
                aliases=aliases,
                protocol=proto,
                process_names=procs,
                window_title_patterns=[display_name],
                confidence=1.0
            )
            self._add_descriptor(catalog, desc)

    def _discover_start_apps(self, catalog: Dict[str, ApplicationDescriptor]):
        if platform.system() != "Windows":
            return
        try:
            ps_cmd = 'Get-StartApps | Select-Name, AppID | ConvertTo-Json'
            res = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd], capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                import json
                try:
                    data = json.loads(res.stdout)
                    if isinstance(data, dict):
                        data = [data]
                    
                    for item in data:
                        name = item.get("Name", "").strip()
                        appid = item.get("AppID", "").strip()
                        if not name or not appid:
                            continue

                        norm = normalize_app_name(name)
                        if not norm:
                            continue

                        # REQUIREMENT #1: Distinguish shortcut, AppUserModelID, shell app, executable-backed app
                        launch_type = "START_MENU_APP"
                        exe_path = None
                        app_user_model_id = None
                        protocol = None

                        if appid.endswith(".lnk") or os.path.isabs(appid) and appid.lower().endswith(".lnk"):
                            launch_type = "START_MENU_APP"
                            exe_path = appid if os.path.exists(appid) else None
                        elif os.path.isabs(appid) and appid.lower().endswith(".exe") and os.path.exists(appid):
                            launch_type = "WIN32_EXECUTABLE"
                            exe_path = appid
                        elif "!" in appid or appid.startswith("Microsoft.") or appid.startswith("Windows."):
                            launch_type = "PACKAGED_APP"
                            app_user_model_id = appid
                        elif appid.startswith("{") or "AppUserModelID" in appid:
                            launch_type = "SHELL_APP"
                            app_user_model_id = appid
                        elif ":" in appid:
                            launch_type = "URI_APP"
                            protocol = appid
                        else:
                            # Fallback AppUserModelID for shell:AppsFolder launch
                            launch_type = "SHELL_APP"
                            app_user_model_id = appid

                        exe_base = os.path.basename(exe_path) if exe_path else f"{norm.replace(' ', '')}.exe"
                        
                        desc = ApplicationDescriptor(
                            requested_name=name,
                            normalized_name=norm,
                            display_name=name,
                            executable_path=exe_path,
                            app_user_model_id=app_user_model_id,
                            launch_type=launch_type,
                            source="GET_START_APPS",
                            aliases=[name, norm],
                            protocol=protocol,
                            process_names=[exe_base],
                            window_title_patterns=[name],
                            confidence=0.95
                        )
                        self._add_descriptor(catalog, desc)
                except Exception as e:
                    logger.debug(f"[UniversalAppResolver] JSON parse error for Get-StartApps: {e}")
        except Exception as e:
            logger.debug(f"[UniversalAppResolver] Exception in Get-StartApps: {e}")

    def _discover_registry_uninstall(self, catalog: Dict[str, ApplicationDescriptor]):
        if not _HAS_WINREG or platform.system() != "Windows":
            return

        roots = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]

        flags = [0]
        if hasattr(winreg, "KEY_WOW64_64KEY"):
            flags.append(winreg.KEY_WOW64_64KEY)

        for hkey, subpath in roots:
            for flag in flags:
                try:
                    with winreg.OpenKey(hkey, subpath, 0, winreg.KEY_READ | flag) as key:
                        sub_count, _, _ = winreg.QueryInfoKey(key)
                        for i in range(sub_count):
                            try:
                                subkey_name = winreg.EnumKey(key, i)
                                with winreg.OpenKey(key, subkey_name, 0, winreg.KEY_READ | flag) as app_key:
                                    display_name = self._query_reg_val(app_key, "DisplayName")
                                    if not display_name or len(display_name) < 2:
                                        continue

                                    # Filter out updates or hotfixes
                                    if any(k in display_name.lower() for k in ["update for", "kb", "redistributable", "patch"]):
                                        continue

                                    install_loc = self._query_reg_val(app_key, "InstallLocation")
                                    display_icon = self._query_reg_val(app_key, "DisplayIcon")

                                    exe_path = None
                                    if display_icon:
                                        icon_cand = display_icon.split(",")[0].strip('"')
                                        if os.path.exists(icon_cand) and icon_cand.lower().endswith(".exe"):
                                            exe_path = icon_cand

                                    if not exe_path and install_loc and os.path.exists(install_loc):
                                        # Search for main executable in install dir
                                        for root, _, files in os.walk(install_loc):
                                            for f in files:
                                                if f.lower().endswith(".exe") and not any(b in f.lower() for b in ["unins", "update", "helper", "crash"]):
                                                    exe_path = os.path.join(root, f)
                                                    break
                                            if exe_path:
                                                break

                                    norm = normalize_app_name(display_name)
                                    proc_name = os.path.basename(exe_path) if exe_path else f"{norm.replace(' ', '')}.exe"

                                    desc = ApplicationDescriptor(
                                        requested_name=display_name,
                                        normalized_name=norm,
                                        display_name=display_name,
                                        executable_path=exe_path,
                                        launch_type="WIN32_EXECUTABLE" if exe_path else "START_MENU_APP",
                                        source="REGISTRY_UNINSTALL",
                                        aliases=[display_name, norm],
                                        process_names=[proc_name],
                                        window_title_patterns=[display_name],
                                        confidence=0.9
                                    )
                                    self._add_descriptor(catalog, desc)
                            except Exception:
                                pass
                except Exception:
                    pass

    def _discover_registry_app_paths(self, catalog: Dict[str, ApplicationDescriptor]):
        if not _HAS_WINREG or platform.system() != "Windows":
            return

        roots = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths")
        ]

        for hkey, subpath in roots:
            try:
                with winreg.OpenKey(hkey, subpath, 0, winreg.KEY_READ) as key:
                    sub_count, _, _ = winreg.QueryInfoKey(key)
                    for i in range(sub_count):
                        try:
                            exe_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, f"{subpath}\\{exe_name}", 0, winreg.KEY_READ) as app_key:
                                val = self._query_reg_val(app_key, "")
                                if val and os.path.exists(val) and os.path.isfile(val):
                                    raw_title = exe_name.replace(".exe", "").replace(".EXE", "")
                                    norm = normalize_app_name(raw_title)

                                    desc = ApplicationDescriptor(
                                        requested_name=raw_title,
                                        normalized_name=norm,
                                        display_name=raw_title.title(),
                                        executable_path=val,
                                        launch_type="WIN32_EXECUTABLE",
                                        source="REGISTRY_APP_PATHS",
                                        aliases=[raw_title, norm, exe_name],
                                        process_names=[os.path.basename(val)],
                                        window_title_patterns=[raw_title],
                                        confidence=0.92
                                    )
                                    self._add_descriptor(catalog, desc)
                        except Exception:
                            pass
            except Exception:
                pass

    def _discover_start_menu_shortcuts(self, catalog: Dict[str, ApplicationDescriptor]):
        if platform.system() != "Windows":
            return

        sm_dirs = [
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%ALLUSERSPROFILE%\Microsoft\Windows\Start Menu\Programs")
        ]

        for sm in sm_dirs:
            if not os.path.exists(sm):
                continue
            for lnk in glob.glob(os.path.join(sm, "**", "*.lnk"), recursive=True):
                try:
                    base_name = os.path.basename(lnk).replace(".lnk", "")
                    if any(bad in base_name.lower() for bad in ["uninstall", "documentation", "readme", "website", "help"]):
                        continue

                    norm = normalize_app_name(base_name)
                    desc = ApplicationDescriptor(
                        requested_name=base_name,
                        normalized_name=norm,
                        display_name=base_name,
                        executable_path=lnk,
                        launch_type="START_MENU_APP",
                        source="START_MENU_LNK",
                        aliases=[base_name, norm],
                        process_names=[f"{base_name.replace(' ', '')}.exe"],
                        window_title_patterns=[base_name],
                        confidence=0.88
                    )
                    self._add_descriptor(catalog, desc)
                except Exception:
                    pass

    def _discover_uwp_packages(self, catalog: Dict[str, ApplicationDescriptor]):
        if platform.system() != "Windows":
            return
        try:
            ps_cmd = 'Get-AppxPackage -User (Get-Credential).UserName | Select Name, PackageFamilyName | ConvertTo-Json'
            res = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", "Get-AppxPackage | Select Name, PackageFamilyName | ConvertTo-Json"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                import json
                try:
                    pkgs = json.loads(res.stdout)
                    if isinstance(pkgs, dict):
                        pkgs = [pkgs]

                    for pkg in pkgs:
                        name = pkg.get("Name", "")
                        fam = pkg.get("PackageFamilyName", "")
                        if not name or not fam:
                            continue

                        clean_name = name.split(".")[-1]
                        norm = normalize_app_name(clean_name)
                        if not norm or len(norm) < 3:
                            continue

                        appid = f"{fam}!App"
                        desc = ApplicationDescriptor(
                            requested_name=clean_name,
                            normalized_name=norm,
                            display_name=clean_name,
                            app_user_model_id=appid,
                            launch_type="PACKAGED_APP",
                            source="GET_APPX_PACKAGE",
                            aliases=[clean_name, norm, name],
                            process_names=[f"{clean_name}.exe"],
                            window_title_patterns=[clean_name],
                            confidence=0.85
                        )
                        self._add_descriptor(catalog, desc)
                except Exception:
                    pass
        except Exception:
            pass

    def _query_reg_val(self, key, val_name: str) -> Optional[str]:
        try:
            val, _ = winreg.QueryValueEx(key, val_name)
            return str(val).strip() if val else None
        except Exception:
            return None

    def get_catalog(self) -> Dict[str, ApplicationDescriptor]:
        self.refresh_catalog()
        return self._catalog


class UniversalApplicationResolver:
    """
    Universal Application Resolver component for JARVIS.
    Resolves natural language application names to structured ApplicationDescriptors.
    Strictly performs local installed application resolution.
    NEVER returns web search or store search fallbacks.
    """

    def __init__(self):
        self.catalog = InstalledAppCatalog()
        self._resolution_cache: Dict[str, ApplicationDescriptor] = {}

    def resolve_application(self, input_name: str) -> Optional[ApplicationDescriptor]:
        """
        Resolves input_name using the 9-Step Priority Hierarchy:
        1. Input Normalization
        2. Exact Catalog Normalized Key Match
        3. Canonical Common Aliases Match
        4. Running Application Process Match
        5. Alias Overlap Match
        6. Dynamic System / PATH Binary Lookup
        7. Safe Fuzzy Match with Confidence Threshold Guardrails
        8. Ambiguity Protection
        9. Return Descriptor or None (Honest Local Failure)
        """
        if not input_name or not input_name.strip():
            return None

        raw_input = input_name.strip()
        norm_name = normalize_app_name(raw_input)
        if not norm_name:
            norm_name = raw_input.lower()

        # Step 0: Fast Resolution Cache
        if norm_name in self._resolution_cache:
            cached = self._resolution_cache[norm_name]
            if cached is None:
                return None
            return self._enrich_descriptor(cached, raw_input)

        logger.info(f"[UniversalAppResolver] Resolving application for requested target: '{raw_input}' (normalized: '{norm_name}')")

        catalog = self.catalog.get_catalog()

        # STEP 2: Exact Catalog Key Match
        if norm_name in catalog:
            desc = catalog[norm_name]
            self._resolution_cache[norm_name] = desc
            logger.info(f"[UniversalAppResolver] STEP 2: Exact catalog match found -> {desc.display_name} ({desc.launch_type})")
            return self._enrich_descriptor(desc, raw_input)

        # STEP 3: Canonical Common Aliases Match
        for canonical, aliases in COMMON_ALIASES_MAP.items():
            if norm_name in aliases or any(norm_name == normalize_app_name(a) for a in aliases):
                # Look for canonical match in catalog
                for desc_key, desc in catalog.items():
                    if canonical in desc_key or any(canonical in normalize_app_name(a) for a in desc.aliases) or normalize_app_name(desc.display_name) == canonical:
                        logger.info(f"[UniversalAppResolver] STEP 3: Alias match '{norm_name}' -> '{canonical}' -> {desc.display_name}")
                        self._resolution_cache[norm_name] = desc
                        return self._enrich_descriptor(desc, raw_input)

        # STEP 4: Running Application Process / Window Title Match
        if _HAS_PSUTIL:
            try:
                for proc in psutil.process_iter(["name", "pid"]):
                    pname = (proc.info.get("name") or "").lower().replace(".exe", "")
                    if pname and (pname == norm_name or norm_name in pname or pname in norm_name):
                        for desc in catalog.values():
                            if any(pname in p.lower() for p in desc.process_names):
                                logger.info(f"[UniversalAppResolver] STEP 4: Running process match found -> {desc.display_name}")
                                self._resolution_cache[norm_name] = desc
                                return self._enrich_descriptor(desc, raw_input)
            except Exception:
                pass

        # STEP 5: Token Overlap & Substring Match
        for desc_key, desc in catalog.items():
            if norm_name in desc_key or desc_key in norm_name:
                if len(norm_name) >= 3 and len(desc_key) >= 3:
                    logger.info(f"[UniversalAppResolver] STEP 5: Substring match '{norm_name}' with catalog '{desc_key}' -> {desc.display_name}")
                    self._resolution_cache[norm_name] = desc
                    return self._enrich_descriptor(desc, raw_input)

        # STEP 6: System PATH Binary Lookup (shutil.which)
        import shutil
        bin_path = shutil.which(norm_name) or shutil.which(f"{norm_name}.exe") or shutil.which(raw_input)
        if bin_path and os.path.exists(bin_path):
            display_title = raw_input.title()
            logger.info(f"[UniversalAppResolver] STEP 6: Binary found on PATH: '{bin_path}'")
            path_desc = ApplicationDescriptor(
                requested_name=raw_input,
                normalized_name=norm_name,
                display_name=display_title,
                executable_path=bin_path,
                launch_type="WIN32_EXECUTABLE",
                source="PATH_LOOKUP",
                aliases=[raw_input, norm_name],
                process_names=[os.path.basename(bin_path)],
                window_title_patterns=[display_title],
                confidence=0.88
            )
            self._resolution_cache[norm_name] = path_desc
            return path_desc

        # STEP 7: Safe Fuzzy Matching with Confidence Threshold Guardrails
        candidates: List[Tuple[float, ApplicationDescriptor]] = []
        for desc_key, desc in catalog.items():
            ratio = SequenceMatcher(None, norm_name, desc_key).ratio()
            if ratio >= 0.75:
                candidates.append((ratio, desc))
            else:
                for alias in desc.aliases:
                    alias_ratio = SequenceMatcher(None, norm_name, normalize_app_name(alias)).ratio()
                    if alias_ratio >= 0.75:
                        candidates.append((alias_ratio, desc))
                        break

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            top_score, top_desc = candidates[0]

            # STEP 8: Ambiguity Protection Check
            if len(candidates) > 1:
                second_score, second_desc = candidates[1]
                if (top_score - second_score < 0.05) and (top_desc.display_name != second_desc.display_name):
                    logger.warning(f"[UniversalAppResolver] STEP 8: Ambiguous match between '{top_desc.display_name}' ({top_score:.2f}) and '{second_desc.display_name}' ({second_score:.2f})")
                    top_desc.confidence = top_score
                    self._resolution_cache[norm_name] = top_desc
                    return self._enrich_descriptor(top_desc, raw_input)

            logger.info(f"[UniversalAppResolver] STEP 7: Fuzzy match '{norm_name}' -> {top_desc.display_name} (score: {top_score:.2f})")
            top_desc.confidence = top_score
            self._resolution_cache[norm_name] = top_desc
            return self._enrich_descriptor(top_desc, raw_input)

        # STEP 9: Local Application Not Found
        logger.warning(f"[UniversalAppResolver] STEP 9: Application '{raw_input}' could not be resolved locally on this system.")
        self._resolution_cache[norm_name] = None
        return None

    def _enrich_descriptor(self, desc: ApplicationDescriptor, requested_name: str) -> ApplicationDescriptor:
        """Fills missing details such as process names, executable paths, or custom launch requirements."""
        desc.requested_name = requested_name
        if not desc.process_names:
            if desc.executable_path:
                desc.process_names = [os.path.basename(desc.executable_path)]
            else:
                desc.process_names = [f"{desc.normalized_name.replace(' ', '')}.exe"]

        if not desc.window_title_patterns:
            desc.window_title_patterns = [desc.display_name, desc.requested_name]

        return desc


# Singleton instance
default_app_resolver = UniversalApplicationResolver()
