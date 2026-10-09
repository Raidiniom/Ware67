import math
import threading
import time


class FixedWindowLimiter:
    """Counts hits per key in fixed time windows, in this process's memory.

    Each uvicorn worker keeps its own counts, so with N workers the effective
    limit is up to N times higher. Good enough to stop a runaway partner script;
    a shared store (e.g. Redis) would be needed for an exact global limit.
    """

    def __init__(self, limit: int, window_seconds: int = 60):
        self.limit = limit
        self.window = window_seconds
        self._window = -1
        self._counts: dict[str, int] = {}
        self._lock = threading.Lock()

    def hit(self, key: str) -> int | None:
        """Records a hit. Returns None if allowed, else seconds until the window resets."""
        now = time.time()
        current = int(now // self.window)
        with self._lock:
            if current != self._window:
                # New window: forget every old count, so memory stays bounded.
                self._window = current
                self._counts = {}
            count = self._counts.get(key, 0)
            if count >= self.limit:
                return max(1, math.ceil((current + 1) * self.window - now))
            self._counts[key] = count + 1
            return None

    def reset(self) -> None:
        with self._lock:
            self._window = -1
            self._counts = {}
