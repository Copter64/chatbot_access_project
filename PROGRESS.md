# Project Progress Summary

**Last Updated:** March 6, 2026
**Current Phase:** Phase 4 Complete (Live-Tested) → Phase 5 Next

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
