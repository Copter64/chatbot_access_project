"""Tests for the web SecurityManager (rate limiting and brute-force detection)."""

import time
from unittest.mock import MagicMock

import pytest

from web.security import SecurityManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sm(
    rate_limit=100,
    window=60,
    threshold=5,
    callback=None,
):
    """Shorthand factory for a SecurityManager."""
    return SecurityManager(
        rate_limit_requests=rate_limit,
        rate_limit_window_seconds=window,
        brute_force_threshold=threshold,
        alert_callback=callback,
    )


# ---------------------------------------------------------------------------
# Rate Limiting
# ---------------------------------------------------------------------------


class TestRateLimiting:
    """Tests for the sliding-window request rate limiter."""

    def test_allows_requests_within_limit(self):
        """Requests up to the limit should not be rate-limited."""
        sm = _sm(rate_limit=5)
        for _ in range(5):
            assert sm.is_rate_limited("1.2.3.4") is False

    def test_blocks_request_over_limit(self):
        """The (N+1)th request within a window should be rate-limited."""
        sm = _sm(rate_limit=3)
        for _ in range(3):
            sm.is_rate_limited("1.2.3.4")
        assert sm.is_rate_limited("1.2.3.4") is True

    def test_returns_true_for_all_subsequent_over_limit_requests(self):
        """Every request beyond the limit should return True."""
        sm = _sm(rate_limit=2)
        sm.is_rate_limited("1.2.3.4")
        sm.is_rate_limited("1.2.3.4")
        assert sm.is_rate_limited("1.2.3.4") is True
        assert sm.is_rate_limited("1.2.3.4") is True

    def test_different_ips_are_tracked_independently(self):
        """Rate limit exhausted for one IP must not affect another."""
        sm = _sm(rate_limit=2)
        sm.is_rate_limited("1.1.1.1")
        sm.is_rate_limited("1.1.1.1")
        sm.is_rate_limited("1.1.1.1")  # over limit
        assert sm.is_rate_limited("2.2.2.2") is False

    def test_request_count_resets_after_window_expires(self):
        """After the window expires the counter resets and requests are allowed."""
        sm = _sm(rate_limit=2, window=0)  # instant expiry
        sm.is_rate_limited("1.2.3.4")
        sm.is_rate_limited("1.2.3.4")
        sm.is_rate_limited("1.2.3.4")  # over limit in first window
        time.sleep(0.05)  # allow window to expire
        # First request in new window should be allowed
        assert sm.is_rate_limited("1.2.3.4") is False


# ---------------------------------------------------------------------------
# Brute-Force Detection
# ---------------------------------------------------------------------------


class TestBruteForceDetection:
    """Tests for the cumulative error counter and alert callback."""

    def test_alert_fires_at_threshold(self):
        """Alert callback should be invoked when error count reaches threshold."""
        callback = MagicMock()
        sm = _sm(threshold=3, callback=callback)
        sm.record_error("1.2.3.4")
        sm.record_error("1.2.3.4")
        sm.record_error("1.2.3.4")  # threshold reached
        callback.assert_called_once()

    def test_alert_callback_receives_ip_and_detail(self):
        """Alert callback should receive the offending IP and a detail string."""
        callback = MagicMock()
        sm = _sm(threshold=1, callback=callback)
        sm.record_error("5.6.7.8")
        args = callback.call_args[0]
        assert args[0] == "5.6.7.8"
        assert isinstance(args[1], str) and len(args[1]) > 0

    def test_alert_fires_only_once_per_ip(self):
        """Alert callback should fire exactly once per IP, no matter how many errors."""
        callback = MagicMock()
        sm = _sm(threshold=3, callback=callback)
        for _ in range(20):
            sm.record_error("1.2.3.4")
        assert callback.call_count == 1

    def test_no_alert_below_threshold(self):
        """Alert should not fire if error count is below threshold."""
        callback = MagicMock()
        sm = _sm(threshold=5, callback=callback)
        for _ in range(4):
            sm.record_error("1.2.3.4")
        callback.assert_not_called()

    def test_no_alert_without_callback(self):
        """Reaching the threshold with no callback configured should not raise."""
        sm = _sm(threshold=2)
        sm.record_error("1.2.3.4")
        sm.record_error("1.2.3.4")  # threshold — nothing should raise

    def test_different_ips_alerted_independently(self):
        """Each IP has its own alert state; two IPs each trigger one alert."""
        callback = MagicMock()
        sm = _sm(threshold=2, callback=callback)
        sm.record_error("1.1.1.1")
        sm.record_error("1.1.1.1")
        sm.record_error("2.2.2.2")
        sm.record_error("2.2.2.2")
        assert callback.call_count == 2

    def test_error_count_persists_across_windows(self):
        """Error count should NOT reset when the rate-limit window expires."""
        sm = _sm(threshold=5, window=0)
        for _ in range(4):
            sm.record_error("1.2.3.4")
        time.sleep(0.05)  # window expires — request_count resets
        sm.record_error("1.2.3.4")  # 5th error — should still trigger
        stats = sm.get_stats("1.2.3.4")
        assert stats["error_count"] == 5
        assert stats["alerted"] is True

    def test_callback_exception_does_not_propagate(self):
        """An exception raised by the callback must not crash the caller."""

        def bad_callback(ip, detail):
            raise RuntimeError("intentional failure")

        sm = _sm(threshold=1, callback=bad_callback)
        sm.record_error("1.2.3.4")  # must not raise


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    """Tests for the get_stats introspection method."""

    def test_stats_for_unknown_ip(self):
        """get_stats should return zeros for an IP that has never been seen."""
        sm = _sm()
        stats = sm.get_stats("99.99.99.99")
        assert stats == {"request_count": 0, "error_count": 0, "alerted": False}

    def test_stats_reflect_activity(self):
        """get_stats should accurately reflect request and error counts."""
        sm = _sm()
        sm.is_rate_limited("1.2.3.4")
        sm.is_rate_limited("1.2.3.4")
        sm.record_error("1.2.3.4")
        stats = sm.get_stats("1.2.3.4")
        assert stats["request_count"] == 2
        assert stats["error_count"] == 1
        assert stats["alerted"] is False

    def test_alerted_flag_set_after_threshold(self):
        """alerted flag should be True once the threshold callback has fired."""
        sm = _sm(threshold=2)
        sm.record_error("1.2.3.4")
        sm.record_error("1.2.3.4")
        assert sm.get_stats("1.2.3.4")["alerted"] is True
