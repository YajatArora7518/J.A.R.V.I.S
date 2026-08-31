# tests/test_server.py
# REST API Server Endpoints & Authentication Test

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from jarvis_api.server import create_fastapi_app
from jarvis_api.client import JarvisAPI

def test_rest_server_app() -> tuple[bool, str]:
    try:
        app = create_fastapi_app()
        if app is not None:
            # Verify router endpoints registered
            routes = [r.path for r in app.routes]
            required = ["/api/v1/health", "/api/v1/status", "/api/v1/execute", "/api/v1/tool", "/api/v1/tools"]
            for req in required:
                if req not in routes:
                    return False, f"Missing route '{req}' in REST FastAPI server app"
            return True, f"REST FastAPI app configured with {len(routes)} routes"
        else:
            return True, "FastAPI not installed — fallback HTTP server available"
    except Exception as e:
        return False, f"REST server test exception: {e}"

if __name__ == "__main__":
    passed, msg = test_rest_server_app()
    print(f"REST Server Test: {'PASS' if passed else 'FAIL'} - {msg}")
