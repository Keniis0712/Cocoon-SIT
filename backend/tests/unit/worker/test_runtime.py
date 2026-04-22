from app.worker.runtime import WorkerRuntime


def test_worker_runtime_delegates_to_worker_services(monkeypatch):
    init_calls = []

    class _ChatDispatchWorkerService:
        def __init__(self, **kwargs):
            init_calls.append(("chat", kwargs))

        def process_next(self):
            return True

    class _DurableJobWorkerService:
        def __init__(self, **kwargs):
            init_calls.append(("durable", kwargs))

        def process_next(self):
            return False

    monkeypatch.setattr("app.worker.runtime.ChatDispatchWorkerService", _ChatDispatchWorkerService)
    monkeypatch.setattr("app.worker.runtime.DurableJobWorkerService", _DurableJobWorkerService)

    runtime = WorkerRuntime(
        session_factory="session_factory",
        chat_queue="chat_queue",
        chat_runtime="chat_runtime",
        durable_jobs="durable_jobs",
        durable_executor="durable_executor",
        realtime_hub="realtime_hub",
        worker_name="worker-1",
    )

    assert init_calls[0][0] == "chat"
    assert init_calls[1][0] == "durable"
    assert runtime.process_next_chat_dispatch() is True
    assert runtime.process_next_durable_job() is False
