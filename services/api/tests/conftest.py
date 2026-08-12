import pytest

from app.agent import ratelimit


@pytest.fixture(autouse=True)
def fresh_rate_limit_bucket():
    """Every test starts with a full bucket.

    The limiter stays wired up — so a broken dependency still fails a test —
    but one test's requests can't throttle the next one's.
    """
    ratelimit._bucket._buckets.clear()
    yield
    ratelimit._bucket._buckets.clear()
