# Discord Game Server Access Bot - Project Outline

## Project Overview
A Python-based Discord bot that allows users with the "gameserver" role to request firewall access to game servers. Users receive a unique webpage link to capture their external IP, which is then automatically added to a Unifi firewall rule for 30 days.

## Tech Stack
- **Language**: Python 3.10+
- **Discord Library**: discord.py
- **Web Framework**: Flask or FastAPI (embedded in bot)
- **Database**: SQLite (Docker-friendly, file-based)
- **Firewall**: Unifi Controller API (UDM Pro compatible)
- **Deployment**: Docker container

---

## Development Guidelines

### Code Standards
- **PEP 8 Compliance**: All Python code must follow PEP 8 style guidelines
  - Use a linter (flake8, pylint) and formatter (black) to enforce standards
  - Maximum line length: 88 characters (black default) or 79 (PEP 8 strict)
  - Proper docstrings for all modules, classes, and functions
  - Type hints where appropriate for better code clarity
  
### Secrets Management (GitHub Public Repository)
- **NEVER commit secrets to version control**
- Use `.env` file for local development (add to `.gitignore`)
- Provide `.env.example` with placeholder values for documentation
- Use environment variables for all sensitive data
- Docker secrets or external secret managers for production
- GitHub Actions: Use GitHub Secrets for CI/CD pipelines
- Rotate all secrets before making repository public

### Documentation Standards
- **Keep documentation in sync with code changes**
- Update README.md when features are added/modified
- Update PROJECT_OUTLINE.md when architecture changes
- Update inline code comments when logic changes
- Update API documentation when endpoints change
- Document breaking changes in CHANGELOG.md
- Each PR should include documentation updates if applicable

---

## Architecture Components

### 1. Discord Bot Module
- Command listener for `/request-access` (slash command)
- Role verification (check for "gameserver" role)
- Generate unique token/link for user
- Send DM with webpage link
- Background task for IP expiration cleanup

### 2. Web Server Module (Flask/FastAPI)
- Endpoint: `/check-ip/<token>` - IP capture page
- Displays user's external IP
- Confirm button to save IP
- Success/error feedback page
- API endpoint for IP submission

### 3. Database Layer (SQLite)
- **Users Table**: Discord ID, username, created_at
- **IP Addresses Table**: user_id, ip_address, added_at, expires_at, is_active
- **Access Tokens Table**: token, user_id, created_at, used (boolean)

### 4. Unifi Integration Module
- API authentication to UDM Pro
- Create/update firewall group with allowed IPs
- Add IP to firewall rule
- Remove expired IPs from firewall rule
- Handle API errors gracefully

### 5. Scheduled Tasks
- Daily cleanup job to remove expired IPs (30+ days old)
- Update Unifi firewall rules after removals
- (Optional) Warning notifications before expiration

---

## Implementation Checklist

> **Workflow Rule**: Mark each checklist item `[x]` immediately upon verified completion. Do not batch-tick items — update the checkbox as soon as the step is tested and confirmed working.

### Phase 1: Foundation & Setup
- [x] Set up project structure and virtual environment
- [x] Configure development tools (black, flake8, pre-commit hooks)
- [x] Create `.gitignore` (include .env, __pycache__, *.pyc, *.db, etc.)
- [x] Create `.env.example` with placeholder values
- [x] Create Dockerfile and docker-compose.yml
- [x] Set up SQLite database with schema
- [x] Create configuration file (loads from environment variables)
- [x] Implement database models and connection handler
- [x] Set up logging system
- [x] Initialize git repository and set up branch protection

### Phase 2: Discord Bot Core
- [x] Initialize discord.py bot with intents
- [x] Implement role verification function
- [x] Create `/request-access` slash command
- [x] Implement token generation (UUID or similar)
- [x] Store token in database
- [x] Send DM with webpage URL to user
- [x] Handle errors (DMs disabled, missing role, etc.)

### Phase 3: Web Server
- [x] Set up Flask application
- [x] Create IP check landing page (HTML template)
- [x] Implement token validation
- [x] Capture user's external IP (from request headers / X-Forwarded-For)
- [x] Create IP confirmation page
- [x] Handle IP submission endpoint (POST /confirm-ip/<token>)
- [x] Store IP in database with 30-day expiration
- [x] Create success/error response pages
- [x] Ensure web server runs in same process as bot (daemon thread, shared loop)
- [x] HTTPS/TLS via Let's Encrypt (ssl.SSLContext, certbot DNS challenge)
- [x] UFW firewall rule for port 8443
- [x] UDM Pro port forward (external 8443 → internal server:8443)
- [x] Favicon 404 suppressed
- [x] 16/16 pytest tests passing

