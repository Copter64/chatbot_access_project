# Discord Bot Testing Guide

This guide provides step-by-step instructions for testing the Discord bot before moving to Phase 3.

---

## Quick Summary

✅ **Automated Tests**: 14/14 PASSED (100%)
- Configuration validation
- Database operations  
- Bot event handlers
- Token generation security
- Role checking logic

⏳ **Manual Tests**: To be performed in Discord

---

## Phase 1: Run Automated Tests

### Step 1: Run the Test Suite

```bash
python3 test_discord_bot.py
```

**Expected Output:**
```
✅ All automated tests passed
📈 Pass Rate: 100.0%
🎉 ALL AUTOMATED TESTS PASSED!
Ready to proceed with manual Discord testing.
```

If any test fails, check the error output and troubleshoot before proceeding.

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
Logged in as YourBotName (ID: ...)
Connected to X guild(s)
Commands synced to guild ...
Bot is ready!
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
4. Try to use the link (will test in Phase 3)

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
- ✅ All tests passed: **Ready for Phase 3**
- ❌ Some tests failed: Debug and retest before Phase 3

---

## Troubleshooting

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

## Next Steps

✅ **If ALL tests pass:**
1. Proceed to Phase 3: Web Server Module
2. Implement IP verification page
3. Test full access flow

❌ **If tests fail:**
1. Review errors above
2. Check logs:
   ```bash
   tail -f data/bot.log
   ```
3. Debug and retest
4. Ask for help if stuck

---

## Command Reference

```bash
# Run automated tests
python3 test_discord_bot.py

# Start the bot
python3 main.py

# Check configuration
python3 validate_bot.py

# View database
sqlite3 data/gameserver_access.db

# View logs
tail -f data/bot.log

# Stop the bot
Ctrl+C
```
