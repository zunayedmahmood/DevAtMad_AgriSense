from __future__ import annotations

import asyncio
import pytest
from app.services.key_pool import GeminiKeyPool


@pytest.mark.asyncio
async def test_key_pool_initialization_and_filtering():
    keys = ["key1", "key2", "  ", "<YOUR_KEY>", "your_mock_key", "key3", "key1"]
    pool = GeminiKeyPool(keys, max_req_per_min_per_key=14)
    assert pool.keys == ["key1", "key2", "key3"]
    assert pool.has_valid_keys() is True


@pytest.mark.asyncio
async def test_key_pool_rotation_and_rate_limiting():
    keys = ["keyA", "keyB", "keyC"]
    pool = GeminiKeyPool(keys, max_req_per_min_per_key=14)

    # Acquire keys and check round-robin / load-balancing across pool
    acquired = []
    for _ in range(6):
        k = await pool.acquire_key()
        acquired.append(k)

    # Each key should be acquired exactly twice (usage = 2 per key)
    assert acquired.count("keyA") == 2
    assert acquired.count("keyB") == 2
    assert acquired.count("keyC") == 2


@pytest.mark.asyncio
async def test_key_pool_enforces_14_req_per_min_ceiling():
    # Test single key with max 14 req/min
    keys = ["key_single"]
    pool = GeminiKeyPool(keys, max_req_per_min_per_key=14)

    # Fill 14 request slots
    for _ in range(14):
        k = await pool.acquire_key()
        assert k == "key_single"

    assert len(pool.request_timestamps["key_single"]) == 14


@pytest.mark.asyncio
async def test_key_pool_rate_limit_failover():
    keys = ["key1", "key2"]
    pool = GeminiKeyPool(keys, max_req_per_min_per_key=14)

    # Mark key1 as rate limited (429 error)
    await pool.mark_key_rate_limited("key1", cooldown_seconds=10.0)

    # Next acquires must use key2
    k1 = await pool.acquire_key()
    k2 = await pool.acquire_key()
    assert k1 == "key2"
    assert k2 == "key2"
