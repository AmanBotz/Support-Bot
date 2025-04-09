# Telegram Support Bot

A lightweight Telegram bot built using [Pyrogram](https://docs.pyrogram.org/) for handling user support messages.

This bot allows users to contact the owner directly by messaging the bot. The owner can reply to users, broadcast announcements, and manage users (ban/unban). MongoDB is used for storing user data.

---

## Features

- **/start** - Welcomes the user and prompts them to send a message.
- **Direct Messaging** - Users can send any message; it is forwarded to the bot owner.
- **Reply Support** - The owner can reply to forwarded messages; responses are sent back to the original user.
- **/ban** - Ban a user (reply to their message or provide user ID).
- **/unban** - Unban a user (reply to their message or provide user ID).
- **/unbanall** - Unban all users.
- **/cast** - Broadcast a message to all users.
- **MongoDB Integration** - Tracks users and ban status.
- **Dockerized** - Ready for deployment with Docker.
- **Healthcheck** - A simple Flask server (`server.py`) for container health checks on port 8000.

---

## Environment Variables

The bot requires the following environment variables to function:

| Variable     | Description                              |
|--------------|------------------------------------------|
| `API_ID`     | Telegram API ID from [my.telegram.org](https://my.telegram.org) |
| `API_HASH`   | Telegram API Hash from [my.telegram.org](https://my.telegram.org) |
| `BOT_TOKEN`  | Token for your bot from BotFather        |
| `OWNER_ID`   | Your personal Telegram user ID (int)     |
| `MONGO_URL`  | MongoDB connection URI                   |

You can create a `.env` file like this:

```env
API_ID=123456
API_HASH=abcdef1234567890abcdef1234567890
BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
OWNER_ID=123456789
MONGO_URL=mongodb://localhost:27017/support_bot
