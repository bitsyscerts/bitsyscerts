"""Unit tests for stats_snapshotter._serialise_payload."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ctpool.stats_snapshotter import _serialise_payload, run_snapshot_loop


def _make_registry_session_factory() -> MagicMock:
    session = AsyncMock()
    session.begin = MagicMock()
    session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
    session.begin.return_value.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory


class TestSerialisePayload:
    def test_serialises_datetime_to_iso_string(self) -> None:
        dt = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
        result = _serialise_payload({"ts": dt})
        assert isinstance(result["ts"], str)
        assert "2025-06-01" in result["ts"]

    def test_serialises_uuid_to_string(self) -> None:
        uid = uuid.uuid4()
        result = _serialise_payload({"id": uid})
        assert isinstance(result["id"], str)
        assert result["id"] == str(uid)

    def test_preserves_plain_scalars(self) -> None:
        payload = {"count": 42, "label": "hello", "ratio": 0.5, "active": True}
        result = _serialise_payload(payload)
        assert result == payload

    def test_handles_nested_structures(self) -> None:
        dt = datetime(2025, 1, 1, tzinfo=UTC)
        payload = {"logs": [{"id": 1, "ts": dt}]}
        result = _serialise_payload(payload)
        assert isinstance(result["logs"][0]["ts"], str)

    def test_raises_for_unserializable_type(self) -> None:
        with pytest.raises(TypeError):
            _serialise_payload({"obj": object()})

    def test_empty_payload_returns_empty_dict(self) -> None:
        assert _serialise_payload({}) == {}


@pytest.mark.asyncio
async def test_run_snapshot_loop_registers_and_heartbeats_worker() -> None:
    """Snapshot loop registers a singleton worker and heartbeats each cycle."""
    settings = MagicMock()
    settings.ct_stats_heavy_refresh_seconds = 30
    settings.ct_worker_stale_seconds = 300
    factory = _make_registry_session_factory()
    engine = MagicMock()
    engine.dispose = AsyncMock()
    row = MagicMock(id=uuid.uuid4())
    heartbeat_mock = AsyncMock()

    with (
        patch("ctpool.stats_snapshotter.create_engine", return_value=engine),
        patch("ctpool.stats_snapshotter.create_session_factory", return_value=factory),
        patch(
            "ctpool.stats_snapshotter.register_worker",
            AsyncMock(return_value=row),
        ) as register_mock,
        patch("ctpool.stats_snapshotter.heartbeat_worker", heartbeat_mock),
        patch(
            "ctpool.stats_snapshotter.reap_stale_worker_rows",
            AsyncMock(return_value=[]),
        ) as reap_mock,
        patch("ctpool.stats_snapshotter.mark_worker_stopped", AsyncMock()) as stop_mock,
        patch(
            "ctpool.stats_snapshotter.take_snapshot_once",
            AsyncMock(return_value={}),
        ),
        patch(
            "ctpool.stats_snapshotter.asyncio.sleep",
            AsyncMock(side_effect=asyncio.CancelledError()),
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await run_snapshot_loop(settings)

    register_mock.assert_awaited_once()
    assert [call.kwargs["status"] for call in heartbeat_mock.await_args_list] == [
        "processing",
        "idle",
    ]
    reap_mock.assert_awaited_once()
    stop_mock.assert_awaited_once()
    engine.dispose.assert_awaited_once()
