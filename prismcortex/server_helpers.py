"""Shared server utilities (keeps server.py thinner)."""
from __future__ import annotations

import os
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from threading import Lock
from typing import Optional


class CountingGemini:
    """Wraps GeminiClient and counts model calls."""

    def __init__(self, model: Optional[str] = None):
        from .llm.gemini import GeminiClient

        self._g = GeminiClient(model=model)
        self.calls = 0

    @property
    def model_id(self):
        return self._g.model_id

    def extract(self, text, context):
        self.calls += 1
        return self._g.extract(text, context)

    def render(self, query, subgraph):
        self.calls += 1
        return self._g.render(query, subgraph)


class RateLimiter:
    """Token-bucket rate limit per client key (API key or IP)."""

    def __init__(self, rpm: int = 600) -> None:
        self._rpm = max(1, rpm)
        self._windows: dict[str, deque] = {}
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        window = 60.0
        with self._lock:
            q = self._windows.setdefault(key, deque())
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= self._rpm:
                return False
            q.append(now)
            return True


def rate_limiter_from_env() -> Optional[RateLimiter]:
    rpm = os.environ.get("PRISMCORTEX_RATE_LIMIT_RPM")
    if rpm is None or rpm == "0":
        return None
    return RateLimiter(rpm=int(rpm))


@lru_cache(maxsize=1)
def read_executor() -> ThreadPoolExecutor:
    """Dedicated pool for /recall and other read paths — not starved by digest work."""
    n = int(os.environ.get("PRISMCORTEX_READ_POOL", "64"))
    return ThreadPoolExecutor(max_workers=max(4, n), thread_name_prefix="pc-read")


@lru_cache(maxsize=1)
def write_executor() -> ThreadPoolExecutor:
    """Digest and other write paths; size aligned with PRISMCORTEX_MAX_CONCURRENT_DIGEST."""
    n = int(os.environ.get("PRISMCORTEX_MAX_CONCURRENT_DIGEST", "16"))
    return ThreadPoolExecutor(max_workers=max(1, n), thread_name_prefix="pc-write")
