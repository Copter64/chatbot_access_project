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

---

## Deployment (Docker — Recommended)

### Automated Bootstrap

The easiest way to deploy on a fresh Ubuntu 24.04 VM:

```bash
curl -fsSL https://raw.githubusercontent.com/Copter64/chatbot_access_project/master/deploy.sh | bash
```

This script installs Docker, clones the repo, sets cert permissions, prompts you
to fill in `.env`, builds the image, and starts the container.

---

### Manual Docker Steps

#### 1. Prerequisites

- Docker + Docker Compose (`curl -fsSL https://get.docker.com | sudo sh`)
- TLS certificate (Let's Encrypt — see [TLS Certificate](#tls-certificate) below)
- `.env` file filled in (copy from `.env.example`)

#### 2. Initial Setup

```bash
# Clone the repo
git clone https://github.com/Copter64/chatbot_access_project.git
cd chatbot_access_project

# Create and fill in the environment file
cp .env.example .env
nano .env
```

#### 3. Cert Permissions for the Container

The container runs as `botuser` (UID 999). Grant it read access to the Let's
Encrypt directory without loosening the base permissions:

```bash
sudo setfacl -R -m u:999:rx /etc/letsencrypt/live /etc/letsencrypt/archive
sudo setfacl -R -m u:999:r  /etc/letsencrypt/archive/yourdomain.com/
```

#### 4. Data Directory Ownership

The container writes the SQLite database and log file to `./data`:

```bash
mkdir -p data
sudo chown -R 999:999 data/
```

#### 5. Build and Start

```bash
docker compose up -d
```

#### 6. Verify

```bash
# Check container is running
docker compose ps

# Tail live logs
docker compose logs -f bot

# Health check (replace 8443 with WEB_PORT if different)
curl -sk https://localhost:8443/health
```

---

### Common Docker Operations

| Task | Command |
|---|---|
| Start | `docker compose up -d` |
| Stop | `docker compose down` |
| Restart | `docker compose restart bot` |
| Tail logs | `docker compose logs -f bot` |
| **Update code + rebuild** | `git pull && docker compose up -d --build` |
| Rebuild image only | `docker compose build` |
| Open a shell in the container | `docker compose exec bot bash` |
| View resource usage | `docker stats` |

> **After any code change** you must rebuild the image — the source is baked in
> at build time. Use `docker compose up -d --build` to rebuild and restart in
> one step.

---

### TLS Certificate

```bash
sudo apt install certbot acl
sudo certbot certonly --manual --preferred-challenges dns -d yourdomain.com
# Add the _acme-challenge TXT record to your DNS when prompted
```

After obtaining certs, apply the ACLs described in step 3 above. Renew with:

```bash
sudo certbot renew --manual --preferred-challenges dns
# Then re-apply ACLs and restart: docker compose restart bot
```

---

## Local / Development Setup

### 1. Prerequisites

- Python 3.10+
- Discord bot token
- Unifi Controller with API access (UDM Pro supported)
- TLS certificate for your domain (Let's Encrypt recommended)

### 2. Installation

```bash
cd chatbot_access_project

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements-dev.txt
```

### 3. Configuration

```bash
cp .env.example .env
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

### 4. Network / Firewall Setup

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

### 5. Run the Bot

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

## Admin Commands

These commands are restricted to Discord user IDs listed in `ADMIN_DISCORD_USER_IDS`.

| Command | Description |
|---|---|
| `/request-access` | Generates a unique HTTPS link; opens it to register your IP (requires the configured role) |
| `/list-ips [user]` | Lists all active firewall IPs. Optionally filter by a specific Discord member |
| `/remove-ip <ip>` | Removes an IP from both the Unifi firewall group and the database |
| `/add-ip <ip> <user> [days]` | Manually adds an IP for a user, bypassing the web flow |

---

## Testing the Bot

See [docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md) for the full testing guide.

### End-to-End Flow

1. User runs `/request-access` in Discord
2. Bot sends a DM with a unique HTTPS link (valid for 15 minutes)
3. User opens the link — sees their external IP
4. User clicks **Confirm Access**
5. IP is saved to the database (valid for 30 days)
6. IP is automatically added to the Unifi firewall group

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
├── unifi_modules/        # Unifi API integration
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

### Reporting a Vulnerability

If you discover a security vulnerability, please open a [GitHub Issue](https://github.com/Copter64/chatbot_access_project/issues) marked **[SECURITY]** or contact the repository owner directly via Discord. Do not include sensitive details in public issues.

## Current Status

- ✅ **Phase 1**: Foundation & Setup — Complete
- ✅ **Phase 2**: Discord Bot Core — Complete
- ✅ **Phase 3**: Web Server + TLS — Complete
- ✅ **Phase 4**: Unifi Integration — Complete
- ✅ **Phase 5**: Cleanup & Scheduling — Complete
- ✅ **Phase 6**: Testing — Complete (174 tests passing)
- ✅ **Phase 7**: Security Hardening — Complete
- ✅ **Phase 8**: Admin Commands — Complete
- ✅ **Phase 9**: Documentation & Release — Complete

## Documentation

- 📖 [Discord Setup Guide](docs/DISCORD_SETUP.md)
- 📖 [Unifi Setup Guide](docs/UNIFI_SETUP.md)
- 📖 [Testing Guide](docs/TESTING_GUIDE.md)
- 📖 [Troubleshooting Guide](docs/TROUBLESHOOTING.md)
- 📖 [Production Deployment Guide](docs/PRODUCTION_DEPLOY.md)
- 📖 [Project Outline](PROJECT_OUTLINE.md)
- 📖 [Changelog](CHANGELOG.md)
