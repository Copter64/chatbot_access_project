"""Tests for the Flask web server routes (Phase 3).

Routes under test:
    GET  /health
    GET  /check-ip/<token>
    POST /confirm-ip/<token>
    GET  /success
"""

import asyncio
import threading
from unittest.mock import AsyncMock, MagicMock

import pytest

from web.app import create_app
from web.security import SecurityManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_TOKEN = "abcdefghijklmnopqrstuvwxyz012345"  # 32 valid chars


def _make_app(loop: asyncio.AbstractEventLoop, token_row=None, rate_limit=100):
    """Create a Flask test app with a mock database instance.

    Args:
        loop: A running asyncio event loop.
        token_row: Value that mock db.get_token will return.
        rate_limit: Per-IP request rate limit for the SecurityManager.
            Use a low value (e.g. 2) to test rate-limiting behaviour.

    Returns:
        Flask: Configured test application.
    """
    mock_db = MagicMock()
    mock_db.get_token = AsyncMock(return_value=token_row)
    mock_db.mark_token_used = AsyncMock(return_value=True)
    mock_db.add_ip_address = AsyncMock(return_value=1)
    mock_db.log_request = AsyncMock(return_value=None)

    app = create_app(mock_db, loop)
    # Swap in a SecurityManager tuned for the test
    app.config["SECURITY"] = SecurityManager(
        rate_limit_requests=rate_limit,
        rate_limit_window_seconds=60,
        brute_force_threshold=20,
    )
    app.config["TESTING"] = True
    return app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def event_loop_thread():
    """Start an asyncio event loop in a background thread.

    The Flask routes use run_coroutine_threadsafe, which requires the loop
    to be running. This fixture mirrors the production setup where the
    Discord bot keeps the main loop alive.

    Yields:
        asyncio.AbstractEventLoop: The running event loop.
    """
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    yield loop
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=2)


@pytest.fixture
def client_no_token(event_loop_thread):
    """Flask test client where the token does not exist in the database."""
    app = _make_app(event_loop_thread, token_row=None)
    with app.test_client() as client:
        yield client


@pytest.fixture
def client_valid_token(event_loop_thread):
    """Flask test client where the token exists and is valid."""
    token_row = {"id": 1, "user_id": 42, "token": VALID_TOKEN}
    app = _make_app(event_loop_thread, token_row=token_row)
    with app.test_client() as client:
        yield client


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_returns_200(self, client_no_token):
        """Health endpoint should always return 200."""
        response = client_no_token.get("/health")
        assert response.status_code == 200

    def test_health_returns_ok_status(self, client_no_token):
        """Health endpoint JSON body should contain status ok."""
        response = client_no_token.get("/health")
        data = response.get_json()
        assert data == {"status": "ok"}


# ---------------------------------------------------------------------------
# GET /check-ip/<token>
# ---------------------------------------------------------------------------


class TestCheckIpGet:
    """Tests for GET /check-ip/<token>."""

    def test_invalid_token_format_returns_400(self, client_no_token):
        """Tokens that fail format validation should return 400."""
        response = client_no_token.get("/check-ip/bad")
        assert response.status_code == 400

    def test_short_token_returns_400(self, client_no_token):
        """Tokens shorter than 16 chars should return 400."""
        response = client_no_token.get("/check-ip/abc")
        assert response.status_code == 400

    def test_expired_or_missing_token_returns_410(self, client_no_token):
        """Valid format token that is not in DB should return 410."""
        response = client_no_token.get(
            "/check-ip/" + VALID_TOKEN,
            environ_base={"REMOTE_ADDR": "8.8.8.8"},
        )
        assert response.status_code == 410

    def test_valid_token_returns_200(self, client_valid_token):
        """Valid, unexpired, unused token should return 200."""
        response = client_valid_token.get(
            "/check-ip/" + VALID_TOKEN,
            environ_base={"REMOTE_ADDR": "8.8.8.8"},
        )
        assert response.status_code == 200

    def test_valid_token_page_contains_confirm_button(self, client_valid_token):
        """Check-ip page must contain a confirm button."""
        response = client_valid_token.get(
            "/check-ip/" + VALID_TOKEN,
            environ_base={"REMOTE_ADDR": "8.8.8.8"},
        )
        assert b"Confirm" in response.data

    def test_valid_token_page_contains_form(self, client_valid_token):
        """Check-ip page must contain a form POSTing to confirm-ip."""
        response = client_valid_token.get(
            "/check-ip/" + VALID_TOKEN,
            environ_base={"REMOTE_ADDR": "8.8.8.8"},
        )
        assert b"/confirm-ip/" in response.data


