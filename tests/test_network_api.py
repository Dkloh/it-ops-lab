from unittest.mock import Mock

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import event, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import network_checks
from app.config import Settings
from app.database import make_engine
from app.main import create_app
from app.models import CheckResult, CheckTarget

BASE = "/api/v1"


@pytest.fixture
def scenario(monkeypatch):
    resolve = Mock(return_value=["93.184.216.34"])
    connect = Mock()
    http = Mock(return_value=(200, None, {"body_read": False, "redirect_not_followed": False}))
    monkeypatch.setattr(network_checks, "resolve", resolve)
    monkeypatch.setattr(network_checks, "connect_tcp", connect)
    monkeypatch.setattr(network_checks, "http_probe", http)
    with TestClient(create_app()) as client:
        service = client.post(
            f"{BASE}/services", json={"name": "retail-pos", "environment": "demo"}
        ).json()
        yield client, service["id"], resolve, connect, http


def target(client, service_id, kind="DNS", **changes):
    payload = {"name": f"Demo {kind}", "check_type": kind, "host": "example.com"}
    if kind == "TCP":
        payload["port"] = 443
    return client.post(f"{BASE}/services/{service_id}/check-targets", json={**payload, **changes})


def run(client, identifier):
    return client.post(f"{BASE}/check-targets/{identifier}/runs")


@pytest.mark.parametrize("kind", ["DNS", "TCP", "HTTP"])
def test_registered_target_and_observation(scenario, kind):
    client, service_id, resolve, _, _ = scenario
    response = target(client, service_id, kind)
    assert response.status_code == 201
    config = response.json()
    assert config["created_at"].endswith("Z") and config["enabled"] is True
    assert client.get(f"{BASE}/services/{service_id}/check-targets").json() == [config]
    resolve.assert_not_called()  # Registration and reads never initiate network checks.
    response = run(client, config["id"])
    assert response.status_code == 201
    result = response.json()
    assert result["outcome"] == "success" and result["target_id"] == config["id"]
    assert result["duration_ms"] >= 0 and result["error_code"] is None
    assert result["checked_at"].endswith("Z")
    assert result["status_code"] == (200 if kind == "HTTP" else None)
    with TestClient(create_app()) as restarted:
        assert restarted.get(f"{BASE}/check-results/{result['id']}").json() == result
        assert restarted.get(f"{BASE}/check-targets/{config['id']}/results").json() == [result]


@pytest.mark.parametrize(
    "changes",
    [
        {"host": "10.0.0.1"},
        {"host": "127.0.0.1"},
        {"host": "169.254.169.254"},
        {"host": "::1"},
        {"host": "fc00::1"},
        {"host": "https://example.com"},
        {"host": "user:password@example.com"},
        {"host": "localhost"},
        {"host": "example.com:443"},
        {"host": "2130706433"},
        {"host": "127.1"},
        {"host": "example..com"},
        {"host": "-bad.example.com"},
        {"host": "example.com\r\n"},
        {"port": 0},
        {"port": 65536},
        {"port": True},
        {"port": "443"},
        {"scheme": "file"},
        {"scheme": "ftp"},
        {"path": "//evil.example.com"},
        {"path": "https://example.com"},
        {"path": "/health?secret=value"},
        {"path": "/%0d%0a"},
        {"path": "/a\\b"},
        {"path": "/x#fragment"},
        {"path": "/a b"},
        {"path": "/x\r\n"},
        {"enabled": "true"},
        {"enabled": 1},
        {"check_type": "PING"},
        {"name": " "},
        {"unknown": "value"},
    ],
)
def test_invalid_configuration(scenario, changes):
    client, service_id, resolver, _, _ = scenario
    response = target(client, service_id, "HTTP", **changes)
    assert response.status_code == 422
    resolver.assert_not_called()


@pytest.mark.parametrize(
    "kind,changes",
    [
        ("DNS", {"port": 53}),
        ("DNS", {"path": "/"}),
        ("DNS", {"scheme": "http"}),
        ("TCP", {"port": None}),
        ("TCP", {"path": "/"}),
        ("TCP", {"scheme": "https"}),
    ],
)
def test_type_specific_configuration(scenario, kind, changes):
    assert target(scenario[0], scenario[1], kind, **changes).status_code == 422


def test_disabled_and_missing_resources(scenario):
    client, service_id, resolve, _, _ = scenario
    config = target(client, service_id, enabled=False).json()
    assert run(client, config["id"]).status_code == 409
    assert client.get(f"{BASE}/check-targets/{config['id']}/results").json() == []
    resolve.assert_not_called()
    assert target(client, 999).status_code == 404
    assert client.get(f"{BASE}/services/999/check-targets").status_code == 404
    assert run(client, 999).status_code == 404
    assert client.get(f"{BASE}/check-targets/999/results").status_code == 404
    assert client.get(f"{BASE}/check-results/999").status_code == 404