### Phase 4: Unifi Firewall Integration
- [x] Research Unifi API documentation for UDM Pro
- [x] Implement Unifi authentication (get/refresh access token)
- [x] Create function to add IP to firewall group
- [x] Create function to remove IP from firewall group
- [x] Implement error handling for API failures
- [x] Test with UDM Pro firewall (live end-to-end confirmed 2026-03-06)
- [x] Document firewall group setup requirements
- [x] Create `GameServerAccess`, `Satisfactory Ports`, `UbuntuServerIP` firewall groups on UDM Pro
- [x] Create `SatisfactoryServerAccess` WAN_IN rule (protocol=all, enabled=true)
- [x] Create/update `SatisfactoryServer` port forward (7777,8888 tcp_udp)

### Phase 5: IP Management & Cleanup
- [x] Implement scheduled task (APScheduler BackgroundScheduler)
- [x] Create daily cleanup job to check for expired IPs
- [x] Remove expired IPs from database (`deactivate_ip()`)
- [x] Sync removed IPs with Unifi firewall (`remove_ip()`)
- [x] Handle multiple IPs per user (add/remove logic)
- [x] Prevent duplicate IP entries

### Phase 6: Testing
- [x] Unit tests for database operations
- [x] Test Discord command with/without role
- [x] Test token generation and validation
- [x] Test IP capture from various networks
- [x] Test Unifi API integration (add/remove)
- [x] Test expiration and cleanup process
- [x] Test error scenarios (invalid tokens, API failures)
- [x] Test Docker container deployment (Dockerfile + docker-compose.yml created)
- [x] Load test with multiple users

### Phase 7: Security Hardening
- [x] Implement rate limiting on web endpoints (Phase 3)
- [x] Validate IP addresses — prevent injection (Phase 3)
- [x] Secure token generation — cryptographically random via `secrets` module (Phase 2)
- [x] Implement HTTPS for web server (Phase 3)
- [x] Add logging for security events (Phases 3 & 5)
- [x] Environment variable validation on startup — `Config.validate()` (Phase 1)
- [x] Verify PEP 8 compliance — black + flake8 enforced via pre-commit (ongoing)
- [x] Set access-token expiration (15-minute TTL via `Config.TOKEN_EXPIRATION_MINUTES`, already implemented in Phase 2)
- [x] Audit all code for hardcoded secrets before GitHub push — scan clean; no real credentials in source
- [x] Run security scanner (`bandit`, `safety`) on codebase and dependencies; fix findings

### Phase 8: Admin Commands
- [x] `/list-ips` — show all active firewall IPs (optionally filtered by user)
- [x] `/remove-ip` — manually remove a specific IP from Unifi and mark inactive in DB
- [x] `/add-ip` — manually add an IP to the firewall group, bypassing the web flow
- [x] Write tests for all new admin commands

### Phase 9: Documentation & Release
- [x] Verify `.env.example` is complete and accurate
- [x] Write comprehensive README with full setup instructions
- [x] Document Unifi firewall group configuration steps (`docs/UNIFI_SETUP.md`)
- [x] Document required Discord bot permissions (`docs/DISCORD_SETUP.md`)
- [x] Document required Unifi API permissions/roles (`docs/UNIFI_SETUP.md`)
- [x] Write troubleshooting guide (`docs/TROUBLESHOOTING.md`)
- [x] Create `CONTRIBUTING.md`
- [x] Create `CHANGELOG.md`
- [x] Add `LICENSE` file (MIT)
- [x] Review all documentation for accuracy and completeness
- [x] Deploy to production server
- [ ] Set up monitoring/alerting

---

## Key Configuration Items

### Environment Variables Needed
```bash
DISCORD_BOT_TOKEN=your_bot_token
DISCORD_GUILD_ID=your_server_id
GAMESERVER_ROLE_NAME=gameserver
UNIFI_HOST=https://your-udm-pro-ip
UNIFI_USERNAME=your_username
UNIFI_PASSWORD=your_password
UNIFI_SITE=default
FIREWALL_GROUP_NAME=GameServerAccess
WEB_PORT=8443
WEB_HOST=0.0.0.0
WEB_BASE_URL=https://yourdomain.com:8443
SSL_CERT=/etc/letsencrypt/live/yourdomain.com/fullchain.pem
SSL_KEY=/etc/letsencrypt/live/yourdomain.com/privkey.pem
DATABASE_PATH=/data/gameserver_access.db
IP_EXPIRATION_DAYS=30
SECRET_KEY=your_random_secret_key
```

### Unifi Firewall Setup Requirements
1. Create firewall group "GameServerAccess" (or configured name)
2. Create firewall rule allowing GameServerAccess group to game server ports
3. Create local user with API access permissions
4. Note the site name (usually "default")

### Discord Bot Permissions Required
- Read Messages/View Channels
- Send Messages
- Use Slash Commands
- Send Messages in DM

---

## Security Considerations

