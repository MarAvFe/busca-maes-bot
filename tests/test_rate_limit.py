"""Token bucket rate limiter."""

from buscamaes.security.rate_limit import _reset_for_tests, check_and_consume


def setup_function():
    _reset_for_tests()


def test_first_request_passes():
    assert check_and_consume(user_id=1, rate_max=3, window_seconds=60) is True


def test_consecutive_requests_consume_bucket():
    for _ in range(3):
        assert check_and_consume(user_id=1, rate_max=3, window_seconds=60) is True
    # Bucket exhausted
    assert check_and_consume(user_id=1, rate_max=3, window_seconds=60) is False


def test_separate_users_have_separate_buckets():
    for _ in range(3):
        check_and_consume(user_id=1, rate_max=3, window_seconds=60)
    # User 1 exhausted, user 2 fresh
    assert check_and_consume(user_id=1, rate_max=3, window_seconds=60) is False
    assert check_and_consume(user_id=2, rate_max=3, window_seconds=60) is True


def test_bucket_refills_over_time(monkeypatch):
    """Simulate clock advance via monkeypatch on time.monotonic."""
    fake_now = [1000.0]

    def fake_monotonic():
        return fake_now[0]

    monkeypatch.setattr("buscamaes.security.rate_limit.time.monotonic", fake_monotonic)

    # rate_max=2, window=10s → refill = 0.2 tokens/s
    assert check_and_consume(user_id=1, rate_max=2, window_seconds=10) is True
    assert check_and_consume(user_id=1, rate_max=2, window_seconds=10) is True
    assert check_and_consume(user_id=1, rate_max=2, window_seconds=10) is False

    # Advance 5 seconds → 1 token refilled
    fake_now[0] += 5
    assert check_and_consume(user_id=1, rate_max=2, window_seconds=10) is True
    assert check_and_consume(user_id=1, rate_max=2, window_seconds=10) is False
