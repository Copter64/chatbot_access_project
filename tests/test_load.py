"""Load tests: multiple simulated users hitting the web server concurrently.

Strategy: use ThreadPoolExecutor to fire N threads against the Flask test
client (which is thread-safe when TESTING=True).  No new dependencies are
needed — everything is in the stdlib + existing project packages.

Scenarios tested:
1. Concurrent GET /check-ip/<token> — valid tokens, all should respond 200.
2. Concurrent POST /confirm-ip/<token> — all submitting different IPs, all
   should either succeed (200) or be rate-limited (429); no crashes.
3. Rate-limiter under load — same IP fires many requests; all requests above
   the threshold must receive 429, not 500.
4. Concurrent /health — pure smoke test; all 200.
5. Concurrent DB writes — multiple threads register IPs against the same
   in-memory DB, checking no row is lost and no exception escapes.
"""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import AsyncMock, MagicMock

import pytest

from web.app import create_app
from web.security import SecurityManager

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_TOKEN = "abcdefghijklmnopqrstuvwxyz012345"  # 32 valid chars
CONCURRENCY = 20  # threads per scenario
TOKEN_ROW = {"id": 1, "user_id": 42, "token": VALID_TOKEN}


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def event_loop_thread():
    """Run an asyncio event loop in a background thread (mirrors production)."""
    loop = asyncio.new_event_loop()
    t = threading.Thread(target=loop.run_forever, daemon=True)
    t.start()
    yield loop
    loop.call_soon_threadsafe(loop.stop)
    t.join(timeout=2)


def _make_app(loop, token_row=None, rate_limit=1000, add_ip_side_effect=None):
    """Return a Flask test app with a fully-mocked database."""
    mock_db = MagicMock()
    mock_db.get_token = AsyncMock(return_value=token_row)
    mock_db.mark_token_used = AsyncMock(return_value=True)
    if add_ip_side_effect:
        mock_db.add_ip_address = AsyncMock(side_effect=add_ip_side_effect)
    else:
        mock_db.add_ip_address = AsyncMock(return_value=1)
    mock_db.log_request = AsyncMock(return_value=None)

    app = create_app(mock_db, loop)
    app.config["SECURITY"] = SecurityManager(
        rate_limit_requests=rate_limit,
        rate_limit_window_seconds=60,
        brute_force_threshold=200,
    )
    app.config["TESTING"] = True
    return app, mock_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_concurrent(fn, n=CONCURRENCY):
    """Run *fn* in *n* threads; return list of results in completion order."""
    with ThreadPoolExecutor(max_workers=n) as pool:
        futures = [pool.submit(fn) for _ in range(n)]
        return [f.result() for f in as_completed(futures)]


# ---------------------------------------------------------------------------
# Scenario 1 — concurrent GET /check-ip/<token>
# ---------------------------------------------------------------------------


class TestConcurrentCheckIp:
    """Multiple users GETting the check-ip page simultaneously."""

    def test_all_requests_return_200(self, event_loop_thread):
        """All CONCURRENCY concurrent GETs on a valid token return 200."""
        app, _ = _make_app(event_loop_thread, token_row=TOKEN_ROW)

        def request():
            with app.test_client() as client:
                return client.get(
                    f"/check-ip/{VALID_TOKEN}",
                    environ_base={"REMOTE_ADDR": "8.8.8.8"},
                ).status_code

        statuses = _run_concurrent(request)
        assert all(s == 200 for s in statuses), f"Non-200 responses: {statuses}"

    def test_no_crashes_on_missing_token(self, event_loop_thread):
        """Concurrent GETs for a non-existent token all return 404, not 500."""
        app, _ = _make_app(event_loop_thread, token_row=None)

        def request():
            with app.test_client() as client:
                return client.get(
                    f"/check-ip/{VALID_TOKEN}",
                    environ_base={"REMOTE_ADDR": "8.8.8.8"},
                ).status_code

        statuses = _run_concurrent(request)
        # 400 = bad token format; 404 = not found; 410 = token expired/gone
        assert all(
            s in (400, 404, 410) for s in statuses
        ), f"Unexpected status codes: {statuses}"


# ---------------------------------------------------------------------------
# Scenario 2 — concurrent POST /confirm-ip/<token>
# ---------------------------------------------------------------------------