def test_recorded_failure_and_rebinding(scenario):
    client, service_id, resolver, connect, _ = scenario
    config = target(client, service_id, "TCP").json()
    assert run(client, config["id"]).json()["outcome"] == "success"
    resolver.return_value = ["169.254.169.254"]  # Different answer on next invocation.
    result = run(client, config["id"]).json()
    assert result["outcome"] == "failure" and result["error_code"] == "UNSAFE_DESTINATION"
    assert connect.call_count == 1
    assert len(client.get(f"{BASE}/check-targets/{config['id']}/results").json()) == 2


def test_history_ties_pagination_and_scoping(scenario, database):
    client, service_id, _, _, _ = scenario
    config = target(client, service_id).json()
    other = target(client, service_id).json()
    rows = [run(client, config["id"]).json() for _ in range(3)]
    run(client, other["id"])
    engine = make_engine(database)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE check_results SET checked_at = '2026-10-27 13:00:00.000000'")
        )
    response = client.get(f"{BASE}/check-targets/{config['id']}/results?offset=1&limit=1")
    assert [item["id"] for item in response.json()] == [rows[1]["id"]]
    assert client.get(f"{BASE}/check-targets/{config['id']}/results?limit=101").status_code == 422
    assert client.get(f"{BASE}/services/{service_id}/check-targets?offset=1&limit=1").json() == [
        other
    ]
    engine.dispose()


def test_run_endpoint_rejects_destination_override(scenario):
    client, service_id, resolve, _, _ = scenario
    config = target(client, service_id).json()
    response = client.post(f"{BASE}/check-targets/{config['id']}/runs", json={"host": "127.0.0.1"})
    assert response.status_code == 422
    resolve.assert_not_called()


def test_stored_config_revalidated(scenario, database):
    client, service_id, resolve, _, _ = scenario
    config = target(client, service_id).json()
    engine = make_engine(database)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE check_targets SET host = '127.0.0.1' WHERE id = :id"), {"id": config["id"]}
        )
    assert run(client, config["id"]).status_code == 409
    resolve.assert_not_called()
    engine.dispose()


def test_result_failure_rolls_back(scenario, database):
    client, service_id, _, _, _ = scenario
    config = target(client, service_id).json()

    def fail(*args):
        raise RuntimeError("simulated persistence error")

    event.listen(CheckResult, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError, match="simulated persistence error"):
            run(client, config["id"])
    finally:
        event.remove(CheckResult, "before_insert", fail)
    assert client.get(f"{BASE}/check-targets/{config['id']}/results").json() == []
    assert run(client, config["id"]).status_code == 201


def test_foreign_keys(scenario, database):
    engine = make_engine(database)
    for row in [
        CheckTarget(
            service_id=999, name="test", check_type="DNS", host="example.com", enabled=True
        ),
        CheckResult(target_id=999, outcome="failure", duration_ms=1, details_json={}),
    ]:
        with Session(engine) as session, pytest.raises(IntegrityError):
            session.add(row)
            session.commit()
    engine.dispose()


def test_migration_cycle_keeps_prior_logs_and_findings(scenario, database):
    client, service_id, _, _, _ = scenario
    from pathlib import Path

    batch = client.post(
        f"{BASE}/services/{service_id}/log-batches?filename=pos.jsonl",
        content=Path("samples/retail-pos.jsonl").read_bytes(),
        headers={"Content-Type": "application/x-ndjson"},
    ).json()
    run_result = client.post(f"{BASE}/log-batches/{batch['id']}/diagnostic-runs").json()
    before = client.get(f"{BASE}/log-events").json()
    config = Config("alembic.ini")
    command.downgrade(config, "e57f984a4626")
    engine = make_engine(database)
    assert "check_targets" not in inspect(engine).get_table_names()
    assert client.get(f"{BASE}/log-events").json() == before
    assert client.get(f"{BASE}/diagnostic-runs/{run_result['id']}").json() == run_result
    assert client.get("/health/ready").status_code == 503
    command.upgrade(config, "head")
    command.check(config)
    assert client.get(f"{BASE}/log-events").json() == before
    assert client.get(f"{BASE}/diagnostic-runs/{run_result['id']}").json() == run_result
    assert client.get("/health/ready").status_code == 200
    engine.dispose()


@pytest.mark.parametrize("value", [0, 0.09, 11])
def test_timeout_configuration_bounds(value):
    with pytest.raises(ValidationError):
        Settings(network_timeout_seconds=value)
