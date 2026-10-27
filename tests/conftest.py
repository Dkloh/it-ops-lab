import pytest
from alembic import command
from alembic.config import Config


@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("IT_OPS_DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    return url
