import json
from datetime import datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import event, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import diagnostic_rules
from app.database import make_engine
from app.main import create_app
from app.models import DiagnosticRun, Finding, FindingEvent, LogEvent


@pytest.fixture
def scenario():
    with TestClient(create_app()) as client:
        service = client.post(
            "/api/v1/services", json={"name": "pos", "environment": "demo"}
        ).json()

        def upload(data):
            response = client.post(
                f"/api/v1/services/{service['id']}/log-batches?filename=pos.jsonl",
                content=data,
                headers={"Content-Type": "application/x-ndjson"},
            )
            assert response.status_code == 201
            return response.json()["id"]

        batch_id = upload(Path("samples/retail-pos.jsonl").read_bytes())
        yield client, batch_id, upload


def run(client, batch_id):
    return client.post(f"/api/v1/log-batches/{batch_id}/diagnostic-runs")


def test_completed_run_evidence_and_restart(scenario):
    client, batch_id, _ = scenario
    search = client.get(
        "/api/v1/log-events", params={"batch_id": batch_id, "severity": "ERROR"}
    ).json()
    response = run(client, batch_id)
    assert response.status_code == 201
    result = response.json()
    assert result["status"] == "completed" and result["ruleset_version"] == "1.0.0"
    assert result["batch_id"] == batch_id and result["service_id"] == 1
    assert result["started_at"].endswith("Z") and result["finished_at"].endswith("Z")
    assert result["started_at"] <= result["finished_at"]
    assert result["finding_count"] == 2
    assert [f["rule_code"] for f in result["findings"]] == [
        "DATABASE_CONNECTION_ERRORS",
        "REPEATED_TIMEOUTS",
    ]
    expected_ids = [row["id"] for row in reversed(search["items"])]
    for finding in result["findings"]:
        assert finding["event_count"] == 3
        assert finding["event_ids"] == expected_ids
        assert finding["first_seen_at"] == "2026-10-27T13:05:00Z"
        assert finding["last_seen_at"] == "2026-10-27T13:07:00Z"
        detail = client.get(f"/api/v1/findings/{finding['id']}").json()
        assert detail["run_id"] == result["id"]
        assert detail["batch_id"] == batch_id and detail["service_id"] == 1
        assert [e["id"] for e in detail["evidence"]] == expected_ids
        assert detail["event_count"] == len(detail["evidence"])
        assert detail["evidence"][0] == {
            "id": expected_ids[0],
            "occurred_at": "2026-10-27T13:05:00Z",
            "severity": "ERROR",
            "source": "pos-api",
            "message": "Database connection timed out",
        }
    with TestClient(create_app()) as restarted:
        assert restarted.get(f"/api/v1/diagnostic-runs/{result['id']}").json() == result
        assert restarted.get(f"/api/v1/findings/{detail['id']}").json() == detail
    assert (
        client.get("/api/v1/log-events", params={"batch_id": batch_id, "severity": "ERROR"}).json()
        == search
    )


def test_separate_historical_runs_and_static_text(scenario, monkeypatch):
    client, batch_id, _ = scenario
    first = run(client, batch_id).json()
    second = run(client, batch_id).json()
    assert first["id"] != second["id"]
    assert len({f["rule_code"] for f in second["findings"]}) == second["finding_count"] == 2
    assert {f["id"] for f in first["findings"]}.isdisjoint(f["id"] for f in second["findings"])
    monkeypatch.setattr(diagnostic_rules, "RULESET_VERSION", "future")
    monkeypatch.setattr(diagnostic_rules, "RULES", ())
    assert client.get(f"/api/v1/diagnostic-runs/{first['id']}").json() == first


def test_empty_patterns_and_batch_isolation(scenario):
    client, _, upload = scenario

    def record(message, severity="ERROR"):
        return json.dumps(
            {"timestamp": "2026-10-27T13:05:00Z", "severity": severity, "message": message}
        ).encode()

    batches = [upload(record("connection timed out")) for _ in range(3)]
    batches.append(upload(record("normal startup", "INFO")))
    batches.append(upload(b"malformed"))  # Rejected but valid batch: no accepted events.
    for batch_id in batches:
        response = run(client, batch_id)
        assert response.status_code == 201
        assert response.json()["finding_count"] == 0
        assert response.json()["findings"] == []


def test_authentication_sample(scenario):
    client, _, upload = scenario
    batch_id = upload(Path("samples/auth-failures.jsonl").read_bytes())
    result = run(client, batch_id).json()
    assert result["finding_count"] == 1
    finding = result["findings"][0]
    assert finding["rule_code"] == "REPEATED_AUTH_FAILURES"
    assert finding["severity"] == "MEDIUM" and finding["event_count"] == 5


