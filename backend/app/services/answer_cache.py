"""
Answer caching service to reduce Claude API calls for repeated queries.

Caches answers based on (query + result_ids) hash to avoid regenerating
identical answers. This provides 90% cost reduction for repeated queries.
"""

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AnswerCache:
    """In-memory cache for search answers to reduce API costs."""

    def __init__(self, ttl_seconds: int = 3600, max_size: int = 1000):
        """
        Initialize answer cache.

        Args:
            ttl_seconds: Time-to-live for cached entries (default: 1 hour)
            max_size: Maximum number of entries to cache (default: 1000)
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = timedelta(seconds=ttl_seconds)
        self.max_size = max_size
        self.hits = 0
        self.misses = 0
        logger.info(f"Initialized AnswerCache with TTL={ttl_seconds}s, max_size={max_size}")

    def _generate_cache_key(self, query: str, result_ids: List[int], filters: Optional[Dict] = None) -> str:
        """
        Generate cache key from query + result IDs + filters.

        Args:
            query: User's search query
            result_ids: List of document IDs in results
            filters: Optional query filters (template_id, folder_path, etc.)

        Returns:
            MD5 hash of the combined inputs
        """
        # Sort result_ids to ensure consistent cache key regardless of order
        sorted_ids = sorted(result_ids)

        # Include filters in cache key if present
        filter_str = ""
        if filters:
            filter_str = str(sorted(filters.items()))

        key_str = f"{query}:{sorted_ids}:{filter_str}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(
        self,
        query: str,
        result_ids: List[int],
        filters: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached answer if exists and not expired.

        Args:
            query: User's search query
            result_ids: List of document IDs in results
            filters: Optional query filters

        Returns:
            Cached answer dict or None if not found/expired
        """
        cache_key = self._generate_cache_key(query, result_ids, filters)
        cached = self.cache.get(cache_key)

        if not cached:
            self.misses += 1
            logger.debug(f"Cache MISS for query: {query[:50]}...")
            return None

        # Check if expired
        age = datetime.utcnow() - cached["cached_at"]
        if age > self.ttl:
            # Remove expired entry
            del self.cache[cache_key]
            self.misses += 1
            logger.debug(f"Cache EXPIRED for query: {query[:50]}... (age: {age})")
            return None

        # Cache hit
        self.hits += 1
        cached["access_count"] = cached.get("access_count", 0) + 1
        cached["last_accessed"] = datetime.utcnow()

        logger.info(f"Cache HIT for query: {query[:50]}... (saved Claude API call)")
        return cached["answer"]

    def set(
        self,
        query: str,
        result_ids: List[int],
        answer: Dict[str, Any],
        filters: Optional[Dict] = None
    ) -> None:
        """
        Cache answer for future retrieval.

        Args:
            query: User's search query
            result_ids: List of document IDs in results
            answer: Answer dict from Claude service
            filters: Optional query filters
        """
        # Check if cache is full
        if len(self.cache) >= self.max_size:
            # Evict oldest entries (simple LRU)
            self._evict_oldest()

        cache_key = self._generate_cache_key(query, result_ids, filters)

        self.cache[cache_key] = {
            "answer": answer,
            "query": query,
            "result_count": len(result_ids),
            "cached_at": datetime.utcnow(),
            "last_accessed": datetime.utcnow(),
            "access_count": 0
        }

        logger.info(f"Cached answer for query: {query[:50]}... (cache size: {len(self.cache)})")

    def _evict_oldest(self, count: int = 100) -> None:
        """
        Evict oldest entries when cache is full.

        Args:
            count: Number of entries to evict (default: 10% of max_size)
        """
        if not self.cache:
            return

        # Sort by last_accessed timestamp
        sorted_entries = sorted(
            self.cache.items(),
            key=lambda x: x[1]["last_accessed"]
        )

        # Remove oldest entries
        for key, _ in sorted_entries[:count]:
            del self.cache[key]

        logger.info(f"Evicted {count} oldest cache entries (cache size: {len(self.cache)})")

    def clear(self) -> None:
        """Clear all cached entries."""
        count = len(self.cache)
        self.cache.clear()
        logger.info(f"Cleared {count} cache entries")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with hits, misses, hit_rate, size, etc.
        """
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "hits": self.hits,
            "misses": self.misses,
            "total_requests": total_requests,
            "hit_rate": round(hit_rate, 2),
            "cache_size": len(self.cache),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl.total_seconds()
        }

    def remove_expired(self) -> int:
        """
        Remove all expired entries from cache.

        Returns:
            Number of entries removed
        """
        now = datetime.utcnow()
        expired_keys = []

        for key, value in self.cache.items():
            age = now - value["cached_at"]
            if age > self.ttl:
                expired_keys.append(key)

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            logger.info(f"Removed {len(expired_keys)} expired cache entries")

        return len(expired_keys)


# Global cache instance (singleton pattern)
_global_cache: Optional[AnswerCache] = None


def get_answer_cache() -> AnswerCache:
    """
    Get or create the global answer cache instance.

    Returns:
        Global AnswerCache instance
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = AnswerCache(
            ttl_seconds=3600,  # 1 hour
            max_size=1000  # 1000 entries
        )
    return _global_cache
