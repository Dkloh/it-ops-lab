import os

import pytest
from sqlalchemy import create_engine, text

from scripts.demo_network_diagnostics import demonstrate


def test_retained_demo_is_offline_persistent_and_repeatable(tmp_path, database):
    for name in ("first.db", "second.sqlite"):
        destination = tmp_path / name
        report = demonstrate(destination)
        assert report["mode"].startswith("SIMULATED")
        assert report["diagnostic_rules"] == ["DATABASE_CONNECTION_ERRORS", "REPEATED_TIMEOUTS"]
        assert [row["error_code"] for row in report["observations"]] == [
            None,
            "TIMEOUT",
            "HTTP_STATUS",
        ]
        engine = create_engine(f"sqlite:///{destination.as_posix()}")
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM log_events")) == 8
            assert connection.scalar(text("SELECT count(*) FROM findings")) == 2
            assert connection.scalar(text("SELECT count(*) FROM check_results")) == 3
            assert (
                connection.scalar(text("SELECT count(*) FROM check_targets WHERE enabled = 0")) == 3
            )
            assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
        engine.dispose()
        assert os.environ["IT_OPS_DATABASE_URL"] == database


def test_demo_refuses_existing_file(tmp_path):
    original = tmp_path / "keep.db"
    original.write_bytes(b"preserve existing data")
    with pytest.raises(FileExistsError):
        demonstrate(original)
    assert original.read_bytes() == b"preserve existing data"


def test_demo_refuses_symlink(tmp_path):
    original = tmp_path / "keep.db"
    original.write_bytes(b"preserve existing data")
    link = tmp_path / "link.db"
    try:
        link.symlink_to(original)
    except OSError:
        if os.name == "nt":
            pytest.skip(
                "Windows requires symlink permission; regular-file refusal is tested separately"
            )
        raise
    with pytest.raises(FileExistsError):
        demonstrate(link)
    assert original.read_bytes() == b"preserve existing data"


def test_demo_rejects_non_database_destination(tmp_path):
    with pytest.raises(ValueError):
        demonstrate(tmp_path / "notes.txt")
    assert not (tmp_path / "notes.txt").exists()
    with pytest.raises(ValueError):
        demonstrate(tmp_path / "ambiguous?query" / "demo.db")
