import asyncio
from database.models import Database

async def test_database():
    """Test database creation and schema initialization."""
    # Create a test database
    db = Database("./test_gameserver.db")
    
    # Connect and initialize schema
    await db.connect()
    await db.initialize_schema()
    
    print("✅ Database created successfully")
    print(f"📁 Database file: {db.db_path}")
    
    # Test creating a user
    user_id = await db.create_user("123456789", "TestUser")
    print(f"✅ User created with ID: {user_id}")
    
    # Test retrieving the user
    user = await db.get_user_by_discord_id("123456789")
    print(f"✅ User retrieved: {user}")
    
    await db.close()
    print("✅ All database tests passed!")

if __name__ == "__main__":
    asyncio.run(test_database())
