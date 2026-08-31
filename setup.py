import sys
import subprocess
from pathlib import Path

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

from setuptools import setup, find_packages

BASE_DIR = Path(__file__).resolve().parent
REQ_FILE = BASE_DIR / "requirements.txt"

def run_environment_setup():
    print("========================================")
    print("       JARVIS ENVIRONMENT SETUP")
    print("========================================")

    print(f"[*] Python Runtime: {sys.executable} (v{sys.version.split()[0]})")
    if sys.version_info < (3, 10):
        print("[-] Error: JARVIS requires Python 3.10 or newer.")
        sys.exit(1)

    for d in [BASE_DIR / "config", BASE_DIR / "memory"]:
        d.mkdir(parents=True, exist_ok=True)

    print("[*] Installing & verifying requirements from requirements.txt...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(REQ_FILE)], check=True)
        print("[OK] Pip dependencies installed successfully.")
    except Exception as e:
        print(f"[-] Error installing dependencies: {e}")
        sys.exit(1)

    print("[*] Installing Playwright Chromium browser binaries...")
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        print("[OK] Playwright Chromium browser installed.")
    except Exception as e:
        print(f"[!] Warning: Playwright browser setup failed: {e}")

    print("\n[*] Running final system health check...")
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    from core.health_check import run_startup_health_check
    all_passed, summary = run_startup_health_check(BASE_DIR)

    if all_passed:
        print("\n[OK] Setup complete! Run 'python main.py' to launch JARVIS.")
    else:
        print("\n[!] Setup finished with warnings. Review diagnostic report above.")

if __name__ == "__main__":
    if len(sys.argv) == 1:
        run_environment_setup()
    else:
        setup(
            name="jarvis-api",
            version="1.0.0",
            packages=find_packages(),
        )

