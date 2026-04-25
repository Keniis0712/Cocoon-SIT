from sqlalchemy import func, select
import pytest

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

pytestmark = pytest.mark.integration


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


def test_bootstrap_service_restores_configured_admin_role_and_status(test_settings):
    settings = test_settings.model_copy(update={"auto_seed_defaults": False})
    container = AppContainer(settings)
    container.bootstrap_schema_and_seed()

    try:
        with container.session_factory() as session:
            container.bootstrap_service.seed_default_data(session)
            admin_role = session.scalar(select(Role).where(Role.name == "admin"))
            user_role = session.scalar(select(Role).where(Role.name == "user"))
            admin = session.scalar(select(User).where(User.username == settings.default_admin_username))
            assert admin_role is not None
            assert user_role is not None
            assert admin is not None
            admin.role_id = user_role.id
            admin.is_active = False
            session.commit()

        with container.session_factory() as session:
            container.bootstrap_service.seed_default_data(session)
            session.commit()

        with container.session_factory() as session:
            admin_role = session.scalar(select(Role).where(Role.name == "admin"))
            admin = session.scalar(select(User).where(User.username == settings.default_admin_username))
            assert admin_role is not None
            assert admin is not None
            assert admin.role_id == admin_role.id
            assert admin.is_active is True
    finally:
        container.shutdown()
