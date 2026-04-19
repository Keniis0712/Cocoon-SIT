from sqlalchemy import func, select

from app.core.container import AppContainer
from app.models import (
    Character,
    Cocoon,
    PromptTemplate,
    Role,
    SessionState,
    TagRegistry,
    User,
)


def test_bootstrap_service_seeds_defaults_into_empty_database(test_settings):
    settings = test_settings.model_copy(update={"auto_seed_defaults": False})
    container = AppContainer(settings)
    container.bootstrap_schema_and_seed()

    try:
        with container.session_factory() as session:
            container.bootstrap_service.seed_default_data(session)
            session.commit()

        with container.session_factory() as session:
            assert session.scalar(select(func.count()).select_from(Role)) == 3
            assert session.scalar(select(func.count()).select_from(User)) == 1
            assert session.scalar(select(func.count()).select_from(Character)) == 0
            assert session.scalar(select(func.count()).select_from(Cocoon)) == 0
            assert session.scalar(select(func.count()).select_from(SessionState)) == 0
            assert session.scalar(select(func.count()).select_from(TagRegistry)) == 1
            assert session.scalar(select(func.count()).select_from(PromptTemplate)) >= 1
    finally:
        container.shutdown()


def test_bootstrap_service_is_idempotent(test_settings):
    settings = test_settings.model_copy(update={"auto_seed_defaults": False})
    container = AppContainer(settings)
    container.bootstrap_schema_and_seed()

    try:
        with container.session_factory() as session:
            container.bootstrap_service.seed_default_data(session)
            container.bootstrap_service.seed_default_data(session)
            session.commit()

        with container.session_factory() as session:
            assert session.scalar(select(func.count()).select_from(Role)) == 3
            assert session.scalar(select(func.count()).select_from(User)) == 1
            assert session.scalar(select(func.count()).select_from(Character)) == 0
            assert session.scalar(select(func.count()).select_from(Cocoon)) == 0
            assert session.scalar(select(func.count()).select_from(SessionState)) == 0
            assert session.scalar(select(func.count()).select_from(TagRegistry)) == 1
    finally:
        container.shutdown()
