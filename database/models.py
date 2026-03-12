"""Database models and schema definitions.

This module defines the database schema using SQLite through aiosqlite.
"""

import os
from typing import Optional

import aiosqlite

from config import Config


class Database:
    """Database connection and schema management class."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file. If None, uses Config value.
        """
        self.db_path = db_path or Config.DATABASE_PATH
        self.connection: Optional[aiosqlite.Connection] = None

    async def connect(self) -> aiosqlite.Connection:
        """Establish database connection.

        Returns:
            aiosqlite.Connection: Active database connection.
        """
        # Ensure directory exists
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            # Convert to absolute path for better debugging
            abs_db_dir = os.path.abspath(db_dir)
            if not os.path.exists(db_dir):
                try:
                    os.makedirs(db_dir, exist_ok=True)
                except PermissionError as e:
                    import sys

                    print(
                        "\n❌ ERROR: Cannot create database directory",
                        file=sys.stderr,
                    )
                    print(f"   Path: {db_dir}", file=sys.stderr)
                    print(f"   Absolute: {abs_db_dir}", file=sys.stderr)
                    print(
                        f"   Current working directory: {os.getcwd()}",
                        file=sys.stderr,
                    )
                    print(f"   Error: {e}", file=sys.stderr)
                    print(
                        "\n💡 Solution: Make sure you're running from "
                        "the project directory:",
                        file=sys.stderr,
                    )
                    print(
                        "   cd /home/copter64/chatbot_access_project",
                        file=sys.stderr,
                    )
                    raise

        self.connection = await aiosqlite.connect(self.db_path)
        self.connection.row_factory = aiosqlite.Row
        return self.connection

    async def close(self) -> None:
        """Close database connection."""
        if self.connection:
            await self.connection.close()
            self.connection = None

    async def initialize_schema(self) -> None:
        """Create database tables if they don't exist."""
        if not self.connection:
            await self.connect()

        async with self.connection.cursor() as cursor:
            # Users table
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discord_id TEXT UNIQUE NOT NULL,
                    discord_username TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # IP Addresses table
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS ip_addresses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    ip_address TEXT NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(user_id, ip_address)
                )
            """)

            # Access Tokens table
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS access_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token TEXT UNIQUE NOT NULL,
                    user_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    used BOOLEAN DEFAULT 0,
                    used_at TIMESTAMP NULL,
                    ip_address TEXT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)

            # Request History table (for rate limiting and auditing)
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS request_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    request_type TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ip_address TEXT NULL,
                    success BOOLEAN DEFAULT 1,
                    error_message TEXT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)

            # Create indexes for better query performance
            await cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ip_addresses_user_id
                ON ip_addresses(user_id)
            """)

            await cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ip_addresses_expires_at
                ON ip_addresses(expires_at)
            """)

            await cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_access_tokens_token
                ON access_tokens(token)
            """)

            await cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_access_tokens_user_id
                ON access_tokens(user_id)
            """)

            await cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_request_history_user_id
                ON request_history(user_id)
            """)

            await cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_request_history_created_at
                ON request_history(created_at)
            """)

        await self.connection.commit()

        # --- Schema migrations ---
        # Add warning_sent column for expiry warning DMs (idempotent).
        # SQLite does not support ALTER TABLE ADD COLUMN IF NOT EXISTS so we
        # attempt the migration and swallow the error if it already exists.
        try:
            async with self.connection.cursor() as cursor:
                await cursor.execute(
                    "ALTER TABLE ip_addresses "
                    "ADD COLUMN warning_sent BOOLEAN DEFAULT 0"
                )
            await self.connection.commit()
        except Exception:
            pass  # column already exists — no action needed

    async def get_user_by_discord_id(self, discord_id: str) -> Optional[dict]:
        """Get user by Discord ID.

        Args:
            discord_id: Discord user ID.

        Returns:
            dict or None: User data if found, None otherwise.
        """
        if not self.connection:
            await self.connect()

        async with self.connection.cursor() as cursor:
            await cursor.execute(
                "SELECT * FROM users WHERE discord_id = ?", (discord_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_user_by_id(self, user_id: int) -> Optional[dict]:
        """Get user by database primary key.

        Args:
            user_id: Database user ID (integer primary key).

        Returns:
            dict or None: User data if found, None otherwise.
        """
        if not self.connection:
            await self.connect()

        async with self.connection.cursor() as cursor:
            await cursor.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def create_user(self, discord_id: str, username: str) -> int:
        """Create a new user.

        Args:
            discord_id: Discord user ID.
            username: Discord username.

        Returns:
            int: Database ID of the created user.
        """
        if not self.connection:
            await self.connect()

        async with self.connection.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO users (discord_id, discord_username)
                VALUES (?, ?)
                ON CONFLICT(discord_id) DO UPDATE SET
                    discord_username = excluded.discord_username,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
            """,
                (discord_id, username),
            )
            result = await cursor.fetchone()
            await self.connection.commit()
            return result[0]

    async def create_access_token(
        self, user_id: int, token: str, expires_at: str
    ) -> int:
        """Create a new access token.

        Args:
            user_id: Database user ID.
            token: Unique access token string.
            expires_at: ISO format timestamp when token expires.

        Returns:
            int: Database ID of the created token.
        """
        if not self.connection:
            await self.connect()

        async with self.connection.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO access_tokens (user_id, token, expires_at)
                VALUES (?, ?, ?)
            """,
                (user_id, token, expires_at),
            )
            await self.connection.commit()
            return cursor.lastrowid

    async def get_token(self, token: str) -> Optional[dict]:
        """Get token information by token string.

        Args:
            token: Access token string.

        Returns:
            dict or None: Token data if found and valid, None otherwise.
        """
        if not self.connection:
            await self.connect()

        async with self.connection.cursor() as cursor:
            await cursor.execute(
                """
                SELECT * FROM access_tokens
                WHERE token = ? AND used = 0 AND expires_at > CURRENT_TIMESTAMP
            """,
                (token,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def mark_token_used(self, token: str, ip_address: str) -> bool:
        """Mark a token as used.

        Args:
            token: Access token string.
            ip_address: IP address that used the token.

        Returns:
            bool: True if token was marked as used, False otherwise.
        """
        if not self.connection:
            await self.connect()

        async with self.connection.cursor() as cursor:
            await cursor.execute(
                """
                UPDATE access_tokens
                SET used = 1, used_at = CURRENT_TIMESTAMP, ip_address = ?
                WHERE token = ? AND used = 0
            """,
                (ip_address, token),
            )
            await self.connection.commit()
            return cursor.rowcount > 0

    async def get_user_active_ips(self, user_id: int) -> list:
        """Get all active IPs for a user.

        Args:
            user_id: Database user ID.

        Returns:
            list: List of active IP address records.
        """
        if not self.connection:
            await self.connect()

        async with self.connection.cursor() as cursor:
            await cursor.execute(
                """
                SELECT * FROM ip_addresses
                WHERE user_id = ? AND is_active = 1 AND expires_at > CURRENT_TIMESTAMP
                ORDER BY added_at DESC
            """,
                (user_id,),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def add_ip_address(
        self, user_id: int, ip_address: str, expires_at: str
    ) -> int:
        """Add an IP address for a user.

        Args:
            user_id: Database user ID.
            ip_address: IP address to add.
            expires_at: ISO format timestamp when IP access expires.

        Returns:
            int: Database ID of the IP address record.
        """
        if not self.connection:
            await self.connect()

        async with self.connection.cursor() as cursor:
            # Check if IP already exists for this user
            await cursor.execute(
                """
                SELECT id FROM ip_addresses
                WHERE user_id = ? AND ip_address = ?
            """,
                (user_id, ip_address),
            )
            existing = await cursor.fetchone()

            if existing:
                # Update existing record
                await cursor.execute(
                    """
                    UPDATE ip_addresses
                    SET is_active = 1, expires_at = ?, added_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """,
                    (expires_at, existing[0]),
                )
                await self.connection.commit()
                return existing[0]
            else:
                # Insert new record
                await cursor.execute(
                    """
                    INSERT INTO ip_addresses (user_id, ip_address, expires_at)
                    VALUES (?, ?, ?)
                """,
                    (user_id, ip_address, expires_at),
                )
                await self.connection.commit()
                return cursor.lastrowid

    async def log_request(
        self,
        user_id: int,
        request_type: str,
        success: bool = True,
        error_message: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Log a user request for audit and rate limiting.

        Args:
            user_id: Database user ID.
            request_type: Type of request (e.g., 'access_request', 'ip_added').
            success: Whether the request was successful.
            error_message: Optional error message if request failed.
            ip_address: Optional IP address associated with request.
        """
        if not self.connection:
            await self.connect()

        async with self.connection.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO request_history
                (user_id, request_type, success, error_message, ip_address)
                VALUES (?, ?, ?, ?, ?)
            """,
                (user_id, request_type, success, error_message, ip_address),
            )
            await self.connection.commit()

    async def get_expired_active_ips(self) -> list:
        """Return all IP records that are active but have passed expiry.

        Returns:
            list[dict]: Each dict contains at minimum ``id``,
                ``user_id``, ``ip_address``, and ``expires_at``.
        """
        if not self.connection:
            await self.connect()

        async with self.connection.cursor() as cursor:
            await cursor.execute("""
                SELECT * FROM ip_addresses
                WHERE is_active = 1 AND expires_at <= CURRENT_TIMESTAMP
                ORDER BY expires_at ASC
            """)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def deactivate_ip(self, ip_id: int) -> bool:
        """Mark a specific IP address record as inactive.

        Args:
            ip_id: Primary key of the ``ip_addresses`` row.

        Returns:
            bool: ``True`` if the row was updated, ``False`` if not found.
        """
        if not self.connection:
            await self.connect()

        async with self.connection.cursor() as cursor:
            await cursor.execute(
                "UPDATE ip_addresses SET is_active = 0 WHERE id = ?",
                (ip_id,),
            )
            await self.connection.commit()
            return cursor.rowcount > 0

    async def get_all_active_ips(self) -> list:
        """Return all currently active IP records joined with user info.

        Returns:
            list[dict]: Each dict contains ``id``, ``ip_address``,
                ``expires_at``, ``user_id``, ``discord_id``,
                and ``discord_username``.
        """
        if not self.connection:
            await self.connect()

        async with self.connection.cursor() as cursor:
            await cursor.execute("""
                SELECT i.id, i.ip_address, i.expires_at, i.user_id,
                       u.discord_id, u.discord_username
                FROM ip_addresses i
                JOIN users u ON u.id = i.user_id
                WHERE i.is_active = 1 AND i.expires_at > CURRENT_TIMESTAMP
                ORDER BY i.expires_at ASC
            """)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_ips_expiring_soon(self, days: int) -> list:
        """Return active IPs that expire within *days* days and haven't been warned.

        Used by the scheduler to find records that need an expiry warning DM.
        Only returns rows where ``warning_sent = 0`` so each user is warned
        at most once per access period.

        Args:
            days: Look-ahead window in days.

        Returns:
            list[dict]: Each dict contains ``id``, ``ip_address``,
                ``expires_at``, ``user_id``, ``discord_id``,
                and ``discord_username``.
        """
        if not self.connection:
            await self.connect()

        async with self.connection.cursor() as cursor:
            await cursor.execute(
                """
                SELECT i.id, i.ip_address, i.expires_at, i.user_id,
                       u.discord_id, u.discord_username
                FROM ip_addresses i
                JOIN users u ON u.id = i.user_id
                WHERE i.is_active = 1
                  AND i.warning_sent = 0
                  AND i.expires_at > CURRENT_TIMESTAMP
                  AND i.expires_at <= datetime('now', '+' || ? || ' days')
                ORDER BY i.expires_at ASC
                """,
                (days,),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def mark_ip_warning_sent(self, ip_id: int) -> bool:
        """Mark an IP record as having had its expiry warning DM sent.

        Args:
            ip_id: Primary key of the ip_addresses row.

        Returns:
            bool: True if the row was updated, False if not found.
        """
        if not self.connection:
            await self.connect()

        async with self.connection.cursor() as cursor:
            await cursor.execute(
                "UPDATE ip_addresses SET warning_sent = 1 WHERE id = ?",
                (ip_id,),
            )
            await self.connection.commit()
            return cursor.rowcount > 0

    async def get_active_ip_by_address(self, ip_address: str) -> Optional[dict]:
        """Find the first active IP record matching *ip_address*.

        Args:
            ip_address: The IP string to look up.

        Returns:
            dict or None: IP record if found and active, otherwise None.
        """
        if not self.connection:
            await self.connect()

        async with self.connection.cursor() as cursor:
            await cursor.execute(
                """
                SELECT * FROM ip_addresses
                WHERE ip_address = ? AND is_active = 1
                ORDER BY expires_at DESC
                LIMIT 1
                """,
                (ip_address,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_recent_requests(
        self, user_id: int, request_type: str, minutes: int
    ) -> int:
        """Get count of recent requests for rate limiting.

        Args:
            user_id: Database user ID.
            request_type: Type of request to count.
            minutes: Number of minutes to look back.

        Returns:
            int: Count of recent requests.
        """
        if not self.connection:
            await self.connect()

        async with self.connection.cursor() as cursor:
            await cursor.execute(
                """
                SELECT COUNT(*) FROM request_history
                WHERE user_id = ? AND request_type = ?
                AND created_at > datetime('now', '-' || ? || ' minutes')
            """,
                (user_id, request_type, minutes),
            )
            result = await cursor.fetchone()
            return result[0] if result else 0


# Create a global database instance
db = Database()
