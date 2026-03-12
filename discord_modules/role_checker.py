"""Role verification utilities for Discord bot.

This module provides functions to check if users have required roles.
"""

from typing import Optional

import discord

from config import Config
from utils.logger import get_logger

logger = get_logger(__name__)


def has_gameserver_role(member: discord.Member) -> bool:
    """Check if a member has the gameserver role.

    Args:
        member: Discord member to check.

    Returns:
        bool: True if member has the required role, False otherwise.
    """
    role_name = Config.GAMESERVER_ROLE_NAME
    has_role = any(role.name.lower() == role_name.lower() for role in member.roles)

    if has_role:
        logger.debug(f"User {member.name} (ID: {member.id}) has '{role_name}' role")
    else:
        logger.debug(
            f"User {member.name} (ID: {member.id}) does NOT have '{role_name}' role"
        )

    return has_role


async def get_member_in_guild(
    interaction: discord.Interaction,
) -> Optional[discord.Member]:
    """Get the member object from an interaction.

    Args:
        interaction: Discord interaction.

    Returns:
        discord.Member or None: Member if found in guild, None otherwise.
    """
    if interaction.guild is None:
        logger.warning("Interaction not in a guild context")
        return None

    if not isinstance(interaction.user, discord.Member):
        logger.warning(
            f"User {interaction.user.name} is not a Member object. "
            f"Attempting to fetch..."
        )
        try:
            member = await interaction.guild.fetch_member(interaction.user.id)
            return member
        except discord.NotFound:
            logger.error(f"Could not find member {interaction.user.id} in guild")
            return None
        except discord.HTTPException as e:
            logger.error(f"HTTP error fetching member: {e}")
            return None

    return interaction.user


async def verify_role_access(interaction: discord.Interaction) -> bool:
    """Verify that the user has the required role for access.

    Args:
        interaction: Discord interaction.

    Returns:
        bool: True if user has required role, False otherwise.
    """
    member = await get_member_in_guild(interaction)

    if member is None:
        logger.warning(
            f"Could not verify role for user {interaction.user.name} "
            f"(ID: {interaction.user.id})"
        )
        return False

    return has_gameserver_role(member)
