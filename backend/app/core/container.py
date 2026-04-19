from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.container_modules import (
    wire_access_services,
    wire_infrastructure_services,
    wire_observability_services,
    wire_prompt_and_audit_services,
    wire_provider_and_catalog_services,
    wire_runtime_services,
    wire_security_services,
    wire_workspace_services,
)
from app.core.db import create_db_engine, create_session_factory
from app.models import Base
from app.services.jobs.chat_dispatch import (
    ChatDispatchQueue,
    InMemoryChatDispatchQueue,
    RedisChatDispatchQueue,
)
from app.services.realtime.backplane import (
    InMemoryRealtimeBackplane,
    RealtimeBackplane,
    RedisRealtimeBackplane,
)


class AppContainer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.engine = create_db_engine(settings.database_url)
        self.session_factory: sessionmaker[Session] = create_session_factory(self.engine)

        wire_infrastructure_services(self)
        wire_security_services(self)
        wire_access_services(self)
        wire_prompt_and_audit_services(self)
        wire_provider_and_catalog_services(self)
        wire_workspace_services(self)
        wire_observability_services(self)
        wire_runtime_services(self)

    def _build_backplane(self) -> RealtimeBackplane:
        if self.settings.realtime_backend == "memory":
            return InMemoryRealtimeBackplane()
        return RedisRealtimeBackplane(
            redis_url=self.settings.redis_url,
            channel_prefix=self.settings.realtime_channel_prefix,
        )

    def _build_chat_queue(self) -> ChatDispatchQueue:
        if self.settings.chat_dispatch_backend == "memory":
            return InMemoryChatDispatchQueue()
        return RedisChatDispatchQueue(
            redis_url=self.settings.redis_url,
            stream_name=self.settings.chat_dispatch_stream,
            group_name=self.settings.chat_dispatch_group,
            consumer_name=self.settings.durable_job_worker_name,
        )

    def initialize(self) -> None:
        self.bootstrap_schema_and_seed()
        self.realtime_hub.start()
        if hasattr(self, "plugin_runtime_manager"):
            self.plugin_runtime_manager.start()

    def bootstrap_schema_and_seed(self) -> None:
        # Keep lightweight create_all only for SQLite-style local/test databases.
        # Postgres environments should rely on Alembic migrations instead.
        if self.settings.auto_create_schema and self.engine.dialect.name == "sqlite":
            Base.metadata.create_all(self.engine)
        with self.session_factory() as session:
            if self.settings.auto_seed_defaults:
                self.bootstrap_service.seed_default_data(session)
            session.commit()

    def shutdown(self) -> None:
        if hasattr(self, "plugin_runtime_manager"):
            self.plugin_runtime_manager.stop()
        self.realtime_hub.stop()
        self.engine.dispose()
