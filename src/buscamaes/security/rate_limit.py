"""In-memory token bucket per Telegram user.

Single-droplet deployment so in-memory state is acceptable. Restart wipes
bucket state — that's fine: a restart is an implicit "reset."

Bucket holds a float number of tokens. Every request consumes 1 token.
Tokens refill linearly at rate_max / window_seconds tokens per second,
capped at rate_max.
"""

import time
from dataclasses import dataclass


@dataclass
class _Bucket:
    tokens: float
    last_refill: float


_buckets: dict[int, _Bucket] = {}


def check_and_consume(user_id: int, rate_max: int, window_seconds: int) -> bool:
    """Return True if request is allowed (and consume a token), False if rate limited."""
    now = time.monotonic()
    refill_rate = rate_max / window_seconds  # tokens/sec
    bucket = _buckets.get(user_id)
    if bucket is None:
        # First request for this user: full bucket.
        bucket = _Bucket(tokens=float(rate_max), last_refill=now)
        _buckets[user_id] = bucket
    else:
        elapsed = now - bucket.last_refill
        bucket.tokens = min(float(rate_max), bucket.tokens + elapsed * refill_rate)
        bucket.last_refill = now

    if bucket.tokens >= 1.0:
        bucket.tokens -= 1.0
        return True
    return False


def _reset_for_tests() -> None:
    """Test helper: wipe all buckets."""
    _buckets.clear()
