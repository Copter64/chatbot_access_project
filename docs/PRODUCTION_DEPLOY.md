# Production Deployment — Proxmox VM with Docker

This guide migrates the bot from its current bare-metal Ubuntu 24.04 host
(`192.168.1.122`) to a dedicated Proxmox VM running Docker.  The `Dockerfile`
and `docker-compose.yml` are already in the repository.

---

## Overview

```
Internet
   │
   ▼
UDM Pro (port forwards 8443, 7777, 8888)
   │
   ▼
Proxmox VM — Ubuntu 24.04 LTS
   ├── Docker container: gameserver-access-bot
   │     ├── Flask HTTPS :8443
   │     └── Discord bot (outbound only)
   └── ./data/  ← SQLite DB + log file (host volume)
```

---

## Step 1 — Create the Proxmox VM

In the Proxmox web UI:

1. Click **Create VM**
2. Recommended specs:

   | Setting | Value |
   |---|---|
   | OS | Ubuntu 24.04 LTS (Noble) ISO |
   | CPU | 2 cores |
   | RAM | 2 GB |
   | Disk | 20 GB (thin-provisioned) |
   | Network | VirtIO bridge on your LAN VLAN |

3. Note the VM's assigned LAN IP after first boot (e.g. `192.168.1.130`).
   Set a **static DHCP reservation** on the UDM Pro for this MAC address so
   the IP never changes.

---

## Step 2 — Install Docker on the VM

SSH into the new VM, then:

```bash
# Update packages
sudo apt update && sudo apt upgrade -y

# Install Docker via the official convenience script
curl -fsSL https://get.docker.com | sudo sh

# Add your user to the docker group (log out and back in after)
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker --version
docker compose version
```

---

## Step 3 — Clone the Repository

```bash
# Install git if needed
sudo apt install -y git

git clone https://github.com/Copter64/chatbot_access_project.git
cd chatbot_access_project
```

---

## Step 4 — Transfer TLS Certificates

The bot needs the Let's Encrypt certs for `home.chrissibiski.com`.
Two options:

### Option A — Copy certs from the current host (quickest)

Run this **from the current host** (`192.168.1.122`):

```bash
# Replace 192.168.1.130 with your new VM's IP
sudo tar czf - /etc/letsencrypt | ssh user@192.168.1.130 \
  "sudo tar xzf - -C /"

# Fix permissions on the VM
ssh user@192.168.1.130 \
  "sudo chown -R root:$USER /etc/letsencrypt/live /etc/letsencrypt/archive && \
   sudo chmod 750 /etc/letsencrypt/live /etc/letsencrypt/archive && \
   sudo chmod 640 /etc/letsencrypt/archive/home.chrissibiski.com/*.pem"
```

### Option B — Re-issue via DNS challenge on the VM

```bash
sudo apt install -y certbot
sudo certbot certonly --manual --preferred-challenges dns \
  -d home.chrissibiski.com
# Add the _acme-challenge DNS TXT record when prompted
```

Set up auto-renewal:
```bash
sudo systemctl enable --now certbot.timer
```

---

## Step 5 — Configure `.env`

```bash
cp .env.example .env
nano .env
```

Only values that need to change from the development setup:

| Variable | New value |
|---|---|
| `WEB_BASE_URL` | `https://home.chrissibiski.com:8443` (same — domain doesn't change) |
| `DATABASE_PATH` | `./data/gameserver_access.db` (unchanged — relative path works in container) |
| `LOG_FILE` | `./data/bot.log` |
| All others | Copy from the current host's `.env` |

> **Never commit `.env`** — it contains credentials.

---

## Step 6 — Create the Data Directory

```bash
mkdir -p data
# The docker compose volume ./data:/app/data will mount this
```

---

## Step 7 — Build and Start the Container

```bash
docker compose up -d --build

# Follow startup logs
docker compose logs -f bot
```

Expected output:
```
✅ Configuration valid
✅ Bot commands set up
✅ Web server running at https://home.chrissibiski.com:8443
✅ Bot initialization complete
Logged in as GameServerInterface#6328
```

Verify the health endpoint from inside the VM:
```bash
curl -sk https://localhost:8443/health
# {"status": "ok"}
```

---

## Step 8 — Update the UDM Pro Port Forwards

The port forwards currently point to `192.168.1.122`. Update them to the new
VM IP (e.g. `192.168.1.130`).

In **UniFi → Firewall & Security → Port Forwarding**, update the **Forward IP**
for each rule:

| Rule | Port | New Forward IP |
|---|---|---|
| `GameServerAccessBot` | `8443` | `192.168.1.130` |
| `Satisfactory Game` | `7777` | `192.168.1.130` |
| `Satisfactory Beacon` | `8888` | `192.168.1.130` |

> If you're keeping the game server on the original host and only moving the bot,
> only update the `8443` rule.

---

## Step 9 — Stop the Old Bot

Once you've verified the new container is working:

```bash
# On 192.168.1.122
pkill -f "python main.py"
```

Remove the old process from any restart mechanism (cron, systemd, etc.) if
applicable.

---

## Step 10 — Verify End-to-End

1. In Discord, run `/request-access` — confirm you receive a DM with a link
2. Open the link on mobile data — confirm it loads over HTTPS
3. Submit the IP — confirm the success page and Unifi group update
4. Run `/list-ips` — confirm the new IP appears

---

## Ongoing Operations

### View logs
```bash
docker compose logs -f bot
# or the persistent log file:
tail -f data/bot.log
```

### Restart after a crash
`restart: unless-stopped` in `docker-compose.yml` handles this automatically.
Docker starts the container on VM boot as well (requires the Docker daemon to
be enabled, which it is by default after `get.docker.com`).

### Update the bot to a new version
```bash
git pull
docker compose up -d --build
```
The SQLite database in `./data/` is preserved across rebuilds.

### Renew TLS certificates
If certs are managed on the VM:
```bash
sudo certbot renew
# No restart needed — the container reads certs at runtime,
# but do restart if the cert file inode changes:
docker compose restart bot
```

If certs are managed on another host and copied over, repeat Step 4 Option A
after renewal.

### Migrate the database from the old host
If you want to preserve existing IP records and token history:

```bash
# On the current host
scp /home/copter64/chatbot_access_project/data/gameserver_access.db \
    user@192.168.1.130:/home/user/chatbot_access_project/data/
```

Do this **before** first-starting the container on the VM, or stop the
container first to avoid a write conflict.

---

## Rollback

If something goes wrong, bring the old bot back up on `192.168.1.122`:

```bash
cd /home/copter64/chatbot_access_project
source venv/bin/activate
nohup python main.py > /tmp/bot.log 2>&1 &
```

And revert the UDM Pro port forwards back to `192.168.1.122`.
