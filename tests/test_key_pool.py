from __future__ import annotations

import asyncio
import pytest
from app.services.key_pool import OpenAIKeyPool


@pytest.mark.asyncio
async def test_openai_key_pool_initialization_and_filtering():
    keys = ["sk-proj-key1", "sk-proj-key2", "  ", "<YOUR_KEY>", "your_mock_key", "sk-proj-key1"]
    pool = OpenAIKeyPool(keys, max_req_per_min_per_key=30)
    assert pool.keys == ["sk-proj-key1", "sk-proj-key2"]
    assert pool.has_valid_keys() is True


@pytest.mark.asyncio
async def test_openai_key_pool_rotation_and_rate_limiting():
    keys = ["sk-keyA", "sk-keyB"]
    pool = OpenAIKeyPool(keys, max_req_per_min_per_key=30)

    acquired = []
    for _ in range(6):
        k = await pool.acquire_key()
        acquired.append(k)

    assert acquired.count("sk-keyA") == 3
    assert acquired.count("sk-keyB") == 3


@pytest.mark.asyncio
async def test_openai_key_pool_rate_limit_failover():
    keys = ["sk-key1", "sk-key2"]
    pool = OpenAIKeyPool(keys, max_req_per_min_per_key=30)

    # Mark key1 as rate limited (429 error)
    await pool.mark_key_rate_limited("sk-key1", cooldown_seconds=10.0)

    # Next acquires must use key2
    k1 = await pool.acquire_key()
    k2 = await pool.acquire_key()
    assert k1 == "sk-key2"
    assert k2 == "sk-key2"