# ---------------------------------------------------------------------------
# POST /confirm-ip/<token>
# ---------------------------------------------------------------------------


class TestConfirmIpPost:
    """Tests for POST /confirm-ip/<token>."""

    def test_invalid_token_format_returns_400(self, client_no_token):
        """Tokens that fail format validation should return 400."""
        response = client_no_token.post("/confirm-ip/bad")
        assert response.status_code == 400

    def test_expired_token_returns_410(self, client_no_token):
        """Confirm on an expired/missing token should return 410."""
        response = client_no_token.post(
            "/confirm-ip/" + VALID_TOKEN,
            environ_base={"REMOTE_ADDR": "8.8.8.8"},
        )
        assert response.status_code == 410

    def test_valid_token_redirects_to_success(self, client_valid_token):
        """Valid token confirm should redirect to /success."""
        response = client_valid_token.post(
            "/confirm-ip/" + VALID_TOKEN,
            follow_redirects=False,
            environ_base={"REMOTE_ADDR": "8.8.8.8"},
        )
        assert response.status_code == 302
        assert "success" in response.headers["Location"]

    def test_success_redirect_includes_ip(self, client_valid_token):
        """Success redirect must include ip query parameter."""
        response = client_valid_token.post(
            "/confirm-ip/" + VALID_TOKEN,
            follow_redirects=False,
            environ_base={"REMOTE_ADDR": "8.8.8.8"},
        )
        assert "ip=" in response.headers["Location"]

    def test_success_redirect_includes_expires(self, client_valid_token):
        """Success redirect must include expires query parameter."""
        response = client_valid_token.post(
            "/confirm-ip/" + VALID_TOKEN,
            follow_redirects=False,
            environ_base={"REMOTE_ADDR": "8.8.8.8"},
        )
        assert "expires=" in response.headers["Location"]


# ---------------------------------------------------------------------------
# Private / non-routable IP rejection
# ---------------------------------------------------------------------------


class TestPrivateIpRejection:
    """GET /check-ip and POST /confirm-ip must reject RFC 1918 and loopback IPs."""

    PRIVATE_IPS = [
        "127.0.0.1",        # loopback
        "10.0.0.1",         # RFC 1918 class A
        "172.16.0.1",       # RFC 1918 class B
        "192.168.1.100",    # RFC 1918 class C
        "169.254.0.1",      # link-local
    ]

    def test_check_ip_rejects_loopback(self, client_valid_token):
        """GET /check-ip must return 400 for loopback addresses."""
        response = client_valid_token.get(
            "/check-ip/" + VALID_TOKEN,
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        )
        assert response.status_code == 400

    def test_check_ip_rejects_rfc1918(self, client_valid_token):
        """GET /check-ip must return 400 for RFC 1918 private addresses."""
        for ip in ("10.0.0.1", "172.16.0.1", "192.168.1.100"):
            response = client_valid_token.get(
                "/check-ip/" + VALID_TOKEN,
                environ_base={"REMOTE_ADDR": ip},
            )
            assert response.status_code == 400, f"Expected 400 for {ip}"

    def test_check_ip_rejects_link_local(self, client_valid_token):
        """GET /check-ip must return 400 for link-local addresses."""
        response = client_valid_token.get(
            "/check-ip/" + VALID_TOKEN,
            environ_base={"REMOTE_ADDR": "169.254.0.1"},
        )
        assert response.status_code == 400

    def test_confirm_ip_rejects_loopback(self, client_valid_token):
        """POST /confirm-ip must return 400 for loopback addresses."""
        response = client_valid_token.post(
            "/confirm-ip/" + VALID_TOKEN,
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        )
        assert response.status_code == 400

    def test_confirm_ip_rejects_rfc1918(self, client_valid_token):
        """POST /confirm-ip must return 400 for RFC 1918 private addresses."""
        for ip in ("10.0.0.1", "172.16.0.1", "192.168.1.100"):
            response = client_valid_token.post(
                "/confirm-ip/" + VALID_TOKEN,
                environ_base={"REMOTE_ADDR": ip},
            )
            assert response.status_code == 400, f"Expected 400 for {ip}"

    def test_private_ip_error_page_content(self, client_valid_token):
        """Private IP rejection must display a descriptive error message."""
        response = client_valid_token.get(
            "/check-ip/" + VALID_TOKEN,
            environ_base={"REMOTE_ADDR": "192.168.1.1"},
        )
        assert b"Private IP" in response.data or b"private" in response.data.lower()


