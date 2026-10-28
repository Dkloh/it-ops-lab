import json
import re
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.database import make_engine
from app.log_search import search_events, summarize_events
from app.main import create_app
from app.models import LogEvent
from app.search_schemas import SearchFilters, TimeFilters

BASE = "/api/v1/log-events"


@pytest.fixture
def scenario():
    with TestClient(create_app()) as client:
        services = [
            client.post("/api/v1/services", json={"name": name, "environment": "demo"}).json()
            for name in ("retail-pos", "auth-gateway", "no-events")
        ]

        def upload(service, data):
            response = client.post(
                f"/api/v1/services/{service['id']}/log-batches?filename=pos.jsonl",
                content=data,
                headers={"Content-Type": "application/x-ndjson"},
            )
            assert response.status_code == 201
            assert response.json()["rejected_count"] == 0
            return response.json()["id"]

        first_batch = upload(services[0], Path("samples/retail-pos.jsonl").read_bytes())
        second_batch = upload(
            services[0],
            json.dumps(
                {
                    "timestamp": "2026-10-27T13:05:00Z",
                    "severity": "DEBUG",
                    "message": "Progress 100%_done",
                    "metadata": {"synthetic": True},
                }
            ).encode(),
        )
        third_batch = upload(
            services[1],
            b"\n".join(
                json.dumps(row).encode()
                for row in [
                    {
                        "timestamp": "2026-10-27T13:06:00Z",
                        "severity": "ERROR",
                        "message": "Synthetic authentication failed",
                    },
                    {
                        "timestamp": "2026-10-27T15:00:00Z",
                        "severity": "CRITICAL",
                        "message": "Synthetic authentication backend unavailable",
                    },
                ]
            ),
        )
        yield client, services, (first_batch, second_batch, third_batch)


def test_all_events_response(scenario):
    client, services, batches = scenario
    response = client.get(BASE)
    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 11
    assert page["offset"] == 0 and page["limit"] == 50
    assert len(page["items"]) == 11
    first = page["items"][0]
    assert first == {
        "id": first["id"],
        "service_id": services[1]["id"],
        "batch_id": batches[2],
        "occurred_at": "2026-10-27T15:00:00Z",
        "severity": "CRITICAL",
        "message": "Synthetic authentication backend unavailable",
        "source": None,
        "metadata": None,
    }
    sample = next(
        item for item in page["items"] if item["message"] == "Synthetic POS application started"
    )
    assert sample["metadata"] == {"terminal": "DEMO-01"}
    assert sample["source"] == "pos-api"
    assert sample["occurred_at"] == "2026-10-27T13:00:00Z"
    assert client.get(f"{BASE}/{sample['id']}").json() == sample


def test_service_and_batch_filters(scenario):
    client, services, batches = scenario
    page = client.get(BASE, params={"service_id": services[0]["id"]}).json()
    assert page["total"] == 9
    assert {item["service_id"] for item in page["items"]} == {services[0]["id"]}
    page = client.get(BASE, params={"batch_id": batches[1]}).json()
    assert page["total"] == 1
    assert page["items"][0]["message"] == "Progress 100%_done"
    assert (
        client.get(BASE, params={"batch_id": batches[0], "service_id": services[1]["id"]}).json()[
            "total"
        ]
        == 0
    )


@pytest.mark.parametrize(
    "severity,expected", [("DEBUG", 1), ("INFO", 4), ("WARNING", 1), ("ERROR", 4), ("CRITICAL", 1)]
)
def test_severity(scenario, severity, expected):
    page = scenario[0].get(BASE, params={"severity": severity}).json()
    assert page["total"] == expected
    assert all(item["severity"] == severity for item in page["items"])


def test_inclusive_range_and_utc(scenario):
    client = scenario[0]
    params = {"start_time": "2026-10-27T09:05:00-04:00", "end_time": "2026-10-27T14:05:00+01:00"}
    page = client.get(BASE, params=params).json()
    assert page["total"] == 3
    assert {item["occurred_at"] for item in page["items"]} == {"2026-10-27T13:05:00Z"}
    assert client.get(BASE, params={"start_time": "2026-10-27T15:00:00Z"}).json()["total"] == 1
    assert client.get(BASE, params={"end_time": "2026-10-27T13:00:00Z"}).json()["total"] == 1


@pytest.mark.parametrize(
    "message,expected",
    [("DATABASE CONNECTION TIMED OUT", 3), ("100%_", 1), ("%", 1), ("_", 1), ("' OR 1=1 --", 0)],
)
def test_literal_substring_search(scenario, message, expected):
    assert scenario[0].get(BASE, params={"message": message}).json()["total"] == expected


def test_combined_filters(scenario):
    client, services, batches = scenario
    page = client.get(
        BASE,
        params={
            "service_id": services[0]["id"],
            "batch_id": batches[0],
            "severity": "ERROR",
            "message": "TIMED OUT",
            "start_time": "2026-10-27T13:05:00Z",
            "end_time": "2026-10-27T13:06:00Z",
            "limit": 1,
            "offset": 1,
        },
    ).json()
    assert page["total"] == 2 and len(page["items"]) == 1
    assert page["items"][0]["metadata"]["attempt"] == 1


def test_deterministic_pagination(scenario):
    client = scenario[0]
    items = client.get(BASE).json()["items"]
    assert items == sorted(items, key=lambda item: (item["occurred_at"], item["id"]), reverse=True)
    pages = [
        client.get(BASE, params={"offset": offset, "limit": 2}).json() for offset in range(0, 12, 2)
    ]
    assert all(page["total"] == 11 for page in pages)
    assert [item for page in pages for item in page["items"]] == items
    assert client.get(BASE, params={"offset": 100}).json()["items"] == []


