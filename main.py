import os
import logging
import threading
import time
import requests

from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import Message

from mongo import (
    get_database,
    add_user,
    update_user_ban_status,
    get_user,
    get_all_users,
)

# ─── Configuration ─────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Telegram & Mongo
BOT_TOKEN = os.environ["BOT_TOKEN"]
API_ID    = int(os.environ["API_ID"])
API_HASH  = os.environ["API_HASH"]
OWNER_ID  = int(os.environ["OWNER_ID"])
db        = get_database()

# Health-check Flask app will run on port 8000
FLASK_PORT = 8000

# FQDN to ping every 30 seconds (must include protocol, e.g. https://example.com/)
FQDN = os.environ.get("FQDN")

# ─── Flask Health-Check ────────────────────────────────────────────────────────

flask_app = Flask(__name__)

@flask_app.route("/")
def health():
    return "🟢 Support Bot is running", 200

def run_flask():
    flask_app.run(host="0.0.0.0", port=FLASK_PORT, use_reloader=False)

# ─── FQDN Ping Task (silent) ────────────────────────────────────────────────────

def ping_fqdn():
    if not FQDN:
        return
    while True:
        try:
            requests.get(FQDN, timeout=10)
        except:
            pass
        time.sleep(30)

# ─── Telegram Bot Setup ─────────────────────────────────────────────────────────

bot = Client(
    "support_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# Keep track of forwarded→original user mapping
reply_mapping = {}

def register_user(user_id: int):
    if get_user(user_id) is None:
        add_user(user_id)
        logger.info(f"Registered user {user_id}")

def is_banned(user_id: int) -> bool:
    u = get_user(user_id)
    return bool(u and u.get("banned", False))

def guard_banned(func):
    """
    Decorator: immediately block & notify banned users.
    """
    def wrapper(client: Client, message: Message):
        uid = message.from_user.id
        register_user(uid)
        if is_banned(uid):
            message.reply("🚫 You are banned from contacting support.")
            return
        return func(client, message)
    return wrapper

# ── Owner-Only Commands ─────────────────────────────────────────────────────────

@bot.on_message(filters.command("ban") & filters.user(OWNER_ID))
def ban_handler(c, m: Message):
    if m.reply_to_message:
        target = reply_mapping.get(m.reply_to_message.id) or m.reply_to_message.from_user.id
    elif len(m.command) > 1:
        target = int(m.command[1])
    else:
        return m.reply("❌ Usage: /ban <user_id> or reply with /ban")
    update_user_ban_status(target, True)
    m.reply(f"🚫 User {target} banned.")
    try: bot.send_message(target, "🚫 You have been banned from support.")
    except: pass

@bot.on_message(filters.command("unban") & filters.user(OWNER_ID))
def unban_handler(c, m: Message):
    if m.reply_to_message:
        target = reply_mapping.get(m.reply_to_message.id) or m.reply_to_message.from_user.id
    elif len(m.command) > 1:
        target = int(m.command[1])
    else:
        return m.reply("❌ Usage: /unban <user_id> or reply with /unban")
    update_user_ban_status(target, False)
    m.reply(f"✅ User {target} unbanned.")
    try: bot.send_message(target, "✅ You have been unbanned. You can now contact support.")
    except: pass

@bot.on_message(filters.command("unbanall") & filters.user(OWNER_ID))
def unbanall_handler(c, m: Message):
    result = db.users.update_many({}, {"$set": {"banned": False}})
    m.reply(f"✅ Unbanned {result.modified_count} users.")

@bot.on_message(filters.command("cast") & filters.user(OWNER_ID))
def cast_handler(c, m: Message):
    if len(m.command) < 2:
        return m.reply("❌ Usage: /cast <message>")
    text = m.text.split(" ", 1)[1]
    broadcast = f"📢 Broadcast:\n\n{text}"
    count = 0
    for u in get_all_users():
        uid = u["_id"]
        if u.get("banned"): continue
        try:
            bot.send_message(uid, broadcast)
            count += 1
        except: pass
    m.reply(f"✅ Broadcast sent to {count} users.")

# ── User Commands & Messaging ────────────────────────────────────────────────────

@bot.on_message(filters.command("start") & ~filters.user(OWNER_ID))
@guard_banned
def start_cmd(c, m: Message):
    m.reply("👋 Welcome! Simply send your message to contact support.")

@bot.on_message(~filters.command(["start","ban","unban","unbanall","cast"]) & ~filters.user(OWNER_ID))
@guard_banned
def user_message(c, m: Message):
    fwd = bot.forward_messages(
        OWNER_ID, m.chat.id, m.id
    )
    fmsg = fwd[0] if isinstance(fwd, list) else fwd
    reply_mapping[fmsg.id] = m.from_user.id
    m.reply("✅ Your message has been sent to support.")

@bot.on_message(filters.user(OWNER_ID) & ~filters.command(["ban","unban","unbanall","cast"]))
def owner_reply(c, m: Message):
    if m.reply_to_message:
        orig = reply_mapping.get(m.reply_to_message.id)
        if orig:
            bot.send_message(orig, m.text)
            m.reply("✉️ Reply sent.")
            del reply_mapping[m.reply_to_message.id]

# ─── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Start Flask health-check
    threading.Thread(target=run_flask, daemon=True).start()

    # Start FQDN pinger (silent)
    threading.Thread(target=ping_fqdn, daemon=True).start()

    # Run the Telegram bot (blocking)
    bot.run()
