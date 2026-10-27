from datetime import datetime

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.database import make_engine
from app.main import create_app


@pytest.fixture
def client():
    with TestClient(create_app()) as client:
        yield client


def create(client, **changes):
    return client.post(
        "/api/v1/services", json={"name": "billing", "environment": "dev", **changes}
    )


def test_crud_and_persistence(client):
    response = create(client, description="Payments")
    assert response.status_code == 201
    service = response.json()
    assert service["name"] == "billing"
    assert service["environment"] == "dev"
    assert service["description"] == "Payments"
    assert datetime.fromisoformat(service["created_at"]).utcoffset().total_seconds() == 0
    path = f"/api/v1/services/{service['id']}"
    assert client.get(path).json() == service
    assert client.get("/api/v1/services").json() == [service]
    assert client.get("/api/v1/services?offset=1&limit=1").json() == []
    response = client.patch(path, json={"description": None, "name": "new-name"})
    assert response.status_code == 200
    assert response.json()["description"] is None
    assert response.json()["environment"] == "dev"
    assert response.json()["created_at"] == service["created_at"]
    with TestClient(create_app()) as restarted:
        assert restarted.get(path).json()["name"] == "new-name"


def test_unique_conflicts_and_rollback(client):
    first = create(client).json()
    assert create(client).status_code == 409
    second = create(client, environment="prod").json()
    path = f"/api/v1/services/{second['id']}"
    assert client.patch(path, json={"environment": "dev"}).status_code == 409
    assert client.get(path).json()["environment"] == "prod"
    assert client.get(f"/api/v1/services/{first['id']}").status_code == 200


@pytest.mark.parametrize("method", ["get", "patch"])
def test_missing_service(client, method):
    kwargs = {"json": {"name": "missing"}} if method == "patch" else {}
    response = getattr(client, method)("/api/v1/services/999", **kwargs)
    assert response.status_code == 404
    assert response.json() == {"detail": "Service not found"}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": ""},
        {"name": "   "},
        {"name": "x" * 101},
        {"environment": ""},
        {"environment": "x" * 51},
        {"description": "x" * 2001},
        {"unexpected": True},
        {"name": 123},
    ],
)
def test_create_validation(client, payload):
    body = {"name": "ok", "environment": "dev", **payload}
    if payload == {}:
        body = {}
    assert client.post("/api/v1/services", json=body).status_code == 422


@pytest.mark.parametrize("payload", [{}, {"name": None}, {"environment": None}, {"id": 3}])
def test_patch_validation(client, payload):
    service_id = create(client).json()["id"]
    assert client.patch(f"/api/v1/services/{service_id}", json=payload).status_code == 422


def test_normalization_and_pagination_validation(client):
    assert create(client, name=" billing ").json()["name"] == "billing"
    assert create(client).status_code == 409
    for query in ("limit=0", "limit=101", "offset=-1"):
        assert client.get(f"/api/v1/services?{query}").status_code == 422


def test_database_constraints_and_foreign_keys(database):
    engine = make_engine(database)
    try:
        with engine.begin() as connection:
            assert connection.scalar(text("PRAGMA foreign_keys")) == 1
            connection.execute(
                text(
                    "INSERT INTO services (name, environment, created_at) "
                    "VALUES ('billing', 'dev', CURRENT_TIMESTAMP)"
                )
            )
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO services (name, environment, created_at) "
                    "VALUES ('billing', 'dev', CURRENT_TIMESTAMP)"
                )
            )
    finally:
        engine.dispose()


def test_readiness_without_schema_and_migration_cycle(client):
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
    assert client.get("/health/live").status_code == 200
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    assert client.get("/health/ready").status_code == 200
    command.check(config)


def test_unavailable_database(tmp_path, monkeypatch):
    monkeypatch.setenv("IT_OPS_DATABASE_URL", f"sqlite:///{tmp_path}/missing/db.sqlite")
    with TestClient(create_app()) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503


@pytest.mark.parametrize("url", ["postgresql://localhost/db", "sqlite:///", "invalid"])
def test_invalid_database_configuration(monkeypatch, url):
    from pydantic import ValidationError

    monkeypatch.setenv("IT_OPS_DATABASE_URL", url)
    with pytest.raises(ValidationError):
        create_app()
