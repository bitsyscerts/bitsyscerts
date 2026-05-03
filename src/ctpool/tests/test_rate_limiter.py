"""Tests for ctpool.rate_limiter — BackoffState and RateLimiter."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from ctpool.rate_limiter import BackoffState, RateLimiter


def _state(
    *,
    consecutive_failures: int = 0,
    backoff_until: datetime | None = None,
    last_429_at: datetime | None = None,
    current_batch_size: int = 256,
    learned_max_batch_size: int = 256,
) -> BackoffState:
    """Build a BackoffState with sensible test defaults."""
    return BackoffState(
        log_source_id=uuid.uuid4(),
        consecutive_failures=consecutive_failures,
        backoff_until=backoff_until,
        last_429_at=last_429_at,
        current_batch_size=current_batch_size,
        learned_max_batch_size=learned_max_batch_size,
    )


@pytest.fixture()
def limiter() -> RateLimiter:
    """RateLimiter with deterministic, small values for tests."""
    return RateLimiter(
        base_backoff_seconds=10,
        max_backoff_seconds=300,
        jitter_fraction=0.0,  # zero jitter for deterministic assertions
        min_batch_size=1,
    )


# ------------------------------------------------------------------
# BackoffState
# ------------------------------------------------------------------


def test_backoff_state_is_frozen() -> None:
    """BackoffState is immutable — assignment to a field raises."""
    state = _state()
    with pytest.raises(Exception):  # FrozenInstanceError  # noqa: B017
        state.consecutive_failures = 99  # type: ignore[misc]


def test_backoff_state_stores_log_source_id() -> None:
    """log_source_id is preserved as-is."""
    log_id = uuid.uuid4()
    state = BackoffState(
        log_source_id=log_id,
        consecutive_failures=0,
        backoff_until=None,
        last_429_at=None,
        current_batch_size=256,
        learned_max_batch_size=256,
    )
    assert state.log_source_id == log_id


# ------------------------------------------------------------------
# handle_429
# ------------------------------------------------------------------


def test_handle_429_increments_consecutive_failures(limiter: RateLimiter) -> None:
    """handle_429 increments consecutive_failures by one."""
    state = _state(consecutive_failures=2)
    updated = limiter.handle_429(state)
    assert updated.consecutive_failures == 3


def test_handle_429_sets_backoff_until_in_future(limiter: RateLimiter) -> None:
    """handle_429 sets backoff_until to a future UTC datetime."""
    state = _state()
    before = datetime.now(UTC)
    updated = limiter.handle_429(state)
    assert updated.backoff_until is not None
    assert updated.backoff_until > before


def test_handle_429_sets_last_429_at(limiter: RateLimiter) -> None:
    """handle_429 records last_429_at as a recent UTC datetime."""
    before = datetime.now(UTC)
    state = _state()
    updated = limiter.handle_429(state)
    assert updated.last_429_at is not None
    assert updated.last_429_at >= before


def test_handle_429_with_retry_after_uses_that_delay(limiter: RateLimiter) -> None:
    """handle_429 with retry_after=60 sets backoff of ~60 s (jitter=0)."""
    state = _state()
    before = datetime.now(UTC)
    updated = limiter.handle_429(state, retry_after=60)
    assert updated.backoff_until is not None
    elapsed = (updated.backoff_until - before).total_seconds()
    assert 59 <= elapsed <= 62


def test_handle_429_halves_batch_size(limiter: RateLimiter) -> None:
    """handle_429 halves current_batch_size."""
    state = _state(current_batch_size=256)
    updated = limiter.handle_429(state)
    assert updated.current_batch_size == 128


def test_handle_429_batch_size_floor_at_min(limiter: RateLimiter) -> None:
    """handle_429 never drops current_batch_size below min_batch_size."""
    state = _state(current_batch_size=1)
    updated = limiter.handle_429(state)
    assert updated.current_batch_size == 1


# ------------------------------------------------------------------
# handle_5xx
# ------------------------------------------------------------------


def test_handle_5xx_increments_consecutive_failures(limiter: RateLimiter) -> None:
    """handle_5xx increments consecutive_failures."""
    state = _state(consecutive_failures=0)
    updated = limiter.handle_5xx(state, status_code=503)
    assert updated.consecutive_failures == 1


def test_handle_5xx_sets_backoff_until_in_future(limiter: RateLimiter) -> None:
    """handle_5xx sets backoff_until to a future datetime."""
    before = datetime.now(UTC)
    updated = limiter.handle_5xx(_state(), status_code=500)
    assert updated.backoff_until is not None
    assert updated.backoff_until > before


def test_handle_5xx_does_not_update_last_429_at(limiter: RateLimiter) -> None:
    """handle_5xx preserves last_429_at unchanged."""
    original_429 = datetime(2025, 1, 1, tzinfo=UTC)
    state = _state(last_429_at=original_429)
    updated = limiter.handle_5xx(state, status_code=500)
    assert updated.last_429_at == original_429


# ------------------------------------------------------------------
# handle_success
# ------------------------------------------------------------------


def test_handle_success_resets_consecutive_failures(limiter: RateLimiter) -> None:
    """handle_success resets consecutive_failures to zero."""
    state = _state(consecutive_failures=5)
    updated = limiter.handle_success(state)
    assert updated.consecutive_failures == 0


def test_handle_success_clears_backoff_until(limiter: RateLimiter) -> None:
    """handle_success clears backoff_until to None."""
    state = _state(backoff_until=datetime.now(UTC))
    updated = limiter.handle_success(state)
    assert updated.backoff_until is None


def test_handle_success_grows_batch_size(limiter: RateLimiter) -> None:
    """handle_success grows current_batch_size toward learned_max."""
    state = _state(current_batch_size=100, learned_max_batch_size=256)
    updated = limiter.handle_success(state)
    assert updated.current_batch_size > 100


def test_handle_success_does_not_exceed_learned_max(limiter: RateLimiter) -> None:
    """handle_success does not grow batch beyond learned_max_batch_size."""
    state = _state(current_batch_size=256, learned_max_batch_size=256)
    updated = limiter.handle_success(state)
    assert updated.current_batch_size <= 256


# ------------------------------------------------------------------
# Eligibility
# ------------------------------------------------------------------


def test_is_eligible_true_when_no_backoff(limiter: RateLimiter) -> None:
    """is_eligible returns True when backoff_until is None."""
    state = _state(backoff_until=None)
    assert limiter.is_eligible(state) is True


def test_is_eligible_false_during_backoff(limiter: RateLimiter) -> None:
    """is_eligible returns False when backoff_until is in the future."""
    from datetime import timedelta

    state = _state(backoff_until=datetime.now(UTC) + timedelta(seconds=60))
    assert limiter.is_eligible(state) is False


def test_seconds_until_eligible_zero_when_no_backoff(limiter: RateLimiter) -> None:
    """seconds_until_eligible returns 0.0 when backoff_until is None."""
    assert limiter.seconds_until_eligible(_state(backoff_until=None)) == 0.0


def test_seconds_until_eligible_positive_during_backoff(limiter: RateLimiter) -> None:
    """seconds_until_eligible returns a positive value during backoff."""
    from datetime import timedelta

    state = _state(backoff_until=datetime.now(UTC) + timedelta(seconds=30))
    remaining = limiter.seconds_until_eligible(state)
    assert remaining > 0.0


def test_exponential_backoff_grows_with_failures(limiter: RateLimiter) -> None:
    """Successive 5xx responses produce increasing backoff windows."""
    state = _state()
    delays: list[float] = []
    for _ in range(4):
        state = limiter.handle_5xx(state, status_code=503)
        assert state.backoff_until is not None
        delays.append((state.backoff_until - datetime.now(UTC)).total_seconds())
    # Each delay should be longer than the previous one
    for i in range(1, len(delays)):
        assert delays[i] > delays[i - 1]
