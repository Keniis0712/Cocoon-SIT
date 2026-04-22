from __future__ import annotations

import weakref

from app.core.db import create_db_engine, create_session_factory
from app.models import Base


class ManagedSQLiteSessionFactory:
    def __init__(self) -> None:
        self._engine = create_db_engine("sqlite:///:memory:")
        Base.metadata.create_all(self._engine)
        self._session_factory = create_session_factory(self._engine)
        self._finalizer = weakref.finalize(
            self,
            ManagedSQLiteSessionFactory._dispose_engine,
            self._engine,
        )

    @staticmethod
    def _dispose_engine(engine) -> None:
        engine.dispose()

    def __call__(self):
        return self._session_factory()

    def dispose(self) -> None:
        if self._finalizer.alive:
            self._finalizer()


def make_sqlite_session_factory() -> ManagedSQLiteSessionFactory:
    return ManagedSQLiteSessionFactory()
