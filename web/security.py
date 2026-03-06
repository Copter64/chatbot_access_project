"""Web security utilities: per-IP rate limiting and brute-force detection.

Provides a thread-safe SecurityManager that:
- Enforces a sliding-window request rate limit per IP address.
- Tracks cumulative 4xx error counts per IP and fires an alert callback
  once the brute-force threshold is reached.

The alert callback is invoked outside the internal lock to avoid deadlocks,
and is guarded so it fires at most once per IP lifetime.
"""

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class _IpState:
    """Per-IP tracking state, protected by SecurityManager._lock."""

    request_count: int = 0
    window_start: float = field(default_factory=time.monotonic)
    error_count: int = 0
    alerted: bool = False


class SecurityManager:
    """Thread-safe per-IP rate limiter and brute-force detector.

    Maintains a sliding-window request counter per IP address.
    Error counts (4xx responses) are tracked cumulatively across windows
    and trigger a one-shot alert callback when the configured threshold
    is exceeded.

    Args:
        rate_limit_requests: Max requests allowed per IP per window.
        rate_limit_window_seconds: Window duration in seconds.
        brute_force_threshold: Number of 4xx errors that triggers an alert.
        alert_callback: Optional callable(ip: str, detail: str) invoked once
            per IP when the brute-force threshold is breached.
    """

    def __init__(
        self,
        rate_limit_requests: int,
        rate_limit_window_seconds: int,
        brute_force_threshold: int,
        alert_callback: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        """Initialize the security manager."""
        self._rate_limit = rate_limit_requests
        self._window = rate_limit_window_seconds
        self._bf_threshold = brute_force_threshold
        self._alert_callback = alert_callback
        self._states: dict[str, _IpState] = defaultdict(_IpState)
        self._lock = threading.Lock()

    def _get_state(self, ip: str) -> _IpState:
        """Return the state for an IP, resetting the window if expired.

        Must be called while holding ``self._lock``.
        Request counts reset each window; error counts never reset.
        """
        state = self._states[ip]
        now = time.monotonic()
        if now - state.window_start > self._window:
            state.request_count = 0
            state.window_start = now
        return state

    def is_rate_limited(self, ip: str) -> bool:
        """Increment request count and return True if the IP exceeds limit.

        Args:
            ip: Client IP address string.

        Returns:
            bool: True if the request should be rejected with HTTP 429.
        """
        with self._lock:
            state = self._get_state(ip)
            state.request_count += 1
            if state.request_count > self._rate_limit:
                logger.warning(
                    f"Rate limit exceeded for IP {ip}: "
                    f"{state.request_count} requests in "
                    f"{self._window}s window"
                )
                return True
            return False

    def record_error(self, ip: str) -> None:
        """Record a 4xx error for an IP; fire alert callback if threshold hit.

        Error counts persist across rate-limit windows. The callback is
        invoked at most once per IP (guarded by the ``alerted`` flag).
        The callback is called outside the lock to avoid deadlocks.

        Args:
            ip: Client IP address string.
        """
        should_alert = False
        detail = ""

        with self._lock:
            state = self._get_state(ip)
            state.error_count += 1
            if state.error_count >= self._bf_threshold and not state.alerted:
                state.alerted = True
                should_alert = True
                detail = (
                    f"{state.error_count} invalid or expired token attempts"
                )
                logger.warning(
                    f"Brute-force threshold reached for IP {ip}: {detail}"
                )

        if should_alert and self._alert_callback:
            try:
                self._alert_callback(ip, detail)
            except Exception as exc:
                logger.error(
                    f"Alert callback failed for IP {ip}: {exc}",
                    exc_info=True,
                )

    def get_stats(self, ip: str) -> dict:
        """Return current tracking stats for an IP (primarily for tests).

        Args:
            ip: Client IP address string.

        Returns:
            dict with keys: ``request_count``, ``error_count``, ``alerted``.
        """
        with self._lock:
            state = self._states.get(ip)
            if state is None:
                return {
                    "request_count": 0,
                    "error_count": 0,
                    "alerted": False,
                }
            return {
                "request_count": state.request_count,
                "error_count": state.error_count,
                "alerted": state.alerted,
            }
