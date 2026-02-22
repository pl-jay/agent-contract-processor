import asyncio
import threading
import time

from app.services.pipeline_executor import PipelineExecutor


class _DummyOrchestrator:
    def __init__(self) -> None:
        self.calls = 0
        self._lock = threading.Lock()

    def run(self, sender: str, subject: str, file_path: str) -> dict:
        _ = sender, subject, file_path
        with self._lock:
            self.calls += 1
            current = self.calls
        time.sleep(0.1)
        return {"contract_id": current}


def test_pipeline_executor_reuses_inflight_idempotent_request() -> None:
    orchestrator = _DummyOrchestrator()
    executor = PipelineExecutor(
        orchestrator=orchestrator,
        max_workers=2,
        wait_timeout_seconds=2,
        idempotency_enabled=True,
    )

    async def _run() -> tuple[str, str]:
        task_one = asyncio.create_task(
            executor.submit_and_wait(
                sender="a",
                subject="b",
                file_path="/tmp/c.pdf",
                idempotency_key="same-key",
            )
        )
        task_two = asyncio.create_task(
            executor.submit_and_wait(
                sender="a",
                subject="b",
                file_path="/tmp/c.pdf",
                idempotency_key="same-key",
            )
        )
        first, second = await asyncio.gather(task_one, task_two)
        return first.request_id, second.request_id

    req_one, req_two = asyncio.run(_run())
    executor.shutdown()

    assert req_one == req_two
    assert orchestrator.calls == 1
