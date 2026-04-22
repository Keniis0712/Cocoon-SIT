import pytest

from app.worker.main import main


def test_worker_main_initializes_loops_and_shuts_down(monkeypatch):
    calls = []

    class _WorkerRuntime:
        def __init__(self):
            self.calls = 0

        def process_next_chat_dispatch(self):
            calls.append("chat")
            return False

        def process_next_durable_job(self):
            calls.append("durable")
            raise KeyboardInterrupt()

    class _Container:
        def __init__(self, settings):
            calls.append(("container", settings))
            self.worker_runtime = _WorkerRuntime()

        def initialize(self):
            calls.append("initialize")

        def shutdown(self):
            calls.append("shutdown")

    monkeypatch.setattr("app.worker.main.configure_logging", lambda: calls.append("logging"))
    monkeypatch.setattr("app.worker.main.get_settings", lambda: "settings")
    monkeypatch.setattr("app.worker.main.WorkerContainer", _Container)

    with pytest.raises(KeyboardInterrupt):
        main()

    assert calls[:4] == ["logging", ("container", "settings"), "initialize", "chat"]
    assert "shutdown" in calls


def test_worker_main_sleeps_when_idle(monkeypatch):
    calls = []

    class _WorkerRuntime:
        def process_next_chat_dispatch(self):
            calls.append("chat")
            return False

        def process_next_durable_job(self):
            calls.append("durable")
            return False

    class _Container:
        def __init__(self, settings):
            self.worker_runtime = _WorkerRuntime()

        def initialize(self):
            calls.append("initialize")

        def shutdown(self):
            calls.append("shutdown")

    def fake_sleep(seconds):
        calls.append(("sleep", seconds))
        raise KeyboardInterrupt()

    monkeypatch.setattr("app.worker.main.configure_logging", lambda: None)
    monkeypatch.setattr("app.worker.main.get_settings", lambda: "settings")
    monkeypatch.setattr("app.worker.main.WorkerContainer", _Container)
    monkeypatch.setattr("app.worker.main.time.sleep", fake_sleep)

    with pytest.raises(KeyboardInterrupt):
        main()

    assert ("sleep", 0.25) in calls
    assert "shutdown" in calls


def test_worker_main_module_entrypoint_calls_main(monkeypatch):
    import runpy

    calls = []

    class _WorkerRuntime:
        def process_next_chat_dispatch(self):
            calls.append("chat")
            return False

        def process_next_durable_job(self):
            calls.append("durable")
            raise KeyboardInterrupt()

    class _Container:
        def __init__(self, settings):
            calls.append(("container", settings))
            self.worker_runtime = _WorkerRuntime()

        def initialize(self):
            calls.append("initialize")

        def shutdown(self):
            calls.append("shutdown")

    monkeypatch.setattr("app.core.logging.configure_logging", lambda: calls.append("logging"))
    monkeypatch.setattr("app.core.config.get_settings", lambda: "settings")
    monkeypatch.setattr("app.worker.container.WorkerContainer", _Container)

    with pytest.raises(KeyboardInterrupt):
        runpy.run_module("app.worker.main", run_name="__main__")

    assert calls[:4] == ["logging", ("container", "settings"), "initialize", "chat"]
    assert "shutdown" in calls
