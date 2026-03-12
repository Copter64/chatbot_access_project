"""Tests for Discord role checking and command logic.

Discord network calls are fully mocked — no live bot connection needed.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from discord_modules.role_checker import (
    get_member_in_guild,
    has_gameserver_role,
    verify_role_access,
)

# Pin the role name to a known value so tests are independent of .env
ROLE_NAME = "gameserver"


@pytest.fixture(autouse=True)
def patch_config_role_name():
    """Patch Config.GAMESERVER_ROLE_NAME for all tests in this module."""
    with patch("discord_modules.role_checker.Config") as mock_cfg:
        mock_cfg.GAMESERVER_ROLE_NAME = ROLE_NAME
        yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_role(name: str) -> discord.Role:
    """Return a minimal mock discord.Role."""
    role = MagicMock(spec=discord.Role)
    role.name = name
    return role


def _make_member(role_names: list) -> discord.Member:
    """Return a mock discord.Member with the given role names."""
    member = MagicMock(spec=discord.Member)
    member.name = "testuser"
    member.id = 123456789
    member.roles = [_make_role(r) for r in role_names]
    return member


def _make_interaction(member=None, in_guild: bool = True):
    """Return a mock discord.Interaction."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild = MagicMock() if in_guild else None
    interaction.user = member or _make_member([])
    return interaction


# ---------------------------------------------------------------------------
# has_gameserver_role
# ---------------------------------------------------------------------------


class TestHasGameserverRole:
    """Tests for the has_gameserver_role() helper."""

    def test_returns_true_when_role_present(self):
        member = _make_member(["gameserver"])
        assert has_gameserver_role(member) is True

    def test_returns_false_when_role_absent(self):
        member = _make_member(["admin", "member"])
        assert has_gameserver_role(member) is False

    def test_case_insensitive_match(self):
        member = _make_member(["GameServer"])
        assert has_gameserver_role(member) is True

    def test_returns_false_for_empty_roles(self):
        member = _make_member([])
        assert has_gameserver_role(member) is False

    def test_returns_true_with_multiple_roles_including_gameserver(self):
        member = _make_member(["admin", "gameserver", "member"])
        assert has_gameserver_role(member) is True

    def test_returns_false_for_similar_but_wrong_role_name(self):
        member = _make_member(["gameservers", "game_server"])
        assert has_gameserver_role(member) is False


# ---------------------------------------------------------------------------
# get_member_in_guild
# ---------------------------------------------------------------------------


class TestGetMemberInGuild:
    """Tests for the get_member_in_guild() coroutine."""

    async def test_returns_none_when_no_guild(self):
        interaction = _make_interaction(in_guild=False)
        result = await get_member_in_guild(interaction)
        assert result is None

    async def test_returns_member_when_user_is_member_instance(self):
        member = _make_member(["gameserver"])
        # isinstance(member, discord.Member) must be True
        interaction = _make_interaction(member=member)
        # Patch isinstance so our mock is treated as discord.Member
        with patch("discord_modules.role_checker.isinstance", return_value=True):
            result = await get_member_in_guild(interaction)
        assert result is member

    async def test_fetches_member_when_user_is_not_member_instance(self):
        """When user is a discord.User (not Member), fetch_member is called."""
        user = MagicMock(spec=discord.User)
        user.name = "testuser"
        user.id = 111
        fetched_member = _make_member(["gameserver"])

        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = MagicMock()
        interaction.guild.fetch_member = AsyncMock(return_value=fetched_member)
        interaction.user = user

        result = await get_member_in_guild(interaction)
        assert result is fetched_member
        interaction.guild.fetch_member.assert_called_once_with(user.id)

    async def test_returns_none_when_fetch_raises_not_found(self):
        user = MagicMock(spec=discord.User)
        user.name = "ghost"
        user.id = 999

        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = MagicMock()
        interaction.guild.fetch_member = AsyncMock(
            side_effect=discord.NotFound(MagicMock(), "not found")
        )
        interaction.user = user

        result = await get_member_in_guild(interaction)
        assert result is None

    async def test_returns_none_when_fetch_raises_http_exception(self):
        user = MagicMock(spec=discord.User)
        user.name = "ghost"
        user.id = 888

        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = MagicMock()
        interaction.guild.fetch_member = AsyncMock(
            side_effect=discord.HTTPException(MagicMock(), "error")
        )
        interaction.user = user

        result = await get_member_in_guild(interaction)
        assert result is None


# ---------------------------------------------------------------------------
# verify_role_access
# ---------------------------------------------------------------------------


class TestVerifyRoleAccess:
    """Tests for the verify_role_access() coroutine."""

    async def test_returns_false_when_not_in_guild(self):
        interaction = _make_interaction(in_guild=False)
        result = await verify_role_access(interaction)
        assert result is False

    async def test_returns_true_with_valid_role(self):
        member = _make_member(["gameserver"])
        interaction = _make_interaction(member=member)
        with patch("discord_modules.role_checker.isinstance", return_value=True):
            result = await verify_role_access(interaction)
        assert result is True

    async def test_returns_false_without_required_role(self):
        member = _make_member(["admin"])
        interaction = _make_interaction(member=member)
        with patch("discord_modules.role_checker.isinstance", return_value=True):
            result = await verify_role_access(interaction)
        assert result is False
