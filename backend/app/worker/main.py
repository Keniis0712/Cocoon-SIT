from __future__ import annotations

import time

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.worker.container import WorkerContainer


def main() -> None:
    configure_logging()
    settings = get_settings()
    container = WorkerContainer(settings)
    container.initialize()
    try:
        while True:
            did_work = container.worker_runtime.process_next_chat_dispatch()
            did_work = container.worker_runtime.process_next_durable_job() or did_work
            if not did_work:
                time.sleep(0.25)
    finally:
        container.shutdown()


if __name__ == "__main__":
    main()
