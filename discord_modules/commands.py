"""Discord slash commands for the Game Server Access Bot.

This module defines all slash commands for the bot.
"""

from datetime import datetime, timedelta

import discord

from config import Config
from database.models import Database
from discord_modules.bot import get_bot
from discord_modules.role_checker import verify_role_access
from utils.logger import get_logger
from utils.token_generator import generate_access_token

logger = get_logger(__name__)


async def setup_commands(db: Database) -> None:
    """Set up all slash commands for the bot.

    Args:
        db: Database instance to use for commands.
    """
    print("\n" + "=" * 60)
    print("📋 Setting up Discord commands...")
    print("=" * 60)
    logger.info("📋 Starting command setup...")

    bot = get_bot()

    @bot.tree.command(
        name="request-access",
        description="Request firewall access to the game server",
    )
    async def request_access(interaction: discord.Interaction):
        """Handle the /request-access command.

        This command generates a unique link for the user to verify their IP.
        """
        # Multiple logging methods to ensure visibility
        msg = (
            f"⚙️  COMMAND INVOKED: /request-access by "
            f"{interaction.user.name} (ID: {interaction.user.id})"
        )
        print("\n" + "=" * 60)
        print(f"🔔 {msg}")
        print(f"Guild: {interaction.guild.name if interaction.guild else 'DM'}")
        print("=" * 60 + "\n")

        logger.info("=" * 60)
        logger.info(msg)
        logger.info(f"Guild: {interaction.guild.name if interaction.guild else 'DM'}")
        logger.info("=" * 60)

        await interaction.response.defer(ephemeral=True)

        try:
            # Check if user has required role
            if not await verify_role_access(interaction):
                msg = (
                    f"🚫 Access DENIED: Missing "
                    f"'{Config.GAMESERVER_ROLE_NAME}' role"
                )
                print(msg)
                logger.info(msg)
                await interaction.followup.send(
                    f"❌ You need the **{Config.GAMESERVER_ROLE_NAME}** "
                    f"role to request server access.",
                    ephemeral=True,
                )
                return

            # Get or create user in database
            user = await db.get_user_by_discord_id(str(interaction.user.id))
            if user is None:
                user_id = await db.create_user(
                    str(interaction.user.id), interaction.user.name
                )
            else:
                user_id = user["id"]

            # Check rate limiting
            recent_requests = await db.get_recent_requests(
                user_id, "access_request", Config.RATE_LIMIT_PERIOD_MINUTES
            )

            if recent_requests >= Config.RATE_LIMIT_REQUESTS:
                logger.info(
                    f"Rate limit exceeded for {interaction.user.name} "
                    f"({recent_requests} recent requests)"
                )
                await interaction.followup.send(
                    f"⏳ You've requested access recently. "
                    f"Please wait {Config.RATE_LIMIT_PERIOD_MINUTES} minutes "
                    f"before requesting again.",
                    ephemeral=True,
                )
                await db.log_request(
                    user_id,
                    "access_request",
                    success=False,
                    error_message="Rate limited",
                )
                return

            # Generate access token
            token = generate_access_token()
            expires_at = datetime.utcnow() + timedelta(
                minutes=Config.TOKEN_EXPIRATION_MINUTES
            )

            logger.info(
                f"Generated access token for {interaction.user.name} "
                f"(expires in {Config.TOKEN_EXPIRATION_MINUTES} minutes)"
            )

            # Save token to database
            await db.create_access_token(user_id, token, expires_at.isoformat())

            # Generate access URL
            access_url = f"{Config.WEB_BASE_URL}/check-ip/{token}"

            # Log the request
            await db.log_request(user_id, "access_request", success=True)

            # Send DM to user
            try:
                dm_message = (
                    f"🔗 **Game Server Access Request**\n\n"
                    f"Click the link below to verify your IP address and "
                    f"gain access to the game server:\n\n"
                    f"{access_url}\n\n"
                    f"⏰ This link expires in "
                    f"**{Config.TOKEN_EXPIRATION_MINUTES} minutes**.\n"
                    f"📝 Your IP will be granted access for "
                    f"**{Config.IP_EXPIRATION_DAYS} days**."
                )

                await interaction.user.send(dm_message)

                # Confirm in channel
                await interaction.followup.send(
                    "✅ I've sent you a DM with your access link! "
                    "Check your direct messages.",
                    ephemeral=True,
                )

                logger.info(
                    f"Access link sent to {interaction.user.name} "
                    f"(ID: {interaction.user.id})"
                )

            except discord.Forbidden:
                # User has DMs disabled
                await interaction.followup.send(
                    f"❌ I couldn't send you a DM. Please enable DMs from "
                    f"server members and try again.\n\n"
                    f"Alternatively, here's your access link "
                    f"(expires in {Config.TOKEN_EXPIRATION_MINUTES} minutes):\n"
                    f"{access_url}",
                    ephemeral=True,
                )
                logger.warning(f"Could not DM {interaction.user.name} - DMs disabled")

        except Exception as e:
            logger.error(f"Error in request_access command: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ An error occurred while processing your request. "
                "Please try again later or contact an administrator.",
                ephemeral=True,
            )

    print("\n" + "=" * 60)
    print("✅ Commands registered successfully")
    print("=" * 60 + "\n")
    logger.info("✅ Commands registered successfully")
    logger.info("Total commands registered: 1")
