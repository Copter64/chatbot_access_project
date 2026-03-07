# Troubleshooting Guide

---

## Bot / startup issues

### Bot doesn't appear online in Discord
- Check the log: `cat /tmp/bot.log`
- Verify `DISCORD_BOT_TOKEN` is correct and not a placeholder
- Confirm "SERVER MEMBERS INTENT" and "GUILD MEMBERS" are enabled in the
  Discord Developer Portal (Bot → Privileged Gateway Intents)

### Commands don't appear after startup
- Discord can take 1–5 minutes to propagate slash commands
- Verify `DISCORD_GUILD_ID` matches your server (right-click server → Copy Server ID)
- Check the log for `✅ Commands synced to guild <id>`

### `Config.validate()` fails at startup
- Run `python validate_bot.py` for a detailed validation report
- Common causes: missing required env var, placeholder value left in `.env`,
  `SECRET_KEY` not set

---

## Web server issues

### Web page hangs / times out (external users)
1. Confirm UDM Pro port forward exists: external `8443` → `SERVER_LAN_IP:8443`
2. Confirm server firewall allows the port: `sudo ufw allow 8443/tcp`
3. Test locally first: `curl -sk https://localhost:8443/health`
4. Test from outside: `curl -sk https://YOUR_PUBLIC_IP:8443/health`
5. Verify `WEB_BASE_URL` uses your **public** domain, not a LAN IP

### Web page shows internal (LAN) IP
- Expected for users on the same local network — WAN_IN rules don't apply to
  LAN traffic anyway
- To test external IP capture, use a phone on **mobile data** (WiFi off)

### TLS / certificate errors
```bash
# Verify cert files are readable by the bot user
python3 -c "open('/etc/letsencrypt/live/yourdomain/privkey.pem').read(); print('OK')"

# Fix permissions
sudo chown -R root:YOUR_USER /etc/letsencrypt/live/ /etc/letsencrypt/archive/
sudo chmod 750 /etc/letsencrypt/live/ /etc/letsencrypt/archive/
sudo chmod 640 /etc/letsencrypt/archive/yourdomain.com/*.pem
```

### Getting 429 Too Many Requests
- Rate limiter triggered; wait for the window to expire (default: 60 s)
- Adjust `WEB_RATE_LIMIT_REQUESTS` / `WEB_RATE_LIMIT_WINDOW_SECONDS` in `.env`

---

## Discord command issues

### `/request-access` — "You need the gameserver role"
- Assign the configured role (`GAMESERVER_ROLE_NAME`) to the user in Discord
- Role name is case-sensitive — it must match exactly

### `/request-access` — "You've requested access recently"
- Rate limit enforced; user must wait `RATE_LIMIT_PERIOD_MINUTES` minutes
- Default: 1 request per 5 minutes

### Bot couldn't send a DM
- User has DMs from server members disabled
- Discord Settings → Privacy & Safety → "Allow direct messages from server members"
- The bot falls back to an ephemeral message with the link

### Admin commands return "You don't have permission"
- Your Discord user ID must be in `ADMIN_DISCORD_USER_IDS` in `.env`
- Find your ID: Discord Settings → Advanced → Enable Developer Mode,
  then right-click your name → Copy User ID

---

## Unifi issues

### Unifi login fails (401)
- Verify `UNIFI_USERNAME` / `UNIFI_PASSWORD` in `.env`
- The user needs **Network Administrator** role in UniFi OS
- Check `UNIFI_HOST` includes the scheme: `https://192.168.1.1`

### Firewall group not found
- `FIREWALL_GROUP_NAME` is case-sensitive; it must match the group name exactly
- Verify the group exists: UniFi → Firewall & Security → Firewall Groups

### IP added to DB but not showing in Unifi
- Check the log for `Unifi add_ip` errors
- Bot starts even if Unifi is unreachable; IPs are DB-only until Unifi reconnects
- Test the API manually (see `docs/UNIFI_SETUP.md` → Step 6)

### External players connected but game server unreachable
- Confirm the WAN_IN allow rule is **enabled** (defaults to off on creation)
- Confirm the rule is positioned **above** any DROP rules
- Confirm the correct port group is attached (game ports: 7777, 8888 for Satisfactory)
- Verify the player's IP is actually in the `GameServerAccess` group:
  UniFi → Firewall Groups → GameServerAccess

---

## Database issues

### `PermissionError: Cannot create database directory`
- The `data/` directory must be writable by the user running the bot
- `mkdir -p data && chown $(whoami) data`

### Resetting the database (development only)
```bash
rm data/gameserver_access.db
python main.py  # schema is re-created on startup
```

---

## Running the test suite
```bash
source venv/bin/activate
python -m pytest tests/ -v
```

All 174 tests should pass. If any fail after a config change, check that
environment variables are not leaking into the test process (tests mock all
config values internally).
