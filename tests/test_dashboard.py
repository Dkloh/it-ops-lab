from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def test_empty_dashboard():
    with TestClient(create_app()) as client:
        assert client.get("/api/v1/dashboard").json() == {
            "service_count": 0,
            "event_count": 0,
            "error_count": 0,
            "warning_count": 0,
            "latest_findings": [],
            "recent_observations": [],
        }


def test_discovery_counts_scope_and_pagination(monkeypatch):
    from app import network_checks

    monkeypatch.setattr(
        network_checks,
        "check",
        lambda *_: network_checks.Observation(
            "failure", 3, "TIMEOUT", None, {"host": "example.com"}
        ),
    )
    with TestClient(create_app()) as client:
        service = client.post(
            "/api/v1/services", json={"name": "pos", "environment": "demo"}
        ).json()
        other = client.post(
            "/api/v1/services", json={"name": "empty", "environment": "demo"}
        ).json()
        batch = client.post(
            f"/api/v1/services/{service['id']}/log-batches?filename=pos.jsonl",
            content=Path("samples/retail-pos.jsonl").read_bytes(),
            headers={"Content-Type": "application/x-ndjson"},
        ).json()
        run = client.post(f"/api/v1/log-batches/{batch['id']}/diagnostic-runs").json()
        target = client.post(
            f"/api/v1/services/{service['id']}/check-targets",
            json={"name": "Demo DNS", "check_type": "DNS", "host": "example.com"},
        ).json()
        result = client.post(f"/api/v1/check-targets/{target['id']}/runs").json()
        overview = client.get("/api/v1/dashboard").json()
        assert (
            overview["service_count"],
            overview["event_count"],
            overview["error_count"],
            overview["warning_count"],
        ) == (2, 8, 3, 1)
        assert len(overview["latest_findings"]) == 2
        assert overview["latest_findings"][0]["service_id"] == service["id"]
        assert overview["recent_observations"][0]["id"] == result["id"]
        assert overview["recent_observations"][0]["target_name"] == "Demo DNS"
        page = client.get(f"/api/v1/services/{service['id']}/log-batches?limit=1").json()
        assert page["items"] == [batch] and page["total"] == 1
        assert client.get(f"/api/v1/services/{other['id']}/log-batches").json()["items"] == []
        page = client.get(f"/api/v1/log-batches/{batch['id']}/diagnostic-runs").json()
        assert page["total"] == 1 and page["items"][0]["finding_count"] == 2
        assert page["items"][0]["id"] == run["id"]
        assert (
            client.get(f"/api/v1/log-batches/{batch['id']}/diagnostic-runs?offset=1").json()[
                "items"
            ]
            == []
        )
        for endpoint in (
            "/api/v1/services/999/log-batches",
            "/api/v1/log-batches/999/diagnostic-runs",
        ):
            assert client.get(endpoint).status_code == 404
        assert (
            client.get(f"/api/v1/services/{service['id']}/log-batches?limit=101").status_code == 422
        )
        for _ in range(3):
            client.post(f"/api/v1/log-batches/{batch['id']}/diagnostic-runs")
            client.post(f"/api/v1/check-targets/{target['id']}/runs")
        overview = client.get("/api/v1/dashboard").json()
        assert len(overview["latest_findings"]) == 5
        assert len(overview["recent_observations"]) == 4
        runs = client.get(f"/api/v1/log-batches/{batch['id']}/diagnostic-runs?limit=2").json()
        assert runs["total"] == 4
        assert runs["items"][0]["id"] > runs["items"][1]["id"]