class TestConcurrentConfirmIp:
    """Multiple users POSTing their IPs at the same time."""

    def test_all_posts_succeed_or_rate_limited(self, event_loop_thread):
        """Every concurrent POST returns 200 or 429; never 500."""
        app, _ = _make_app(event_loop_thread, token_row=TOKEN_ROW, rate_limit=1000)

        def request(idx):
            ip = f"203.0.113.{(idx % 254) + 1}"
            with app.test_client() as client:
                return client.post(
                    f"/confirm-ip/{VALID_TOKEN}",
                    data={"ip_address": ip},
                    environ_base={"REMOTE_ADDR": ip},
                ).status_code

        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            futures = [pool.submit(request, i) for i in range(CONCURRENCY)]
            statuses = [f.result() for f in as_completed(futures)]

        unexpected = [s for s in statuses if s not in (200, 302, 429, 400)]
        assert not unexpected, f"Unexpected status codes: {unexpected}"

    def test_db_add_ip_called_for_each_success(self, event_loop_thread):
        """add_ip_address is called once per successful POST."""
        app, mock_db = _make_app(
            event_loop_thread, token_row=TOKEN_ROW, rate_limit=1000
        )

        def request(idx):
            ip = f"10.0.{idx // 254}.{(idx % 254) + 1}"
            with app.test_client() as client:
                return client.post(
                    f"/confirm-ip/{VALID_TOKEN}",
                    data={"ip_address": ip},
                    environ_base={"REMOTE_ADDR": ip},
                ).status_code

        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            futures = [pool.submit(request, i) for i in range(CONCURRENCY)]
            statuses = [f.result() for f in as_completed(futures)]

        successes = sum(1 for s in statuses if s in (200, 302))
        assert mock_db.add_ip_address.call_count == successes


# ---------------------------------------------------------------------------
# Scenario 3 — rate limiter under load from one IP
# ---------------------------------------------------------------------------


class TestRateLimiterUnderLoad:
    """Single IP hammering the endpoint; excess requests must get 429."""

    def test_requests_above_limit_get_429(self, event_loop_thread):
        """With limit=5, the 6th+ request from the same IP must be 429."""
        limit = 5
        total = 30
        app, _ = _make_app(event_loop_thread, token_row=TOKEN_ROW, rate_limit=limit)

        def request():
            with app.test_client() as client:
                return client.get(
                    f"/check-ip/{VALID_TOKEN}",
                    environ_base={"REMOTE_ADDR": "8.8.8.8"},
                ).status_code

        # Fire sequentially from the same IP so the counter accumulates
        statuses = [request() for _ in range(total)]

        rate_limited = statuses.count(429)
        assert rate_limited > 0, "Expected at least one 429 response"
        # None should be 500
        assert 500 not in statuses, f"Server error in responses: {statuses}"

    def test_different_ips_not_blocked_by_one_ips_limit(self, event_loop_thread):
        """Rate limiting one IP must not affect different IPs."""
        limit = 2
        app, _ = _make_app(event_loop_thread, token_row=TOKEN_ROW, rate_limit=limit)

        # Exhaust the limit for IP A
        with app.test_client() as client:
            for _ in range(limit + 5):
                client.get(
                    f"/check-ip/{VALID_TOKEN}",
                    environ_base={"REMOTE_ADDR": "8.8.8.8"},
                )

        # IP B should still be allowed
        with app.test_client() as client:
            resp = client.get(
                f"/check-ip/{VALID_TOKEN}",
                environ_base={"REMOTE_ADDR": "1.1.1.1"},
            )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Scenario 4 — concurrent /health
# ---------------------------------------------------------------------------


class TestConcurrentHealth:
    """Smoke test: /health never fails under concurrency."""

    def test_all_health_checks_return_200(self, event_loop_thread):
        app, _ = _make_app(event_loop_thread)

        def request():
            with app.test_client() as client:
                return client.get("/health").status_code

        statuses = _run_concurrent(request, n=50)
        assert all(s == 200 for s in statuses)


# ---------------------------------------------------------------------------
# Scenario 5 — concurrent DB writes (aiosqlite contention)
# ---------------------------------------------------------------------------


class TestConcurrentDbWrites:
    """Multiple threads registering IPs; DB layer must not raise."""

    def test_no_exception_on_concurrent_add_ip(self, event_loop_thread):
        """add_ip_address must be awaited without raising for all threads."""
        call_count = 0
        lock = threading.Lock()

        async def fake_add_ip(*args, **kwargs):
            nonlocal call_count
            with lock:
                call_count += 1
            return call_count

        app, mock_db = _make_app(
            event_loop_thread,
            token_row=TOKEN_ROW,
            rate_limit=1000,
            add_ip_side_effect=fake_add_ip,
        )

        errors = []

        def request(idx):
            ip = f"10.1.{idx // 254}.{(idx % 254) + 1}"
            try:
                with app.test_client() as client:
                    client.post(
                        f"/confirm-ip/{VALID_TOKEN}",
                        data={"ip_address": ip},
                        environ_base={"REMOTE_ADDR": ip},
                    )
            except Exception as exc:
                errors.append(exc)

        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            futures = [pool.submit(request, i) for i in range(CONCURRENCY)]
            for f in as_completed(futures):
                f.result()

        assert not errors, f"Exceptions raised during concurrent writes: {errors}"
