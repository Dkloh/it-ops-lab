"""Offline POS investigation using temporary SQLite and controlled network mocks."""

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.main import create_app

ROOT = Path(__file__).resolve().parents[1]


def demonstrate():
    with (
        TemporaryDirectory() as directory,
        patch.dict(
            os.environ, {"IT_OPS_DATABASE_URL": f"sqlite:///{Path(directory).as_posix()}/demo.db"}
        ),
        patch("app.network_checks.resolve", return_value=["93.184.216.34"]),
        patch("app.network_checks.connect_tcp", side_effect=TimeoutError),
        patch(
            "app.network_checks.http_probe",
            return_value=(503, None, {"body_read": False, "redirect_not_followed": False}),
        ),
    ):
        command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
        with TestClient(create_app()) as client:
            service = client.post(
                "/api/v1/services", json={"name": "retail-pos", "environment": "simulated-demo"}
            ).json()
            batch_response = client.post(
                f"/api/v1/services/{service['id']}/log-batches?filename=retail-pos.jsonl",
                content=(ROOT / "samples/retail-pos.jsonl").read_bytes(),
                headers={"Content-Type": "application/x-ndjson"},
            )
            assert batch_response.status_code == 201
            batch = batch_response.json()
            errors = client.get(f"/api/v1/log-events?batch_id={batch['id']}&severity=ERROR").json()
            findings = client.post(f"/api/v1/log-batches/{batch['id']}/diagnostic-runs").json()
            assert findings["finding_count"] == 2
            observations = []
            for kind in ("DNS", "TCP", "HTTP"):
                payload = {"name": f"Simulated {kind}", "host": "example.com", "check_type": kind}
                if kind == "TCP":
                    payload["port"] = 443
                response = client.post(
                    f"/api/v1/services/{service['id']}/check-targets", json=payload
                )
                assert response.status_code == 201
                target = response.json()
                result = client.post(f"/api/v1/check-targets/{target['id']}/runs")
                assert result.status_code == 201
                result = result.json()
                assert client.get(f"/api/v1/check-results/{result['id']}").json() == result
                observations.append(result)
            assert [row["error_code"] for row in observations] == [None, "TIMEOUT", "HTTP_STATUS"]
            return {
                "mode": "SIMULATED: no external requests; temporary database only",
                "historical_error_times": [row["occurred_at"] for row in errors["items"]],
                "diagnostic_rules": [finding["rule_code"] for finding in findings["findings"]],
                "observations": observations,
                "hypothesis": "Investigate upstream/database connectivity and pool configuration; "
                "current simulated checks do not establish the cause of earlier errors.",
            }


if __name__ == "__main__":
    print(json.dumps(demonstrate(), indent=2))
