"""Unit tests for database/models.py.

Uses an in-memory SQLite database so tests are fast, isolated,
and leave no files on disk.
"""

import pytest

from database.models import Database


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def db():
    """Provide a fresh in-memory Database for each test."""
    database = Database(db_path=":memory:")
    await database.connect()
    await database.initialize_schema()
    yield database
    await database.close()


# ---------------------------------------------------------------------------
# User operations
# ---------------------------------------------------------------------------


class TestUsers:
    """Tests for user creation and lookup."""

    async def test_get_user_returns_none_when_not_found(self, db):
        result = await db.get_user_by_discord_id("nonexistent")
        assert result is None

    async def test_create_user_returns_int_id(self, db):
        uid = await db.create_user("111", "alice")
        assert isinstance(uid, int)
        assert uid > 0

    async def test_create_user_persists(self, db):
        await db.create_user("222", "bob")
        user = await db.get_user_by_discord_id("222")
        assert user is not None
        assert user["discord_username"] == "bob"

    async def test_create_user_upserts_username(self, db):
        """Creating the same discord_id twice updates the username."""
        await db.create_user("333", "old_name")
        await db.create_user("333", "new_name")
        user = await db.get_user_by_discord_id("333")
        assert user["discord_username"] == "new_name"

    async def test_two_different_users(self, db):
        id1 = await db.create_user("aaa", "user1")
        id2 = await db.create_user("bbb", "user2")
        assert id1 != id2


# ---------------------------------------------------------------------------
# Access token operations
# ---------------------------------------------------------------------------


class TestAccessTokens:
    """Tests for token create / get / mark-used."""

    async def test_create_token_returns_int(self, db):
        uid = await db.create_user("100", "alice")
        tok_id = await db.create_access_token(
            uid, "abc123xyz" * 4, "2099-12-31 23:59:59"
        )
        assert isinstance(tok_id, int)

    async def test_get_token_returns_data(self, db):
        uid = await db.create_user("101", "alice")
        token = "validtoken1234567890abcdef123456"
        await db.create_access_token(uid, token, "2099-12-31 23:59:59")
        row = await db.get_token(token)
        assert row is not None
        assert row["token"] == token

    async def test_get_token_returns_none_for_unknown(self, db):
        result = await db.get_token("doesnotexist12345678901234567890")
        assert result is None

    async def test_get_token_returns_none_for_expired(self, db):
        uid = await db.create_user("102", "alice")
        token = "expiredtoken234567890abcdef1234"
        await db.create_access_token(uid, token, "2000-01-01 00:00:00")
        result = await db.get_token(token)
        assert result is None

    async def test_mark_token_used_returns_true(self, db):
        uid = await db.create_user("103", "alice")
        token = "marktokenused567890abcdef123456"
        await db.create_access_token(uid, token, "2099-12-31 23:59:59")
        result = await db.mark_token_used(token, "1.2.3.4")
        assert result is True

    async def test_mark_token_used_prevents_reuse(self, db):
        uid = await db.create_user("104", "alice")
        token = "reusetoken1234567890abcdef12345"
        await db.create_access_token(uid, token, "2099-12-31 23:59:59")
        await db.mark_token_used(token, "1.2.3.4")
        # get_token should now return None (used=1)
        result = await db.get_token(token)
        assert result is None

    async def test_mark_token_used_stores_ip(self, db):
        uid = await db.create_user("105", "alice")
        token = "storeipabc1234567890abcdef12345"
        await db.create_access_token(uid, token, "2099-12-31 23:59:59")
        await db.mark_token_used(token, "5.6.7.8")
        async with db.connection.cursor() as cur:
            await cur.execute(
                "SELECT ip_address FROM access_tokens WHERE token = ?", (token,)
            )
            row = await cur.fetchone()
        assert row[0] == "5.6.7.8"

    async def test_mark_nonexistent_token_returns_false(self, db):
        result = await db.mark_token_used("nosuchtoken12345678901234567890", "1.1.1.1")
        assert result is False


# ---------------------------------------------------------------------------
# IP address operations
# ---------------------------------------------------------------------------


