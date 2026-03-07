# Unifi UDM Pro Setup Guide

This guide walks through the Unifi configuration required before running the bot.

---

## Overview

The bot manages a **Firewall Address Group** on the UDM Pro. When a user
registers their IP, the bot adds it to that group. A WAN_IN firewall rule
allows that group through to your game server ports. When the IP expires the
bot removes it automatically.

---

## Step 1 — Create a Local API User

The bot authenticates to the UDM Pro via its local REST API. Create a dedicated
read/write user rather than using your main admin account.

1. Open **UniFi OS** → **Users & Permissions** (top-right user icon → Users).
2. Click **Create User**.
3. Fill in a username (e.g. `botapi`) and a strong password.
4. Set role to **Network Administrator** (required to read/write firewall groups).
5. Save and note the credentials — these go into `.env` as `UNIFI_USERNAME` /
   `UNIFI_PASSWORD`.

> **Tip:** `UNIFI_SITE` is almost always `default` unless you have multiple
> sites configured.

---

## Step 2 — Create the Firewall Address Group

1. Open **Firewall & Security** → **Firewall Groups** (or **Security** → **Firewall**
   depending on your firmware).
2. Click **Create New Group**.
   - **Type**: IPv4 Address/Subnet Group
   - **Name**: `GameServerAccess` (must match `FIREWALL_GROUP_NAME` in `.env`)
3. Leave the address list empty — the bot will populate it at runtime.
4. Save.

---

## Step 3 — Add Your Game Server to an Address Group

Create a second, static group for your game server's **LAN IP**:

1. Create another Firewall Group:
   - **Type**: IPv4 Address/Subnet Group
   - **Name**: `GameServerIP`
   - **Address**: your server's LAN IP (e.g. `192.168.1.122`)
2. Save.

---

## Step 4 — Create the WAN_IN Allow Rule

This rule allows players in `GameServerAccess` to reach your server.

1. Go to **Firewall & Security** → **Firewall Rules** → **WAN In**.
2. Click **Create New Rule**.

| Field | Value |
|---|---|
| Name | `Allow GameServerAccess to GameServer` |
| Enabled | ✅ **On** (critical — it defaults to off) |
| Action | Accept |
| Protocol | TCP and UDP |
| Source type | Address/Port Group |
| Source group | `GameServerAccess` |
| Destination type | Address/Port Group |
| Destination address group | `GameServerIP` |
| Destination port group | Create a port group for your game ports (see below) |

**Create a port group first** (Firewall Groups → Create):
- **Type**: Port Group
- **Name**: `SatisfactoryPorts`
- **Ports**: `7777` (game), `8888` (beacon) — add as individual entries

3. Save the rule. **Move it above any default DROP rules** using the drag handle.

---

## Step 5 — Port Forward (External Access)

For external players to reach the web server that captures their IP:

1. Go to **Firewall & Security** → **Port Forwarding**.
2. Create a new rule:

| Field | Value |
|---|---|
| Name | `GameServerAccessBot` |
| Enabled | ✅ On |
| From | Any (or restrict to specific WAN interface) |
| Port | `8443` (must match `WEB_PORT`) |
| Forward IP | Your server's LAN IP |
| Forward Port | `8443` |
| Protocol | TCP |

Also add a port forward for each game port if external players need them:

| Name | Port | Forward IP | Forward Port | Protocol |
|---|---|---|---|---|
| `Satisfactory Game` | `7777` | `192.168.1.122` | `7777` | UDP+TCP |
| `Satisfactory Beacon` | `8888` | `192.168.1.122` | `8888` | UDP+TCP |

---

## Step 6 — Verify API Access

Test that the bot can reach your UDM Pro before starting:

```bash
cd /path/to/chatbot_access_project
source venv/bin/activate
python - << 'PYEOF'
from unifi_modules.client import UnifiClient
from config import Config

client = UnifiClient(
    host=Config.UNIFI_HOST,
    username=Config.UNIFI_USERNAME,
    password=Config.UNIFI_PASSWORD,
    site=Config.UNIFI_SITE,
    verify_ssl=Config.UNIFI_VERIFY_SSL,
)
client.login()
print("✅ Login OK")
groups = client.get_firewall_groups()
print(f"Found {len(groups)} firewall groups")
for g in groups:
    print(f"  - {g['name']}")
PYEOF
```

Expected output:
```
✅ Login OK
Found N firewall groups
  - GameServerAccess
  ...
```

---

## Required `.env` Values

```dotenv
UNIFI_HOST=https://192.168.1.1        # Your UDM Pro LAN IP
UNIFI_USERNAME=botapi
UNIFI_PASSWORD=your_strong_password
UNIFI_SITE=default
UNIFI_VERIFY_SSL=false                 # true if you have a valid cert on UDM Pro
FIREWALL_GROUP_NAME=GameServerAccess  # Must match your group name exactly
```

> Set `UNIFI_VERIFY_SSL=true` in production if your UDM Pro has a valid TLS
> certificate (e.g. via Let's Encrypt + custom domain). Self-signed certs require
> `false`.

---

## Troubleshooting

### Login returns 401
- Verify username and password in `.env`
- Ensure the user has **Network Administrator** role (not just read-only)

### Firewall group not found
- The group name is **case-sensitive** — `FIREWALL_GROUP_NAME` must match exactly

### External players can connect but LAN players can't (or vice versa)
- WAN_IN rules do **not** apply to LAN-originated traffic — this is expected
- LAN players bypass the firewall group entirely and connect directly

### Rule has no effect even though IP is in the group
- Confirm the WAN_IN rule is **enabled** (the enabled toggle defaults to off on creation)
- Confirm the rule is positioned **above** any DROP/REJECT rules in the list
