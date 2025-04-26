# Telegram Support Bot

A versatile Telegram support bot built with Pyrogram and MongoDB. It handles user messages, admin commands, health checks, and periodic FQDN pings seamlessly.


# Features

#no need uptimerobot

**/start:** Greets users and guides them to send support messages.

**Message Forwarding:** Forwards user messages to the designated owner.

**Owner Replies:** Routes owner replies back to the correct user automatically.

**User Management:**

**/ban:** Ban a user by replying to their message or specifying their user ID.

**/unban:** Unban a user similarly by reply or ID.

**/unbanall:** Lift bans for all users in bulk.


**Broadcast (/cast):** Send a formatted announcement to all non-banned users.

**Health Check:*** Built-in Flask endpoint at / on port 8000, returning status.

**FQDN Pinger:** Periodically (every 30 seconds) sends a request to a configured URL to keep services awake. Means your bot will not sleep.

# Environment Variables

```env
API_ID=123456
API_HASH=abcdef1234567890abcdef1234567890
BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
OWNER_ID=123456789
MONGO_URL=mongodb://localhost:27017/support_bot
FQDN=https://example.com/ # your server url, so your bot will not sleep