1. **Token Security**: Use cryptographically secure random tokens (secrets module)
2. **Token Expiration**: Tokens should expire after 15-30 minutes if not used
3. **Rate Limiting**: Prevent abuse of `/request-access` command (1 request per 5 minutes per user)
4. **IP Validation**: Validate IP format before adding to firewall
5. **HTTPS**: Run behind reverse proxy (nginx) with SSL certifi

### GitHub Public Repository Checklist
- [x] All secrets are loaded from environment variables only
- [x] `.env` file is in `.gitignore`
- [x] `.env.example` contains only placeholder values (no real credentials)
- [x] No API keys, tokens, or passwords in code or comments
- [x] No hardcoded IP addresses or internal hostnames
- [x] Git history audited for accidentally committed secrets (use `git-secrets` or `truffleHog`)
- [x] Use pre-commit hooks to prevent secret commits (detect-secrets, git-secrets)
- [x] README includes security disclosure policy
- [x] Dependencies regularly updated and scanned for vulnerabilities
6. **Credential Storage**: Never commit .env file, use Docker secrets in production
7. **Unifi API**: Store credentials securely, use HTTPS for API calls
8. **Database**: Backup database regularly, not exposed outside container
9. **Logging**: Log security events but sanitize sensitive data

---

---

## Project File Structure
```
chatbot_access_project/
├── discord_modules/
│   ├── __init__.py
│   ├── bot.py                 # Main bot instance
│   ├── commands.py            # Slash commands
│   └── role_checker.py        # Role verification
├── unifi_modules/
│   ├── __init__.py
│   ├── api_client.py          # Unifi API wrapper
│   └── firewall_manager.py    # IP add/remove logic
├── ip_address_helper/
│   ├── __init__.py
│   └── validator.py           # IP validation utilities
├── web/
│   ├── __init__.py
│   ├── app.py                 # Flask/FastAPI app
│   ├── routes.py              # Web routes
│   └── templates/
│       ├── check_ip.html
│   tests/                     # Unit and integration tests
│   ├── __init__.py
│   ├── test_database.py
│   ├── test_discord_commands.py
│   ├── test_unifi_api.py
│   └── test_web_routes.py
├── docs/                      # Additional documentation
│   ├── SETUP.md
│   ├── UNIFI_CONFIG.md
│   └── API.md
├── .github/
│   └── workflows/
│       └── ci.yml             # GitHub Actions for testing/linting
├── main.py                    # Entry point
├── config.py                  # Configuration loader
├── requirements.txt           # Production dependencies
├── requirements-dev.txt       # Development dependencies (black, flake8, etc.)
├── Dockerfile
├── docker-compose.yml
├── .env.example               # Template with placeholder values
├── .gitignore                 # Excludes .env, *.db, __pycache__, etc.
├── .pre-commit-config.yaml    # Pre-commit hooks configuration
└── README.md                  # Main documentation
```

---

## Next Steps

1. Review this outline and confirm approach
2. Set up Unifi API access on UDM Pro
3. Create Discord bot application and get token
4. Begin Phase 1 implementation
5. Iterate and test each phase

---

## Future Enhancements

### Bug Fixes
- [x] Reject RFC 1918 private IP addresses — only accept publicly routable IPs when capturing user addresses

### Features
- [x] Add the gameserver info to the bot chat after the access-request is complete, for now we can add it in the .env or another config file for the chatbot to pull from.
- [x] Send Discord DM warning 3 days before IP access expires — prevents users getting locked out unexpectedly
- [x] Walk through building a testing pipeline to use with github in order to streamline the process more
- [ ] Refresh expiry timer if the IP has been active in the last 30 days — detect recent activity via Unifi logs and auto-extend
  - Approach: query Unifi `/stat/event` endpoint for recent traffic from the IP; if activity found within 30 days, extend expiry by 30 days
  - Run as part of the existing scheduler job (alongside cleanup and expiry warnings)
  - Next step: investigate whether Unifi API `/stat/event` surfaces inbound external IP traffic through the firewall group
- [ ] Discord channel log sink — forward bot log messages to a dedicated Discord channel with a corresponding role
- [ ] Audit log of all access grants and removals — searchable history for admin accountability
- [ ] `/server-health` slash command — report game server status from within Discord
- [ ] `/request-gamesave` slash command — allow users to request a game save from Discord
- [ ] Multiple game server support — manage access to more than one server
- [ ] Dashboard showing current active IPs per user
- [ ] Admin dashboard web interface
- [ ] IP geolocation display
- [ ] Email notifications (optional)

---

**Notes:**
- UDM Pro fully supports Unifi Controller API
- Consider using `apscheduler` for scheduled cleanup tasks
- `aiohttp` for async Unifi API calls alongside discord.py
- SQLite with `aiosqlite` for async database operations
