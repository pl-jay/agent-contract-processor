from __future__ import annotations

import asyncio
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
import logging
import threading
import uuid
from typing import Any, Protocol


class ContractPipeline(Protocol):
    def run(self, sender: str, subject: str, file_path: str) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class PipelineExecutionOutcome:
    completed: bool
    request_id: str
    result: dict[str, Any] | None


class PipelineExecutor:
    def __init__(
        self,
        orchestrator: ContractPipeline,
        *,
        max_workers: int,
        wait_timeout_seconds: int,
        idempotency_enabled: bool = True,
    ) -> None:
        self._logger = logging.getLogger(__name__)
        self._orchestrator = orchestrator
        self._wait_timeout_seconds = max(wait_timeout_seconds, 1)
        self._idempotency_enabled = idempotency_enabled
        self._pool = ThreadPoolExecutor(
            max_workers=max(max_workers, 1),
            thread_name_prefix="contract-pipeline",
        )
        self._lock = threading.Lock()
        self._futures: dict[str, Future[dict[str, Any]]] = {}
        self._idempotency_index: dict[str, str] = {}

    async def submit_and_wait(
        self,
        *,
        sender: str,
        subject: str,
        file_path: str,
        idempotency_key: str | None = None,
    ) -> PipelineExecutionOutcome:
        request_id, future = self._get_or_submit(
            sender=sender,
            subject=subject,
            file_path=file_path,
            idempotency_key=idempotency_key,
        )

        try:
            result = await asyncio.wait_for(
                asyncio.wrap_future(future),
                timeout=self._wait_timeout_seconds,
            )
            return PipelineExecutionOutcome(
                completed=True,
                request_id=request_id,
                result=result,
            )
        except asyncio.TimeoutError:
            self._logger.warning(
                "Pipeline still running after sync timeout; returning accepted response",
                extra={
                    "event": "pipeline_deferred_response",
                    "request_id": request_id,
                    "wait_timeout_seconds": self._wait_timeout_seconds,
                },
            )
            return PipelineExecutionOutcome(
                completed=False,
                request_id=request_id,
                result=None,
            )

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=False)

    def _get_or_submit(
        self,
        *,
        sender: str,
        subject: str,
        file_path: str,
        idempotency_key: str | None,
    ) -> tuple[str, Future[dict[str, Any]]]:
        normalized_key = (idempotency_key or "").strip()

        with self._lock:
            if self._idempotency_enabled and normalized_key:
                existing_request_id = self._idempotency_index.get(normalized_key)
                if existing_request_id:
                    existing_future = self._futures.get(existing_request_id)
                    if existing_future and not existing_future.done():
                        self._logger.info(
                            "Reusing in-flight pipeline execution for idempotency key",
                            extra={
                                "event": "pipeline_idempotency_reused",
                                "request_id": existing_request_id,
                            },
                        )
                        return existing_request_id, existing_future

            request_id = uuid.uuid4().hex
            future = self._pool.submit(self._orchestrator.run, sender, subject, file_path)
            self._futures[request_id] = future

            if self._idempotency_enabled and normalized_key:
                self._idempotency_index[normalized_key] = request_id

            future.add_done_callback(
                lambda fut, rid=request_id, key=normalized_key: self._on_done(
                    request_id=rid,
                    idempotency_key=key,
                    future=fut,
                )
            )
            return request_id, future

    def _on_done(
        self,
        *,
        request_id: str,
        idempotency_key: str,
        future: Future[dict[str, Any]],
    ) -> None:
        with self._lock:
            self._futures.pop(request_id, None)
            if idempotency_key and self._idempotency_index.get(idempotency_key) == request_id:
                self._idempotency_index.pop(idempotency_key, None)

        exc = future.exception()
        if exc is not None:
            self._logger.error(
                "Asynchronous pipeline execution failed",
                extra={
                    "event": "pipeline_async_failed",
                    "request_id": request_id,
                    "error": str(exc),
                },
                exc_info=(type(exc), exc, exc.__traceback__),
            )
            return

        result = future.result()
        self._logger.info(
            "Asynchronous pipeline execution completed",
            extra={
                "event": "pipeline_async_completed",
                "request_id": request_id,
                "contract_id": result.get("contract_id"),
            },
        )
