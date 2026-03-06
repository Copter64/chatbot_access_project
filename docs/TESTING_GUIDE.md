# Discord Bot Testing Guide

This guide covers manual and automated testing for all completed phases.

---

## Test Status Overview

| Phase | Automated | Manual |
|---|---|---|
| Phase 2 — Discord Bot | ✅ 14/14 passed | ✅ Verified in Discord |
| Phase 3 — Web Server + TLS | ✅ 16/16 passed | ✅ End-to-end flow verified |

---

## Running All Automated Tests

```bash
source venv/bin/activate
python -m pytest tests/ -v
```

**Expected Output:**
```
tests/test_web_routes.py ................      16 passed
```

---

## Phase 2: Start the Bot

### Step 1: Start the Bot

In a terminal, run:

```bash
python3 main.py
```

**Expected Output:**
```
✅ Configuration valid
✅ Database initialized
✅ Discord bot initialized
✅ Bot commands set up
✅ Web server running at https://yourdomain.com:8443
✅ Bot initialization complete
```

⏱️ **Wait for "Bot is ready!"** - this means the bot is connected and commands are synced.

### Step 2: Verify Bot is Online

In Discord:
1. Go to your server member list
2. Find your bot's name
3. ✅ Should show as **ONLINE** (green status)

**If bot is offline:**
- Check terminal for error messages
- Verify `DISCORD_BOT_TOKEN` in `.env` is correct
- Check bot is invited to your server

---

## Phase 3: Manual Testing Checklist

Follow these tests in order. Keep the bot running while testing!

### 🧪 TEST 1: Command Visibility

**Objective:** Verify `/request-access` command appears

**Steps:**
1. In Discord, click the message box
2. Type `/` (forward slash)
3. You should see: `request-access` command

**Expected Result:**
```
/request-access  Request firewall access to the game server
```

**✅ PASS if:** Command appears in the slash command menu  
**❌ FAIL if:** Command doesn't appear

**Troubleshooting:**
- Wait 1-5 minutes for Discord to sync
- Try pressing Ctrl+R to refresh Discord
- Restart the Discord client
- Check that `DISCORD_GUILD_ID` in `.env` matches your server

---

### 🧪 TEST 2: Role Verification (Negative Test)

**Objective:** Verify bot requires "gameserver" role

**Setup:**
1. Create a test user (or use a friend)
2. **Make sure this user does NOT have the "gameserver" role**

**Steps:**
1. Have the test user run: `/request-access`
2. Look at the response

**Expected Result:**
```
❌ You need the **gameserver** role to request server access.
```

**✅ PASS if:** Error message about missing role appears  
**❌ FAIL if:** User gets access link or different error

---

### 🧪 TEST 3: Successful Access Request (Positive Test)

**Objective:** Verify users WITH role get access link

**Setup:**
1. Assign the "gameserver" role to yourself

**Steps:**
1. Run: `/request-access`
2. Wait for response

**Expected Result (with DMs enabled):**
```
✅ I've sent you a DM with your access link!
Check your direct messages.
```

Then check your DMs - you should see:
```
🔗 Game Server Access Request

Click the link below to verify your IP address and gain access 
to the game server:

http://yourdomain.com:8080/check-ip/[TOKEN_HERE]

⏰ This link expires in 15 minutes.
📝 Your IP will be granted access for 30 days.
```

**Expected Result (if DMs disabled):**
```
✅ I've sent you a DM with your access link!

Alternatively, here's your access link:
http://yourdomain.com:8080/check-ip/[TOKEN_HERE]
```

**✅ PASS if:**
- DM received (if enabled) OR
- Ephemeral message in channel (if DMs disabled)
- Access link is formatted correctly
- Token looks like: `a3bC9xYzT2q...` (32 random characters)

**❌ FAIL if:**
- No response or error
- Link format is wrong
- Token format is wrong

---

### 🧪 TEST 4: Token Expiration

**Objective:** Verify tokens expire after 15 minutes

**Steps:**
1. Copy the access link from TEST 3
2. Note the current time
3. Wait 15 minutes
4. Try to use the link — it should show an error page (expired)

**Expected Behavior:**
- Within 15 minutes: Link should work
- After 15 minutes: Link should be invalid

✅ **PASS if:** Token format is correct and expires as expected

