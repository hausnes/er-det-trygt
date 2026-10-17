from app.ratelimit import RateLimiter


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_allows_up_to_limit_then_blocks():
    clock = FakeClock()
    limiter = RateLimiter([(3, 60)], clock=clock)
    assert [limiter.check("a") for _ in range(3)] == [None, None, None]
    assert limiter.check("a") == 60


def test_clients_are_limited_separately():
    limiter = RateLimiter([(1, 60)], clock=FakeClock())
    assert limiter.check("a") is None
    assert limiter.check("b") is None
    assert limiter.check("a") is not None


def test_allowed_again_when_window_has_passed():
    clock = FakeClock()
    limiter = RateLimiter([(2, 60)], clock=clock)
    limiter.check("a")
    clock.now += 30
    limiter.check("a")
    clock.now += 10
    assert limiter.check("a") == 20  # den første går ut 60 s etter at han kom
    clock.now += 20
    assert limiter.check("a") is None


def test_longest_limit_applies():
    clock = FakeClock()
    limiter = RateLimiter([(10, 60), (3, 3600)], clock=clock)
    for _ in range(3):
        assert limiter.check("a") is None
        clock.now += 61
    assert limiter.check("a") == 3600 - 3 * 61


def test_blocked_requests_do_not_count():
    clock = FakeClock()
    limiter = RateLimiter([(1, 60)], clock=clock)
    limiter.check("a")
    for _ in range(5):
        limiter.check("a")
    clock.now += 60
    assert limiter.check("a") is None


def test_inactive_clients_are_cleaned_up():
    clock = FakeClock()
    limiter = RateLimiter([(5, 60)], clock=clock)
    limiter.check("a")
    clock.now += 120
    limiter.check("b")
    assert list(limiter.hits) == ["b"]
