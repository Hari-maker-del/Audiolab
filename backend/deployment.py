"""Small, dependency-free safeguards for Audiolab deployments."""
from collections import deque
import hmac
import ipaddress
import threading
import time


PUBLIC_HEALTH_PATHS = frozenset({"/health", "/healthz"})


def is_loopback_client(host: str | None) -> bool:
    """Only treat an actual loopback address as local; never trust proxy headers."""
    if not host:
        return False
    if host.strip().lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip()).is_loopback
    except ValueError:
        return False


def authorize_request(
    *,
    path: str,
    method: str,
    client_host: str | None,
    configured_api_key: str,
    supplied_api_key: str = "",
) -> tuple[bool, str | None]:
    """Allow health probes, loopback-only access by default, or constant-time API-key auth."""
    if method.upper() == "OPTIONS":
        return True, None
    if method.upper() == "GET" and path in PUBLIC_HEALTH_PATHS:
        return True, None
    if configured_api_key:
        if hmac.compare_digest(supplied_api_key.encode("utf-8"), configured_api_key.encode("utf-8")):
            return True, None
        return False, "Missing or invalid Audiolab API key."
    if is_loopback_client(client_host):
        return True, None
    return False, "Remote API access is disabled. Configure AUDIOLAB_API_KEY and use a trusted server-side client."


class SlidingWindowRateLimiter:
    """Thread-safe, bounded-memory rate limiter using a sliding time window."""

    def __init__(self, max_clients: int = 4096):
        self.max_clients = max(32, int(max_clients))
        self._events: dict[tuple[str, str], deque[float]] = {}
        self._last_seen: dict[tuple[str, str], float] = {}
        self._lock = threading.Lock()

    def allow(
        self,
        client_key: str,
        bucket: str,
        *,
        limit: int,
        window_seconds: float = 60.0,
        now: float | None = None,
    ) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        current = time.monotonic() if now is None else float(now)
        limit = max(1, int(limit))
        window = max(1.0, float(window_seconds))
        key = (str(client_key or "unknown"), str(bucket))
        with self._lock:
            events = self._events.setdefault(key, deque())
            while events and events[0] <= current - window:
                events.popleft()
            self._last_seen[key] = current
            if len(events) >= limit:
                retry = max(1, int(events[0] + window - current + 0.999))
                return False, retry
            events.append(current)
            if len(self._events) > self.max_clients:
                oldest = min(self._last_seen, key=self._last_seen.get)
                self._events.pop(oldest, None)
                self._last_seen.pop(oldest, None)
            return True, 0
