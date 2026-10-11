"""
Circuit breaker pattern for downstream service failures.

Used by the rate limiter around Redis: after repeated failures the breaker OPENs and
requests skip Redis immediately (no 1-second timeout per request); after
`recovery_timeout` one trial call is let through (HALF_OPEN) and, if it works, the
breaker CLOSEs again and Redis is used once more.
"""
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitOpenError(Exception):
    """Raised instead of calling the protected function while the circuit is OPEN."""


@dataclass
class CircuitConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5       # Consecutive failures before opening
    recovery_timeout: int = 30       # Seconds to stay open
    half_open_max_requests: int = 1  # Trial requests allowed while half-open


class CircuitBreaker:
    """
    States:
    - CLOSED: calls flow normally, consecutive failures are counted
    - OPEN: calls are rejected until the recovery timeout elapses
    - HALF_OPEN: a limited number of trial calls decide whether to close or re-open
    """

    def __init__(self, name: str, config: CircuitConfig | None = None):
        self.name = name
        self.config = config or CircuitConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.half_open_requests = 0
        self._lock = threading.Lock()
        logger.info("Circuit breaker '%s' initialized in CLOSED state", name)

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Run func under circuit breaker protection."""
        with self._lock:
            if self.state == CircuitState.OPEN:
                if time.time() - self.last_failure_time >= self.config.recovery_timeout:
                    logger.info("Circuit '%s' moving to HALF-OPEN after timeout", self.name)
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_requests = 0
                else:
                    raise CircuitOpenError(
                        f"Circuit breaker '{self.name}' is OPEN. Service unavailable."
                    )
            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_requests >= self.config.half_open_max_requests:
                    raise CircuitOpenError(
                        f"Circuit breaker '{self.name}' is OPEN. Service unavailable."
                    )
                self.half_open_requests += 1

        try:
            result = func(*args, **kwargs)
        except Exception:
            self._on_failure()
            raise
        self._on_success()
        return result

    def _on_success(self) -> None:
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                logger.info("Circuit '%s' moving to CLOSED (recovered)", self.name)
            self.state = CircuitState.CLOSED
            self.failure_count = 0

    def _on_failure(self) -> None:
        with self._lock:
            self.last_failure_time = time.time()
            if self.state == CircuitState.HALF_OPEN:
                logger.warning("Circuit '%s' back to OPEN (trial call failed)", self.name)
                self.state = CircuitState.OPEN
                self.failure_count = self.config.failure_threshold
            elif self.state == CircuitState.CLOSED:
                self.failure_count += 1
                if self.failure_count >= self.config.failure_threshold:
                    logger.warning(
                        "Circuit '%s' moving to OPEN after %d failures",
                        self.name,
                        self.failure_count,
                    )
                    self.state = CircuitState.OPEN

    def get_state(self) -> dict:
        """Current state for monitoring."""
        recovery_in = 0.0
        if self.state == CircuitState.OPEN:
            elapsed = time.time() - self.last_failure_time
            recovery_in = max(0.0, self.config.recovery_timeout - elapsed)
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "recovery_in": recovery_in,
        }
