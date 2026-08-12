"""A per-IP token bucket for /agent/chat.

Every chat turn spends money on someone else's API key, and the endpoint is
unauthenticated. This stops the trivial abuse case.

**It is not a real rate limiter.** State is per process, so N workers means N
buckets, and it keys on an IP that a client can rotate. The durable version
belongs at the edge (Cloudflare, nginx) or in Redis. This exists so that a
single misbehaving client — or a runaway retry loop in the browser — can't
quietly drain the account before anyone notices.
"""

import os
import threading
from collections import OrderedDict
from time import monotonic

from fastapi import HTTPException, Request

# Roughly one turn every 12s sustained, with a burst of 5 for normal back-and-forth.
DEFAULT_CAPACITY = 5.0
DEFAULT_REFILL_PER_SECOND = 1 / 12
# Bound the table so a flood of unique IPs can't grow it without limit.
MAX_TRACKED_CLIENTS = 4_096


class TokenBucket:
    def __init__(
        self,
        capacity: float = DEFAULT_CAPACITY,
        refill_per_second: float = DEFAULT_REFILL_PER_SECOND,
        max_clients: int = MAX_TRACKED_CLIENTS,
    ) -> None:
        self.capacity = capacity
        self.refill_per_second = refill_per_second
        self.max_clients = max_clients
        self._buckets: OrderedDict[str, tuple[float, float]] = OrderedDict()
        self._lock = threading.Lock()

    def take(self, key: str, now: float | None = None) -> float | None:
        """Spend one token. Returns None if allowed, else seconds to wait."""
        now = monotonic() if now is None else now

        with self._lock:
            tokens, last_seen = self._buckets.get(key, (self.capacity, now))
            tokens = min(self.capacity, tokens + (now - last_seen) * self.refill_per_second)

            if tokens < 1.0:
                self._buckets[key] = (tokens, now)
                self._buckets.move_to_end(key)
                return (1.0 - tokens) / self.refill_per_second

            self._buckets[key] = (tokens - 1.0, now)
            self._buckets.move_to_end(key)
            while len(self._buckets) > self.max_clients:
                self._buckets.popitem(last=False)
            return None


_bucket = TokenBucket()


def _client_key(request: Request) -> str:
    # Only trust a forwarded header when something in front is known to set it;
    # otherwise a client sets its own key and the limit is decorative.
    if os.environ.get("TRUST_PROXY_HEADERS") == "1":
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request) -> None:
    if os.environ.get("DISABLE_RATE_LIMIT") == "1":
        return

    retry_after = _bucket.take(_client_key(request))
    if retry_after is None:
        return

    raise HTTPException(
        status_code=429,
        detail="Too many requests. Give it a moment and try again.",
        headers={"Retry-After": str(max(1, int(retry_after)))},
    )
