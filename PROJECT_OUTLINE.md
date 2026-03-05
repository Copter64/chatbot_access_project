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
- [ ] Set up Flask/FastAPI application
- [ ] Create IP check landing page (HTML template)
- [ ] Implement token validation
- [ ] Capture user's external IP (from request headers)
- [ ] Create IP confirmation page
- [ ] Handle IP submission endpoint
- [ ] Store IP in database with 30-day expiration
- [ ] Create success/error response pages
- [ ] Ensure web server runs in same process as bot

### Phase 4: Unifi Firewall Integration
- [ ] Research Unifi API documentation for UDM Pro
- [ ] Implement Unifi authentication (get/refresh access token)
- [ ] Create function to add IP to firewall group
- [ ] Create function to remove IP from firewall group
- [ ] Implement error handling for API failures
- [ ] Test with UDM Pro firewall
- [ ] Document firewall group setup requirements

### Phase 5: IP Management & Cleanup
- [ ] Implement scheduled task (APScheduler or similar)
- [ ] Create daily cleanup job to check for expired IPs
- [ ] Remove expired IPs from database
- [ ] Sync removed IPs with Unifi firewall
- [ ] (Optional) Send Discord DM warning 3 days before expiration
- [ ] Handle multiple IPs per user (add/remove logic)
- [ ] Prevent duplicate IP entries

### Phase 6: Testing
- [ ] Unit tests for database operations
- [ ] Test Discord command with/without role
- [ ] Test token generation and validation
- [ ] Test IP capture from various networks
- [ ] Test Unifi API integration (add/remove)
- [ ] Test expiration and cleanup process
- [ ] Test error scenarios (invalid tokens, API failures)
- [ ] Test Docker container deployment
- [ ] Load test with multiple users

### Phase 7: Security & Polish
- [ ] Implement rate limiting on web endpoints
- [ ] Validate IP addresses (prevent injection)
- [ ] Secure token generation (cryptographically random)
- [ ] Set token expiration (e.g., 15 minutes if unused)
- [ ] Audit all code for hardcoded secrets before GitHub push
- [ ] Run security scanner (bandit, safety) on dependencies
- [ ] Create admin commands (view IPs, manual add/remove)
- [ ] Verify PEP 8 compliance across entire codebase
- [ ] Implement HTTPS for web server (or behind reverse proxy)
- [ ] Add logging for security events
- [ ] Environment variable validation on startup
- [ ] Createcomprehensive README with setup instructions
- [ ] Document Unifi firewall configuration steps
- [ ] Document required Discord bot permissions
- [ ] Document required Unifi API permissions/roles
- [ ] Verify .env.example is complete and accurate
- [ ] Write troubleshooting guide
- [ ] Create CONTRIBUTING.md for potential contributors
- [ ] Create CHANGELOG.md to track version history
- [ ] Add LICENSE file (MIT, GPL, etc.)
- [ ] Review all documentation for accuracy and completenessot permissions
- [ ] Document required Unifi API permissions/roles
- [ ] Create .env.example file
- [ ] Write troubleshooting guide
- [ ] Deploy to production server
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
WEB_PORT=8080
WEB_HOST=0.0.0.0
DATABASE_PATH=/data/gameserver_access.db
IP_EXPIRATION_DAYS=30
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
- [ ] All secrets are loaded from environment variables only
- [ ] `.env` file is in `.gitignore`
- [ ] `.env.example` contains only placeholder values (no real credentials)
- [ ] No API keys, tokens, or passwords in code or comments
- [ ] No hardcoded IP addresses or internal hostnames
- [ ] Git history audited for accidentally committed secrets (use `git-secrets` or `truffleHog`)
- [ ] Use pre-commit hooks to prevent secret commits (detect-secrets, git-secrets)
- [ ] README includes security disclosure policy
- [ ] Dependencies regularly updated and scanned for vulnerabilitiescate
6. **Credential Storage**: Never commit .env file, use Docker secrets in production
7. **Unifi API**: Store credentials securely, use HTTPS for API calls
8. **Database**: Backup database regularly, not exposed outside container
9. **Logging**: Log security events but sanitize sensitive data

---

## Additional Features (Future Enhancements)

- [ ] Dashboard showing current active IPs per user
- [ ] Manual IP entry command for advanced users
- [ ] Extend access command (restart 30-day timer)
- [ ] Multiple game server support
- [ ] Audit log of all access grants/removals
- [ ] Email notifications (optional)
- [ ] IP geolocation display
- [ ] Admin dashboard web interface

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
## Development Workflow Best Practices

1. **Before Each Commit**
   - Run `black` to format code
   - Run `flake8` to check for PEP 8 violations
   - Run tests to ensure nothing is broken
   - Update relevant documentation if needed
   - Verify no secrets are being committed

2. **Pull Request Process**
   - Write descriptive commit messages
   - Include documentation updates in PR
   - Ensure CI/CD pipeline passes
   - Request code review from peers

3. **Documentation Updates Triggers**
   - New feature added → Update README and relevant docs
   - API endpoint changed → Update API.md
   - Configuration changed → Update .env.example and SETUP.md
   - Bug fix → Update CHANGELOG.md
   - Architecture change → Update PROJECT_OUTLINE.md

---

**Notes:**
- UDM Pro fully supports Unifi Controller API
- Consider using `apscheduler` for scheduled cleanup tasks
- `aiohttp` for async Unifi API calls alongside discord.py
- SQLite with `aiosqlite` for async database operations
- Use `python-dotenv` to load environment variables from .env file
- Consider GitHub Actions for automated testing and linting on every pushs
└── README.md                  # Main documentationt__.py
│   ├── token_generator.py
│   ├── scheduler.py           # Cleanup tasks
│   └── logger.py
├── main.py                    # Entry point
├── config.py                  # Configuration loader
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## Next Steps

1. Review this outline and confirm approach
2. Set up Unifi API access on UDM Pro
3. Create Discord bot application and get token
4. Begin Phase 1 implementation
5. Iterate and test each phase

---

**Notes:**
- UDM Pro fully supports Unifi Controller API
- Consider using `apscheduler` for scheduled cleanup tasks
- `aiohttp` for async Unifi API calls alongside discord.py
- SQLite with `aiosqlite` for async database operations
