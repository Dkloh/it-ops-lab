# IT Ops Lab

An IT operations and log diagnostics portfolio project. Milestone 1 provides a
FastAPI application foundation; log ingestion, databases, diagnostics, and a web
interface are not implemented yet.

## Install

Requires Python 3.12 or newer. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1` instead.
Dependencies use compatible version ranges; there is no lockfile yet.

## Run

```bash
python -m uvicorn app.main:create_app --factory --reload
```

The development server listens on `127.0.0.1:8000`. Interactive API documentation
is available at `/docs`.

```bash
curl --fail http://127.0.0.1:8000/health/live
# {"status":"alive"}
curl --fail http://127.0.0.1:8000/health/ready
# {"status":"ready"}
```

Liveness confirms the process can serve requests. Readiness confirms the app was
created with valid configuration and can serve requests. There are currently no
external dependencies to check; database readiness belongs to a later milestone.

## Configuration and logging

Configuration is validated at application creation. Invalid values prevent startup.
Environment variables are optional:

| Variable | Default | Accepted values |
| --- | --- | --- |
| `IT_OPS_APP_NAME` | `IT Ops Lab` | Nonempty string |
| `IT_OPS_ENVIRONMENT` | `development` | `development`, `test`, `production` |
| `IT_OPS_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |

For example, `IT_OPS_LOG_LEVEL=DEBUG python -m uvicorn app.main:create_app --factory`.
The environment label does not itself enable production security settings.
No `.env` file is loaded automatically and no credentials are required.

Application request events are JSON lines on stdout with UTC timestamps, level,
logger, message, method, path, status, and duration. Query strings, headers, and
request bodies are not logged. Unhandled request exceptions are logged and re-raised.
Uvicorn keeps its own server/access log format. Paths and exception messages may
contain sensitive data; review logging before handling real operational data.

## Test and lint

```bash
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

Tests cover health responses, environment configuration, invalid configuration,
request logging, and exception formatting. They require no external services.

## Structure and request flow

- `app/main.py`: application factory, request logging middleware, health routes.
- `app/config.py`: typed environment configuration and validation.
- `app/logging.py`: application logger and JSON formatter.
- `tests/test_foundation.py`: automated foundation checks.
- `pyproject.toml`: package metadata, dependencies, pytest and Ruff configuration.

Uvicorn creates the application through `create_app()`. Each HTTP request passes
through the logging middleware to FastAPI's matching route. FastAPI validates and
serializes the response model as JSON. The middleware logs completion and returns
the response through Uvicorn to the client.

This is a local development foundation. Authentication, persistence, diagnostic
features, deployment configuration, and CI are future work.
