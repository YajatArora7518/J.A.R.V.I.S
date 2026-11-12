"""API acceptance with a fake assistant; no real laptop commands."""
from types import SimpleNamespace
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
import pytest
from jarvis_api.server import create_fastapi_app


@pytest.fixture
def api():
    assistant = MagicMock()
    assistant.config = SimpleNamespace(api_server_key="fixture-key")
    status = SimpleNamespace(status="fixture", all_systems_operational=True, to_dict=lambda: {"status": "fixture"})
    assistant.get_status.return_value = status
    assistant.execute.return_value.to_dict.return_value = {"success": True, "message": "fixture"}
    assistant.call_tool.return_value.to_dict.return_value = {"success": True}
    with TestClient(create_fastapi_app(assistant)) as client:
        yield client, assistant


def test_api_health_is_available_and_commands_need_the_configured_key(api):
    client, assistant = api
    assert client.get("/api/v1/health").status_code == 200
    for headers in ({}, {"X-JARVIS-API-KEY": "wrong"}):
        assert client.post("/api/v1/execute", json={"command": "fixture"}, headers=headers).status_code == 401
    assistant.execute.assert_not_called()


def test_api_validated_command_dispatches_once_and_malformed_body_is_rejected(api):
    client, assistant = api
    headers = {"X-JARVIS-API-KEY": "fixture-key"}
    assert client.post("/api/v1/execute", json={}, headers=headers).status_code == 422
    assert client.post("/api/v1/execute", json={"command": "calculate 3 * 7"}, headers=headers).json()["success"]
    assistant.execute.assert_called_once_with("calculate 3 * 7")


def test_api_tool_dispatch_preserves_exact_arguments(api):
    client, assistant = api
    arguments = {"contact": "Fixture", "message": "Exact नमस्ते"}
    result = client.post("/api/v1/tool", json={"tool": "whatsapp_send_message", "arguments": arguments}, headers={"X-JARVIS-API-KEY": "fixture-key"})
    assert result.status_code == 200
    assistant.call_tool.assert_called_once_with("whatsapp_send_message", arguments)
