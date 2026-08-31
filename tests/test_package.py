# tests/test_package.py
# Package Import & Metadata Verification Test

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

def test_package_exports() -> tuple[bool, str]:
    try:
        import jarvis_api
        from jarvis_api import JarvisAPI, JarvisServer, start_api_server, __version__
        if __version__ == "1.0.0" and JarvisAPI is not None and JarvisServer is not None:
            return True, f"jarvis_api v{__version__} exports verified"
        return False, "Package exports failed check"
    except Exception as e:
        return False, f"Package import exception: {e}"

if __name__ == "__main__":
    passed, msg = test_package_exports()
    print(f"Package Test: {'PASS' if passed else 'FAIL'} - {msg}")
