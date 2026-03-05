"""Main entry point for Discord Game Server Access Bot.

This bot allows users with the "gameserver" role to request firewall access
by capturing their external IP and adding it to a Unifi firewall rule.
"""

import asyncio

from config import Config
from database.models import Database
from discord_modules.bot import initialize_bot
from discord_modules.commands import setup_commands
from utils.logger import setup_logger

# Set up logger
logger = setup_logger()


async def initialize_database() -> Database:
    """Initialize database connection and schema.

    Returns:
        Database: Initialized database instance.
    """
    logger.info("Initializing database...")
    db = Database(Config.DATABASE_PATH)
    await db.connect()
    await db.initialize_schema()
    logger.info(f"Database initialized at {Config.DATABASE_PATH}")
    return db


async def main():
    """Run the main bot application."""
    db = None
    bot = None

    try:
        # Display configuration
        logger.info("Starting Discord Game Server Access Bot")
        Config.display()

        # Validate configuration
        logger.info("Validating configuration...")
        Config.validate()
        logger.info("✅ Configuration valid")

        # Initialize database
        db = await initialize_database()

        # Initialize Discord bot
        logger.info("Initializing Discord bot...")
        bot = initialize_bot()
        logger.info("✅ Discord bot initialized")

        # Set up commands
        logger.info("Setting up bot commands...")
        await setup_commands(db)
        logger.info("✅ Bot commands set up")

        # TODO: Initialize web server
        logger.info("Web server initialization will be implemented in Phase 3")

        # TODO: Initialize scheduler for cleanup tasks
        logger.info("Scheduler initialization will be implemented in Phase 4")

        logger.info("✅ Bot initialization complete")
        logger.info("Starting Discord bot...")

        # Start the bot
        await bot.start(Config.DISCORD_BOT_TOKEN)

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise
    finally:
        # Cleanup
        if db:
            await db.close()
            logger.info("Database connection closed")

        if bot and not bot.is_closed():
            await bot.close()
            logger.info("Discord bot connection closed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}", exc_info=True)
        exit(1)
