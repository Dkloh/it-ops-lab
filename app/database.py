"""SQLite engine and request-scoped sessions."""

from fastapi import Request
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    pass


def make_engine(url: str):
    engine = create_engine(url, hide_parameters=True, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    return engine


def get_session(request: Request):
    with Session(request.app.state.engine) as session:
        yield session
