"""
Circuit breaker pattern for LLM providers.

Prevents cascading failures by temporarily blocking requests
to a provider that is consistently failing or exceeding latency thresholds.

States:
- CLOSED: Normal operation, requests flow through.
- OPEN: Provider is blocked, requests are immediately rejected.
- HALF_OPEN: A single test request is allowed to probe recovery.
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger(__name__)


class CircuitState(enum.StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """Circuit breaker for a single LLM provider.

    Opens when consecutive failures exceed the threshold or when
    latency consistently exceeds the latency threshold.

    Automatically transitions to HALF_OPEN after the recovery timeout,
    allowing a single probe request. If that succeeds, returns to CLOSED.
    """

    name: str
    failure_threshold: int = 5
    latency_threshold_ms: float = 5000.0
    recovery_timeout_seconds: float = 60.0

    # Internal state
    _state: CircuitState = field(default=CircuitState.CLOSED, repr=False)
    _failure_count: int = field(default=0, repr=False)
    _latency_violations: int = field(default=0, repr=False)
    _last_failure_time: float = field(default=0.0, repr=False)
    _last_state_change: float = field(default_factory=time.monotonic, repr=False)

    @property
    def state(self) -> CircuitState:
        """Get the current state, auto-transitioning to HALF_OPEN if recovery timeout elapsed."""
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.recovery_timeout_seconds:
                self._transition_to(CircuitState.HALF_OPEN)
        return self._state

    @property
    def is_closed(self) -> bool:
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    def record_success(self, latency_ms: float) -> None:
        """Record a successful request.

        In HALF_OPEN state, this closes the circuit breaker.
        In CLOSED state, this resets failure counters.
        """
        if self._state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.CLOSED)
            logger.info("circuit_breaker_recovered", name=self.name)

        self._failure_count = 0
        self._latency_violations = 0

        # Track latency violations even on success
        if latency_ms > self.latency_threshold_ms:
            self._latency_violations += 1
            if self._latency_violations >= self.failure_threshold:
                self._trip(f"Latency threshold exceeded {self._latency_violations} times")

    def record_failure(self, error: str = "") -> None:
        """Record a failed request.

        In HALF_OPEN state, immediately re-opens the circuit.
        In CLOSED state, increments the failure counter and possibly trips.
        """
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            self._trip(f"Probe request failed: {error}")
        elif self._failure_count >= self.failure_threshold:
            self._trip(f"Failure threshold reached: {self._failure_count} consecutive failures")

    def _trip(self, reason: str) -> None:
        """Open the circuit breaker."""
        self._transition_to(CircuitState.OPEN)
        logger.warning(
            "circuit_breaker_tripped",
            name=self.name,
            reason=reason,
            failure_count=self._failure_count,
        )

    def _transition_to(self, new_state: CircuitState) -> None:
        old_state = self._state
        self._state = new_state
        self._last_state_change = time.monotonic()

        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._latency_violations = 0

    def get_metrics(self) -> dict[str, object]:
        """Return circuit breaker metrics for observability."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "latency_violations": self._latency_violations,
            "time_in_state_seconds": time.monotonic() - self._last_state_change,
        }
