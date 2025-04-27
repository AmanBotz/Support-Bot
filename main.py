import os
import logging
import threading
import time
import requests
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import Message
from mongo import get_database, add_user, update_user_ban_status, get_user, get_all_users

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
OWNER_ID = int(os.environ.get("OWNER_ID", 0))
FQDN = os.environ.get("FQDN")

# Initialize clients
app = Client("support_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
db = get_database()
reply_mapping = {}

# Flask setup
flask_app = Flask(__name__)
@flask_app.route("/")
def health_check():
    return "🟢 Support Bot Operational", 200

def run_flask():
    flask_app.run(host='0.0.0.0', port=8000, use_reloader=False)

# FQDN Pinger
def ping_fqdn():
    while True:
        try:
            if FQDN:
                requests.get(FQDN, timeout=10)
        except Exception as e:
            pass
        time.sleep(30)

# Helper functions
def register_user(user_id: int):
    if not get_user(user_id):
        add_user(user_id)
        logger.info(f"New user: {user_id}")

def is_banned(user_id: int) -> bool:
    user = get_user(user_id)
    return user.get("banned", False) if user else False

def guard_banned(func):
    def wrapper(client: Client, message: Message):
        user_id = message.from_user.id
        register_user(user_id)
        if is_banned(user_id):
            message.reply("🚫 Account Restricted\n\nYour access to support has been suspended.")
            return
        return func(client, message)
    return wrapper

# ================= Command Handlers =================
@app.on_message(filters.command("ban") & filters.user(OWNER_ID))
def ban_handler(client: Client, message: Message):
    try:
        target_id = (reply_mapping.get(message.reply_to_message.id) 
                    if message.reply_to_message else int(message.command[1]))
    except:
        message.reply("🔍 Invalid format!\nUsage: /ban <user_id> or reply to message")
        return

    update_user_ban_status(target_id, True)
    message.reply(f"🔨 Banned User ID: {target_id}")
    try:
        app.send_message(target_id, "⛔ Account Restricted\n\nYou can no longer contact support.")
    except Exception as e:
        logger.error(f"Ban notification failed: {e}")

@app.on_message(filters.command("unban") & filters.user(OWNER_ID))
def unban_handler(client: Client, message: Message):
    try:
        target_id = (reply_mapping.get(message.reply_to_message.id) 
                    if message.reply_to_message else int(message.command[1]))
    except:
        message.reply("🔍 Invalid format!\nUsage: /unban <user_id> or reply to message")
        return

    update_user_ban_status(target_id, False)
    message.reply(f"🎉 Unbanned User ID: {target_id}")
    try:
        app.send_message(target_id, "✅ Access Restored\n\nYou can now contact support again!")
    except Exception as e:
        logger.error(f"Unban notification failed: {e}")

@app.on_message(filters.command("unbanall") & filters.user(OWNER_ID))
def unbanall_handler(client: Client, message: Message):
    db.users.update_many({}, {"$set": {"banned": False}})
    message.reply("🌟 Mass Unban Complete\n\nAll users have been reinstated!")

@app.on_message(filters.command("cast") & filters.user(OWNER_ID))
def cast_handler(client: Client, message: Message):
    if len(message.command) < 2:
        message.reply("📢 Broadcast Format:\n/cast <your message>")
        return
    
    broadcast_text = f"📣 Official Announcement\n\n{message.text.split(' ', 1)[1]}"
    sent_count = 0
    
    for user in get_all_users():
        if not user.get("banned"):
            try:
                app.send_message(user["_id"], broadcast_text)
                sent_count += 1
            except Exception as e:
                logger.error(f"Broadcast failed for {user['_id']}: {e}")
    
    message.reply(f"📡 Broadcast Status\nMessages delivered: {sent_count}")

# ================= User Interaction =================
@app.on_message(filters.command("start") & ~filters.user(OWNER_ID))
@guard_banned
def start_handler(client: Client, message: Message):
    app.send_message(
        message.from_user.id,
        "👋 Welcome to Support!\n\n"
        "• Simply type your message to contact our team\n"
        "• We typically respond within 24 hours\n"
        "• Keep it concise for faster assistance"
    )

@app.on_message(~filters.command(["ban", "unban", "unbanall", "cast", "start"]) & ~filters.user(OWNER_ID))
@guard_banned
def user_message_handler(client: Client, message: Message):
    try:
        forwarded = message.forward(OWNER_ID)
        reply_mapping[forwarded.id] = message.from_user.id
        message.reply("📬 Message Received!\n\nOur team will respond shortly.")
    except Exception as e:
        logger.error(f"Forward failed: {e}")
        message.reply("⚠️ Message Delivery Failed\nPlease try again later.")

@app.on_message(filters.user(OWNER_ID) & ~filters.command(["ban", "unban", "unbanall", "cast"]))
def owner_reply_handler(client: Client, message: Message):
    if message.reply_to_message:
        original_user_id = reply_mapping.get(message.reply_to_message.id)
        if original_user_id:
            try:
                app.send_message(original_user_id, f"📩 Support Response\n\n{message.text}")
                message.reply("✅ Reply Delivered")
                del reply_mapping[message.reply_to_message.id]
            except Exception as e:
                logger.error(f"Reply failed: {e}")
                message.reply("❌ Failed to send reply")

# ================= System Start =================
def start_background_services():
    # Start Flask server
    threading.Thread(target=run_flask, daemon=True).start()
    # Start FQDN pinger
    if FQDN:
        threading.Thread(target=ping_fqdn, daemon=True).start()

if __name__ == "__main__":
    start_background_services()
    logger.info("Starting support system...")
    app.run()
