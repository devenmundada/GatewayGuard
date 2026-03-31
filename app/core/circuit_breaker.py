"""
Circuit breaker pattern for downstream service failures.
"""
import time
import logging
from enum import Enum
from typing import Callable, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, blocking requests
    HALF_OPEN = "half_open" # Testing if service recovered

@dataclass
class CircuitConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5      # Failures before opening
    recovery_timeout: int = 30       # Seconds to stay open
    half_open_max_requests: int = 1  # Requests to test in half-open

class CircuitBreaker:
    """
    Circuit breaker that prevents cascading failures.
    
    States:
    - CLOSED: Requests flow normally, count failures
    - OPEN: Requests blocked, waiting for recovery timeout
    - HALF-OPEN: Testing if service recovered
    """
    
    def __init__(self, name: str, config: Optional[CircuitConfig] = None):
        self.name = name
        self.config = config or CircuitConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.half_open_requests = 0
        logger.info(f"Circuit breaker '{name}' initialized in CLOSED state")
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Returns:
            Function result if successful
            
        Raises:
            Exception from function or circuit breaker open
        """
        # Check if circuit is open
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if time.time() - self.last_failure_time >= self.config.recovery_timeout:
                logger.info(f"Circuit '{self.name}' moving to HALF-OPEN after timeout")
                self.state = CircuitState.HALF_OPEN
                self.half_open_requests = 0
            else:
                # Still open
                logger.warning(f"Circuit '{self.name}' is OPEN - request blocked")
                raise Exception(f"Circuit breaker '{self.name}' is OPEN. Service unavailable.")
        
        # Execute function
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _on_success(self):
        """Handle successful request."""
        if self.state == CircuitState.HALF_OPEN:
            logger.info(f"Circuit '{self.name}' moving to CLOSED (recovered)")
            self.state = CircuitState.CLOSED
            self.failure_count = 0
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0
        logger.debug(f"Circuit '{self.name}' success - state: {self.state.value}, failures: {self.failure_count}")
    
    def _on_failure(self):
        """Handle failed request."""
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.CLOSED:
            self.failure_count += 1
            if self.failure_count >= self.config.failure_threshold:
                logger.warning(f"Circuit '{self.name}' moving to OPEN after {self.failure_count} failures")
                self.state = CircuitState.OPEN
                
        elif self.state == CircuitState.HALF_OPEN:
            logger.warning(f"Circuit '{self.name}' moving back to OPEN (test request failed)")
            self.state = CircuitState.OPEN
            self.failure_count = self.config.failure_threshold
    
    def get_state(self) -> dict:
        """Get current circuit state for monitoring."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "recovery_in": max(0, self.config.recovery_timeout - (time.time() - self.last_failure_time)) if self.state == CircuitState.OPEN else 0
        }
