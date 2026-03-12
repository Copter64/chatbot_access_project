"""Discord bot client initialization and event handlers.

This module sets up the Discord bot with proper intents and event handlers.
"""

import discord
from discord import app_commands
from datetime import datetime, timezone
from typing import Optional

from config import Config
from utils.logger import get_logger

logger = get_logger(__name__)


class GameServerBot(discord.Client):
    """Discord bot client for game server access management."""

    def __init__(self):
        """Initialize the Discord bot with required intents."""
        # Set up intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True

        super().__init__(intents=intents)

        # Command tree for slash commands
        self.tree = app_commands.CommandTree(self)
        self.guild_id = None

    async def setup_hook(self):
        """Set up hook called when bot is ready."""
        # Parse guild ID
        try:
            self.guild_id = int(Config.DISCORD_GUILD_ID)
            guild = discord.Object(id=self.guild_id)

            # Copy global commands to guild for faster updates during development
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)

            logger.info(f"✅ Commands synced to guild {self.guild_id}")
            print(f"\n✅ Commands synced to guild {self.guild_id}\n")
        except ValueError:
            logger.error(f"Invalid DISCORD_GUILD_ID: {Config.DISCORD_GUILD_ID}")
            raise

        # Set up command tree error handler
        @self.tree.error
        async def on_app_command_error(
            interaction: discord.Interaction,
            error: app_commands.AppCommandError,
        ):
            msg = f"App command error in " f"'{interaction.command.name}': {error}"
            logger.error(msg, exc_info=True)
            print(f"❌ {msg}\n")

    async def on_ready(self):
        """Event handler called when bot is ready."""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guild(s)")
        logger.info("Bot is ready!")

    async def on_interaction(self, interaction: discord.Interaction):
        """Event handler for all interactions."""
        if interaction.type == discord.InteractionType.application_command:
            logger.info(
                f"Command '/{interaction.command.name}' used by "
                f"{interaction.user.name} (ID: {interaction.user.id}) "
                f"in {interaction.guild.name if interaction.guild else 'DM'}"
            )

    async def on_error(self, event: str, *args, **kwargs):
        """Event handler for errors."""
        logger.error(f"Error in event {event}", exc_info=True)

    async def send_admin_alert(self, ip: str, detail: str) -> None:
        """Send a security alert DM to all configured admin Discord users.

        Called by the web security manager when a brute-force threshold is
        reached. Silently skips admins with DMs disabled or invalid IDs.

        Args:
            ip: The offending client IP address.
            detail: Human-readable description of the suspicious activity.
        """
        if not Config.ADMIN_DISCORD_USER_IDS:
            logger.warning(
                "Security alert triggered but ADMIN_DISCORD_USER_IDS "
                "is not configured — alert not delivered."
            )
            return

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        message = (
            f"⚠️ **Security Alert — Possible Brute-Force Attempt**\n"
            f"**IP Address:** `{ip}`\n"
            f"**Details:** {detail}\n"
            f"**Time:** {timestamp}"
        )

        for user_id in Config.ADMIN_DISCORD_USER_IDS:
            try:
                user = await self.fetch_user(user_id)
                await user.send(message)
                logger.info(f"Security alert sent to admin user_id={user_id}")
            except discord.Forbidden:
                logger.warning(
                    f"Cannot DM admin {user_id}: DMs disabled or bot blocked"
                )
            except discord.NotFound:
                logger.warning(f"Admin user {user_id} not found")
            except Exception as exc:
                logger.error(
                    f"Error sending security alert to admin {user_id}: {exc}",
                    exc_info=True,
                )

    async def send_server_info_dm(
        self, discord_user_id: str, ip: str, expires: str
    ) -> None:
        """Send a server connection info DM to a user after IP confirmation.

        Builds the message from GAMESERVER_* config values. If
        GAMESERVER_HOST is not configured, only the access-granted
        confirmation is sent. Silently skips users with DMs disabled.

        Args:
            discord_user_id: Discord user ID string to DM.
            ip: The confirmed IP address that was added to the firewall.
            expires: Expiry date string in YYYY-MM-DD format.
        """
        lines = [
            "✅ **Access Granted!**\n",
            f"Your IP `{ip}` has been added to the server firewall.",
            f"Access expires on **{expires}**.",
        ]

        if Config.GAMESERVER_HOST:
            server_name = Config.GAMESERVER_NAME or "Game Server"
            lines.append(f"\n🎮 **{server_name} — Connection Info**")
            lines.append(f"🌐 Host: `{Config.GAMESERVER_HOST}`")
            if Config.GAMESERVER_PORT:
                lines.append(f"🔌 Port: `{Config.GAMESERVER_PORT}`")
            if Config.GAMESERVER_PASSWORD:
                lines.append(f"🔑 Password: `{Config.GAMESERVER_PASSWORD}`")
            if Config.GAMESERVER_EXTRA_INFO:
                lines.append(f"\n📝 {Config.GAMESERVER_EXTRA_INFO}")

        message = "\n".join(lines)

        try:
            user = await self.fetch_user(int(discord_user_id))
            await user.send(message)
            logger.info(
                f"Server info DM sent to discord_user_id={discord_user_id}"
            )
        except discord.Forbidden:
            logger.warning(
                f"Cannot DM user {discord_user_id}: DMs disabled or bot blocked"
            )
        except discord.NotFound:
            logger.warning(f"User {discord_user_id} not found")
        except Exception as exc:
            logger.error(
                f"Error sending server info DM to {discord_user_id}: {exc}",
                exc_info=True,
            )


# Global bot instance
bot: Optional[GameServerBot] = None


def get_bot() -> GameServerBot:
    """Get the bot instance.

    Returns:
        GameServerBot: The bot instance.

    Raises:
        RuntimeError: If bot has not been initialized.
    """
    if bot is None:
        raise RuntimeError("Bot has not been initialized. Call initialize_bot() first.")
    return bot


def initialize_bot() -> GameServerBot:
    """Initialize and return the bot instance.

    Returns:
        GameServerBot: The initialized bot instance.
    """
    global bot
    if bot is None:
        bot = GameServerBot()
        logger.info("Discord bot initialized")
    return bot
