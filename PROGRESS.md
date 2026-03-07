# Project Progress Summary

**Last Updated:** March 7, 2026
**Current Phase:** Phase 5 Complete → Phase 6 (Testing / Docker) Next

---

## ✅ Completed Work

### Phase 1: Foundation & Setup (100% Complete)
- ✅ Project structure with all directories
- ✅ Python venv (3.12) with all dependencies
- ✅ Development tools: black, flake8, pre-commit
- ✅ Configuration system with validation
- ✅ Database schema with SQLite
- ✅ Logging system with colored output
- ✅ Entry point (main.py)

### Phase 2: Discord Bot Core (100% Complete)
- ✅ Discord bot client (GameServerBot class)
- ✅ Role verification (/request-access command)
- ✅ Token generation (cryptographically secure)
- ✅ Database operations for Users, Access tokens, IP addresses, Request history
- ✅ Rate limiting (1 request per 5 minutes)
- ✅ DM sending with fallback to ephemeral messages
- ✅ Comprehensive error handling
- ✅ 14/14 automated tests passing

### Phase 3: Web Server Module (100% Complete)
- ✅ Flask app factory (`web/app.py`) running in daemon thread
- ✅ Routes (`web/routes.py`):
  - `GET /health` — health check
  - `GET /check-ip/<token>` — validates token, shows detected IP
  - `POST /confirm-ip/<token>` — saves IP to DB, marks token used, redirects
  - `GET /success` — access granted confirmation page
- ✅ HTML templates (dark-themed):
  - `check_ip.html` — IP confirmation page
  - `success.html` — access granted page
  - `error.html` — expired/invalid token page
- ✅ HTTPS/TLS via Let's Encrypt cert (`fullchain.pem` / `privkey.pem`)
  - Cert: `/etc/letsencrypt/live/home.chrissibiski.com/` (expires 2026-06-03)
  - SSL context built with `ssl.PROTOCOL_TLS_SERVER`
  - Graceful fallback to HTTP if SSL_CERT/SSL_KEY not set
- ✅ Full end-to-end flow tested end-to-end (HTTP and HTTPS)
- ✅ 16/16 pytest tests passing
- ✅ Token single-use enforcement confirmed (410 on re-use)
- ✅ Integrated into `main.py` (shares asyncio loop + database with bot)

### Phase 4: Unifi Firewall Integration (100% Complete)
- ✅ `UnifiClient` — cookie-based auth, CSRF management, auto-retry on 401
- ✅ `UnifiFirewallManager` — idempotent `add_ip()`, `remove_ip()`, `sync_group()`
- ✅ `confirm_ip` route calls `add_ip()` best-effort (never blocks web response)
- ✅ 31/31 new Unifi tests (74/74 total) passing, flake8 + black + isort clean
- ✅ Live end-to-end test against UDM Pro confirmed working (2026-03-06)
- ✅ Satisfactory server port/firewall issues diagnosed and fixed:
  - `SatisfactoryServerAccess` WAN_IN rule enabled, protocol set to `all`
  - Port group updated to `7777`, `8888` (removed obsolete 15000/15777)
  - Port forward updated to `7777,8888 tcp_udp`

### Phase 5: IP Cleanup Scheduler (100% Complete)
- ✅ `database/models.py` — added `get_expired_active_ips()` and `deactivate_ip()`
- ✅ `utils/scheduler.py` — new module:
  - `cleanup_expired_ips(db, unifi_manager)` async coroutine: fetches expired rows, removes each from Unifi (best-effort), marks `is_active=0` in DB
  - `start_scheduler(db, loop, unifi_manager, interval_hours)` — APScheduler `BackgroundScheduler` wired to the main asyncio event loop via `run_coroutine_threadsafe`
  - `stop_scheduler()` — graceful shutdown
- ✅ `config.py` — added `CLEANUP_INTERVAL_HOURS` (default 24)
- ✅ `.env.example` — documented `CLEANUP_INTERVAL_HOURS=24`
- ✅ `main.py` — scheduler started after web server, stopped in `finally` block
- ✅ 9 new tests in `tests/test_scheduler.py` (83/83 total passing)
- ✅ black + flake8 + isort all clean

