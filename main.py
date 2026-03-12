"""Main entry point for Discord Game Server Access Bot.

This bot allows users with the "gameserver" role to request firewall access
by capturing their external IP and adding it to a Unifi firewall rule.
"""

import asyncio

from config import Config
from database.models import Database
from discord_modules.bot import initialize_bot
from discord_modules.commands import setup_commands
from unifi_modules.client import UnifiClient
from unifi_modules.firewall import UnifiFirewallManager
from utils.logger import setup_logger
from utils.scheduler import start_scheduler, stop_scheduler
from web.app import create_app, run_web_server

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

        # Initialise Unifi firewall manager (best-effort — bot starts even
        # if Unifi is unreachable; login is lazy and happens on first IP add)
        unifi_manager = None
        try:
            logger.info("Initializing Unifi client...")
            unifi_client = UnifiClient(
                host=Config.UNIFI_HOST,
                username=Config.UNIFI_USERNAME,
                password=Config.UNIFI_PASSWORD,
                site=Config.UNIFI_SITE,
                verify_ssl=Config.UNIFI_VERIFY_SSL,
            )
            unifi_manager = UnifiFirewallManager(
                unifi_client, Config.FIREWALL_GROUP_NAME
            )
            logger.info(
                f"✅ Unifi client initialized "
                f"(group='{Config.FIREWALL_GROUP_NAME}', "
                f"host={Config.UNIFI_HOST})"
            )
        except Exception as exc:
            logger.error(
                f"Failed to initialize Unifi client: {exc} — "
                "IP confirmations will be saved to DB only until Unifi is available",
                exc_info=True,
            )

        # Set up commands (needs unifi_manager for admin commands)
        logger.info("Setting up bot commands...")
        await setup_commands(db, unifi_manager=unifi_manager)
        logger.info("✅ Bot commands set up")

        # Initialize and start web server in background thread
        logger.info("Initializing web server...")
        loop = asyncio.get_running_loop()

        # Build a sync alert callback that schedules an async bot DM
        def _alert_callback(ip: str, detail: str) -> None:
            """Fire-and-forget: schedule admin alert DM on the bot loop."""
            if bot is not None:
                asyncio.run_coroutine_threadsafe(bot.send_admin_alert(ip, detail), loop)

        def _server_info_callback(
            discord_user_id: str, ip: str, expires: str
        ) -> None:
            """Fire-and-forget: schedule server info DM on the bot loop."""
            if bot is not None:
                asyncio.run_coroutine_threadsafe(
                    bot.send_server_info_dm(discord_user_id, ip, expires), loop
                )

        flask_app = create_app(
            db,
            loop,
            alert_callback=_alert_callback,
            unifi_manager=unifi_manager,
            server_info_callback=_server_info_callback,
        )
        run_web_server(flask_app)
        logger.info(f"✅ Web server running at {Config.WEB_BASE_URL}")

        # Start the background cleanup scheduler
        start_scheduler(
            db,
            loop,
            unifi_manager=unifi_manager,
            interval_hours=Config.CLEANUP_INTERVAL_HOURS,
        )

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
        stop_scheduler()

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
