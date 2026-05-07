"""Unit tests for stats_snapshotter._serialise_payload."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from ctpool.stats_snapshotter import _serialise_payload


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
