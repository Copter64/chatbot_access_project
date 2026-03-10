"""Discord slash commands for the Game Server Access Bot.

This module defines all slash commands for the bot.
"""

import asyncio
import ipaddress
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands

from config import Config
from database.models import Database
from discord_modules.bot import get_bot
from discord_modules.role_checker import verify_role_access
from utils.logger import get_logger
from utils.token_generator import generate_access_token

logger = get_logger(__name__)


def is_admin(interaction: discord.Interaction) -> bool:
    """Return True if the interaction user is a configured admin.

    Args:
        interaction: Discord interaction to check.

    Returns:
        bool: True when the user's ID is in Config.ADMIN_DISCORD_USER_IDS.
    """
    return interaction.user.id in Config.ADMIN_DISCORD_USER_IDS


def _validate_ip(ip_str: str) -> bool:
    """Return True if *ip_str* is a valid, publicly routable IP address.

    Rejects RFC 1918 private addresses, loopback, link-local, and all
    other non-globally-routable ranges, in addition to malformed strings.

    Args:
        ip_str: IP address string to validate.

    Returns:
        bool: True if the address is valid and globally routable.
    """
    try:
        return ipaddress.ip_address(ip_str).is_global
    except ValueError:
        return False


async def setup_commands(db: Database, unifi_manager=None) -> None:
    """Set up all slash commands for the bot.

    Args:
        db: Database instance to use for commands.
        unifi_manager: Optional Unifi firewall manager for admin commands.
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
            expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
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

    # ------------------------------------------------------------------
    # Admin: /list-ips
    # ------------------------------------------------------------------

    @bot.tree.command(
        name="list-ips",
        description="[Admin] List active firewall IPs",
    )
    @app_commands.describe(
        user="Optional: filter by a specific Discord member"
    )
    async def list_ips(
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None,
    ):
        """Handle the /list-ips admin command."""
        await interaction.response.defer(ephemeral=True)

        if not is_admin(interaction):
            await interaction.followup.send(
                "❌ You don't have permission to use this command.",
                ephemeral=True,
            )
            return

        try:
            if user is not None:
                db_user = await db.get_user_by_discord_id(str(user.id))
                if db_user is None:
                    await interaction.followup.send(
                        f"ℹ️ No records found for {user.mention}.",
                        ephemeral=True,
                    )
                    return
                ips = await db.get_user_active_ips(db_user["id"])
                rows = [
                    {
                        **ip,
                        "discord_username": user.name,
                        "discord_id": str(user.id),
                    }
                    for ip in ips
                ]
            else:
                rows = await db.get_all_active_ips()

            if not rows:
                await interaction.followup.send(
                    "ℹ️ No active firewall IPs found.", ephemeral=True
                )
                return

            lines = [f"**Active firewall IPs ({len(rows)} total)**"]
            for r in rows[:20]:  # Discord 2000-char limit guard
                lines.append(
                    f"`{r['ip_address']}` — "
                    f"{r.get('discord_username', 'unknown')} — "
                    f"expires {r['expires_at'][:10]}"
                )
            if len(rows) > 20:
                lines.append(f"*…and {len(rows) - 20} more*")

            await interaction.followup.send(
                "\n".join(lines), ephemeral=True
            )
            logger.info(
                f"Admin {interaction.user.name} listed "
                f"{len(rows)} active IPs"
            )

        except Exception as exc:
            logger.error(f"Error in list_ips: {exc}", exc_info=True)
            await interaction.followup.send(
                "❌ An error occurred fetching IP list.", ephemeral=True
            )

    # ------------------------------------------------------------------
    # Admin: /remove-ip
    # ------------------------------------------------------------------

    @bot.tree.command(
        name="remove-ip",
        description="[Admin] Remove an IP from the firewall and database",
    )
    @app_commands.describe(ip_address="The IP address to remove")
    async def remove_ip_cmd(
        interaction: discord.Interaction, ip_address: str
    ):
        """Handle the /remove-ip admin command."""
        await interaction.response.defer(ephemeral=True)

        if not is_admin(interaction):
            await interaction.followup.send(
                "❌ You don't have permission to use this command.",
                ephemeral=True,
            )
            return

        if not _validate_ip(ip_address):
            await interaction.followup.send(
                f"❌ `{ip_address}` is not a valid IP address.",
                ephemeral=True,
            )
            return

        try:
            record = await db.get_active_ip_by_address(ip_address)
            if record is None:
                await interaction.followup.send(
                    f"ℹ️ No active record found for `{ip_address}`.",
                    ephemeral=True,
                )
                return

            # Remove from Unifi (blocking call → executor)
            unifi_ok = False
            unifi_note = "(Unifi unavailable — DB-only removal)"
            if unifi_manager is not None:
                loop = asyncio.get_event_loop()
                try:
                    unifi_ok = await loop.run_in_executor(
                        None, lambda: unifi_manager.remove_ip(ip_address)
                    )
                    unifi_note = (
                        "✅ Removed from Unifi"
                        if unifi_ok
                        else "⚠️ IP not found in Unifi group"
                    )
                except Exception as exc:
                    logger.error(
                        f"Unifi remove_ip failed for {ip_address}: {exc}"
                    )
                    unifi_note = f"⚠️ Unifi error: {exc}"

            # Deactivate in DB
            await db.deactivate_ip(record["id"])

            await interaction.followup.send(
                f"🗑️ Removed `{ip_address}` from firewall.\n"
                f"Database: ✅ deactivated\n"
                f"Unifi: {unifi_note}",
                ephemeral=True,
            )
            logger.info(
                f"Admin {interaction.user.name} removed IP "
                f"{ip_address} (DB id={record['id']})"
            )

        except Exception as exc:
            logger.error(f"Error in remove_ip_cmd: {exc}", exc_info=True)
            await interaction.followup.send(
                "❌ An error occurred removing the IP.", ephemeral=True
            )

    # ------------------------------------------------------------------
    # Admin: /add-ip
    # ------------------------------------------------------------------

    @bot.tree.command(
        name="add-ip",
        description="[Admin] Manually add an IP to the firewall for a user",
    )
    @app_commands.describe(
        ip_address="The IP address to add",
        user="The Discord member this IP belongs to",
        days="Access duration in days (default: configured expiry)",
    )
    async def add_ip_cmd(
        interaction: discord.Interaction,
        ip_address: str,
        user: discord.Member,
        days: Optional[int] = None,
    ):
        """Handle the /add-ip admin command."""
        await interaction.response.defer(ephemeral=True)

        if not is_admin(interaction):
            await interaction.followup.send(
                "❌ You don't have permission to use this command.",
                ephemeral=True,
            )
            return

        if not _validate_ip(ip_address):
            await interaction.followup.send(
                f"❌ `{ip_address}` is not a valid IP address (private/non-routable IPs are not accepted).",
                ephemeral=True,
            )
            return

        duration = days if days is not None else Config.IP_EXPIRATION_DAYS
        if duration < 1 or duration > 365:
            await interaction.followup.send(
                "❌ Days must be between 1 and 365.", ephemeral=True
            )
            return

        try:
            # Ensure user exists in DB
            user_id = await db.create_user(str(user.id), user.name)

            expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
                days=duration
            )

            # Add to Unifi (blocking call → executor)
            unifi_ok = False
            unifi_note = "(Unifi unavailable — DB-only add)"
            if unifi_manager is not None:
                loop = asyncio.get_event_loop()
                try:
                    unifi_ok = await loop.run_in_executor(
                        None, lambda: unifi_manager.add_ip(ip_address)
                    )
                    unifi_note = (
                        "✅ Added to Unifi"
                        if unifi_ok
                        else "⚠️ Already in Unifi group"
                    )
                except Exception as exc:
                    logger.error(
                        f"Unifi add_ip failed for {ip_address}: {exc}"
                    )
                    unifi_note = f"⚠️ Unifi error: {exc}"

            # Upsert in DB
            await db.add_ip_address(
                user_id, ip_address, expires_at.isoformat()
            )

            await interaction.followup.send(
                f"✅ Added `{ip_address}` for {user.mention} "
                f"({duration} days).\n"
                f"Database: ✅ saved\n"
                f"Unifi: {unifi_note}",
                ephemeral=True,
            )
            logger.info(
                f"Admin {interaction.user.name} added IP {ip_address} "
                f"for {user.name} ({duration} days)"
            )

        except Exception as exc:
            logger.error(f"Error in add_ip_cmd: {exc}", exc_info=True)
            await interaction.followup.send(
                "❌ An error occurred adding the IP.", ephemeral=True
            )

    print("\n" + "=" * 60)
    print("✅ Commands registered successfully")
    print("=" * 60 + "\n")
    logger.info("✅ Commands registered successfully")
    logger.info("Total commands registered: 4")
