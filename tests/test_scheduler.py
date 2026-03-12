"""Tests for the background cleanup scheduler.

Covers:
- cleanup_expired_ips coroutine behaviour with various DB/Unifi states
- start_scheduler / stop_scheduler lifecycle
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from utils.scheduler import (
    cleanup_expired_ips,
    start_scheduler,
    stop_scheduler,
    warn_expiring_ips,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ip_record(ip_id: int, ip: str) -> dict:
    """Return a minimal ip_addresses row dict."""
    return {
        "id": ip_id,
        "user_id": 1,
        "ip_address": ip,
        "expires_at": "2020-01-01 00:00:00",
        "is_active": 1,
    }


# ---------------------------------------------------------------------------
# cleanup_expired_ips tests
# ---------------------------------------------------------------------------


class TestCleanupExpiredIps:
    """Unit tests for the cleanup_expired_ips coroutine."""

    @pytest.mark.asyncio
    async def test_no_expired_ips_returns_zero_counts(self):
        """When DB has no expired IPs the function is a no-op."""
        db = MagicMock()
        db.get_expired_active_ips = AsyncMock(return_value=[])
        db.deactivate_ip = AsyncMock()
        unifi = MagicMock()

        result = await cleanup_expired_ips(db, unifi)

        assert result == {"removed": 0, "skipped": 0, "unifi_errors": 0}
        db.deactivate_ip.assert_not_called()
        unifi.remove_ip.assert_not_called()

    @pytest.mark.asyncio
    async def test_removes_expired_ips_from_unifi_and_db(self):
        """Expired IPs are removed from Unifi and deactivated in the DB."""
        db = MagicMock()
        records = [
            _make_ip_record(1, "1.2.3.4"),
            _make_ip_record(2, "5.6.7.8"),
        ]
        db.get_expired_active_ips = AsyncMock(return_value=records)
        db.deactivate_ip = AsyncMock(return_value=True)
        unifi = MagicMock()
        unifi.remove_ip = MagicMock(return_value=True)

        result = await cleanup_expired_ips(db, unifi)

        assert result["removed"] == 2
        assert result["skipped"] == 0
        assert result["unifi_errors"] == 0
        unifi.remove_ip.assert_any_call("1.2.3.4")
        unifi.remove_ip.assert_any_call("5.6.7.8")
        assert db.deactivate_ip.call_count == 2

    @pytest.mark.asyncio
    async def test_unifi_error_still_deactivates_in_db(self):
        """A Unifi error is logged but the DB is still updated."""
        db = MagicMock()
        db.get_expired_active_ips = AsyncMock(
            return_value=[_make_ip_record(1, "1.2.3.4")]
        )
        db.deactivate_ip = AsyncMock(return_value=True)
        unifi = MagicMock()
        unifi.remove_ip = MagicMock(side_effect=Exception("Unifi unreachable"))

        result = await cleanup_expired_ips(db, unifi)

        assert result["removed"] == 1
        assert result["unifi_errors"] == 1
        db.deactivate_ip.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_no_unifi_manager_deactivates_in_db_only(self):
        """When unifi_manager is None the DB is still updated."""
        db = MagicMock()
        db.get_expired_active_ips = AsyncMock(
            return_value=[_make_ip_record(3, "9.10.11.12")]
        )
        db.deactivate_ip = AsyncMock(return_value=True)

        result = await cleanup_expired_ips(db, None)

        assert result["removed"] == 1
        assert result["unifi_errors"] == 0
        db.deactivate_ip.assert_called_once_with(3)

    @pytest.mark.asyncio
    async def test_partial_unifi_failure(self):
        """Some IPs succeed, one Unifi removal fails — all DB rows updated."""
        db = MagicMock()
        records = [
            _make_ip_record(1, "1.1.1.1"),
            _make_ip_record(2, "2.2.2.2"),
            _make_ip_record(3, "3.3.3.3"),
        ]
        db.get_expired_active_ips = AsyncMock(return_value=records)
        db.deactivate_ip = AsyncMock(return_value=True)

        call_count = {"n": 0}

        def _remove(ip):
            call_count["n"] += 1
            if ip == "2.2.2.2":
                raise Exception("network error")

        unifi = MagicMock()
        unifi.remove_ip = MagicMock(side_effect=_remove)

        result = await cleanup_expired_ips(db, unifi)

        assert result["removed"] == 3
        assert result["unifi_errors"] == 1
        assert db.deactivate_ip.call_count == 3

    @pytest.mark.asyncio
    async def test_ip_not_found_in_db_counts_as_skipped(self):
        """If deactivate_ip returns False the record is counted as skipped."""
        db = MagicMock()
        db.get_expired_active_ips = AsyncMock(
            return_value=[_make_ip_record(99, "8.8.8.8")]
        )
        db.deactivate_ip = AsyncMock(return_value=False)
        unifi = MagicMock()
        unifi.remove_ip = MagicMock(return_value=True)

        result = await cleanup_expired_ips(db, unifi)

        assert result["removed"] == 0
        assert result["skipped"] == 1


# ---------------------------------------------------------------------------
# Scheduler lifecycle tests
# ---------------------------------------------------------------------------


class TestSchedulerLifecycle:
    """Tests for start_scheduler / stop_scheduler."""

    def test_start_creates_running_scheduler_with_job(self):
        """start_scheduler returns a running BackgroundScheduler with one job."""
        import asyncio

        loop = asyncio.new_event_loop()
        db = MagicMock()
        unifi = MagicMock()

        try:
            scheduler = start_scheduler(db, loop, unifi_manager=unifi, interval_hours=1)
            assert scheduler.running
            jobs = scheduler.get_jobs()
            assert len(jobs) == 1
            assert jobs[0].id == "cleanup_expired_ips"
        finally:
            scheduler.shutdown(wait=False)
            loop.close()

    def test_stop_scheduler_shuts_down_cleanly(self):
        """stop_scheduler stops a running scheduler without raising errors."""
        import asyncio

        loop = asyncio.new_event_loop()
        db = MagicMock()

        try:
            start_scheduler(db, loop, unifi_manager=None, interval_hours=24)
            stop_scheduler()  # should not raise
        finally:
            # Ensure cleanup even if the test fails
            try:
                stop_scheduler()
            except Exception:
                pass
            loop.close()

    def test_stop_scheduler_noop_when_not_started(self):
        """stop_scheduler is safe to call even if the scheduler was never started."""
        import utils.scheduler as sched_module

        sched_module._scheduler = None
        stop_scheduler()  # must not raise


# ---------------------------------------------------------------------------
# warn_expiring_ips tests
# ---------------------------------------------------------------------------


def _make_expiring_record(ip_id: int, ip: str, discord_id: str = "111") -> dict:
    """Return a minimal ip_addresses row dict for expiry-warning tests."""
    return {
        "id": ip_id,
        "user_id": 1,
        "ip_address": ip,
        "expires_at": "2026-03-14 00:00:00",
        "is_active": 1,
        "warning_sent": 0,
        "discord_id": discord_id,
        "discord_username": "testuser",
    }


class TestWarnExpiringIps:
    """Unit tests for the warn_expiring_ips coroutine."""

    @pytest.mark.asyncio
    async def test_no_expiring_ips_returns_zero_counts(self):
        """When no IPs are expiring soon the function is a no-op."""
        db = MagicMock()
        db.get_ips_expiring_soon = AsyncMock(return_value=[])
        db.mark_ip_warning_sent = AsyncMock()
        callback = MagicMock()

        result = await warn_expiring_ips(db, callback, warning_days=3)

        assert result == {"warned": 0, "errors": 0}
        callback.assert_not_called()
        db.mark_ip_warning_sent.assert_not_called()

    @pytest.mark.asyncio
    async def test_warns_each_expiring_ip(self):
        """Callback is called once per expiring IP and each row is marked."""
        db = MagicMock()
        records = [
            _make_expiring_record(1, "1.2.3.4", "111"),
            _make_expiring_record(2, "5.6.7.8", "222"),
        ]
        db.get_ips_expiring_soon = AsyncMock(return_value=records)
        db.mark_ip_warning_sent = AsyncMock(return_value=True)
        callback = MagicMock()

        result = await warn_expiring_ips(db, callback, warning_days=3)

        assert result["warned"] == 2
        assert result["errors"] == 0
        assert callback.call_count == 2
        callback.assert_any_call("111", "1.2.3.4", "2026-03-14")
        callback.assert_any_call("222", "5.6.7.8", "2026-03-14")
        assert db.mark_ip_warning_sent.call_count == 2

    @pytest.mark.asyncio
    async def test_no_callback_returns_zero_without_db_query(self):
        """When warning_callback is None no DB interaction occurs."""
        db = MagicMock()
        db.get_ips_expiring_soon = AsyncMock()

        result = await warn_expiring_ips(db, None, warning_days=3)

        assert result == {"warned": 0, "errors": 0}
        db.get_ips_expiring_soon.assert_not_called()

    @pytest.mark.asyncio
    async def test_callback_error_counted_as_error(self):
        """If the callback raises, the record is counted as an error."""
        db = MagicMock()
        db.get_ips_expiring_soon = AsyncMock(
            return_value=[_make_expiring_record(1, "1.2.3.4")]
        )
        db.mark_ip_warning_sent = AsyncMock(return_value=True)
        callback = MagicMock(side_effect=Exception("DM failed"))

        result = await warn_expiring_ips(db, callback, warning_days=3)

        assert result["warned"] == 0
        assert result["errors"] == 1
        db.mark_ip_warning_sent.assert_not_called()

    @pytest.mark.asyncio
    async def test_expires_at_trimmed_to_date(self):
        """expires_at with a time component is truncated to YYYY-MM-DD."""
        db = MagicMock()
        record = _make_expiring_record(1, "1.2.3.4")
        record["expires_at"] = "2026-03-14 12:34:56"
        db.get_ips_expiring_soon = AsyncMock(return_value=[record])
        db.mark_ip_warning_sent = AsyncMock(return_value=True)
        callback = MagicMock()

        await warn_expiring_ips(db, callback, warning_days=3)

        callback.assert_called_once_with("111", "1.2.3.4", "2026-03-14")