---

## 🔧 Development Environment Commands

```bash
source /home/copter64/chatbot_access_project/venv/bin/activate
cd /home/copter64/chatbot_access_project

# Run bot (HTTPS on port 8443)
nohup python main.py > /tmp/bot.log 2>&1 &

# Monitor logs
tail -f /tmp/bot.log

# Run tests
python -m pytest tests/ -v

# Stop bot
pkill -f "python main.py"
```

## 🔒 TLS Certificate Renewal

Cert expires **2026-06-03**. Renew before then:
```bash
sudo certbot renew --manual --preferred-challenges dns
# Add the new _acme-challenge TXT record when prompted
```

---

---

## Phase 4: Unifi Firewall Integration — 2026-03-06

### What Was Implemented

- **`unifi_modules/client.py`** — `UnifiClient` class: cookie-based auth against UDM Pro (`POST /api/auth/login`), CSRF token management, lazy first-time login, automatic re-authentication on 401, thread-safe lock, graceful `UnifiAPIError` / `UnifiAuthError` exceptions.
- **`unifi_modules/firewall.py`** — `UnifiFirewallManager` class: `add_ip()`, `remove_ip()`, `get_group_ips()`, `sync_group()` against `/proxy/network/api/s/{site}/rest/firewallgroup`. All operations are idempotent. Phase 5 `sync_group()` method included.
- **`unifi_modules/__init__.py`** — Package init exporting all public classes.
- **`web/routes.py`** — `confirm_ip` now calls `unifi_manager.add_ip(client_ip)` after DB save. Best-effort: Unifi failure is logged but never blocks the success page.
- **`web/app.py`** — `create_app()` now accepts optional `unifi_manager` param injected as `app.config["UNIFI"]`.
- **`main.py`** — Creates `UnifiClient` + `UnifiFirewallManager` at startup (lazy auth — no login until first IP confirmation). Gracefully degrades if Unifi is unreachable at boot.
- **`requirements.txt`** — Added `requests>=2.31.0`.
- **`.flake8`** — Created with `max-line-length = 88` to match black (was missing; flake8 was using 79-char default).

### Tests

- **`tests/test_unifi_client.py`** — 14 tests: login success/failure/network-error, CSRF storage, lazy login, retry on 401, HTTP error propagation, `is_authenticated()`.
- **`tests/test_unifi_firewall.py`** — 17 tests: group fetch, not-found error, API error propagation, `add_ip` (new/duplicate/empty), `remove_ip` (present/absent/last), `sync_group` (update/no-op/empty).
- **Total: 74/74 tests passing**, flake8 + black + isort all clean.

### Notes

- Unifi group **must exist** in UDM Pro before the bot runs: Network → Firewall & Security → Groups → Create Address Group named `GameServerAccess`.
- Live test against UDM Pro still pending (requires network access to 192.168.1.1 with valid credentials).

**Status:** 🟢 PHASE 4 COMPLETE

---

## Phase 4: Live UDM Pro Testing & Satisfactory Server Debugging — 2026-03-06

### Live UDM Pro Test — Confirmed Working

The full end-to-end flow was verified against the production UDM Pro at `192.168.1.1`:
- Bot generates token → user clicks DM link → Flask captures external IP → `confirm_ip` calls `UnifiFirewallManager.add_ip()` → IP appears in `GameServerAccess` firewall group on UDM Pro within seconds.
- `UNIFI_VERIFY_SSL=false` required (UDM Pro uses a self-signed cert). Real credentials stored in `.env` only.

### Unifi Objects Created (Production)

| Object | Type | Value |
|---|---|---|
| `GameServerAccess` | Address Group | External player IPs (managed by bot) |
| `Satisfactory Ports` | Port Group | `7777`, `8888` |
| `UbuntuServerIP` | Address Group | `192.168.1.122` (game server LAN IP) |
| `SatisfactoryServerAccess` | WAN_IN Firewall Rule #20005 | Allows `GameServerAccess` → `UbuntuServerIP`:`Satisfactory Ports` (protocol: all, enabled: true) |
| `SatisfactoryServer` | Port Forward | External `7777,8888 tcp_udp` → `192.168.1.122` |

