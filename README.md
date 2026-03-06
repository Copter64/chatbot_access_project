# Discord Game Server Access Bot

A Discord bot that manages game server firewall access by capturing user IPs and
adding them to Unifi firewall rules.

## Features

- 🔐 Role-based access control (requires configurable Discord role)
- 🔑 Secure token generation for single-use access links
- 🌐 HTTPS web server — captures user's external IP via browser
- ⏱️ Configurable IP expiration (default: 30 days)
- 🚦 Rate limiting to prevent abuse
- 📝 Comprehensive audit logging
- 🛡️ PEP 8 compliant, secure code

## Quick Start

### 1. Prerequisites

- Python 3.10+
- Discord bot token
- Unifi Controller with API access (UDM Pro supported)
- TLS certificate for your domain (Let's Encrypt recommended)

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
- `DISCORD_BOT_TOKEN` — Your Discord bot token
- `DISCORD_GUILD_ID` — Your Discord server ID
- `GAMESERVER_ROLE_NAME` — Role name that grants access (default: `gameserver`)
- `UNIFI_HOST` — Your Unifi controller address
- `UNIFI_USERNAME` — Unifi admin username
- `UNIFI_PASSWORD` — Unifi admin password
- `WEB_BASE_URL` — Public HTTPS URL users will visit (e.g. `https://home.example.com:8443`)
- `SSL_CERT` — Path to TLS fullchain cert (e.g. `/etc/letsencrypt/live/example.com/fullchain.pem`)
- `SSL_KEY` — Path to TLS private key
- `SECRET_KEY` — Random string for Flask session signing (generate with `python -c "import secrets; print(secrets.token_hex(32))"`)

See [docs/DISCORD_SETUP.md](docs/DISCORD_SETUP.md) for detailed Discord setup instructions.

### 4. TLS Certificate (Let's Encrypt)

```bash
sudo apt install certbot
sudo certbot certonly --manual --preferred-challenges dns -d yourdomain.com
# Add the _acme-challenge TXT record to your DNS when prompted
```

Grant the bot user read access to the certs:

```bash
sudo chown -R root:YOUR_USER /etc/letsencrypt/live/ /etc/letsencrypt/archive/
sudo chmod 750 /etc/letsencrypt/live/ /etc/letsencrypt/archive/
sudo chmod 640 /etc/letsencrypt/archive/yourdomain.com/*.pem
```

### 5. Network / Firewall Setup

For external users to reach the web server:

1. **UDM Pro port forward**: External port `8443` → internal `YOUR_SERVER_IP:8443`
   - In Unifi: Network → Firewall & Security → Port Forwarding
   - Ensure both the **external** and **internal** ports match `WEB_PORT`
2. **Server firewall**: Allow port `8443/tcp`
   ```bash
   sudo ufw allow 8443/tcp
   ```
3. **DNS**: Public A record for your domain must point to your **public IP**, not your internal LAN IP
   - Use DDNS (UDM Pro has a built-in client) to keep it updated if your ISP IP changes
   - Internal DNS override (split-horizon) pointing to the LAN IP is fine for local users

### 6. Run the Bot

```bash
# Foreground (development)
python3 main.py

# Background (persistent)
nohup python main.py > /tmp/bot.log 2>&1 &
```

Expected startup output:
```
✅ Configuration valid
✅ Database initialized
✅ Discord bot initialized
✅ Bot commands set up
✅ Web server running at https://yourdomain.com:8443
✅ Bot initialization complete
```

## Testing the Bot

See [docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md) for the full testing guide.

### End-to-End Flow

1. User runs `/request-access` in Discord
2. Bot sends a DM with a unique HTTPS link (valid for 15 minutes)
3. User opens the link — sees their external IP
4. User clicks **Confirm Access**
5. IP is saved to the database (valid for 30 days)
6. *(Phase 4)* IP is automatically added to the Unifi firewall group

**Testing from outside your network:**
Use a phone on **mobile data** (WiFi off) to simulate an external user. LAN users will see their internal IP, which is also valid for LAN-only use cases.

## Project Structure

```
chatbot_access_project/
├── discord_modules/       # Discord bot logic
│   ├── bot.py            # Bot client and events
│   ├── commands.py       # Slash commands
│   └── role_checker.py   # Role verification
├── database/             # Database layer
│   └── models.py         # Schema and operations
├── utils/                # Shared utilities
│   ├── logger.py         # Logging setup
│   └── token_generator.py# Token generation
├── web/                  # Flask web server
│   ├── app.py            # App factory + TLS setup
│   ├── routes.py         # Endpoints
│   └── templates/        # HTML pages
│       ├── check_ip.html
│       ├── success.html
│       └── error.html
├── unifi_modules/        # Unifi API integration (Phase 4)
├── docs/                 # Documentation
│   ├── DISCORD_SETUP.md
│   └── TESTING_GUIDE.md
├── config.py             # Configuration loader
├── main.py               # Entry point
└── .env.example          # Config template
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
python3 -m pytest tests/ -v
```

## Troubleshooting

### Bot doesn't appear online

- Verify `DISCORD_BOT_TOKEN` is correct
- Ensure "SERVER MEMBERS INTENT" is enabled in Discord Developer Portal

### Commands don't show up

- Wait 1-5 minutes for Discord to sync
- Verify `DISCORD_GUILD_ID` matches your server

### Web page hangs / times out (external)

- Confirm UDM Pro port forward **internal** port matches `WEB_PORT` (not an old value)
- Confirm `sudo ufw allow 8443/tcp` has been run on the server
- Test: `curl -sk https://YOUR_PUBLIC_IP:8443/health`

### Web page shows internal IP on LAN

- Expected — users on the same LAN will see their LAN IP
- Test external IP capture using a phone on mobile data (WiFi off)

### TLS certificate errors

- Verify cert files are readable: `python3 -c "open('/etc/letsencrypt/live/yourdomain/privkey.pem').read(); print('OK')"`
- Check permissions on `/etc/letsencrypt/archive/`
- Cert expires 90 days after issue — renew with `sudo certbot renew --manual --preferred-challenges dns`

### Can't send DMs

- Users must have DMs enabled from server members
- Bot falls back to ephemeral message if DMs are disabled

## Security

- ✅ Never commit `.env` file
- ✅ All secrets loaded from environment variables only
- ✅ TLS enforced on web server
- ✅ Tokens are single-use and expire after 15 minutes
- ✅ Rate limiting on `/request-access`

## Current Status

- ✅ **Phase 1**: Foundation & Setup — Complete
- ✅ **Phase 2**: Discord Bot Core — Complete
- ✅ **Phase 3**: Web Server + TLS — Complete
- ⏳ **Phase 4**: Unifi Integration — Next
- ⏳ **Phase 5**: Cleanup & Scheduling — Pending

## Documentation

- 📖 [Discord Setup Guide](docs/DISCORD_SETUP.md)
- 📖 [Testing Guide](docs/TESTING_GUIDE.md)
- 📖 [Project Outline](PROJECT_OUTLINE.md)
