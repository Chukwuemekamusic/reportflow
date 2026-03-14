import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import app.db.base as db_base
from app.services import storage_service
from app.workers import celery_app
from app.workers.tasks.base import ReportBaseTask


def _reset_worker_loop() -> None:
    loop = celery_app._worker_loop
    if loop is not None and not loop.is_closed():
        loop.close()
    celery_app._worker_loop = None
    asyncio.set_event_loop(None)


def setup_function() -> None:
    _reset_worker_loop()


def teardown_function() -> None:
    _reset_worker_loop()


def test_run_async_reuses_one_loop_per_process() -> None:
    async def current_loop():
        return asyncio.get_running_loop()

    first_loop = celery_app.run_async(current_loop())
    second_loop = celery_app.run_async(current_loop())

    assert first_loop is second_loop
    assert celery_app._worker_loop is first_loop


def test_worker_process_signals_manage_loop_and_engine_disposal() -> None:
    fake_engine = SimpleNamespace(dispose=AsyncMock())

    with patch.object(db_base, "engine", fake_engine):
        celery_app.init_worker_loop()
        loop = celery_app._worker_loop

        assert loop is not None
        assert not loop.is_closed()
        assert fake_engine.dispose.await_count == 1

        celery_app.shutdown_worker_loop()

    assert fake_engine.dispose.await_count == 2
    assert loop.is_closed()
    assert celery_app._worker_loop is None


def test_update_progress_uses_shared_async_runner() -> None:
    task = ReportBaseTask()

    def fake_run_async(coro):
        assert asyncio.iscoroutine(coro)
        coro.close()

    with patch("app.workers.tasks.base.run_async", side_effect=fake_run_async) as mock_run_async, patch.object(task, "_publish_event") as mock_publish:
        task.update_progress("job-123", 5, "Connecting to database...", eta_secs=90)

    assert mock_run_async.call_count == 1
    mock_publish.assert_called_once_with(
        "job-123",
        {"event": "progress", "job_id": "job-123", "progress": 5, "stage": "Connecting to database...", "eta_secs": 90},
    )


def test_upload_file_sync_runs_upload_on_worker_loop() -> None:
    async def fake_upload(file_bytes: bytes, object_key: str, content_type: str) -> str:
        return f"{object_key}:{content_type}:{file_bytes.decode()}"

    with patch("app.services.storage_service.upload_file", new=fake_upload):
        result = storage_service.upload_file_sync(b"pdf", "reports/job-1.pdf", "application/pdf")

    assert result == "reports/job-1.pdf:application/pdf:pdf"