# ---------------------------------------------------------------------------
# GET /success
# ---------------------------------------------------------------------------


class TestSuccessPage:
    """Tests for GET /success."""

    def test_success_page_returns_200(self, client_no_token):
        """Success page should return 200."""
        response = client_no_token.get("/success?ip=1.2.3.4&expires=2026-06-01")
        assert response.status_code == 200

    def test_success_page_displays_ip(self, client_no_token):
        """Success page must display the IP address."""
        response = client_no_token.get("/success?ip=1.2.3.4&expires=2026-06-01")
        assert b"1.2.3.4" in response.data

    def test_success_page_displays_expiry(self, client_no_token):
        """Success page must display the expiry date."""
        response = client_no_token.get("/success?ip=1.2.3.4&expires=2026-06-01")
        assert b"2026-06-01" in response.data

    def test_success_page_rejects_invalid_ip(self, client_no_token):
        """Success page must return 400 for a non-IP ip param."""
        response = client_no_token.get(
            "/success?ip=not_an_ip&expires=2026-06-01"
        )
        assert response.status_code == 400

    def test_success_page_rejects_invalid_date(self, client_no_token):
        """Success page must return 400 for a malformed expires param."""
        response = client_no_token.get(
            "/success?ip=1.2.3.4&expires=tuesday"
        )
        assert response.status_code == 400

    def test_success_page_accepts_ipv6(self, client_no_token):
        """Success page should accept a valid IPv6 address."""
        response = client_no_token.get(
            "/success?ip=2001:db8::1&expires=2026-06-01"
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /robots.txt
# ---------------------------------------------------------------------------


class TestRobotsTxt:
    """Tests for GET /robots.txt — crawlers must be disallowed."""

    def test_robots_returns_200(self, client_no_token):
        """robots.txt must return 200."""
        response = client_no_token.get("/robots.txt")
        assert response.status_code == 200

    def test_robots_disallows_all(self, client_no_token):
        """robots.txt must contain Disallow: / for all user-agents."""
        response = client_no_token.get("/robots.txt")
        assert b"Disallow: /" in response.data

    def test_robots_content_type_is_text(self, client_no_token):
        """robots.txt must be served as text/plain."""
        response = client_no_token.get("/robots.txt")
        assert "text/plain" in response.content_type


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------


class TestSecurityHeaders:
    """Every response must include the required security headers."""

    def test_health_has_security_headers(self, client_no_token):
        """Health endpoint must include security headers."""
        response = client_no_token.get("/health")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "Content-Security-Policy" in response.headers

    def test_error_page_has_security_headers(self, client_no_token):
        """Error pages must include security headers."""
        response = client_no_token.get("/check-ip/badtoken")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"


# ---------------------------------------------------------------------------
# Rate limiting (web-level)
# ---------------------------------------------------------------------------


class TestWebRateLimiting:
    """Tests for the per-IP request rate limiter on web routes."""

    def test_check_ip_returns_429_when_rate_limited(self, event_loop_thread):
        """After exceeding the per-IP limit /check-ip should return 429."""
        app = _make_app(event_loop_thread, rate_limit=2)
        with app.test_client() as client:
            client.get(f"/check-ip/{VALID_TOKEN}", environ_base={"REMOTE_ADDR": "8.8.8.8"})
            client.get(f"/check-ip/{VALID_TOKEN}", environ_base={"REMOTE_ADDR": "8.8.8.8"})
            response = client.get(f"/check-ip/{VALID_TOKEN}", environ_base={"REMOTE_ADDR": "8.8.8.8"})
        assert response.status_code == 429

    def test_confirm_ip_returns_429_when_rate_limited(self, event_loop_thread):
        """After exceeding the per-IP limit /confirm-ip should return 429."""
        app = _make_app(event_loop_thread, rate_limit=2)
        with app.test_client() as client:
            client.post(f"/confirm-ip/{VALID_TOKEN}", environ_base={"REMOTE_ADDR": "8.8.8.8"})
            client.post(f"/confirm-ip/{VALID_TOKEN}", environ_base={"REMOTE_ADDR": "8.8.8.8"})
            response = client.post(f"/confirm-ip/{VALID_TOKEN}", environ_base={"REMOTE_ADDR": "8.8.8.8"})
        assert response.status_code == 429

    def test_health_not_rate_limited(self, event_loop_thread):
        """Health endpoint is exempt from rate limiting."""
        app = _make_app(event_loop_thread, rate_limit=2)
        with app.test_client() as client:
            for _ in range(10):
                response = client.get("/health")
        assert response.status_code == 200

    def test_rate_limit_error_page_content(self, event_loop_thread):
        """429 response should render an informative error page."""
        app = _make_app(event_loop_thread, rate_limit=1)
        with app.test_client() as client:
            client.get(f"/check-ip/{VALID_TOKEN}", environ_base={"REMOTE_ADDR": "8.8.8.8"})
            response = client.get(f"/check-ip/{VALID_TOKEN}", environ_base={"REMOTE_ADDR": "8.8.8.8"})
        assert b"Too Many Requests" in response.data


# ---------------------------------------------------------------------------
# Server info callback
# ---------------------------------------------------------------------------


def _make_app_with_callback(
    loop: asyncio.AbstractEventLoop,
    callback,
    token_row=None,
):
    """Create a Flask test app with a server_info_callback injected."""
    mock_db = MagicMock()
    mock_db.get_token = AsyncMock(return_value=token_row)
    mock_db.mark_token_used = AsyncMock(return_value=True)
    mock_db.add_ip_address = AsyncMock(return_value=1)
    mock_db.log_request = AsyncMock(return_value=None)
    mock_db.get_user_by_id = AsyncMock(
        return_value={"id": 42, "discord_id": "111222333444"}
    )

    app = create_app(mock_db, loop, server_info_callback=callback)
    app.config["TESTING"] = True
    return app


class TestServerInfoCallback:
    """Verify the server_info_callback is invoked after IP confirmation."""

    def test_callback_called_on_successful_confirm(self, event_loop_thread):
        """Callback receives (discord_id, ip, expires) on successful POST."""
        callback = MagicMock()
        token_row = {"id": 1, "user_id": 42, "token": VALID_TOKEN}
        app = _make_app_with_callback(event_loop_thread, callback, token_row)

        with app.test_client() as client:
            response = client.post(
                f"/confirm-ip/{VALID_TOKEN}",
                environ_base={"REMOTE_ADDR": "8.8.8.8"},
            )

        assert response.status_code == 302
        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == "111222333444"
        assert args[1] == "8.8.8.8"
        # expires is a YYYY-MM-DD string
        assert len(args[2]) == 10 and args[2][4] == "-"

    def test_callback_not_called_when_token_invalid(self, event_loop_thread):
        """Callback must NOT be invoked if the token is expired/missing."""
        callback = MagicMock()
        app = _make_app_with_callback(event_loop_thread, callback, token_row=None)

        with app.test_client() as client:
            client.post(
                f"/confirm-ip/{VALID_TOKEN}",
                environ_base={"REMOTE_ADDR": "8.8.8.8"},
            )

        callback.assert_not_called()

    def test_callback_not_called_when_no_callback_configured(
        self, event_loop_thread
    ):
        """Confirm-IP succeeds normally when no callback is registered."""
        token_row = {"id": 1, "user_id": 42, "token": VALID_TOKEN}
        app = _make_app(event_loop_thread, token_row=token_row)

        with app.test_client() as client:
            response = client.post(
                f"/confirm-ip/{VALID_TOKEN}",
                environ_base={"REMOTE_ADDR": "8.8.8.8"},
            )

        assert response.status_code == 302