### Satisfactory Server Disconnect Investigation

Players kept timing out (~25 seconds after joining). Investigation via `journalctl -u satisfactory`:

**Root Cause — Three compounding issues found and fixed:**

1. **`SatisfactoryServerAccess` WAN_IN rule was `enabled=false`** — The default DROP policy was silently blocking all inbound game traffic for external players. LAN player (`192.168.1.187`) was unaffected (WAN_IN rules do not apply to LAN-originated traffic). Fixed: `enabled=true`.

2. **Rule protocol was `udp` only** — Blocked TCP traffic on port 8888. Fixed: `protocol=all`.

3. **Port 8888 (TCP) missing from port group and port forward** — Satisfactory Patch 1.1.0.0 (current server version) replaced old ports 15000 and 15777 with a new **Reliable Messaging** subsystem on port 8888 TCP (`LogReliableMessaging: Server streaming socket bound to port 8888`). The port group still had the obsolete ports. Fixed: port group updated to `['7777', '8888']`; port forward updated to `7777,8888 tcp_udp`.

**Key diagnostic evidence:**
- Every external disconnect: `Result=ConnectionTimeout` preceded by `LogReliableMessaging: Warning: Handshake with player timed out` — the RM TCP handshake on port 8888 was blocked.
- `RegisterPlayerWithSession: Failed IsOnline: false` appears on every connection (LAN and external) — this is a **non-fatal warning** from the EOS offline subsystem and is NOT the cause of disconnects. Safe to ignore.
- After all three fixes, user confirmed: **"the firewall rules work fine now"**.

**Post-fix log analysis (05:47–05:50 UTC):**
- External player `71.163.123.211` ("The Boundless Sky"): connected, `Join succeeded`, RM transport established — no timeout. ✅
- LAN player `192.168.1.187` (copter64): now occasionally disconnecting every ~30 seconds with `Missed Acks: Count: 56` immediately before timeout — this is a **client-side issue** on `192.168.1.187` (game freezing for 30+ seconds), not a firewall problem. Check Windows Event Viewer on that machine around disconnect times.

### Notes for Next Session

- **Phase 5 (APScheduler cleanup) not yet started.** Next step: daily background task that queries DB for expired IPs and calls `unifi_manager.remove_ip()` for each, then marks `is_active=0`.
- `RATE_LIMIT_PERIOD_MINUTES` is currently `1` (set during testing). Reset to `5` before production use.
- Bot restart command:
  ```bash
  pkill -9 -f "python main.py"; sleep 2; fuser -k 8443/tcp; sleep 2; \
  cd /home/copter64/chatbot_access_project && source venv/bin/activate && \
  PYTHONUNBUFFERED=1 nohup python main.py > /tmp/bot.log 2>&1 &
  ```

**Status:** 🟢 PHASE 4 FULLY LIVE-TESTED — READY FOR PHASE 5

---

## Phase 5: IP Cleanup Scheduler — 2026-03-07

### What Was Implemented

**`database/models.py`**
- `get_expired_active_ips()` — queries `ip_addresses` for rows where `is_active = 1 AND expires_at <= CURRENT_TIMESTAMP`, returns list of dicts.
- `deactivate_ip(ip_id)` — sets `is_active = 0` for the given primary key, returns `bool`.

**`utils/scheduler.py`** (new file)
- `cleanup_expired_ips(db, unifi_manager)` — async coroutine that processes all expired IPs: removes each from the Unifi firewall group (best-effort; logs error and continues on failure), then deactivates the row in the DB. Returns a summary dict `{removed, skipped, unifi_errors}`.
- `start_scheduler(db, loop, unifi_manager, interval_hours)` — creates an APScheduler `BackgroundScheduler` with a single interval job. The job uses `asyncio.run_coroutine_threadsafe` to dispatch the cleanup coroutine onto the main event loop (safe because the DB connection and Discord bot share that loop). The scheduler runs as a daemon thread.
- `stop_scheduler()` — graceful shutdown; safe to call even if scheduler was never started.

