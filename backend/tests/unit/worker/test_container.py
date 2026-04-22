from types import SimpleNamespace

from app.core.config import Settings
from app.worker.container import WorkerContainer


def test_worker_container_wires_executor_and_runtime(monkeypatch):
    recorded = {}

    def fake_app_container_init(self, settings):
        self.settings = settings
        self.chat_runtime = "chat-runtime"
        self.durable_jobs = "durable-jobs"
        self.audit_service = "audit-service"
        self.round_cleanup = "round-cleanup"
        self.prompt_service = "prompt-service"
        self.provider_registry = "provider-registry"
        self.session_factory = "session-factory"
        self.chat_queue = "chat-queue"
        self.realtime_hub = "realtime-hub"

    class _FakeExecutor:
        def __init__(self, **kwargs):
            recorded["executor_kwargs"] = kwargs
            self.token = "executor"

    class _FakeRuntime:
        def __init__(self, **kwargs):
            recorded["runtime_kwargs"] = kwargs

    monkeypatch.setattr("app.worker.container.AppContainer.__init__", fake_app_container_init)
    monkeypatch.setattr("app.worker.container.DurableJobExecutor", _FakeExecutor)
    monkeypatch.setattr("app.worker.container.WorkerRuntime", _FakeRuntime)

    settings = Settings(durable_job_worker_name="worker-x")
    container = WorkerContainer(settings)

    assert recorded["executor_kwargs"] == {
        "chat_runtime": "chat-runtime",
        "durable_jobs": "durable-jobs",
        "audit_service": "audit-service",
        "round_cleanup": "round-cleanup",
        "prompt_service": "prompt-service",
        "provider_registry": "provider-registry",
    }
    assert recorded["runtime_kwargs"] == {
        "session_factory": "session-factory",
        "chat_queue": "chat-queue",
        "chat_runtime": "chat-runtime",
        "durable_jobs": "durable-jobs",
        "durable_executor": container.durable_executor,
        "realtime_hub": "realtime-hub",
        "worker_name": "worker-x",
    }


def test_worker_container_initialize_bootstraps_schema(monkeypatch):
    def fake_app_container_init(self, settings):
        self.settings = settings
        self.chat_runtime = "chat-runtime"
        self.durable_jobs = "durable-jobs"
        self.audit_service = "audit-service"
        self.round_cleanup = "round-cleanup"
        self.prompt_service = "prompt-service"
        self.provider_registry = "provider-registry"
        self.session_factory = "session-factory"
        self.chat_queue = "chat-queue"
        self.realtime_hub = "realtime-hub"

    monkeypatch.setattr("app.worker.container.AppContainer.__init__", fake_app_container_init)
    monkeypatch.setattr("app.worker.container.DurableJobExecutor", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr("app.worker.container.WorkerRuntime", lambda **kwargs: SimpleNamespace())

    settings = Settings()
    container = WorkerContainer(settings)
    calls = []
    container.bootstrap_schema_and_seed = lambda: calls.append("bootstrapped")

    container.initialize()

    assert calls == ["bootstrapped"]