@pytest.mark.parametrize(
    "path,detail",
    [
        ("/api/v1/diagnostic-runs/999", "Diagnostic run not found"),
        ("/api/v1/findings/999", "Finding not found"),
    ],
)
def test_missing_resources(scenario, path, detail):
    response = scenario[0].get(path)
    assert response.status_code == 404 and response.json() == {"detail": detail}
    assert run(scenario[0], 999).status_code == 404


@pytest.mark.parametrize("identifier", ["0", "-1", "not-an-id", str(2**63)])
def test_invalid_ids(scenario, identifier):
    client = scenario[0]
    assert client.get(f"/api/v1/diagnostic-runs/{identifier}").status_code == 422
    assert client.get(f"/api/v1/findings/{identifier}").status_code == 422
    assert client.post(f"/api/v1/log-batches/{identifier}/diagnostic-runs").status_code == 422


@pytest.mark.parametrize("failure_stage", ["engine", "finding", "association"])
def test_atomic_rollback(scenario, database, monkeypatch, failure_stage):
    client, batch_id, _ = scenario
    historical = run(client, batch_id).json()
    original_events = client.get("/api/v1/log-events").json()

    def fail(*args):
        raise RuntimeError("simulated failure")

    model = Finding if failure_stage == "finding" else FindingEvent
    if failure_stage == "engine":
        monkeypatch.setattr(diagnostic_rules, "analyze", fail)
    else:
        event.listen(model, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError, match="simulated failure"):
            run(client, batch_id)
        with TestClient(create_app(), raise_server_exceptions=False) as safe_client:
            response = run(safe_client, batch_id)
            assert response.status_code == 500
            assert response.text == "Internal Server Error"
    finally:
        if failure_stage != "engine":
            event.remove(model, "before_insert", fail)
    assert client.get(f"/api/v1/diagnostic-runs/{historical['id']}").json() == historical
    assert client.get("/api/v1/log-events").json() == original_events
    engine = make_engine(database)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(DiagnosticRun)) == 1
        assert session.scalar(select(func.count()).select_from(Finding)) == 2
        assert session.scalar(select(func.count()).select_from(FindingEvent)) == 6
    engine.dispose()


def test_constraints(scenario, database):
    client, batch_id, _ = scenario
    result = run(client, batch_id).json()
    engine = make_engine(database)
    with engine.connect() as connection:
        assert connection.scalar(text("PRAGMA foreign_keys")) == 1
    finding_id = result["findings"][0]["id"]
    event_id = result["findings"][0]["event_ids"][0]
    attempts = [
        FindingEvent(finding_id=finding_id, event_id=event_id),
        FindingEvent(finding_id=999, event_id=event_id),
        FindingEvent(finding_id=finding_id, event_id=999),
        DiagnosticRun(
            batch_id=999,
            ruleset_version="1.0.0",
            status="completed",
            started_at=datetime(2026, 1, 1),
        ),
        DiagnosticRun(
            batch_id=batch_id,
            ruleset_version="1.0.0",
            status="invalid",
            started_at=datetime(2026, 1, 1),
        ),
    ]
    for attempt in attempts:
        with Session(engine) as session, pytest.raises(IntegrityError):
            session.add(attempt)
            session.commit()
    with Session(engine) as session:
        original = session.get(Finding, finding_id)
        copied = {
            c.name: getattr(original, c.name) for c in Finding.__table__.columns if c.name != "id"
        }
    for changes in ({}, {"run_id": 999}):
        with Session(engine) as session, pytest.raises(IntegrityError):
            session.add(Finding(**{**copied, **changes}))
            session.commit()
    engine.dispose()


def test_migrations_preserve_existing_data(scenario, database):
    client, batch_id, _ = scenario
    before = client.get("/api/v1/log-events").json()
    config = Config("alembic.ini")
    command.downgrade(config, "67136625fb8f")
    engine = make_engine(database)
    assert "diagnostic_runs" not in inspect(engine).get_table_names()
    assert client.get("/api/v1/log-events").json() == before
    assert client.get("/health/ready").status_code == 503
    command.upgrade(config, "head")
    command.check(config)
    assert client.get("/api/v1/log-events").json() == before
    result = run(client, batch_id).json()
    assert result["finding_count"] == 2
    with Session(engine) as session:
        assert len(session.scalars(select(LogEvent)).all()) == 8
    engine.dispose()