**`config.py`** — `CLEANUP_INTERVAL_HOURS: int` (env var, default `24`).

**`.env.example`** — `CLEANUP_INTERVAL_HOURS=24` documented.

**`main.py`** — replaced TODO comment with `start_scheduler(...)` call; `stop_scheduler()` added to `finally` block.

### Tests (`tests/test_scheduler.py` — 9 new tests)
| Test | Scenario |
|---|---|
| `test_no_expired_ips_returns_zero_counts` | No expired IPs → no-op |
| `test_removes_expired_ips_from_unifi_and_db` | 2 expired IPs → both removed from Unifi + deactivated |
| `test_unifi_error_still_deactivates_in_db` | Unifi raises exception → DB still updated |
| `test_no_unifi_manager_deactivates_in_db_only` | `unifi_manager=None` → DB deactivated, no crash |
| `test_partial_unifi_failure` | 3 IPs, 1 Unifi error → all 3 deactivated in DB |
| `test_ip_not_found_in_db_counts_as_skipped` | `deactivate_ip` returns False → counted as skipped |
| `test_start_creates_running_scheduler_with_job` | Scheduler starts, has one job with correct ID |
| `test_stop_scheduler_shuts_down_cleanly` | Stop doesn't raise |
| `test_stop_scheduler_noop_when_not_started` | Safe to call when `_scheduler = None` |

**Total: 83/83 tests passing. black + flake8 + isort clean.**

### Live End-to-End Test — Confirmed Working (2026-03-07)

Run via `/tmp/test_cleanup.py` against the production UDM Pro:

```
[1] Added 192.0.2.1 to Unifi group 'GameServerAccess'          ✅
[2] Inserted DB row with expires_at = yesterday                 ✅
[3] cleanup_expired_ips() → {removed: 1, skipped: 0, errors: 0} ✅
[4] IP removed from Unifi group                                 ✅
[5] DB row is_active = 0                                        ✅
🎉 All checks passed
```

**Status:** 🟢 PHASE 5 COMPLETE — LIVE TESTED

---

## Phase 6 — Testing & Docker

### New Test Files Created

| File | Tests | Coverage |
|---|---|---|
| `tests/test_database.py` | 30 | All `Database` CRUD methods (Users, AccessTokens, IPAddresses, RequestHistory) using `:memory:` SQLite |
| `tests/test_discord_commands.py` | 14 | `has_gameserver_role`, `get_member_in_guild`, `verify_role_access` with full MagicMock isolation |
| `tests/test_token_generator.py` | 17 | `generate_token`, `generate_access_token`, `is_valid_token_format` — length, charset, uniqueness, edge cases |

**Key fix:** `test_discord_commands.py` patches `Config.GAMESERVER_ROLE_NAME` to "gameserver" so tests are independent of `.env` environment.

### Docker Files Created

- `Dockerfile` — `python:3.12-slim`, non-root `botuser`, layer-cached deps, `/app/data` volume
- `docker-compose.yml` — `restart: unless-stopped`, `env_file: .env`, `./data:/app/data` + `/etc/letsencrypt` mounts, `${WEB_PORT:-8443}` port mapping, 256MB memory limit
- `.dockerignore` — excludes `venv/`, `.env`, `data/`, `__pycache__/`, `.git/`

### Final Test Count

**Total: 150/150 tests passing. black + flake8 + isort clean.**

`tests/test_load.py` added (8 tests): concurrent GET/POST under 20 threads, rate-limiter saturation from one IP, different-IP isolation, 50-thread `/health` smoke, concurrent aiosqlite writes with no exceptions.

**Status:** 🟢 PHASE 6 COMPLETE

---

## Phase 7 — Security Hardening

### Scanner Results

| Tool | Result |
|---|---|
| `bandit` | 0 issues — 2 false positives suppressed with `# nosec` |
| `safety` | 0 vulnerabilities across 119 packages |

