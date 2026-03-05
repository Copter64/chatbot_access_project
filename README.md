# Discord Game Server Access Bot

A Discord bot that manages game server firewall access by capturing user IPs and adding them to Unifi firewall rules.

## Features

- 🔐 Role-based access control (requires "gameserver" role)
- 🔑 Secure token generation for access links
- ⏱️ Configurable IP expiration (default: 30 days)
- 🚦 Rate limiting to prevent abuse
- 📝 Comprehensive audit logging
- 🛡️ PEP 8 compliant, secure code

## Quick Start

### 1. Prerequisites

- Python 3.10+
- Discord bot token
- Unifi Controller with API access (UDM Pro supported)

### 2. Installation

```bash
# Clone the repository
cd chatbot_access_project

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements-dev.txt
```

### 3. Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your values
nano .env
```

Required configuration:
- `DISCORD_BOT_TOKEN` - Your Discord bot token
- `DISCORD_GUILD_ID` - Your Discord server ID
- `UNIFI_HOST` - Your Unifi controller address
- `UNIFI_USERNAME` - Unifi API username
- `UNIFI_PASSWORD` - Unifi API password

See [docs/DISCORD_SETUP.md](docs/DISCORD_SETUP.md) for detailed Discord setup instructions.

### 4. Validate Configuration

```bash
# Run the validation script
python3 validate_bot.py
```

This will:
- ✅ Check your .env configuration
- ✅ Validate bot token format
- ✅ Test Discord connection (optional)
- ✅ Verify role exists in server

### 5. Run the Bot

```bash
# Start the bot
python3 main.py
```

You should see:
```
✅ Configuration valid
✅ Database initialized
✅ Discord bot initialized
✅ Bot commands set up
Bot is ready!
```

## Testing the Bot

### Step 1: Validate Configuration

Run the validator to check your setup:

```bash
python3 validate_bot.py
```

Answer "yes" when prompted to test the connection.

### Step 2: Check Bot Status

1. The bot should appear **online** in your Discord server
2. Check the terminal logs for any errors
3. Verify commands are synced (may take 1-5 minutes)

### Step 3: Test the Command

In your Discord server:

1. Type `/` to see available commands
2. You should see: `/request-access`
3. Run the command

**Expected Behavior:**

- ✅ **With "gameserver" role**: You receive a DM with access link
- ❌ **Without role**: Error message about missing role
- ⏳ **Rate limited**: Message about waiting before requesting again

### Step 4: Test Role Verification

1. Create a test user without the "gameserver" role
2. Try `/request-access` - should fail with role error
3. Assign the "gameserver" role
4. Try again - should succeed

### Step 5: Check Database

```bash
# View database contents
sqlite3 data/gameserver_access.db

# Check users
.mode column
.headers on
SELECT * FROM users;

# Check tokens
SELECT token, created_at, used FROM access_tokens;

# Exit
.quit
```

## Project Structure

```
chatbot_access_project/
├── discord_modules/       # Discord bot logic
│   ├── bot.py            # Bot client and events
│   ├── commands.py       # Slash commands
│   └── role_checker.py   # Role verification
├── database/             # Database layer
│   └── models.py         # Schema and operations
├── utils/                # Utilities
│   ├── logger.py         # Logging setup
│   └── token_generator.py# Token generation
├── web/                  # Web server (Phase 3)
├── docs/                 # Documentation
│   └── DISCORD_SETUP.md  # Discord setup guide
├── config.py             # Configuration loader
├── main.py               # Entry point
├── validate_bot.py       # Configuration validator
└── requirements.txt      # Dependencies
```

## Development

### Code Quality

All code follows PEP 8 standards:

```bash
# Format code
python3 -m black .

# Check for issues
python3 -m flake8 . --max-line-length=88 --extend-ignore=E203,W503

# Run pre-commit hooks
pre-commit run --all-files
```

### Testing

```bash
# Run Phase 2 tests
python3 test_phase2.py

# Validate configuration
python3 validate_bot.py
```

## Troubleshooting

### Bot doesn't appear online

- Verify `DISCORD_BOT_TOKEN` is correct
- Check the bot is invited to your server
- Ensure "SERVER MEMBERS INTENT" is enabled in Discord Developer Portal

### Commands don't show up

- Wait 1-5 minutes for Discord to sync
- Verify `DISCORD_GUILD_ID` matches your server
- Try restarting the Discord client
- Re-run the bot to sync commands again

### Role verification fails

- Ensure role name matches `GAMESERVER_ROLE_NAME` in .env
- Role names are case-insensitive
- Create the role if it doesn't exist

### Can't send DMs

- Users must have DMs enabled from server members
- Bot falls back to ephemeral message if DMs are disabled

## Security

- ✅ Never commit `.env` file
- ✅ Keep bot token secret
- ✅ Regenerate token if exposed
- ✅ Use environment variables for all secrets
- ✅ Review `.gitignore` before pushing

## Current Status

- ✅ **Phase 1**: Foundation & Setup - Complete
- ✅ **Phase 2**: Discord Bot Core - Complete
- ⏳ **Phase 3**: Web Server Module - Next
- ⏳ **Phase 4**: Unifi Integration - Pending
- ⏳ **Phase 5**: Cleanup & Scheduling - Pending

## Documentation

- 📖 [Discord Setup Guide](docs/DISCORD_SETUP.md)
- 📖 [Project Outline](PROJECT_OUTLINE.md)

## License

[Your License Here]

## Support

For issues or questions, please check:
1. [docs/DISCORD_SETUP.md](docs/DISCORD_SETUP.md)
2. Run `python3 validate_bot.py` for diagnostics
3. Check logs in `data/bot.log`
