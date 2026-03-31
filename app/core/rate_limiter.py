"""
Rate limiting with Redis + in-memory fallback.
This is the PRODUCTION-GRADE version.
"""
import time
import logging
from typing import Dict, Optional, Tuple
import redis
from app.config import settings

logger = logging.getLogger(__name__)

class RateLimiter:
    """
    Production rate limiter: Redis first, memory fallback.
    """
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client
        self.memory_store: Dict[str, list] = {}
        self.redis_available = False
        
        if redis_client:
            try:
                redis_client.ping()
                self.redis_available = True
                logger.info("✅ Redis connected - using production rate limiting")
            except Exception as e:
                logger.warning(f"Redis unavailable: {e}. Using in-memory fallback.")
                self.redis_available = False
    
    def _memory_check(self, key: str, limit: int, window: int) -> Tuple[bool, int]:
        """Fallback: in-memory rate limiting."""
        now = time.time()
        if key in self.memory_store:
            self.memory_store[key] = [t for t in self.memory_store[key] if now - t < window]
            count = len(self.memory_store[key])
            if count >= limit:
                return False, 0
            self.memory_store[key].append(now)
            return True, limit - (count + 1)
        else:
            self.memory_store[key] = [now]
            return True, limit - 1
    
    def _redis_check(self, key: str, limit: int, window: int) -> Tuple[bool, int]:
        """Primary: Redis rate limiting."""
        try:
            current = self.redis.get(key)
            current = int(current) if current else 0
            
            if current >= limit:
                return False, 0
            
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, window)
            pipe.execute()
            
            remaining = limit - (current + 1)
            return True, max(remaining, 0)
            
        except Exception as e:
            logger.error(f"Redis error: {e}. Falling back to memory.")
            self.redis_available = False
            return self._memory_check(key, limit, window)
    
    def check_rate_limit(self, key: str, limit: int, window: int) -> Tuple[bool, int]:
        """Check rate limit with Redis + memory fallback."""
        if self.redis_available and self.redis:
            return self._redis_check(key, limit, window)
        else:
            return self._memory_check(key, limit, window)
