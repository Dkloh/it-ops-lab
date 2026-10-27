import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import make_engine
from app.log_parser import MAX_FILE_BYTES, MAX_LINE_BYTES, MAX_RECORDS, InvalidUpload, parse_logs
from app.main import create_app
from app.models import IngestionError, LogBatch, LogEvent

RECORD = {"timestamp": "2026-10-27T12:00:00-04:00", "severity": "INFO", "message": "Started"}


def line(**changes):
    return json.dumps({**RECORD, **changes}).encode()


@pytest.fixture
def client():
    with TestClient(create_app()) as client:
        client.post("/api/v1/services", json={"name": "demo", "environment": "test"})
        yield client


def upload(client, data, service_id=1, filename="example.jsonl"):
    return client.post(
        f"/api/v1/services/{service_id}/log-batches",
        params={"filename": filename},
        content=data,
        headers={"Content-Type": "application/x-ndjson"},
    )


def test_valid_persisted_upload(client, database):
    response = upload(client, line(source="api", metadata={"attempt": 1}) + b"\n")
    assert response.status_code == 201
    batch = response.json()
    assert (batch["accepted_count"], batch["rejected_count"], batch["status"]) == (
        1,
        0,
        "completed",
    )
    assert datetime.fromisoformat(batch["created_at"]).tzinfo is not None
    with TestClient(create_app()) as restarted:
        assert restarted.get(f"/api/v1/log-batches/{batch['id']}").json() == batch
        assert restarted.get(f"/api/v1/log-batches/{batch['id']}/errors").json() == []
    engine = make_engine(database)
    with Session(engine) as session:
        event = session.scalar(select(LogEvent))
        assert event.batch_id == batch["id"]
        assert event.occurred_at == datetime(2026, 10, 27, 16)
        assert event.severity == "INFO"
        assert event.message == "Started"
        assert event.source == "api"
        assert event.metadata_json == {"attempt": 1}
    engine.dispose()


@pytest.mark.parametrize(
    "bad",
    [
        b"{secret-password",
        b"[]",
        b"null",
        b"{}",
        line(timestamp="invalid"),
        line(timestamp="2026-10-27T12:00:00"),
        line(timestamp=123),
        line(severity="INVALID"),
        line(severity="info"),
        line(message=None),
        line(message=""),
        line(metadata=[]),
        line(source=3),
        b"\xff",
        b'{"timestamp": NaN}',
        b" ",
        b"x" * (MAX_LINE_BYTES + 1),
    ],
)
def test_mixed_records_and_safe_reasons(client, bad):
    response = upload(client, line() + b"\n" + bad + b"\n" + line())
    assert response.status_code == 201
    batch = response.json()
    assert (batch["accepted_count"], batch["rejected_count"], batch["status"]) == (2, 1, "partial")
    errors = client.get(f"/api/v1/log-batches/{batch['id']}/errors").json()
    assert len(errors) == 1
    assert errors[0]["line_number"] == 2
    assert errors[0]["reason"]
    assert "secret-password" not in json.dumps(errors)


@pytest.mark.parametrize("field", ["timestamp", "severity", "message"])
def test_missing_required_fields(client, field):
    record = dict(RECORD)
    record.pop(field)
    response = upload(client, json.dumps(record).encode())
    assert response.status_code == 201
    assert response.json()["status"] == "rejected"
    assert response.json()["accepted_count"] == 0
    assert response.json()["rejected_count"] == 1


@pytest.mark.parametrize("data", [b"", b"\n", b" \r\n\t"])
def test_empty_file_creates_nothing(client, data, database):
    assert upload(client, data).status_code == 400
    engine = make_engine(database)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(LogBatch)) == 0
    engine.dispose()


def test_oversized_stream(client, database):
    chunks = (b"x" * 65536 for _ in range(17))
    assert upload(client, chunks).status_code == 413
    engine = make_engine(database)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(LogBatch)) == 0
    engine.dispose()


def test_missing_resources(client):
    assert upload(client, line(), service_id=999).status_code == 404
    assert client.get("/api/v1/log-batches/999").status_code == 404
    assert client.get("/api/v1/log-batches/999/errors").status_code == 404


@pytest.mark.parametrize("filename", ["logs.txt", "../logs.jsonl", "a\\logs.jsonl"])
def test_invalid_filename(client, filename):
    assert upload(client, line(), filename=filename).status_code == 400


def test_error_pagination(client):
    batch = upload(client, b"invalid\ninvalid\ninvalid").json()
    errors = client.get(f"/api/v1/log-batches/{batch['id']}/errors?offset=1&limit=1").json()
    assert errors == [{"line_number": 2, "reason": "Malformed JSON"}]
    assert client.get(f"/api/v1/log-batches/{batch['id']}/errors?limit=101").status_code == 422


def test_limits_and_crlf_parser():
    records, errors = parse_logs(line() + b"\r\n" + line() + b"\r\n")
    assert len(records) == 2
    assert not errors
    with pytest.raises(InvalidUpload):
        parse_logs(b"x" * (MAX_FILE_BYTES + 1))
    with pytest.raises(InvalidUpload):
        parse_logs(b"x\n" * (MAX_RECORDS + 1))


def test_sample(client):
    batch = upload(client, Path("samples/application.jsonl").read_bytes()).json()
    assert batch["accepted_count"] == 3
    assert batch["rejected_count"] == 0


def test_ingestion_foreign_keys(database):
    engine = make_engine(database)
    with Session(engine) as session, pytest.raises(IntegrityError):
        session.add(
            LogBatch(
                service_id=999,
                filename="test.jsonl",
                status="completed",
                accepted_count=0,
                rejected_count=0,
            )
        )
        session.commit()
    engine.dispose()


def test_atomic_failure(client, database, monkeypatch):
    from sqlalchemy import event

    def fail_insert(*args):
        raise RuntimeError("simulated insert failure")

    event.listen(LogEvent, "before_insert", fail_insert)
    try:
        with pytest.raises(RuntimeError, match="simulated insert failure"):
            upload(client, line())
    finally:
        event.remove(LogEvent, "before_insert", fail_insert)
    engine = make_engine(database)
    with Session(engine) as session:
        for model in (LogBatch, LogEvent, IngestionError):
            assert session.scalar(select(func.count()).select_from(model)) == 0
    engine.dispose()


def test_utf8_bom_and_unicode_validation(client):
    assert (
        upload(client, b"\xef\xbb\xbf" + line(message="Synthetic café")).json()["accepted_count"]
        == 1
    )
    batch = upload(client, line(metadata={"value": "\ud800"})).json()
    assert batch["rejected_count"] == 1
    assert batch["accepted_count"] == 0


def test_nonfinite_metadata(client):
    body = line(metadata={"value": 1}).replace(b'"value": 1', b'"value": 1e999')
    assert upload(client, body).json()["rejected_count"] == 1


def test_unsupported_multipart(client):
    response = client.post("/api/v1/services/1/log-batches", files={"file": ("log.jsonl", line())})
    assert response.status_code == 415


def test_safe_specific_reason(client):
    batch = upload(client, line(timestamp="secret-example")).json()
    errors = client.get(f"/api/v1/log-batches/{batch['id']}/errors").json()
    assert errors == [{"line_number": 1, "reason": "Invalid field: timestamp"}]
