import pytest
from sqlalchemy.pool import StaticPool

from app.core.db import create_db_engine, create_session_factory, session_scope


def test_create_db_engine_uses_static_pool_for_in_memory_sqlite(monkeypatch):
    recorded = {}

    def fake_create_engine(database_url, **kwargs):
        recorded["database_url"] = database_url
        recorded["kwargs"] = kwargs
        return "engine"

    monkeypatch.setattr("app.core.db.create_engine", fake_create_engine)

    result = create_db_engine("sqlite:///:memory:")

    assert result == "engine"
    assert recorded["database_url"] == "sqlite:///:memory:"
    assert recorded["kwargs"]["future"] is True
    assert recorded["kwargs"]["connect_args"] == {"check_same_thread": False}
    assert recorded["kwargs"]["poolclass"] is StaticPool


def test_create_db_engine_uses_default_kwargs_for_non_sqlite(monkeypatch):
    recorded = {}

    def fake_create_engine(database_url, **kwargs):
        recorded["database_url"] = database_url
        recorded["kwargs"] = kwargs
        return "engine"

    monkeypatch.setattr("app.core.db.create_engine", fake_create_engine)

    create_db_engine("postgresql://example")

    assert recorded["database_url"] == "postgresql://example"
    assert recorded["kwargs"] == {"future": True, "connect_args": {}}


def test_create_session_factory_sets_expected_defaults():
    engine = create_db_engine("sqlite:///:memory:")
    try:
        factory = create_session_factory(engine)

        assert factory.kw["bind"] is engine
        assert factory.kw["autoflush"] is False
        assert factory.kw["autocommit"] is False
        assert factory.kw["expire_on_commit"] is False
    finally:
        engine.dispose()


class _FakeSession:
    def __init__(self):
        self.events = []

    def commit(self):
        self.events.append("commit")

    def rollback(self):
        self.events.append("rollback")

    def close(self):
        self.events.append("close")


def test_session_scope_commits_and_closes():
    session = _FakeSession()

    with session_scope(lambda: session) as yielded:
        assert yielded is session
        yielded.events.append("used")

    assert session.events == ["used", "commit", "close"]


def test_session_scope_rolls_back_and_reraises():
    session = _FakeSession()

    with pytest.raises(RuntimeError):
        with session_scope(lambda: session):
            raise RuntimeError("boom")

    assert session.events == ["rollback", "close"]
