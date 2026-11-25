"""Memory-bounded sliding-window rate limiter per client IP/session (SRD §10.2)."""

import time


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int = 30, window_seconds: int = 60, max_buckets: int = 5000):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.max_buckets = max_buckets
        self._buckets: dict[str, list[float]] = {}

    def _evict_if_needed(self, cutoff: float) -> None:
        if len(self._buckets) < self.max_buckets:
            return
        stale_keys = [k for k, vals in self._buckets.items() if not vals or vals[-1] <= cutoff]
        for k in stale_keys:
            del self._buckets[k]
        while len(self._buckets) >= self.max_buckets:
            oldest_key = next(iter(self._buckets))
            del self._buckets[oldest_key]

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        entries = [ts for ts in self._buckets.get(key, []) if ts > cutoff]
        if len(entries) >= self.max_requests:
            self._buckets[key] = entries
            return False
        if key not in self._buckets:
            self._evict_if_needed(cutoff)
        entries.append(now)
        self._buckets[key] = entries
        return True

    def clear(self) -> None:
        self._buckets.clear()
