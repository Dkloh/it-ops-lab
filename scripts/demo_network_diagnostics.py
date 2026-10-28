"""Offline POS investigation using temporary SQLite and controlled network mocks."""

import argparse
import json
import os
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import create_app
from app.models import CheckTarget

ROOT = Path(__file__).resolve().parents[1]


def demonstrate(database: Path | None = None):
    with ExitStack() as stack:
        if database is None:
            directory = stack.enter_context(TemporaryDirectory())
            destination = Path(directory) / "demo.db"
        else:
            destination = database.expanduser().absolute()
            if any(char in str(destination) for char in ("?", "#", "\x00")):
                raise ValueError("Demo database paths cannot contain URL metacharacters")
            if destination.suffix.lower() not in {".db", ".sqlite", ".sqlite3"}:
                raise ValueError("Choose a new .db, .sqlite or .sqlite3 file")
            # Exclusive creation refuses existing files AND symlinks; never delete user data.
            with destination.open("xb"):
                pass
        return populate(destination, retained=database is not None)


def populate(destination: Path, retained: bool):
    with (
        patch.dict(os.environ, {"IT_OPS_DATABASE_URL": f"sqlite:///{destination.as_posix()}"}),
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
            if retained:
                # Seeded observations are simulated. Prevent accidental live reruns when
                # this file is later opened by the ordinary, non-mocked local API.
                with Session(client.app.state.engine) as session:
                    for target in session.scalars(
                        select(CheckTarget).where(CheckTarget.service_id == service["id"])
                    ):
                        target.enabled = False
                    session.commit()
            return {
                "mode": "SIMULATED: no external requests",
                "database": str(destination) if retained else "temporary (removed after demo)",
                "retained_targets_disabled": retained,
                "service_id": service["id"],
                "batch_id": batch["id"],
                "run_id": findings["id"],
                "historical_error_times": [row["occurred_at"] for row in errors["items"]],
                "diagnostic_rules": [finding["rule_code"] for finding in findings["findings"]],
                "observations": observations,
                "hypothesis": "Investigate upstream/database connectivity and pool configuration; "
                "current simulated checks do not establish the cause of earlier errors.",
            }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Offline synthetic POS demonstration")
    parser.add_argument(
        "--database",
        type=Path,
        help="Retain a NEW disposable SQLite file; existing paths are refused",
    )
    args = parser.parse_args()
    try:
        print(json.dumps(demonstrate(args.database), indent=2))
    except (FileExistsError, ValueError, FileNotFoundError) as exc:
        parser.exit(2, f"Demo refused: {exc}\n")
