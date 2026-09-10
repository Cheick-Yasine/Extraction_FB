"""Circuit Breaker explicite — protège chaque compte et chaque groupe.

États : CLOSED → OPEN → HALF_OPEN → CLOSED
Conçu pour empêcher les cascades d'échecs sur 6 mois de runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, TypeVar

from extraction_fb.domain.models import CircuitState

T = TypeVar("T")


@dataclass
class CircuitBreaker:
    """Circuit Breaker simple, déterministe et testable."""

    name: str
    failure_threshold: int = 3
    recovery_timeout: timedelta = field(default_factory=lambda: timedelta(hours=24))
    half_open_max_calls: int = 1

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    opened_at: datetime | None = None
    half_open_calls: int = 0

    def allow_request(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)

        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if self.opened_at and (now - self.opened_at) >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                return True
            return False

        # HALF_OPEN
        if self.half_open_calls < self.half_open_max_calls:
            self.half_open_calls += 1
            return True
        return False

    def record_success(self) -> None:
        self.failure_count = 0
        self.half_open_calls = 0
        self.state = CircuitState.CLOSED
        self.opened_at = None

    def record_failure(self, now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        self.failure_count += 1

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.opened_at = now
            return

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.opened_at = now

    def force_open(self, now: datetime | None = None) -> None:
        """Utilisé lors d'un BlocageDetecteError ou SessionExpireeError."""
        now = now or datetime.now(timezone.utc)
        self.state = CircuitState.OPEN
        self.opened_at = now
        self.failure_count = self.failure_threshold

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
        }


class CircuitBreakerRegistry:
    """Registre de circuit breakers isolés (par compte, par groupe, ...)."""

    def __init__(self) -> None:
        self._breakers: dict[str, CircuitBreaker] = {}

    def get(self, name: str, **kwargs) -> CircuitBreaker:
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name=name, **kwargs)
        return self._breakers[name]

    def all_status(self) -> dict[str, dict]:
        return {k: v.to_dict() for k, v in self._breakers.items()}
