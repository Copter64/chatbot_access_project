# Discord Bot Setup Guide

This guide walks through creating and configuring the Discord bot for testing.

---

## Step 1: Create Discord Application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **"New Application"**
3. Give it a name (e.g., "Game Server Access Bot")
4. Click **"Create"**

---

## Step 2: Configure Bot User

1. In your application, click **"Bot"** in the left sidebar
2. Click **"Add Bot"** → **"Yes, do it!"**
3. Under **"Privileged Gateway Intents"**, enable:
   - ✅ **PRESENCE INTENT** (optional)
   - ✅ **SERVER MEMBERS INTENT** (required for role checking)
   - ✅ **MESSAGE CONTENT INTENT** (required)

4. Click **"Save Changes"**

---

## Step 3: Get Your Bot Token

1. In the **"Bot"** section, click **"Reset Token"**
2. Click **"Yes, do it!"**
3. **Copy the token** (you won't be able to see it again!)
4. Keep this token secret - never commit it to git!

---

## Step 4: Configure Bot Permissions

1. Go to **"OAuth2"** → **"URL Generator"** in the left sidebar
2. Under **"SCOPES"**, select:
   - ✅ `bot`
   - ✅ `applications.commands`

3. Under **"BOT PERMISSIONS"**, select:
   - ✅ **Send Messages**
   - ✅ **Send Messages in Threads**
   - ✅ **Read Message History**
   - ✅ **Use Slash Commands**
   - ✅ **Read Messages/View Channels** <-----Read messages looks like its under the scopes.

4. Copy the generated URL at the bottom (Added here for reference)

https://discord.com/oauth2/authorize?client_id=1478969997693948106&permissions=277025459200&response_type=code&redirect_uri=https%3A%2F%2Flocalhost&integration_type=0&scope=bot+applications.commands+messages.read

---

## Step 5: Invite Bot to Your Server

1. Paste the URL from Step 4 into your browser
2. Select your Discord server from the dropdown
3. Click **"Authorize"**
4. Complete the captcha
5. The bot will appear offline in your server (normal until you run it)

---

## Step 6: Get Your Server (Guild) ID

### Method 1: Enable Developer Mode
1. In Discord, go to **User Settings** → **Advanced**
2. Enable **"Developer Mode"**
3. Right-click your server icon
4. Click **"Copy Server ID"**

### Method 2: From Discord URL
1. Open Discord in browser
2. Navigate to your server
3. The URL will look like: `https://discord.com/channels/123456789/...`
4. The first number (123456789) is your Guild ID

---

## Step 7: Create "gameserver" Role

1. In your Discord server, go to **Server Settings** → **Roles**
2. Click **"Create Role"**
3. Name it exactly: `gameserver` (or update `GAMESERVER_ROLE_NAME` in .env)
4. Set any permissions/color you want
5. Click **"Save Changes"**
6. Assign this role to yourself or test users

---

## Step 8: Update .env File

Update your `.env` file with the real values:

```bash
# Discord Bot Configuration
DISCORD_BOT_TOKEN=YOUR_BOT_TOKEN_HERE
DISCORD_GUILD_ID=YOUR_SERVER_ID_HERE
GAMESERVER_ROLE_NAME=gameserver
```

**Important:** Make sure `.env` is in `.gitignore` to prevent committing secrets!

---

## Step 9: Test the Bot

Run the bot:

```bash
source venv/bin/activate
python3 main.py
```

You should see:
- ✅ Bot logs in successfully
- ✅ Commands synced to your guild
- ✅ "Bot is ready!" message

---

## Step 10: Test the Command

1. In your Discord server, type `/` and you should see:
   - `/request-access` - Request firewall access to the game server

2. Try running `/request-access`:
   - ✅ If you have the "gameserver" role: You'll get a DM with an access link
   - ❌ If you don't have the role: You'll see an error message

---

## Troubleshooting

### Bot doesn't appear online
- Check that `DISCORD_BOT_TOKEN` is correct
- Make sure the bot is running (`python3 main.py`)
- Check terminal for error messages

### Commands don't appear
- Wait 1-5 minutes for Discord to sync commands
- Make sure you're in the correct server
- Try restarting Discord client
- Check that `DISCORD_GUILD_ID` matches your server

### "Missing Permissions" error
- Go back to OAuth2 URL Generator and regenerate the invite link
- Re-invite the bot with proper permissions

### Can't verify roles
- Make sure "SERVER MEMBERS INTENT" is enabled in Bot settings
- The bot's role must be higher than the "gameserver" role in server settings

### DMs don't work
- Make sure user has DMs enabled from server members
- Check "Privacy Settings" in the server

---

## Security Reminders

- ✅ Never share your bot token
- ✅ Never commit `.env` to git
- ✅ Regenerate token if accidentally exposed
- ✅ Keep the `.gitignore` file updated

---

## Next Steps

Once the bot is working:
1. ✅ Test `/request-access` command
2. ✅ Verify role checking
3. ✅ Test rate limiting (try command twice quickly)
4. ⏭️ Move to Phase 3: Web Server
