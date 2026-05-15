import time
from collections import defaultdict, deque


class SlidingWindowRateLimiter:
    def __init__(self):
        self._bucket: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        now = time.time()
        q = self._bucket[key]
        while q and now - q[0] > window_seconds:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True
