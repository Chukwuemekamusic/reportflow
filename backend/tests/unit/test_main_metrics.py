import asyncio
from unittest.mock import AsyncMock, Mock, call, patch

import pytest
from fastapi import FastAPI

from app import main


@pytest.mark.asyncio
async def test_update_queue_metrics_reads_all_celery_queues() -> None:
    fake_redis = AsyncMock()
    fake_redis.llen.side_effect = [1, 2, 3]

    gauge = Mock()
    label_metrics = {queue: Mock() for queue in main.QUEUE_NAMES}
    gauge.labels.side_effect = lambda *, queue: label_metrics[queue]

    with patch.object(main, "QUEUE_DEPTH", gauge), patch.object(
        main.aioredis, "from_url", return_value=fake_redis
    ) as mock_from_url:
        await main.update_queue_metrics()

    mock_from_url.assert_called_once_with(main.settings.celery_broker_url)
    assert fake_redis.llen.await_args_list == [call("high"), call("default"), call("low")]
    label_metrics["high"].set.assert_called_once_with(1)
    label_metrics["default"].set.assert_called_once_with(2)
    label_metrics["low"].set.assert_called_once_with(3)
    fake_redis.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_lifespan_starts_and_stops_queue_metrics_task() -> None:
    app = FastAPI()
    refresh_started = asyncio.Event()
    refresh_cancelled = asyncio.Event()

    async def fake_refresh_queue_metrics() -> None:
        refresh_started.set()
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            refresh_cancelled.set()
            raise

    with patch.object(main, "ensure_bucket_exists", AsyncMock()) as mock_bucket, patch.object(
        main, "update_queue_metrics", AsyncMock()
    ) as mock_update, patch.object(
        main, "refresh_queue_metrics", fake_refresh_queue_metrics
    ):
        async with main.lifespan(app):
            await asyncio.wait_for(refresh_started.wait(), timeout=1)
            assert hasattr(app.state, "queue_metrics_task")
            assert not app.state.queue_metrics_task.done()

    mock_bucket.assert_awaited_once()
    mock_update.assert_awaited_once()
    await asyncio.wait_for(refresh_cancelled.wait(), timeout=1)


def test_create_app_excludes_metrics_endpoint_from_http_metrics() -> None:
    instrumentator_instance = Mock()
    instrumentator_instance.instrument.return_value = instrumentator_instance
    instrumentator_instance.expose.return_value = instrumentator_instance

    with patch.object(main, "Instrumentator", return_value=instrumentator_instance) as mock_instrumentator:
        app = main.create_app()

    mock_instrumentator.assert_called_once_with(excluded_handlers=["/metrics"])
    instrumentator_instance.instrument.assert_called_once_with(app)
    instrumentator_instance.expose.assert_called_once_with(app)