---

### 🧪 TEST 5: Rate Limiting

**Objective:** Verify bot prevents spam requests

**Steps:**
1. Run: `/request-access`
2. Immediately run: `/request-access` again
3. Look at the second response

**Expected Result:**
```
⏳ You've requested access recently. 
Please wait 5 minutes before requesting again.
```

**✅ PASS if:** Rate limit message appears  
**❌ FAIL if:** Second request succeeds

**Configuration:**
- Default: 1 request per 5 minutes
- Edit `RATE_LIMIT_REQUESTS` and `RATE_LIMIT_PERIOD_MINUTES` in `.env` to change

---

### 🧪 TEST 6: Database Verification

**Objective:** Verify data is saved correctly

**Setup:**
- Keep bot running
- Run `/request-access` once first

**Steps:**

1. Open another terminal:
```bash
sqlite3 data/gameserver_access.db
```

2. View users:
```sql
SELECT * FROM users;
```

Expected output:
```
id|discord_id|discord_username|created_at|updated_at
1|123456789|YourUsername|...|...
```

3. View tokens:
```sql
SELECT token, user_id, used, used_at FROM access_tokens;
```

Expected output:
```
token|user_id|used|used_at
abC1xyz9...|1|0|
```

4. View requests:
```sql
SELECT user_id, request_type, success FROM request_history;
```

Expected output:
```
user_id|request_type|success
1|access_request|1
```

5. Exit SQLite:
```sql
.quit
```

**✅ PASS if:**
- Users table has your user
- Tokens table has the token you received
- Request history shows "access_request" with success=1

**❌ FAIL if:**
- Tables are empty
- Incorrect data

---

### 🧪 TEST 7: DM Handling (Both Cases)

**Objective:** Verify both DM and fallback behavior

**Case 1: User WITH DMs Enabled**

1. Ensure a user has DMs from server members enabled
2. Run `/request-access`
3. **Expected:** User receives a DM with link

**Case 2: User WITH DMs Disabled**

1. Disable DMs from server members
2. Run `/request-access`
3. **Expected:** Ephemeral message in channel with link

**✅ PASS if:** Both cases work correctly

---

### 🧪 TEST 8: Error Recovery

**Objective:** Verify bot handles disconnection gracefully

**Steps:**

1. Bot is running - run `/request-access` ✅ (should work)
2. Stop the bot (press Ctrl+C in terminal)
3. Try `/request-access` again ❌ (should fail)
4. Restart the bot (python3 main.py)
5. Wait for "Bot is ready!" message
6. Run `/request-access` again ✅ (should work)

**✅ PASS if:**
- Works before stop
- Fails while stopped
- Works again after restart

---

## Test Results Summary

After completing all tests, fill in the checklist below:

```
TEST 1: Command Visibility          [  ] PASS  [  ] FAIL
TEST 2: Role Verification (Neg)     [  ] PASS  [  ] FAIL
TEST 3: Access Request (Pos)        [  ] PASS  [  ] FAIL
TEST 4: Token Expiration            [  ] PASS  [  ] FAIL
TEST 5: Rate Limiting               [  ] PASS  [  ] FAIL
TEST 6: Database Verification       [  ] PASS  [  ] FAIL
TEST 7: DM Handling                 [  ] PASS  [  ] FAIL
TEST 8: Error Recovery              [  ] PASS  [  ] FAIL
```

**Status:**
- ✅ All tests passed: **Ready for Phase 3 web flow testing**
- ❌ Some tests failed: Debug and retest

---

## Phase 2 Troubleshooting

### "Command doesn't appear"
1. Wait 1-5 minutes for Discord to sync
2. Restart Discord client
3. Check `DISCORD_GUILD_ID` in `.env`
4. Restart the bot

### "Bot is offline"
1. Check `DISCORD_BOT_TOKEN` in `.env`
2. Check terminal for error messages
3. Verify bot is invited to server
4. Check Discord Developer Portal > Bot > Intents are enabled

### "Can't verify roles"
1. Ensure "SERVER MEMBERS INTENT" is enabled in Discord Developer Portal
2. Verify "gameserver" role exists in server
3. Assign role to test user

### "No DMs received"
1. User must enable "Allow direct messages from server members"
2. Check spam/other folders
3. User can see link in channel as fallback

