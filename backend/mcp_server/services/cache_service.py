"""
Caching Service for MCP Server

Provides LRU caching with TTL support for frequently accessed data.
Optimizes performance by reducing database and Elasticsearch queries.
"""

from cachetools import TTLCache
from typing import Any, Optional, Callable
from datetime import datetime
import hashlib
import json
import logging
from functools import wraps

from mcp_server.config import config

logger = logging.getLogger(__name__)


class CacheService:
    """
    Thread-safe caching service with TTL support.

    Uses LRU eviction when cache is full and automatic expiration
    based on configured TTL values.
    """

    def __init__(self):
        """Initialize cache with configured max size"""
        self.enabled = config.CACHE_ENABLED

        if self.enabled:
            # Main cache with default TTL
            self._cache = TTLCache(
                maxsize=config.CACHE_MAX_SIZE,
                ttl=config.CACHE_DEFAULT_TTL
            )

            # Separate caches with different TTLs
            self._templates_cache = TTLCache(
                maxsize=100,
                ttl=config.CACHE_TEMPLATES_TTL
            )

            self._stats_cache = TTLCache(
                maxsize=50,
                ttl=config.CACHE_STATS_TTL
            )

            self._documents_cache = TTLCache(
                maxsize=500,
                ttl=config.CACHE_DOCUMENTS_TTL
            )

            logger.info(f"Cache service initialized (max_size={config.CACHE_MAX_SIZE})")
        else:
            logger.info("Cache service disabled")

    def _get_cache_for_category(self, category: str) -> TTLCache:
        """Get the appropriate cache based on category"""
        cache_map = {
            "templates": self._templates_cache,
            "stats": self._stats_cache,
            "documents": self._documents_cache,
        }
        return cache_map.get(category, self._cache)

    def get(self, key: str, category: str = "default") -> Optional[Any]:
        """
        Get value from cache

        Args:
            key: Cache key
            category: Cache category (templates, stats, documents, default)

        Returns:
            Cached value or None if not found/expired
        """
        if not self.enabled:
            return None

        cache = self._get_cache_for_category(category)
        value = cache.get(key)

        if value is not None:
            logger.debug(f"Cache HIT: {category}/{key}")
        else:
            logger.debug(f"Cache MISS: {category}/{key}")

        return value

    def set(self, key: str, value: Any, category: str = "default") -> None:
        """
        Set value in cache

        Args:
            key: Cache key
            value: Value to cache
            category: Cache category
        """
        if not self.enabled:
            return

        cache = self._get_cache_for_category(category)
        cache[key] = value
        logger.debug(f"Cache SET: {category}/{key}")

    def delete(self, key: str, category: str = "default") -> None:
        """Delete value from cache"""
        if not self.enabled:
            return

        cache = self._get_cache_for_category(category)
        if key in cache:
            del cache[key]
            logger.debug(f"Cache DELETE: {category}/{key}")

    def clear(self, category: Optional[str] = None) -> None:
        """
        Clear cache

        Args:
            category: Specific category to clear, or None to clear all
        """
        if not self.enabled:
            return

        if category:
            cache = self._get_cache_for_category(category)
            cache.clear()
            logger.info(f"Cache cleared: {category}")
        else:
            self._cache.clear()
            self._templates_cache.clear()
            self._stats_cache.clear()
            self._documents_cache.clear()
            logger.info("All caches cleared")

    def get_stats(self) -> dict:
        """Get cache statistics"""
        if not self.enabled:
            return {"enabled": False}

        return {
            "enabled": True,
            "default": {
                "size": len(self._cache),
                "maxsize": self._cache.maxsize,
                "ttl": self._cache.ttl
            },
            "templates": {
                "size": len(self._templates_cache),
                "maxsize": self._templates_cache.maxsize,
                "ttl": self._templates_cache.ttl
            },
            "stats": {
                "size": len(self._stats_cache),
                "maxsize": self._stats_cache.maxsize,
                "ttl": self._stats_cache.ttl
            },
            "documents": {
                "size": len(self._documents_cache),
                "maxsize": self._documents_cache.maxsize,
                "ttl": self._documents_cache.ttl
            }
        }

    @staticmethod
    def make_key(*args, **kwargs) -> str:
        """
        Generate cache key from arguments

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Hash-based cache key
        """
        # Create deterministic string from args
        key_parts = [str(arg) for arg in args]
        key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
        key_string = "|".join(key_parts)

        # Hash for consistent length
        return hashlib.md5(key_string.encode()).hexdigest()


# Global cache instance
cache_service = CacheService()


def cached(category: str = "default", key_prefix: str = ""):
    """
    Decorator for caching function results

    Args:
        category: Cache category
        key_prefix: Prefix for cache key

    Example:
        @cached(category="templates", key_prefix="template_list")
        async def get_all_templates():
            # Expensive operation
            return templates
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = CacheService.make_key(key_prefix, func.__name__, *args, **kwargs)

            # Try cache first
            cached_value = cache_service.get(cache_key, category)
            if cached_value is not None:
                return cached_value

            # Execute function
            result = await func(*args, **kwargs)

            # Cache result
            cache_service.set(cache_key, result, category)

            return result

        return wrapper
    return decorator
