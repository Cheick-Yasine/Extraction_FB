"""Tests unitaires du Circuit Breaker — prouve le comportement déterministe."""

from datetime import datetime, timedelta, timezone

from extraction_fb.domain.models import CircuitState
from extraction_fb.infrastructure.resilience.circuit_breaker import CircuitBreaker


def test_starts_closed():
    cb = CircuitBreaker(name="test")
    assert cb.state == CircuitState.CLOSED
    assert cb.allow_request() is True


def test_opens_after_threshold():
    cb = CircuitBreaker(name="test", failure_threshold=3)
    now = datetime.now(timezone.utc)

    cb.record_failure(now)
    cb.record_failure(now)
    assert cb.state == CircuitState.CLOSED

    cb.record_failure(now)
    assert cb.state == CircuitState.OPEN
    assert cb.allow_request(now) is False


def test_recovers_after_timeout():
    cb = CircuitBreaker(
        name="test",
        failure_threshold=1,
        recovery_timeout=timedelta(hours=1),
    )
    now = datetime.now(timezone.utc)

    cb.record_failure(now)
    assert cb.state == CircuitState.OPEN

    later = now + timedelta(hours=2)
    assert cb.allow_request(later) is True
    assert cb.state == CircuitState.HALF_OPEN

    cb.record_success()
    assert cb.state == CircuitState.CLOSED


def test_force_open():
    cb = CircuitBreaker(name="test")
    now = datetime.now(timezone.utc)
    cb.force_open(now)
    assert cb.state == CircuitState.OPEN
    assert cb.allow_request(now) is False