### "Database is empty"
1. Check you're using the correct database file
2. Verify path: `data/gameserver_access.db`
3. Run tests again to populate database

---

## Phase 2 Next Steps

✅ **If ALL Phase 2 tests pass:**
1. Proceed to Phase 3 web flow testing (see section below)

❌ **If tests fail:**
1. Review errors above
2. Check logs:
   ```bash
   tail -f /tmp/bot.log
   ```
3. Debug and retest

---

## Command Reference

```bash
# Run all automated tests
python -m pytest tests/ -v

# Start the bot
python3 main.py

# Watch logs live
tail -f /tmp/bot.log

# View database
sqlite3 data/gameserver_access.db

# Stop bot (background)
pkill -f "python main.py"
```

---

## Phase 3 Manual Tests (Web Flow)

### Prerequisites

Before testing externally:
- ✅ `sudo ufw allow 8443/tcp` run on server
- ✅ UDM Pro port forward: external `8443` → `YOUR_SERVER_IP:8443`
  - **The internal port must match `WEB_PORT`** — a common gotcha is having a stale port value
- ✅ Public DNS A record points to public IP (verify with external DNS, not internal DNS)
- ✅ Bot is running and `/health` returns `{"status": "ok"}`

```bash
# Quick health check from outside
curl -sk https://home.chrissibiski.com:8443/health
```

### End-to-End Flow Test

**From inside LAN (PC/laptop):**
1. Run `/request-access` in Discord
2. Open the DM link in a browser
3. Page shows your **LAN IP** (e.g. `192.168.1.x`) — this is expected for LAN users
4. Click **Confirm Access** — success page shown with IP and expiry date
5. Try the same link again — should show "Link Expired or Already Used" (410)

**From outside network (recommended for full test):**
1. Turn off WiFi on your phone (use mobile data only)
2. Run `/request-access` in Discord
3. Open the DM link — page shows your **public/mobile IP**
4. Click **Confirm Access** — success page shown
5. Verify IP saved in the database (see below)

### Verify IP in Database

```bash
sqlite3 data/gameserver_access.db "
SELECT u.discord_username, i.ip_address, i.added_at, i.expires_at
FROM ip_addresses i JOIN users u ON i.user_id = u.id
ORDER BY i.added_at DESC LIMIT 5;
"
```

### Error Page Tests

| Test | Steps | Expected |
|---|---|---|
| Expired/used token | Visit a link that was already confirmed | Error page (410) |
| Invalid token format | Visit `/check-ip/badtoken` | Error page (400) |
| Double submit | POST confirm twice on same token | Error page (410) on second |

### Monitoring Logs During Tests

```bash
tail -f /tmp/bot.log
# Filter to web requests only
tail -f /tmp/bot.log | grep -E 'GET|POST|ERROR|confirmed|denied'
```

---

## Networking Troubleshooting

### Page hangs / times out externally
1. Check UDM Pro port forward — the **internal port** must match `WEB_PORT` (currently `8443`)
2. Check server firewall: `sudo ufw status | grep 8443` — must show `ALLOW`
3. Test public IP directly: `curl -sk https://YOUR_PUBLIC_IP:8443/health`

### Page loads but shows internal IP
- User is on the same LAN — expected behaviour
- Use a phone on mobile data (WiFi off) to test external IP

### DNS resolves to internal IP externally
- Internal DNS override (split-horizon) is fine for LAN users
- Verify public DNS: `curl -s "https://dns.google/resolve?name=yourdomain.com&type=A"`

### TLS certificate error in browser
- Cert may have expired (Let's Encrypt certs last 90 days)
- Renew: `sudo certbot renew --manual --preferred-challenges dns`
- Check file permissions: `python3 -c "open('/etc/letsencrypt/live/yourdomain/privkey.pem').read()"`

---

## Next Steps

✅ **If ALL Phase 2 + Phase 3 tests pass:**
- Proceed to Phase 4: Unifi API Integration
- Requires: real `UNIFI_USERNAME`, `UNIFI_PASSWORD`, and `FIREWALL_GROUP_NAME` in `.env`

❌ **If tests fail:**
1. Review errors above
2. Check logs: `tail -f /tmp/bot.log`
3. Debug and retest

