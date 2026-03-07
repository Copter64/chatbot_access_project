# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.0.0] — 2026-03-07

### Added
- **Phase 1 — Foundation**: project structure, SQLite schema (users,
  ip_addresses, access_tokens, request_history), `Config` class with full
  environment-variable validation, structured logging via `coloredlogs`
- **Phase 2 — Discord Bot**: `/request-access` slash command, role-based
  access gate (`GAMESERVER_ROLE_NAME`), per-user rate limiting, single-use
  access tokens with configurable TTL (`TOKEN_EXPIRATION_MINUTES=15`),
  cryptographically random token generation via `secrets` module
- **Phase 3 — Web Server**: Flask + Werkzeug TLS web server on port 8443,
  `/check-ip/<token>` IP capture page, `/confirm-ip/<token>` POST endpoint,
  brute-force detection and per-IP rate limiting (`SecurityManager`),
  security headers (CSP, HSTS, X-Frame-Options)
- **Phase 4 — Unifi Integration**: `UnifiClient` (lazy login, CSRF handling,
  retry logic), `UnifiFirewallManager` (add/remove/sync), live end-to-end
  test against UDM Pro
- **Phase 5 — Cleanup Scheduler**: `APScheduler` background job to remove
  expired IPs from Unifi and mark them inactive in the DB,
  `CLEANUP_INTERVAL_HOURS` config variable
- **Phase 6 — Testing**: 174 tests across 9 files covering database CRUD,
  Discord commands, token generation, web routes, security, scheduler, Unifi
  client, Unifi firewall, and load testing (20-thread concurrency)
- **Phase 7 — Security Hardening**: `bandit` and `safety` scans (0 issues),
  hardcoded-secrets audit, `# nosec` suppressions for 2 intentional
  false positives
- **Phase 8 — Admin Commands**: `/list-ips`, `/remove-ip`, `/add-ip` slash
  commands gated on `ADMIN_DISCORD_USER_IDS`; `get_all_active_ips()` and
  `get_active_ip_by_address()` DB methods; Unifi calls run via
  `run_in_executor` to avoid blocking the event loop
- **Phase 9 — Documentation**: comprehensive README, Unifi setup guide,
  troubleshooting guide, `CONTRIBUTING.md`, `CHANGELOG.md`, `LICENSE`,
  `Dockerfile`, `docker-compose.yml`, `.dockerignore`

### Security
- All secrets loaded exclusively from environment variables
- Tokens are single-use and expire after 15 minutes
- TLS enforced on the web server (Let's Encrypt)
- Rate limiting on both Discord commands and web endpoints
- `detect-secrets` and `detect-private-key` pre-commit hooks active
