import json
import logging

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.logging import JsonFormatter
from app.main import create_app


@pytest.fixture
def client():
    with TestClient(create_app(Settings(environment="test"))) as client:
        yield client


@pytest.mark.parametrize(
    ("path", "status"), [("/health/live", "alive"), ("/health/ready", "ready")]
)
def test_health(client, path, status):
    response = client.get(path)
    assert response.status_code == 200
    assert response.json() == {"status": status}
    assert response.headers["content-type"] == "application/json"


def test_configuration_from_environment(monkeypatch):
    monkeypatch.setenv("IT_OPS_APP_NAME", "Support Lab")
    monkeypatch.setenv("IT_OPS_ENVIRONMENT", "test")
    monkeypatch.setenv("IT_OPS_LOG_LEVEL", "DEBUG")
    app = create_app()
    assert app.title == "Support Lab"
    assert app.state.settings.environment == "test"
    assert app.state.settings.log_level == "DEBUG"


@pytest.mark.parametrize(
    ("name", "value"),
    [("ENVIRONMENT", "staging"), ("LOG_LEVEL", "TRACE"), ("APP_NAME", "")],
)
def test_invalid_configuration_prevents_app_creation(monkeypatch, name, value):
    monkeypatch.setenv(f"IT_OPS_{name}", value)
    with pytest.raises(ValidationError):
        create_app()


def test_request_logging(capsys):
    with TestClient(create_app(Settings(environment="test"))) as client:
        client.get("/health/live?token=do-not-log")
    event = json.loads(capsys.readouterr().out.strip())
    assert event["message"] == "request_completed"
    assert event["method"] == "GET"
    assert event["path"] == "/health/live"
    assert event["status_code"] == 200
    assert event["duration_ms"] >= 0
    assert "do-not-log" not in json.dumps(event)


def test_json_formatter_preserves_exception():
    try:
        raise RuntimeError("example failure")
    except RuntimeError:
        import sys

        record = logging.LogRecord("it_ops_lab", logging.ERROR, "", 0, "failed", (), sys.exc_info())
    event = json.loads(JsonFormatter().format(record))
    assert event["level"] == "ERROR"
    assert "RuntimeError: example failure" in event["exception"]
