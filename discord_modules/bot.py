"""Discord bot client initialization and event handlers.

This module sets up the Discord bot with proper intents and event handlers.
"""

import discord
from discord import app_commands
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
