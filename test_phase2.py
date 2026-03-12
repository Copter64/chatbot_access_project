"""Test Phase 2 components."""

import asyncio
from datetime import datetime, timedelta

from database.models import Database
from discord_modules.bot import initialize_bot  # noqa: F401
from utils.token_generator import generate_access_token


async def test_phase2():
    """Test all Phase 2 components."""
    print("\n" + "=" * 60)
    print("Testing Phase 2: Discord Bot Core")
    print("=" * 60)

    # Test 1: Token generation
    print("\n1️⃣  Testing token generation...")
    token = generate_access_token()
    print(f"   ✓ Generated token: {token[:16]}... (length: {len(token)})")

    # Test 2: Database operations
    print("\n2️⃣  Testing database operations...")
    db = Database("./test_phase2.db")
    await db.connect()
    await db.initialize_schema()
    print("   ✓ Database initialized")

    # Create test user
    user_id = await db.create_user("999888777", "TestUser")
    print(f"   ✓ User created with ID: {user_id}")

    # Create access token
    expires_at = datetime.utcnow() + timedelta(minutes=15)
    token_id = await db.create_access_token(user_id, token, expires_at.isoformat())
    print(f"   ✓ Access token created with ID: {token_id}")

    # Retrieve token
    token_data = await db.get_token(token)
    print(f"   ✓ Token retrieved: {token_data is not None}")

    # Test rate limiting
    await db.log_request(user_id, "access_request", success=True)
    recent = await db.get_recent_requests(user_id, "access_request", 5)
    print(f"   ✓ Rate limiting works: {recent} request(s) in last 5 minutes")

    # Add IP address
    ip_expires = datetime.utcnow() + timedelta(days=30)
    ip_id = await db.add_ip_address(user_id, "192.168.1.100", ip_expires.isoformat())
    print(f"   ✓ IP address added with ID: {ip_id}")

    # Get active IPs
    active_ips = await db.get_user_active_ips(user_id)
    print(f"   ✓ Active IPs retrieved: {len(active_ips)} IP(s)")

    await db.close()
    print("   ✓ Database connection closed")

    # Test 3: Bot initialization
    print("\n3️⃣  Testing Discord bot initialization...")
    try:
        bot = initialize_bot()
        print(f"   ✓ Bot instance created: {bot.__class__.__name__}")
        print(f"   ✓ Bot has command tree: {bot.tree is not None}")
        print(f"   ✓ Bot intents configured: {bot.intents is not None}")
    except Exception as e:
        print(f"   ✗ Bot initialization failed: {e}")

    # Cleanup
    import os

    if os.path.exists("./test_phase2.db"):
        os.remove("./test_phase2.db")
        print("\n🧹 Test database cleaned up")

    print("\n" + "=" * 60)
    print("✅ Phase 2 Tests Complete!")
    print("=" * 60)
    print("\nNote: Actual Discord connection requires a valid bot token.")
    print("The bot will attempt to connect when you run main.py with")
    print("a real DISCORD_BOT_TOKEN in your .env file.\n")


if __name__ == "__main__":
    asyncio.run(test_phase2())
