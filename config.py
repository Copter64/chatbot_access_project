"""Configuration module for Discord Game Server Access Bot.

This module loads and validates environment variables from .env file
and provides configuration to the entire application.
"""

import os
import sys
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the project root directory (where config.py is located)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


class Config:
    """Application configuration class.

    Loads all configuration from environment variables with validation.
    """

    # Discord Configuration
    DISCORD_BOT_TOKEN: str = os.getenv("DISCORD_BOT_TOKEN", "")
    DISCORD_GUILD_ID: str = os.getenv("DISCORD_GUILD_ID", "")
    GAMESERVER_ROLE_NAME: str = os.getenv("GAMESERVER_ROLE_NAME", "gameserver")

    # Unifi Configuration
    UNIFI_HOST: str = os.getenv("UNIFI_HOST", "")
    UNIFI_USERNAME: str = os.getenv("UNIFI_USERNAME", "")
    UNIFI_PASSWORD: str = os.getenv("UNIFI_PASSWORD", "")
    UNIFI_SITE: str = os.getenv("UNIFI_SITE", "default")
    UNIFI_VERIFY_SSL: bool = os.getenv("UNIFI_VERIFY_SSL", "true").lower() == "true"
    FIREWALL_GROUP_NAME: str = os.getenv("FIREWALL_GROUP_NAME", "GameServerAccess")

    # Web Server Configuration
    WEB_PORT: int = int(os.getenv("WEB_PORT", "8080"))
    WEB_HOST: str = os.getenv("WEB_HOST", "0.0.0.0")  # nosec B104
    WEB_BASE_URL: str = os.getenv("WEB_BASE_URL", f"http://localhost:{WEB_PORT}")

    # Database Configuration
    _db_path_env = os.getenv("DATABASE_PATH", "./data/gameserver_access.db")
    DATABASE_PATH: str = (
        _db_path_env
        if os.path.isabs(_db_path_env)
        else os.path.join(PROJECT_ROOT, _db_path_env)
    )

    # IP Access Configuration
    IP_EXPIRATION_DAYS: int = int(os.getenv("IP_EXPIRATION_DAYS", "30"))
    TOKEN_EXPIRATION_MINUTES: int = int(os.getenv("TOKEN_EXPIRATION_MINUTES", "15"))
    MAX_IPS_PER_USER: int = int(os.getenv("MAX_IPS_PER_USER", "5"))

    # Rate Limiting (Discord command)
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "1"))
    RATE_LIMIT_PERIOD_MINUTES: int = int(os.getenv("RATE_LIMIT_PERIOD_MINUTES", "5"))

    # Cleanup Scheduler
    CLEANUP_INTERVAL_HOURS: int = int(os.getenv("CLEANUP_INTERVAL_HOURS", "24"))

    # Web Security
    WEB_RATE_LIMIT_REQUESTS: int = int(os.getenv("WEB_RATE_LIMIT_REQUESTS", "30"))
    WEB_RATE_LIMIT_WINDOW_SECONDS: int = int(
        os.getenv("WEB_RATE_LIMIT_WINDOW_SECONDS", "60")
    )
    WEB_BRUTE_FORCE_THRESHOLD: int = int(os.getenv("WEB_BRUTE_FORCE_THRESHOLD", "10"))
    # Comma-separated Discord user IDs to DM on security alerts
    ADMIN_DISCORD_USER_IDS: list[int] = [
        int(x.strip())
        for x in os.getenv("ADMIN_DISCORD_USER_IDS", "").split(",")
        if x.strip().isdigit()
    ]

    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    _log_file_env = os.getenv("LOG_FILE")
    LOG_FILE: Optional[str] = (
        None
        if not _log_file_env
        else (
            _log_file_env
            if os.path.isabs(_log_file_env)
            else os.path.join(PROJECT_ROOT, _log_file_env)
        )
    )

    # Game Server Connection Info (sent to users after IP is confirmed)
    GAMESERVER_NAME: str = os.getenv("GAMESERVER_NAME", "Game Server")
    GAMESERVER_HOST: str = os.getenv("GAMESERVER_HOST", "")
    GAMESERVER_PORT: str = os.getenv("GAMESERVER_PORT", "")
    GAMESERVER_PASSWORD: str = os.getenv("GAMESERVER_PASSWORD", "")
    GAMESERVER_EXTRA_INFO: str = os.getenv("GAMESERVER_EXTRA_INFO", "")

    # TLS / SSL
    SSL_CERT: Optional[str] = os.getenv("SSL_CERT") or None
    SSL_KEY: Optional[str] = os.getenv("SSL_KEY") or None

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")

    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration values.

        Returns:
            bool: True if all required values are set, False otherwise.

        Raises:
            SystemExit: If critical configuration values are missing.
        """
        errors = []

        # Check required Discord settings
        if not cls.DISCORD_BOT_TOKEN:
            errors.append("DISCORD_BOT_TOKEN is required")
        if not cls.DISCORD_GUILD_ID:
            errors.append("DISCORD_GUILD_ID is required")

        # Check required Unifi settings
        if not cls.UNIFI_HOST:
            errors.append("UNIFI_HOST is required")
        if not cls.UNIFI_USERNAME:
            errors.append("UNIFI_USERNAME is required")
        if not cls.UNIFI_PASSWORD:
            errors.append("UNIFI_PASSWORD is required")

        # Check secret key for production
        if not cls.SECRET_KEY:
            errors.append("SECRET_KEY is required (use a random string)")

        if errors:
            print("❌ Configuration validation failed:", file=sys.stderr)
            for error in errors:
                print(f"   - {error}", file=sys.stderr)
            print(
                "\n📝 Please check your .env file and ensure all required "
                "variables are set.",
                file=sys.stderr,
            )
            print(
                "   See .env.example for reference.\n",
                file=sys.stderr,
            )
            sys.exit(1)

        return True

    @classmethod
    def display(cls) -> None:
        """Display current configuration (without sensitive values)."""
        print("\n" + "=" * 50)
        print("🔧 Bot Configuration")
        print("=" * 50)
        print(f"Discord Guild ID: {cls.DISCORD_GUILD_ID}")
        print(f"Role Name: {cls.GAMESERVER_ROLE_NAME}")
        print(f"Unifi Host: {cls.UNIFI_HOST}")
        print(f"Unifi Site: {cls.UNIFI_SITE}")
        print(f"Firewall Group: {cls.FIREWALL_GROUP_NAME}")
        print(f"Web Port: {cls.WEB_PORT}")
        print(f"Web Base URL: {cls.WEB_BASE_URL}")
        print(f"Database: {cls.DATABASE_PATH}")
        print(f"IP Expiration: {cls.IP_EXPIRATION_DAYS} days")
        print(f"Max IPs per User: {cls.MAX_IPS_PER_USER}")
        print(f"Log Level: {cls.LOG_LEVEL}")
        print("=" * 50 + "\n")


# Validate configuration on module import
if __name__ != "__main__":
    # Only validate if not running directly
    pass  # Validation will be called explicitly in main.py
