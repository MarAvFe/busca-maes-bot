# RNP Circuit Breaker & Throttle

## Background

RNP enforces a **10 free queries per 2 minutes** cap per IP address (per their ToS). In production (2026-05-04), the droplet IP exceeded this limit during testing and was rate-blocked, preventing further queries until the block expired (24–48h).

## Design

The bot implements two complementary safeguards:

### 1. Throttle (Proactive Rate Limiting)

**Policy:** Max 8 requests per 120 seconds per process.

- Sliding window maintained in `RNPClient._request_times`.
- Every HTTP call (login + each query step) acquires a slot before executing.
- When throttle is full, subsequent calls raise `RNPUnavailable` immediately.
- Per-process in-memory state; restart resets the window.

**Why 8/120s?** Safety margin under RNP's 10/2min cap. Accounts for burst queries and login retries without risk of hitting the cap.

### 2. Circuit Breaker (Reactive Failure Handling)

**Policy:** Trip to OPEN after 3 login-block failures within 10 minutes. Cool off for 30 minutes, then HALF_OPEN (probe mode).

States:
- **CLOSED:** Normal operation, all calls pass through.
- **OPEN:** RNP is blocking; calls raise `RNPUnavailable` without attempting requests.
- **HALF_OPEN:** Cool-off expired; next call is allowed as a probe. Success → CLOSED. Failure → back to OPEN for another 30m.

Failures counted: `RuntimeError("login blocked")` only.
NOT counted: `RuntimeError("invalid credentials")` (config issue, not RNP throttling).

**Why 3 / 10min / 30min?** Three failures within a short window signals IP-level blocking (not transient). 30min is long enough for RNP's rate limiter to reset without hammering their API.

## User Facing

When the breaker is open or throttle exhausted:

```
❌ RNP no está disponible en este momento. Intentá más tarde.
```

Audit log shows `result="unavailable"` (distinct from `error`).

## Implementation

- `RNPUnavailable` exception type in `src/buscamaes/sources/rnp/client.py`.
- `_throttle_acquire()` checks window; raises if full.
- `_check_breaker()` evaluates state and transitions; returns False if OPEN.
- `_record_breaker_failure()` records login blocks; trips on threshold.
- Every HTTP call (login + query steps) calls `_throttle_acquire()`.
- `query_plate()` calls `_check_breaker()` before attempting login.
- Handlers catch `RNPUnavailable` separately from generic `Exception`; logs at DEBUG level; audit result = "unavailable".

## Testing

- `tests/test_rnp_throttle.py` — throttle limits to 8, raises on 9th.
- `tests/test_rnp_breaker.py` — breaker trips on 3 failures, transitions states, probes correctly.
- `tests/test_handle_plate.py` — handlers distinguish unavailable errors.

## Monitoring

Breaker state transitions log at INFO level with correlation_id:

```json
{
  "timestamp": "2026-05-04T...",
  "level": "INFO",
  "logger": "buscamaes.sources.rnp.client",
  "message": "Breaker: open → half_open (cooloff expired)",
  "correlation_id": "abc123def456"
}
```

Check logs for `Breaker:` lines to track breaker activity.

## Future

If RNP whitelists the droplet IP or we move to per-user credentials (M0.8), this breaker can be relaxed or removed. For now, it protects the bot from self-inflicted rate-limiting while waiting for RNP support.