class TestIPAddresses:
    """Tests for add_ip_address, get_user_active_ips,
    get_expired_active_ips, and deactivate_ip."""

    async def test_add_ip_returns_int(self, db):
        uid = await db.create_user("200", "alice")
        ip_id = await db.add_ip_address(uid, "10.0.0.1", "2099-12-31 23:59:59")
        assert isinstance(ip_id, int)

    async def test_add_ip_shows_in_active_list(self, db):
        uid = await db.create_user("201", "alice")
        await db.add_ip_address(uid, "10.0.0.2", "2099-12-31 23:59:59")
        ips = await db.get_user_active_ips(uid)
        assert any(r["ip_address"] == "10.0.0.2" for r in ips)

    async def test_expired_ip_not_in_active_list(self, db):
        uid = await db.create_user("202", "alice")
        await db.add_ip_address(uid, "10.0.0.3", "2000-01-01 00:00:00")
        ips = await db.get_user_active_ips(uid)
        assert not any(r["ip_address"] == "10.0.0.3" for r in ips)

    async def test_add_duplicate_ip_updates_expiry(self, db):
        """Adding the same user+IP again reactivates and updates expires_at."""
        uid = await db.create_user("203", "alice")
        id1 = await db.add_ip_address(uid, "10.0.0.4", "2000-01-01 00:00:00")
        id2 = await db.add_ip_address(uid, "10.0.0.4", "2099-12-31 23:59:59")
        assert id1 == id2  # same row, updated in place
        ips = await db.get_user_active_ips(uid)
        assert len(ips) == 1

    async def test_get_expired_active_ips_returns_expired(self, db):
        uid = await db.create_user("204", "alice")
        await db.add_ip_address(uid, "10.0.0.5", "2000-01-01 00:00:00")
        expired = await db.get_expired_active_ips()
        assert any(r["ip_address"] == "10.0.0.5" for r in expired)

    async def test_get_expired_active_ips_excludes_future(self, db):
        uid = await db.create_user("205", "alice")
        await db.add_ip_address(uid, "10.0.0.6", "2099-12-31 23:59:59")
        expired = await db.get_expired_active_ips()
        assert not any(r["ip_address"] == "10.0.0.6" for r in expired)

    async def test_get_expired_active_ips_excludes_already_inactive(self, db):
        uid = await db.create_user("206", "alice")
        ip_id = await db.add_ip_address(uid, "10.0.0.7", "2000-01-01 00:00:00")
        await db.deactivate_ip(ip_id)
        expired = await db.get_expired_active_ips()
        assert not any(r["ip_address"] == "10.0.0.7" for r in expired)

    async def test_deactivate_ip_returns_true(self, db):
        uid = await db.create_user("207", "alice")
        ip_id = await db.add_ip_address(uid, "10.0.0.8", "2099-12-31 23:59:59")
        result = await db.deactivate_ip(ip_id)
        assert result is True

    async def test_deactivate_ip_hides_from_active(self, db):
        uid = await db.create_user("208", "alice")
        ip_id = await db.add_ip_address(uid, "10.0.0.9", "2099-12-31 23:59:59")
        await db.deactivate_ip(ip_id)
        ips = await db.get_user_active_ips(uid)
        assert not any(r["ip_address"] == "10.0.0.9" for r in ips)

    async def test_deactivate_unknown_id_returns_false(self, db):
        result = await db.deactivate_ip(99999)
        assert result is False


# ---------------------------------------------------------------------------
# Request history / rate limiting
# ---------------------------------------------------------------------------


class TestRequestHistory:
    """Tests for log_request and get_recent_requests."""

    async def test_log_request_stores_entry(self, db):
        uid = await db.create_user("300", "alice")
        await db.log_request(uid, "access_request", success=True)
        count = await db.get_recent_requests(uid, "access_request", minutes=5)
        assert count == 1

    async def test_get_recent_requests_zero_when_empty(self, db):
        uid = await db.create_user("301", "alice")
        count = await db.get_recent_requests(uid, "access_request", minutes=5)
        assert count == 0

    async def test_get_recent_requests_counts_multiple(self, db):
        uid = await db.create_user("302", "alice")
        await db.log_request(uid, "access_request")
        await db.log_request(uid, "access_request")
        count = await db.get_recent_requests(uid, "access_request", minutes=5)
        assert count == 2

    async def test_get_recent_requests_ignores_different_type(self, db):
        uid = await db.create_user("303", "alice")
        await db.log_request(uid, "other_event")
        count = await db.get_recent_requests(uid, "access_request", minutes=5)
        assert count == 0

    async def test_log_request_with_error_message(self, db):
        uid = await db.create_user("304", "alice")
        await db.log_request(
            uid, "access_request", success=False, error_message="Rate limited"
        )
        count = await db.get_recent_requests(uid, "access_request", minutes=5)
        assert count == 1
