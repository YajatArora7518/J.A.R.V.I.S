# jarvis_api/server.py
# Production REST API Server for JARVIS

import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from jarvis_api.config import JarvisConfig
from jarvis_api.client import JarvisAPI
from jarvis_api.version import __version__

logger = logging.getLogger("JARVIS.RESTServer")


def create_fastapi_app(jarvis: Optional[JarvisAPI] = None):
    try:
        from fastapi import FastAPI, HTTPException, Header, Depends, status
        from fastapi.middleware.cors import CORSMiddleware
        from pydantic import BaseModel
    except ImportError:
        return None

    app = FastAPI(
        title="JARVIS REST API",
        version=__version__,
        description="RESTful Developer API for controlling JARVIS personal AI assistant.",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    jarvis_client = jarvis or JarvisAPI()
    cfg = jarvis_client.config

    # Restricted Localhost CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1", "http://localhost"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Auth Dependency
    def verify_api_key(x_jarvis_api_key: Optional[str] = Header(None)):
        if cfg.api_server_key and x_jarvis_api_key != cfg.api_server_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing X-JARVIS-API-KEY header."
            )
        return x_jarvis_api_key

    # Request Schemas
    class ExecuteRequest(BaseModel):
        command: str

    class ToolRequest(BaseModel):
        tool: str
        arguments: Optional[Dict[str, Any]] = None

    class TaskRequest(BaseModel):
        goal: str
        priority: Optional[str] = "normal"

    class MemoryRequest(BaseModel):
        key: str
        value: Any
        category: Optional[str] = "notes"

    @app.get("/api/v1/health")
    def health_check():
        st = jarvis_client.get_status()
        return {
            "status": st.status,
            "version": __version__,
            "all_systems_operational": st.all_systems_operational
        }

    @app.get("/api/v1/status", dependencies=[Depends(verify_api_key)])
    def system_status():
        return jarvis_client.get_status().to_dict()

    @app.get("/api/v1/tools", dependencies=[Depends(verify_api_key)])
    def list_tools():
        return {"tools": jarvis_client.list_tools()}

    @app.post("/api/v1/execute", dependencies=[Depends(verify_api_key)])
    def execute_command(req: ExecuteRequest):
        try:
            res = jarvis_client.execute(req.command)
            return res.to_dict()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/v1/tool", dependencies=[Depends(verify_api_key)])
    def call_tool(req: ToolRequest):
        try:
            res = jarvis_client.call_tool(req.tool, req.arguments or {})
            return res.to_dict()
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/v1/task", dependencies=[Depends(verify_api_key)])
    def submit_task(req: TaskRequest):
        try:
            res = jarvis_client.run_task(req.goal, req.priority or "normal")
            return res.to_dict()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/v1/memory", dependencies=[Depends(verify_api_key)])
    def get_memory(category: Optional[str] = None, key: Optional[str] = None):
        return {"memory": jarvis_client.get_memory(category, key)}

    @app.post("/api/v1/memory", dependencies=[Depends(verify_api_key)])
    def save_memory(req: MemoryRequest):
        res = jarvis_client.remember(req.key, req.value, req.category or "notes")
        return res.to_dict()

    @app.delete("/api/v1/memory/{key}", dependencies=[Depends(verify_api_key)])
    def delete_memory(key: str, category: str = "notes"):
        deleted = jarvis_client.delete_memory(category, key)
        return {"success": deleted, "key": key}

    return app


class JarvisServer:
    """
    JARVIS REST API Server instance runner.
    """
    def __init__(self, config: Optional[JarvisConfig] = None):
        self.config = config or JarvisConfig()
        self.client = JarvisAPI(self.config)

    def run(self):
        app = create_fastapi_app(self.client)
        if app is not None:
            try:
                import uvicorn
                print(f"[JARVIS REST] 🚀 Server starting on http://{self.config.host}:{self.config.port} (Docs: http://{self.config.host}:{self.config.port}/docs)")
                uvicorn.run(app, host=self.config.host, port=self.config.port, log_level="info")
                return
            except Exception as e:
                print(f"[JARVIS REST] Uvicorn failed: {e}")

        # Fallback to standard library http.server if uvicorn/fastapi not ready
        self._run_fallback_server()

    def _run_fallback_server(self):
        from http.server import HTTPServer, BaseHTTPRequestHandler

        client = self.client
        cfg = self.config

        class RequestHandler(BaseHTTPRequestHandler):
            def _send_json(self, data, status_code=200):
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode("utf-8"))

            def do_GET(self):
                if self.path == "/api/v1/health":
                    st = client.get_status()
                    self._send_json({"status": st.status, "version": __version__})
                elif self.path == "/api/v1/tools":
                    self._send_json({"tools": client.list_tools()})
                elif self.path == "/api/v1/status":
                    self._send_json(client.get_status().to_dict())
                else:
                    self._send_json({"error": "Not Found"}, 404)

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
                if self.path == "/api/v1/execute":
                    res = client.execute(body.get("command", ""))
                    self._send_json(res.to_dict())
                elif self.path == "/api/v1/tool":
                    res = client.call_tool(body.get("tool", ""), body.get("arguments", {}))
                    self._send_json(res.to_dict())
                else:
                    self._send_json({"error": "Not Found"}, 404)

        server = HTTPServer((cfg.host, cfg.port), RequestHandler)
        print(f"[JARVIS REST Fallback] 🚀 Server active at http://{cfg.host}:{cfg.port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.server_close()


def start_api_server(config: Optional[JarvisConfig] = None):
    srv = JarvisServer(config)
    srv.run()


def main():
    start_api_server()


if __name__ == "__main__":
    main()
