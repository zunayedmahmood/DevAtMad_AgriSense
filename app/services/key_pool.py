from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Callable, List, Optional

logger = logging.getLogger("agrisense.key_pool")


class OpenAIKeyPool:
    """Robust multi-key pool manager for OpenAI API calls.
    
    Features:
    - Rotates across 2 (or more) OpenAI API keys.
    - Tracks per-key request rate limits.
    - Automatically skips invalid/mock keys.
    - Handles rate-limit errors (429 / RateLimitError) with instant key failover.
    """

    def __init__(self, keys: List[str], max_req_per_min_per_key: int = 1700):
        clean_keys = []
        for k in keys:
            if k and isinstance(k, str):
                s = k.strip()
                if s and not s.startswith("<") and "your_" not in s.lower():
                    if s not in clean_keys:
                        clean_keys.append(s)
        
        self.keys: List[str] = clean_keys
        self.max_req_per_min: int = max_req_per_min_per_key
        # Timestamps of requests made in the last 60 seconds per key
        self.request_timestamps: dict[str, List[float]] = {k: [] for k in self.keys}
        # Cooldown expiration timestamps for keys that hit 429 errors
        self.cooldowns: dict[str, float] = {k: 0.0 for k in self.keys}
        self.lock = asyncio.Lock()

    @classmethod
    def from_settings_and_env(cls, settings: Any) -> OpenAIKeyPool:
        collected: List[str] = []
        
        # 1. Check comma-separated OPENAI_API_KEYS
        keys_env = getattr(settings, "openai_api_keys", None) or os.environ.get("OPENAI_API_KEYS")
        if keys_env and isinstance(keys_env, str):
            collected.extend([k.strip() for k in keys_env.split(",") if k.strip()])
            
        # 2. Check individual settings fields & env vars
        single_fields = [
            getattr(settings, "openai_api_key", None),
            getattr(settings, "openai_api_key_2", None),
            os.environ.get("OPENAI_API_KEY"),
            os.environ.get("OPENAI_API_KEY_2"),
        ]
        for val in single_fields:
            if val and isinstance(val, str) and val.strip():
                collected.append(val.strip())

        return cls(keys=collected, max_req_per_min_per_key=1700)

    def has_valid_keys(self) -> bool:
        return len(self.keys) > 0

    def _purge_old_timestamps(self, key: str, now: float) -> None:
        window_start = now - 60.0
        self.request_timestamps[key] = [ts for ts in self.request_timestamps[key] if ts > window_start]

    async def acquire_key(self) -> str:
        """Acquires the best available OpenAI API key obeying rate limits."""
        if not self.keys:
            raise RuntimeError("No valid OpenAI API keys configured in key pool.")

        while True:
            async with self.lock:
                now = time.time()
                eligible_keys: List[tuple[str, int]] = []

                for k in self.keys:
                    # Check if key is cooling down from error
                    if self.cooldowns[k] > now:
                        continue
                    
                    self._purge_old_timestamps(k, now)
                    usage = len(self.request_timestamps[k])
                    if usage < self.max_req_per_min:
                        eligible_keys.append((k, usage))

                if eligible_keys:
                    # Pick key with minimum usage to balance load evenly
                    eligible_keys.sort(key=lambda x: x[1])
                    selected_key = eligible_keys[0][0]
                    self.request_timestamps[selected_key].append(now)
                    logger.debug("OpenAI key pool selected key ...%s (Usage: %d in last 60s)", 
                                 selected_key[-6:], len(self.request_timestamps[selected_key]))
                    return selected_key

                # All keys are currently at limit or cooling down. Wait briefly.
                min_wait = 1.0
                for k in self.keys:
                    self._purge_old_timestamps(k, now)
                    if self.request_timestamps[k]:
                        oldest = self.request_timestamps[k][0]
                        wait = max(0.1, (oldest + 60.01) - now)
                        min_wait = min(min_wait, wait)

            logger.info("All OpenAI API keys reached rate limit. Waiting %.2fs...", min_wait)
            await asyncio.sleep(min_wait)

    async def mark_key_rate_limited(self, key: str, cooldown_seconds: float = 15.0) -> None:
        """Puts a key into temporary cooldown if it returns a 429 rate limit error."""
        async with self.lock:
            now = time.time()
            self.cooldowns[key] = now + cooldown_seconds
            logger.warning("OpenAI API key ...%s marked rate limited; cooling down for %.1fs", 
                           key[-6:], cooldown_seconds)

    async def execute_with_retry(self, fn: Callable[[str], Any], max_attempts: int = 3) -> Any:
        """Executes an OpenAI call with dynamic key rotation and automatic retry on rate limits."""
        last_exception = None
        for attempt in range(max_attempts):
            if not self.has_valid_keys():
                break
            key = await self.acquire_key()
            try:
                return await fn(key)
            except Exception as exc:
                exc_str = str(exc).lower()
                is_rate_limit = "429" in exc_str or "rate_limit" in exc_str or "quota" in exc_str
                if is_rate_limit:
                    await self.mark_key_rate_limited(key, cooldown_seconds=15.0)
                    last_exception = exc
                    logger.warning("Attempt %d hit OpenAI rate limit on key ...%s. Rotating key...", attempt + 1, key[-6:])
                    continue
                else:
                    raise exc

        if last_exception:
            raise last_exception
        raise RuntimeError("Failed to execute OpenAI API call across key pool.")