### False Positives Suppressed

- [config.py](config.py#L41): `# nosec B104` — `WEB_HOST="0.0.0.0"` is intentional for Docker/server deployment
- [validate_bot.py](validate_bot.py#L34): `# nosec B105` — comparison against placeholder string is detector logic, not a hardcoded credential

### Secrets Audit

- Grepped all source for hardcoded passwords, tokens, IPs — clean
- All IPs found are in docs, test fixtures, or `.env.example` placeholders
- `Config.TOKEN_EXPIRATION_MINUTES` defaults to 15 minutes — token TTL was already implemented in Phase 2

**Total: 150/150 tests passing. bandit clean. safety 0 CVEs.**

**Status:** 🟢 PHASE 7 COMPLETE

---

## Phase 8 — Admin Commands

### New Slash Commands

| Command | Description |
|---|---|
| `/list-ips` | Admin-only. Lists all active firewall IPs (optional `user` filter). Truncates at 20 entries. |
| `/remove-ip` | Admin-only. Removes an IP from Unifi and marks it inactive in the DB. |
| `/add-ip` | Admin-only. Manually adds an IP for a user, bypassing the web flow. |

All three commands:
- Gate on `Config.ADMIN_DISCORD_USER_IDS` (returns ❌ to non-admins)
- Validate IP address format via `_validate_ip()` before any DB/Unifi call
- Run Unifi calls via `asyncio.run_in_executor` to avoid blocking the event loop
- Degrade gracefully when `unifi_manager=None` (DB-only update with clear message)

### Supporting Changes

- `database/models.py`: added `get_all_active_ips()` (JOIN with users) and `get_active_ip_by_address()`
- `discord_modules/commands.py`: added `is_admin()` and `_validate_ip()` module-level helpers; updated `setup_commands(db, unifi_manager=None)` signature
- `main.py`: moved Unifi initialisation **before** `setup_commands` so `unifi_manager` is available; passes it in
- Fixed two `datetime.utcnow()` deprecation warnings → `datetime.now(timezone.utc).replace(tzinfo=None)`

### Tests

`tests/test_admin_commands.py` — 24 tests across 5 classes:
- `TestIsAdmin`, `TestValidateIp` — module-level helpers
- `TestListIps`, `TestRemoveIp`, `TestAddIp` — admin check, invalid inputs, success with/without Unifi, edge cases

**Total: 174/174 tests passing. flake8 clean.**

**Status:** 🟢 PHASE 8 COMPLETE

---

## Phase 9 — Documentation & Release

### Files Created

| File | Description |
|---|---|
| `docs/UNIFI_SETUP.md` | Step-by-step: API user, firewall group, WAN_IN rule, port forwards, verification |
| `docs/TROUBLESHOOTING.md` | Organised by category: bot startup, web server, Discord commands, Unifi, database |
| `CONTRIBUTING.md` | Dev setup, pre-commit hooks, code standards, module boundaries, secrets policy |
| `CHANGELOG.md` | Keep-a-Changelog format, v1.0.0 entry covering all 9 phases |
| `LICENSE` | MIT, Copyright 2026 Copter64 |
| `docs/PRODUCTION_DEPLOY.md` | Step-by-step: Proxmox VM creation, Docker install, cert migration, DB migration, UDM Pro port-forward update, rollback procedure |

### README.md Updates
- Added **Admin Commands** section (all 4 slash commands)
- Added **Docker Deployment** section with `docker compose` quickstart
- Updated **Current Status** to show all 9 phases complete
- Updated **Documentation** links list to include new guides

### Remaining (operational, not code)
- ~~Follow `docs/PRODUCTION_DEPLOY.md` to deploy on Proxmox VM~~ ✅ Done — bot running on Docker VM at 192.168.1.53, workflow end-to-end verified
- Set up monitoring/alerting (e.g. UptimeRobot pinging `/health`)

**Status:** 🟢 PHASE 9 COMPLETE — ALL DEVELOPMENT PHASES DONE
