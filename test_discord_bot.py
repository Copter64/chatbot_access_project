#!/usr/bin/env python3
"""Comprehensive Discord bot testing suite.

This script tests all Phase 2 Discord bot functionality with your actual Discord server.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta

from config import Config
from database.models import Database
from discord_modules.bot import initialize_bot
from discord_modules.commands import setup_commands
from utils.logger import setup_logger
from utils.token_generator import generate_access_token

logger = setup_logger("test_suite")


class DiscordBotTestSuite:
    """Test suite for Discord bot functionality."""

    def __init__(self):
        """Initialize test suite."""
        self.test_results = []
        self.db = None
        self.bot = None

    async def setup(self):
        """Set up test environment."""
        logger.info("\n" + "=" * 70)
        logger.info("DISCORD BOT TEST SUITE - Setup Phase")
        logger.info("=" * 70)

        # Initialize database
        logger.info("\n1️⃣  Initializing test database...")
        self.db = Database("./test_discord_bot.db")
        await self.db.connect()
        await self.db.initialize_schema()
        logger.info("   ✅ Test database initialized")

        # Initialize bot
        logger.info("\n2️⃣  Initializing Discord bot...")
        self.bot = initialize_bot()
        logger.info("   ✅ Bot instance created")

        # Setup commands
        logger.info("\n3️⃣  Setting up commands...")
        await setup_commands(self.db)
        logger.info("   ✅ Commands registered")

    async def test_config(self):
        """Test configuration."""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 1: Configuration Validation")
        logger.info("=" * 70)

        tests = [
            ("Discord Bot Token set", bool(Config.DISCORD_BOT_TOKEN)),
            ("Discord Guild ID set", bool(Config.DISCORD_GUILD_ID)),
            ("Gameserver role name set", bool(Config.GAMESERVER_ROLE_NAME)),
            ("Token valid type", isinstance(Config.DISCORD_BOT_TOKEN, str)),
            ("Guild ID valid type", isinstance(Config.DISCORD_GUILD_ID, str)),
            ("IP expiration > 0", Config.IP_EXPIRATION_DAYS > 0),
            ("Token expiration > 0", Config.TOKEN_EXPIRATION_MINUTES > 0),
            ("Rate limit >= 1", Config.RATE_LIMIT_REQUESTS >= 1),
        ]

        for test_name, result in tests:
            status = "✅" if result else "❌"
            logger.info(f"   {status} {test_name}")
            self.test_results.append((test_name, result))

    async def test_database(self):
        """Test database operations."""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 2: Database Operations")
        logger.info("=" * 70)

        try:
            # Create user
            logger.info("\n   Testing user creation...")
            user_id = await self.db.create_user("999888777", "TestUser")
            logger.info(f"   ✅ User created with ID: {user_id}")

            # Retrieve user
            user = await self.db.get_user_by_discord_id("999888777")
            test_pass = user is not None and user["id"] == user_id
            logger.info(f"   {'✅' if test_pass else '❌'} User retrieved: {test_pass}")
            self.test_results.append(("User creation and retrieval", test_pass))

            # Create token
            logger.info("\n   Testing token creation...")
            token = generate_access_token()
            expires_at = datetime.utcnow() + timedelta(minutes=15)
            token_id = await self.db.create_access_token(
                user_id, token, expires_at.isoformat()
            )
            logger.info(f"   ✅ Token created with ID: {token_id}")

            # Retrieve token
            token_data = await self.db.get_token(token)
            test_pass = token_data is not None
            logger.info(
                f"   {'✅' if test_pass else '❌'} Token retrieved: {test_pass}"
            )
            self.test_results.append(("Token creation and retrieval", test_pass))

            # Mark token as used
            logger.info("\n   Testing token usage...")
            marked = await self.db.mark_token_used(token, "192.168.1.100")
            logger.info(f"   {'✅' if marked else '❌'} Token marked as used: {marked}")

            # Try to get token again (should fail)
            token_data_again = await self.db.get_token(token)
            test_pass = token_data_again is None
            logger.info(
                f"   {'✅' if test_pass else '❌'} "
                f"Used token cannot be reused: {test_pass}"
            )
            self.test_results.append(("Token one-time use enforcement", test_pass))

            # Add IP address
            logger.info("\n   Testing IP address addition...")
            ip_expires = datetime.utcnow() + timedelta(days=30)
            ip_id = await self.db.add_ip_address(
                user_id, "192.168.1.100", ip_expires.isoformat()
            )
            logger.info(f"   ✅ IP address added with ID: {ip_id}")

            # Get active IPs
            active_ips = await self.db.get_user_active_ips(user_id)
            test_pass = len(active_ips) == 1
            logger.info(
                f"   {'✅' if test_pass else '❌'} "
                f"Active IPs retrieved ({len(active_ips)} found)"
            )
            self.test_results.append(("IP address management", test_pass))

            # Test rate limiting
            logger.info("\n   Testing rate limiting...")
            await self.db.log_request(user_id, "access_request", success=True)
            await self.db.log_request(user_id, "access_request", success=True)
            recent = await self.db.get_recent_requests(user_id, "access_request", 5)
            test_pass = recent == 2
            logger.info(
                f"   {'✅' if test_pass else '❌'} "
                f"Rate limiting tracking ({recent} requests logged)"
            )
            self.test_results.append(("Rate limiting tracking", test_pass))

        except Exception as e:
            logger.error(f"   ❌ Database test failed: {e}", exc_info=True)
            self.test_results.append(("Database operations", False))

    async def test_bot_event_handlers(self):
        """Test bot event handlers."""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 3: Bot Event Handlers")
        logger.info("=" * 70)

        try:
            # Check bot has event handlers
            test_pass = hasattr(self.bot, "on_ready")
            logger.info(f"   {'✅' if test_pass else '❌'} Bot has on_ready handler")
            self.test_results.append(("on_ready event handler", test_pass))

            test_pass = hasattr(self.bot, "on_error")
            logger.info(f"   {'✅' if test_pass else '❌'} Bot has on_error handler")
            self.test_results.append(("on_error event handler", test_pass))

            # Check command tree
            test_pass = self.bot.tree is not None
            logger.info(f"   {'✅' if test_pass else '❌'} Bot has command tree")
            self.test_results.append(("Command tree configured", test_pass))

            # Check commands are registered
            commands = self.bot.tree.get_commands()
            test_pass = len(commands) > 0
            logger.info(
                f"   {'✅' if test_pass else '❌'} "
                f"Commands registered ({len(commands)} commands)"
            )

            for cmd in commands:
                logger.info(f"      - /{cmd.name}: {cmd.description}")

            self.test_results.append(("Commands registered", test_pass))

        except Exception as e:
            logger.error(f"   ❌ Bot event handler test failed: {e}")
            self.test_results.append(("Bot event handlers", False))

    async def test_token_generator(self):
        """Test token generation."""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 4: Token Generation Security")
        logger.info("=" * 70)

        try:
            tokens = set()
            logger.info("\n   Generating 10 tokens...")

            for i in range(10):
                token = generate_access_token()
                tokens.add(token)

            # Test uniqueness
            test_pass = len(tokens) == 10
            logger.info(
                f"   {'✅' if test_pass else '❌'} " f"All tokens unique: {test_pass}"
            )
            self.test_results.append(("Token uniqueness", test_pass))

            # Test length and format
            sample_token = list(tokens)[0]
            test_pass = 25 < len(sample_token) < 40
            logger.info(
                f"   {'✅' if test_pass else '❌'} "
                f"Token length valid (32 chars): {len(sample_token)} chars"
            )
            self.test_results.append(("Token length", test_pass))

            # Test character set (alphanumeric + -_)
            import string

            allowed = set(string.ascii_letters + string.digits + "-_")
            test_pass = all(c in allowed for c in sample_token)
            logger.info(
                f"   {'✅' if test_pass else '❌'} "
                f"Token uses safe characters: {test_pass}"
            )
            self.test_results.append(("Token character set", test_pass))

        except Exception as e:
            logger.error(f"   ❌ Token generation test failed: {e}")
            self.test_results.append(("Token generation", False))

    async def test_role_checker_logic(self):
        """Test role checking logic (without Discord)."""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 5: Role Checking Logic")
        logger.info("=" * 70)

        try:
            logger.info("\n   Note: This tests the logic without Discord.")
            logger.info("   Full role checking requires running bot in Discord server.")
            logger.info("   See: TEST 6 below for manual Discord testing.")

            # Test token format validation
            from utils.token_generator import is_valid_token_format

            test_pass = is_valid_token_format("valid_token_12345678901234567890")
            logger.info(f"   {'✅' if test_pass else '❌'} Valid token accepted")
            self.test_results.append(("Valid token format", test_pass))

            test_pass = not is_valid_token_format("bad")
            logger.info(f"   {'✅' if test_pass else '❌'} Invalid token rejected")
            self.test_results.append(("Invalid token rejected", test_pass))

            test_pass = not is_valid_token_format(None)
            logger.info(f"   {'✅' if test_pass else '❌'} None token rejected")
            self.test_results.append(("None token rejected", test_pass))

        except Exception as e:
            logger.error(f"   ❌ Role checker test failed: {e}")
            self.test_results.append(("Role checking logic", False))

    async def test_manual_discord(self):
        """Provide guide for manual Discord testing."""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 6: Manual Discord Server Testing (Follow These Steps)")
        logger.info("=" * 70)

        logger.info("\n📋 MANUAL TEST CHECKLIST:")
        logger.info("\n✅ PRE-REQUISITES:")
        logger.info("   1. Start the bot: python3 main.py")
        logger.info("   2. Wait for: 'Bot is ready!' message")
        logger.info("   3. Verify bot appears ONLINE in Discord")

        logger.info("\n🧪 TEST 1: Command Visibility")
        logger.info("   1. Go to your Discord server")
        logger.info("   2. Type '/' in the chat box")
        logger.info("   3. You should see: /request-access")
        logger.info("   4. ✅ PASS if command appears")

        logger.info("\n🧪 TEST 2: Without Role (Negative Test)")
        logger.info("   1. Create a test user WITHOUT 'gameserver' role")
        logger.info("   2. Run: /request-access")
        logger.info("   3. Expected: Error message about missing role")
        logger.info("   4. ✅ PASS if error message appears")

        logger.info("\n🧪 TEST 3: With Role (Positive Test)")
        logger.info("   1. Assign 'gameserver' role to yourself")
        logger.info("   2. Run: /request-access")
        logger.info("   3. Expected: DM with access link or ephemeral message")
        logger.info("   4. ✅ PASS if you get the access link")

        logger.info("\n🧪 TEST 4: Token Validation")
        logger.info("   1. Copy the access link from the DM")
        logger.info("   2. Visit the link (will test in Phase 3)")
        logger.info("   3. Note the token format and expiration")

        logger.info("\n🧪 TEST 5: Rate Limiting")
        logger.info("   1. Run: /request-access again quickly")
        logger.info("   2. Expected: Rate limit message (wait X minutes)")
        logger.info("   3. ✅ PASS if rate limit is enforced")

        logger.info("\n🧪 TEST 6: Database Verification")
        logger.info("   1. Check database tables:")
        logger.info("      sqlite3 data/gameserver_access.db")
        logger.info("      SELECT * FROM users;")
        logger.info("      SELECT * FROM access_tokens;")
        logger.info("      SELECT * FROM request_history;")
        logger.info("   2. ✅ PASS if data appears after /request-access")

        logger.info("\n🧪 TEST 7: DM Handling")
        logger.info("   1. Test user WITH DMs enabled:")
        logger.info("      - Should receive DM with link")
        logger.info("   2. Test user WITH DMs disabled:")
        logger.info("      - Should see ephemeral message in channel")
        logger.info("   3. ✅ PASS if both cases work")

        logger.info("\n🧪 TEST 8: Error Handling")
        logger.info("   1. Stop the bot (Ctrl+C)")
        logger.info("   2. Try running: /request-access")
        logger.info("   3. Expected: Error (bot offline)")
        logger.info("   4. Restart bot")
        logger.info("   5. ✅ PASS if bot recovers")

    def print_summary(self):
        """Print test results summary."""
        logger.info("\n" + "=" * 70)
        logger.info("TEST RESULTS SUMMARY")
        logger.info("=" * 70)

        passed = sum(1 for _, result in self.test_results if result)
        total = len(self.test_results)

        logger.info(f"\n📊 Automated Tests: {passed}/{total} passed\n")

        for test_name, result in self.test_results:
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"   {status} - {test_name}")

        pass_rate = (passed / total * 100) if total > 0 else 0
        logger.info(f"\n📈 Pass Rate: {pass_rate:.1f}%")

        if passed == total:
            logger.info("\n🎉 ALL AUTOMATED TESTS PASSED!")
            logger.info("Ready to proceed with manual Discord testing.")
        else:
            logger.info(f"\n⚠️  {total - passed} test(s) failed.")
            logger.info("Please review errors above.")

    async def cleanup(self):
        """Clean up test environment."""
        if self.db:
            await self.db.close()

        # Remove test database
        if os.path.exists("./test_discord_bot.db"):
            os.remove("./test_discord_bot.db")
            logger.info("🧹 Test database cleaned up")

    async def run(self):
        """Run all tests."""
        try:
            await self.setup()
            await self.test_config()
            await self.test_database()
            await self.test_bot_event_handlers()
            await self.test_token_generator()
            await self.test_role_checker_logic()
            await self.test_manual_discord()
            self.print_summary()
        except Exception as e:
            logger.error(f"Test suite failed: {e}", exc_info=True)
        finally:
            await self.cleanup()


async def main():
    """Run the test suite."""
    suite = DiscordBotTestSuite()
    await suite.run()

    logger.info("\n" + "=" * 70)
    logger.info("To run the bot with your Discord server:")
    logger.info("=" * 70)
    logger.info("\n   python3 main.py\n")
    logger.info("Then follow the manual tests above!\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTests cancelled by user")
        sys.exit(0)
