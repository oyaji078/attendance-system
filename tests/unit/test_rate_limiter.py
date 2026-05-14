from __future__ import annotations

import pytest

from app.core.rate_limiter import InMemoryRateLimiter


def test_in_memory_allows_within_limit() -> None:
    limiter = InMemoryRateLimiter(max_attempts=5, window_seconds=60)
    for _ in range(5):
        assert limiter.is_allowed("test-key") is True


def test_in_memory_rejects_excess() -> None:
    limiter = InMemoryRateLimiter(max_attempts=5, window_seconds=60)
    for _ in range(5):
        limiter.is_allowed("test-key")
    assert limiter.is_allowed("test-key") is False


def test_in_memory_separate_keys() -> None:
    limiter = InMemoryRateLimiter(max_attempts=2, window_seconds=60)
    assert limiter.is_allowed("key-a") is True
    assert limiter.is_allowed("key-a") is True
    assert limiter.is_allowed("key-a") is False
    assert limiter.is_allowed("key-b") is True


def test_in_memory_blocks_stays_blocked() -> None:
    limiter = InMemoryRateLimiter(max_attempts=2, window_seconds=60)
    assert limiter.is_allowed("test-key") is True
    assert limiter.is_allowed("test-key") is True
    assert limiter.is_allowed("test-key") is False
    assert limiter.is_allowed("test-key") is False


def test_in_memory_default_config() -> None:
    limiter = InMemoryRateLimiter(max_attempts=5, window_seconds=60)
    assert limiter.max_attempts == 5
    assert limiter.window_seconds == 60
