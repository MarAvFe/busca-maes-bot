"""In-memory token bucket + daily counter per user.

Token bucket: request rate limiting (per-window).
Daily counter: abuse detection (resets UTC midnight).

Bucket state wiped on restart (acceptable). Counter persistent would need DB;
in-memory reset acceptable since denial persists in denied_users table.
"""

import time
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class _Bucket:
    tokens: float
    last_refill: float


_buckets: dict[int, _Bucket] = {}
_daily_counter: dict[int, tuple[str, int]] = {}  # {user_id: (date_utc, count)}


def check_and_consume(user_id: int, rate_max: int, window_seconds: int) -> bool:
    """True if allowed, False if rate-limited. Consumes token."""
    now = time.monotonic()
    refill_rate = rate_max / window_seconds
    bucket = _buckets.get(user_id)
    if bucket is None:
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


def increment_daily(user_id: int) -> int:
    """Increment daily counter (resets at UTC midnight). Return new count."""
    today = datetime.now(UTC).date().isoformat()
    stored_date, count = _daily_counter.get(user_id, ("", 0))
    if stored_date != today:
        count = 0
    count += 1
    _daily_counter[user_id] = (today, count)
    return count


def _reset_for_tests() -> None:
    """Test helper: wipe buckets + counters."""
    _buckets.clear()
    _daily_counter.clear()
