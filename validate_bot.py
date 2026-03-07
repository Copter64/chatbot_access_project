#!/usr/bin/env python3
"""Discord bot configuration validator and test script.

This script validates your bot configuration and can test the connection.
"""

import asyncio
import os
import sys

from config import Config
from utils.logger import setup_logger

logger = setup_logger("validator")


def check_env_file():
    """Check if .env file exists."""
    if not os.path.exists(".env"):
        logger.error("❌ .env file not found!")
        logger.info("   Copy .env.example to .env and fill in your values:")
        logger.info("   cp .env.example .env")
        return False
    logger.info("✅ .env file exists")
    return True


def check_bot_token():
    """Check if bot token is configured."""
    if not Config.DISCORD_BOT_TOKEN:
        logger.error("❌ DISCORD_BOT_TOKEN is not set in .env")
        return False

    if Config.DISCORD_BOT_TOKEN == "your_discord_bot_token_here":  # nosec B105
        logger.error("❌ DISCORD_BOT_TOKEN is still set to placeholder value")
        logger.info("   Get your bot token from:")
        logger.info("   https://discord.com/developers/applications")
        return False

    if Config.DISCORD_BOT_TOKEN.startswith("test_"):
        logger.warning("⚠️  DISCORD_BOT_TOKEN looks like a test value")
        logger.info("   Make sure to use your real bot token from Discord")
        return False

    # Check token format (Discord tokens are typically 70+ characters)
    if len(Config.DISCORD_BOT_TOKEN) < 50:
        logger.warning("⚠️  DISCORD_BOT_TOKEN seems too short")
        logger.info(f"   Token length: {len(Config.DISCORD_BOT_TOKEN)} chars")
        logger.info("   Discord tokens are usually 70+ characters")
        return False

    logger.info(f"✅ DISCORD_BOT_TOKEN is set ({len(Config.DISCORD_BOT_TOKEN)} chars)")
    return True


def check_guild_id():
    """Check if guild ID is configured."""
    if not Config.DISCORD_GUILD_ID:
        logger.error("❌ DISCORD_GUILD_ID is not set in .env")
        return False

    if Config.DISCORD_GUILD_ID == "your_discord_server_id_here":
        logger.error("❌ DISCORD_GUILD_ID is still set to placeholder value")
        logger.info("   Enable Developer Mode in Discord, right-click your")
        logger.info("   server icon, and select 'Copy Server ID'")
        return False

    if Config.DISCORD_GUILD_ID == "123456789":
        logger.warning("⚠️  DISCORD_GUILD_ID looks like a test value")
        return False

    # Guild IDs are numeric snowflakes (typically 17-20 digits)
    if not Config.DISCORD_GUILD_ID.isdigit():
        logger.error("❌ DISCORD_GUILD_ID must be numeric")
        return False

    if len(Config.DISCORD_GUILD_ID) < 17:
        logger.warning("⚠️  DISCORD_GUILD_ID seems too short")
        logger.info(f"   Guild ID: {Config.DISCORD_GUILD_ID}")
        logger.info("   Discord Guild IDs are usually 17-20 digits")

    logger.info(f"✅ DISCORD_GUILD_ID is set ({Config.DISCORD_GUILD_ID})")
    return True


def check_role_name():
    """Check role name configuration."""
    logger.info(f"✅ GAMESERVER_ROLE_NAME is set to: '{Config.GAMESERVER_ROLE_NAME}'")
    logger.info("   Make sure this role exists in your Discord server!")
    return True


async def test_bot_connection():
    """Test actual bot connection to Discord."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Discord Bot Connection...")
    logger.info("=" * 60 + "\n")

    try:
        from discord_modules.bot import initialize_bot

        bot = initialize_bot()

        logger.info("Attempting to connect to Discord...")
        logger.info("Press Ctrl+C to stop\n")

        # Set up a simple ready event to confirm connection
        @bot.event
        async def on_ready():
            logger.info("=" * 60)
            logger.info("✅ BOT CONNECTED SUCCESSFULLY!")
            logger.info("=" * 60)
            logger.info(f"Bot User: {bot.user.name}#{bot.user.discriminator}")
            logger.info(f"Bot ID: {bot.user.id}")
            logger.info(f"Connected to {len(bot.guilds)} guild(s):")

            for guild in bot.guilds:
                logger.info(f"  - {guild.name} (ID: {guild.id})")

                # Check if this is our configured guild
                if str(guild.id) == Config.DISCORD_GUILD_ID:
                    logger.info(f"\n✅ Found configured guild: {guild.name}")

                    # Check for the gameserver role
                    role_found = False
                    for role in guild.roles:
                        if role.name.lower() == Config.GAMESERVER_ROLE_NAME.lower():
                            logger.info(
                                f"✅ Found '{Config.GAMESERVER_ROLE_NAME}' "
                                f"role (ID: {role.id})"
                            )
                            role_found = True
                            break

                    if not role_found:
                        logger.warning(
                            f"⚠️  Role '{Config.GAMESERVER_ROLE_NAME}' "
                            f"not found in {guild.name}"
                        )
                        logger.info("   Available roles:")
                        for role in guild.roles:
                            if role.name != "@everyone":
                                logger.info(f"     - {role.name}")

            logger.info("\nCommands registered:")
            for command in bot.tree.get_commands():
                logger.info(f"  /{command.name} - {command.description}")

            logger.info("\n" + "=" * 60)
            logger.info("Bot is running. Press Ctrl+C to stop.")
            logger.info("Try /request-access in your Discord server!")
            logger.info("=" * 60 + "\n")

        await bot.start(Config.DISCORD_BOT_TOKEN)

    except KeyboardInterrupt:
        logger.info("\nBot stopped by user")
    except Exception as e:
        logger.error(f"\n❌ Bot connection failed: {e}", exc_info=True)
        logger.info("\nCommon issues:")
        logger.info("  1. Invalid bot token")
        logger.info("  2. Bot not invited to server")
        logger.info("  3. Missing intents in Discord Developer Portal")
        logger.info("  4. Network/firewall issues")
        return False
    finally:
        if "bot" in locals() and not bot.is_closed():
            await bot.close()

    return True


async def main():
    """Run configuration validation."""
    print("\n" + "=" * 60)
    print("Discord Bot Configuration Validator")
    print("=" * 60 + "\n")

    # Check configuration
    checks = [
        check_env_file(),
        check_bot_token(),
        check_guild_id(),
        check_role_name(),
    ]

    if not all(checks):
        logger.error("\n❌ Configuration validation failed!")
        logger.info("\n📖 See docs/DISCORD_SETUP.md for setup instructions")
        sys.exit(1)

    logger.info("\n" + "=" * 60)
    logger.info("✅ All configuration checks passed!")
    logger.info("=" * 60)

    # Ask if user wants to test connection
    print("\nDo you want to test the bot connection? (y/n): ", end="")
    response = input().strip().lower()

    if response in ["y", "yes"]:
        await test_bot_connection()
    else:
        logger.info("\nSkipping connection test.")
        logger.info("To test later, run: python3 validate_bot.py")

    logger.info("\n✅ Validation complete!")
    logger.info("\n📖 See docs/DISCORD_SETUP.md for more help")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nValidation cancelled by user")
        sys.exit(0)