@pytest.mark.parametrize(
    "params", [{"service_id": 999}, {"batch_id": 999}, {"message": "no match"}]
)
def test_empty_results(scenario, params):
    response = scenario[0].get(BASE, params=params)
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "offset": 0, "limit": 50}


def test_missing_event_and_summary_routing(scenario):
    client = scenario[0]
    response = client.get(f"{BASE}/999999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Log event not found"}
    assert client.get(f"{BASE}/summary").status_code == 200
    assert client.get(f"{BASE}/not-an-id").status_code == 422


@pytest.mark.parametrize(
    "params",
    [
        {"severity": "error"},
        {"severity": "INVALID"},
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"service_id": 0},
        {"batch_id": -1},
        {"offset": 2**63},
        {"service_id": 2**63},
        {"message": ""},
        {"message": "x" * 8001},
    ],
)
def test_invalid_search_parameters(scenario, params):
    assert scenario[0].get(BASE, params=params).status_code == 422


@pytest.mark.parametrize(
    "params",
    [
        {"start_time": "bad"},
        {"end_time": "2026-10-27T12:00:00"},
        {"start_time": "123456"},
        {"start_time": "2026-10-27"},
        {"start_time": "2026-10-28T00:00:00Z", "end_time": "2026-10-27T00:00:00Z"},
        {"start_time": "0001-01-01T00:00:00+01:00"},
    ],
)
@pytest.mark.parametrize("path", [BASE, f"{BASE}/summary"])
def test_invalid_time_parameters(scenario, params, path):
    response = scenario[0].get(path, params=params)
    assert response.status_code == 422
    assert "detail" in response.json()


def test_summary(scenario):
    client, services, _ = scenario
    summary = client.get(f"{BASE}/summary").json()
    assert summary == {
        "total": 11,
        "by_severity": {"DEBUG": 1, "INFO": 4, "WARNING": 1, "ERROR": 4, "CRITICAL": 1},
        "by_service": [
            {
                "service_id": services[0]["id"],
                "name": "retail-pos",
                "environment": "demo",
                "count": 9,
            },
            {
                "service_id": services[1]["id"],
                "name": "auth-gateway",
                "environment": "demo",
                "count": 2,
            },
        ],
        "earliest": "2026-10-27T13:00:00Z",
        "latest": "2026-10-27T15:00:00Z",
    }


def test_filtered_summary_and_no_matches(scenario):
    client, services, batches = scenario
    summary = client.get(
        f"{BASE}/summary",
        params={
            "service_id": services[0]["id"],
            "batch_id": batches[0],
            "start_time": "2026-10-27T09:05:00-04:00",
            "end_time": "2026-10-27T13:07:00Z",
        },
    ).json()
    assert summary["total"] == 4
    assert summary["by_severity"] == {
        "DEBUG": 0,
        "INFO": 0,
        "WARNING": 1,
        "ERROR": 3,
        "CRITICAL": 0,
    }
    assert summary["earliest"] == "2026-10-27T13:05:00Z"
    assert summary["latest"] == "2026-10-27T13:07:00Z"
    assert summary["by_service"][0]["count"] == 4
    empty = client.get(f"{BASE}/summary", params={"service_id": services[2]["id"]}).json()
    assert empty["total"] == 0 and empty["by_service"] == []
    assert empty["earliest"] is None and empty["latest"] is None
    assert all(count == 0 for count in empty["by_severity"].values())


def test_independent_query_module(scenario, database):
    engine = make_engine(database)
    with Session(engine) as session:
        assert search_events(session, SearchFilters(severity="ERROR", limit=1)).total == 4
        assert summarize_events(session, TimeFilters()).total == 11
    engine.dispose()


def test_index_migration_preserves_events(scenario, database):
    client = scenario[0]
    before = client.get(BASE).json()
    config = Config("alembic.ini")
    command.downgrade(config, "998d068b4d03")
    engine = make_engine(database)
    assert "ix_log_events_batch_id" in {
        i["name"] for i in inspect(engine).get_indexes("log_events")
    }
    assert client.get(BASE).json() == before
    command.upgrade(config, "head")
    assert client.get(BASE).json() == before
    names = {i["name"] for i in inspect(engine).get_indexes("log_events")}
    assert names == {
        "ix_log_events_batch_occurred",
        "ix_log_events_severity_occurred",
        "ix_log_events_occurred",
    }
    command.check(config)
    with Session(engine) as session:
        assert len(session.scalars(select(LogEvent)).all()) == 11
    engine.dispose()


def test_documented_sql(scenario, database):
    blocks = re.findall(r"```sql\n(.*?)```", Path("docs/sql-investigations.md").read_text(), re.S)
    assert len(blocks) == 5
    engine = make_engine(database)
    with engine.connect() as connection:
        results = [connection.execute(text(sql)).mappings().all() for sql in blocks]
    assert len(results[0]) == 4
    assert {row["severity"]: row["event_count"] for row in results[1]} == {
        "DEBUG": 1,
        "INFO": 4,
        "WARNING": 1,
        "ERROR": 4,
        "CRITICAL": 1,
    }
    assert [(row["name"], row["error_count"]) for row in results[2]] == [
        ("retail-pos", 3),
        ("auth-gateway", 2),
    ]
    assert len(results[3]) == 3
    assert [(row["hour_utc"], row["error_count"]) for row in results[4]] == [
        ("2026-10-27T13:00:00Z", 4),
        ("2026-10-27T15:00:00Z", 1),
    ]
    engine.dispose()
