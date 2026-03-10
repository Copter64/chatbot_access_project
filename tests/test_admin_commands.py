"""Tests for admin slash commands: /list-ips, /remove-ip, /add-ip.

Strategy: mock `get_bot()` so `bot.tree.command()` captures the handler
closures without needing a live bot.  Each handler is then called directly
with a mock discord.Interaction.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from discord_modules.commands import _validate_ip, is_admin, setup_commands


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ADMIN_ID = 111111111111111111
NON_ADMIN_ID = 999999999999999999


def _make_interaction(user_id: int = ADMIN_ID, guild: bool = True):
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock(spec=discord.Member)
    interaction.user.id = user_id
    interaction.user.name = "testadmin"
    interaction.user.mention = f"<@{user_id}>"
    interaction.guild = MagicMock() if guild else None
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    return interaction


def _make_member(user_id: int = 55555, name: str = "player"):
    m = MagicMock(spec=discord.Member)
    m.id = user_id
    m.name = name
    m.mention = f"<@{user_id}>"
    return m


def _make_db(
    all_active_ips=None,
    active_ip_record=None,
    user_id_return=42,
    user_row=None,
    active_ips_for_user=None,
):
    db = MagicMock()
    db.get_all_active_ips = AsyncMock(
        return_value=all_active_ips if all_active_ips is not None else []
    )
    db.get_active_ip_by_address = AsyncMock(return_value=active_ip_record)
    db.deactivate_ip = AsyncMock(return_value=True)
    db.create_user = AsyncMock(return_value=user_id_return)
    db.add_ip_address = AsyncMock(return_value=1)
    db.get_user_by_discord_id = AsyncMock(return_value=user_row)
    db.get_user_active_ips = AsyncMock(
        return_value=active_ips_for_user if active_ips_for_user is not None else []
    )
    return db


def _make_unifi(add_result=True, remove_result=True):
    u = MagicMock()
    u.add_ip = MagicMock(return_value=add_result)
    u.remove_ip = MagicMock(return_value=remove_result)
    return u


async def _get_handlers(db, unifi_manager=None):
    """Run setup_commands with a fake bot and return captured handlers."""
    handlers = {}

    def fake_command(name="", description="", **kwargs):
        def decorator(fn):
            handlers[name] = fn
            return fn

        return decorator

    mock_bot = MagicMock()
    mock_bot.tree.command.side_effect = fake_command

    with patch("discord_modules.commands.get_bot", return_value=mock_bot):
        with patch("discord_modules.commands.Config") as mock_cfg:
            mock_cfg.GAMESERVER_ROLE_NAME = "gameserver"
            mock_cfg.ADMIN_DISCORD_USER_IDS = [ADMIN_ID]
            mock_cfg.RATE_LIMIT_PERIOD_MINUTES = 60
            mock_cfg.RATE_LIMIT_REQUESTS = 5
            mock_cfg.TOKEN_EXPIRATION_MINUTES = 15
            mock_cfg.IP_EXPIRATION_DAYS = 30
            await setup_commands(db, unifi_manager=unifi_manager)

    return handlers


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


class TestIsAdmin:
    """Tests for the is_admin() helper."""

    def test_returns_true_for_admin(self):
        interaction = _make_interaction(user_id=ADMIN_ID)
        with patch(
            "discord_modules.commands.Config"
        ) as mock_cfg:
            mock_cfg.ADMIN_DISCORD_USER_IDS = [ADMIN_ID]
            assert is_admin(interaction) is True

    def test_returns_false_for_non_admin(self):
        interaction = _make_interaction(user_id=NON_ADMIN_ID)
        with patch(
            "discord_modules.commands.Config"
        ) as mock_cfg:
            mock_cfg.ADMIN_DISCORD_USER_IDS = [ADMIN_ID]
            assert is_admin(interaction) is False

    def test_returns_false_when_no_admins_configured(self):
        interaction = _make_interaction(user_id=ADMIN_ID)
        with patch(
            "discord_modules.commands.Config"
        ) as mock_cfg:
            mock_cfg.ADMIN_DISCORD_USER_IDS = []
            assert is_admin(interaction) is False


class TestValidateIp:
    """Tests for the _validate_ip() helper."""

    def test_valid_ipv4(self):
        assert _validate_ip("8.8.8.8") is True

    def test_valid_ipv6(self):
        assert _validate_ip("2001:4860:4860::8888") is True

    def test_invalid_string(self):
        assert _validate_ip("not-an-ip") is False

    def test_empty_string(self):
        assert _validate_ip("") is False

    def test_out_of_range_octet(self):
        assert _validate_ip("999.0.0.1") is False


# ---------------------------------------------------------------------------
# /list-ips
# ---------------------------------------------------------------------------


class TestListIps:
    """Tests for the /list-ips admin command."""

    async def test_non_admin_is_rejected(self):
        db = _make_db()
        handlers = await _get_handlers(db)
        interaction = _make_interaction(user_id=NON_ADMIN_ID)

        with patch("discord_modules.commands.Config") as mock_cfg:
            mock_cfg.ADMIN_DISCORD_USER_IDS = [ADMIN_ID]
            await handlers["list-ips"](interaction)

        interaction.followup.send.assert_awaited_once()
        msg = interaction.followup.send.call_args[0][0]
        assert "permission" in msg

    async def test_empty_result_message(self):
        db = _make_db(all_active_ips=[])
        handlers = await _get_handlers(db)
        interaction = _make_interaction(user_id=ADMIN_ID)

        with patch("discord_modules.commands.Config") as mock_cfg:
            mock_cfg.ADMIN_DISCORD_USER_IDS = [ADMIN_ID]
            await handlers["list-ips"](interaction)

        msg = interaction.followup.send.call_args[0][0]
        assert "No active" in msg

    async def test_returns_all_ips_when_no_user_filter(self):
        ips = [
            {
                "ip_address": "1.2.3.4",
                "expires_at": "2026-04-07T00:00:00",
                "discord_username": "alice",
                "discord_id": "123",
                "user_id": 1,
            }
        ]
        db = _make_db(all_active_ips=ips)
        handlers = await _get_handlers(db)
        interaction = _make_interaction(user_id=ADMIN_ID)

        with patch("discord_modules.commands.Config") as mock_cfg:
            mock_cfg.ADMIN_DISCORD_USER_IDS = [ADMIN_ID]
            await handlers["list-ips"](interaction)

        msg = interaction.followup.send.call_args[0][0]
        assert "1.2.3.4" in msg
        assert "1 total" in msg

    async def test_user_filter_with_no_db_record(self):
        db = _make_db(user_row=None)
        handlers = await _get_handlers(db)
        interaction = _make_interaction(user_id=ADMIN_ID)
        member = _make_member()

        with patch("discord_modules.commands.Config") as mock_cfg:
            mock_cfg.ADMIN_DISCORD_USER_IDS = [ADMIN_ID]
            await handlers["list-ips"](interaction, user=member)

        msg = interaction.followup.send.call_args[0][0]
        assert "No records" in msg

    async def test_truncates_at_20_entries(self):
        ips = [
            {
                "ip_address": f"10.0.0.{i}",
                "expires_at": "2026-04-07T00:00:00",
                "discord_username": "user",
                "discord_id": "1",
                "user_id": 1,
            }
            for i in range(25)
        ]
        db = _make_db(all_active_ips=ips)
        handlers = await _get_handlers(db)
        interaction = _make_interaction(user_id=ADMIN_ID)

        with patch("discord_modules.commands.Config") as mock_cfg:
            mock_cfg.ADMIN_DISCORD_USER_IDS = [ADMIN_ID]
            await handlers["list-ips"](interaction)

        msg = interaction.followup.send.call_args[0][0]
        assert "5 more" in msg


# ---------------------------------------------------------------------------
# /remove-ip
# ---------------------------------------------------------------------------


class TestRemoveIp:
    """Tests for the /remove-ip admin command."""

    async def test_non_admin_is_rejected(self):
        db = _make_db()
        handlers = await _get_handlers(db)
        interaction = _make_interaction(user_id=NON_ADMIN_ID)

        with patch("discord_modules.commands.Config") as mock_cfg:
            mock_cfg.ADMIN_DISCORD_USER_IDS = [ADMIN_ID]
            await handlers["remove-ip"](interaction, ip_address="1.2.3.4")

        msg = interaction.followup.send.call_args[0][0]
        assert "permission" in msg

    async def test_invalid_ip_rejected(self):
        db = _make_db()
        handlers = await _get_handlers(db)
        interaction = _make_interaction(user_id=ADMIN_ID)

        with patch("discord_modules.commands.Config") as mock_cfg:
            mock_cfg.ADMIN_DISCORD_USER_IDS = [ADMIN_ID]
            await handlers["remove-ip"](interaction, ip_address="not-valid")

        msg = interaction.followup.send.call_args[0][0]
        assert "not a valid IP" in msg

    async def test_no_active_record_message(self):
        db = _make_db(active_ip_record=None)
        handlers = await _get_handlers(db)
        interaction = _make_interaction(user_id=ADMIN_ID)

        with patch("discord_modules.commands.Config") as mock_cfg:
            mock_cfg.ADMIN_DISCORD_USER_IDS = [ADMIN_ID]
            await handlers["remove-ip"](interaction, ip_address="1.2.3.4")

        msg = interaction.followup.send.call_args[0][0]
        assert "No active record" in msg

    async def test_successful_removal_with_unifi(self):
        record = {"id": 7, "ip_address": "1.2.3.4", "user_id": 1}
        db = _make_db(active_ip_record=record)
        unifi = _make_unifi(remove_result=True)
        handlers = await _get_handlers(db, unifi_manager=unifi)
        interaction = _make_interaction(user_id=ADMIN_ID)

        with patch("discord_modules.commands.Config") as mock_cfg:
            mock_cfg.ADMIN_DISCORD_USER_IDS = [ADMIN_ID]
            await handlers["remove-ip"](interaction, ip_address="1.2.3.4")

        db.deactivate_ip.assert_awaited_once_with(7)
        msg = interaction.followup.send.call_args[0][0]
        assert "deactivated" in msg

    async def test_removal_without_unifi(self):
        """When unifi_manager is None only the DB record is deactivated."""
        record = {"id": 5, "ip_address": "5.6.7.8", "user_id": 2}
        db = _make_db(active_ip_record=record)
        handlers = await _get_handlers(db, unifi_manager=None)
        interaction = _make_interaction(user_id=ADMIN_ID)

        with patch("discord_modules.commands.Config") as mock_cfg:
            mock_cfg.ADMIN_DISCORD_USER_IDS = [ADMIN_ID]
            await handlers["remove-ip"](interaction, ip_address="5.6.7.8")

        db.deactivate_ip.assert_awaited_once_with(5)
        msg = interaction.followup.send.call_args[0][0]
        assert "unavailable" in msg


# ---------------------------------------------------------------------------
# /add-ip
# ---------------------------------------------------------------------------


class TestAddIp:
    """Tests for the /add-ip admin command."""

    async def test_non_admin_is_rejected(self):
        db = _make_db()
        handlers = await _get_handlers(db)
        interaction = _make_interaction(user_id=NON_ADMIN_ID)
        member = _make_member()

        with patch("discord_modules.commands.Config") as mock_cfg:
            mock_cfg.ADMIN_DISCORD_USER_IDS = [ADMIN_ID]
            mock_cfg.IP_EXPIRATION_DAYS = 30
            await handlers["add-ip"](
                interaction, ip_address="1.2.3.4", user=member
            )

        msg = interaction.followup.send.call_args[0][0]
        assert "permission" in msg

    async def test_invalid_ip_rejected(self):
        db = _make_db()
        handlers = await _get_handlers(db)
        interaction = _make_interaction(user_id=ADMIN_ID)
        member = _make_member()

        with patch("discord_modules.commands.Config") as mock_cfg:
            mock_cfg.ADMIN_DISCORD_USER_IDS = [ADMIN_ID]
            mock_cfg.IP_EXPIRATION_DAYS = 30
            await handlers["add-ip"](
                interaction, ip_address="bad", user=member
            )

        msg = interaction.followup.send.call_args[0][0]
        assert "not a valid IP" in msg

    async def test_days_out_of_range_rejected(self):
        db = _make_db()
        handlers = await _get_handlers(db)
        interaction = _make_interaction(user_id=ADMIN_ID)
        member = _make_member()

        with patch("discord_modules.commands.Config") as mock_cfg:
            mock_cfg.ADMIN_DISCORD_USER_IDS = [ADMIN_ID]
            mock_cfg.IP_EXPIRATION_DAYS = 30
            await handlers["add-ip"](
                interaction, ip_address="1.2.3.4", user=member, days=400
            )

        msg = interaction.followup.send.call_args[0][0]
        assert "between 1 and 365" in msg

    async def test_successful_add_with_unifi(self):
        db = _make_db(user_id_return=42)
        unifi = _make_unifi(add_result=True)
        handlers = await _get_handlers(db, unifi_manager=unifi)
        interaction = _make_interaction(user_id=ADMIN_ID)
        member = _make_member()

        with patch("discord_modules.commands.Config") as mock_cfg:
            mock_cfg.ADMIN_DISCORD_USER_IDS = [ADMIN_ID]
            mock_cfg.IP_EXPIRATION_DAYS = 30
            await handlers["add-ip"](
                interaction, ip_address="1.2.3.4", user=member
            )

        db.add_ip_address.assert_awaited_once()
        msg = interaction.followup.send.call_args[0][0]
        assert "saved" in msg

    async def test_successful_add_without_unifi(self):
        db = _make_db(user_id_return=10)
        handlers = await _get_handlers(db, unifi_manager=None)
        interaction = _make_interaction(user_id=ADMIN_ID)
        member = _make_member()

        with patch("discord_modules.commands.Config") as mock_cfg:
            mock_cfg.ADMIN_DISCORD_USER_IDS = [ADMIN_ID]
            mock_cfg.IP_EXPIRATION_DAYS = 30
            await handlers["add-ip"](
                interaction, ip_address="2.3.4.5", user=member
            )

        db.add_ip_address.assert_awaited_once()
        msg = interaction.followup.send.call_args[0][0]
        assert "unavailable" in msg

    async def test_custom_days_used(self):
        db = _make_db(user_id_return=3)
        handlers = await _get_handlers(db)
        interaction = _make_interaction(user_id=ADMIN_ID)
        member = _make_member()

        with patch("discord_modules.commands.Config") as mock_cfg:
            mock_cfg.ADMIN_DISCORD_USER_IDS = [ADMIN_ID]
            mock_cfg.IP_EXPIRATION_DAYS = 30
            await handlers["add-ip"](
                interaction, ip_address="9.9.9.9", user=member, days=7
            )

        msg = interaction.followup.send.call_args[0][0]
        assert "7 days" in msg
