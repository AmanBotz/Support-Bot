import os
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from mongo import get_database, add_user, update_user_ban_status, get_user, get_all_users

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Read configuration from environment variables.
BOT_TOKEN = os.environ.get("BOT_TOKEN")
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
OWNER_ID = int(os.environ.get("OWNER_ID", 0))

# Initialize the Pyrogram bot.
app = Client("support_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Initialize MongoDB connection.
db = get_database()

# Global mapping: forwarded message ID (in owner's chat) -> original sender ID.
reply_mapping = {}

def register_user(user_id: int):
    """Register a new user in the database if not already present."""
    if get_user(user_id) is None:
        add_user(user_id)
        logger.info(f"Registered user {user_id}")

def is_banned(user_id: int) -> bool:
    """Return True if the user is banned (as per the database record)."""
    user = get_user(user_id)
    return user.get("banned", False) if user else False

# ========= Owner-only Command Handlers =========
@app.on_message(filters.command("ban") & filters.user(OWNER_ID))
def ban_handler(client: Client, message: Message):
    """
    Ban a user by replying to their message or providing their user_id.
    Notifies the target user of the ban.
    """
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    elif len(message.command) >= 2:
        try:
            target_id = int(message.command[1])
        except ValueError:
            message.reply("❌ Invalid user_id provided.")
            return
    else:
        message.reply("❌ Usage: /ban <user_id> or reply to a user's message with /ban")
        return

    update_user_ban_status(target_id, True)
    message.reply(f"🚫 User {target_id} has been banned.")
    try:
        app.send_message(chat_id=target_id, text="🚫 You have been banned from contacting support.")
    except Exception as e:
        logger.error(f"Failed to notify banned user {target_id}: {e}")

@app.on_message(filters.command("unban") & filters.user(OWNER_ID))
def unban_handler(client: Client, message: Message):
    """
    Unban a user by replying to their message or providing their user_id.
    Notifies the target user of the unban.
    """
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    elif len(message.command) >= 2:
        try:
            target_id = int(message.command[1])
        except ValueError:
            message.reply("❌ Invalid user_id provided.")
            return
    else:
        message.reply("❌ Usage: /unban <user_id> or reply to a user's message with /unban")
        return

    update_user_ban_status(target_id, False)
    message.reply(f"✅ User {target_id} has been unbanned.")
    try:
        app.send_message(chat_id=target_id, text="✅ You have been unbanned. You can now contact support.")
    except Exception as e:
        logger.error(f"Failed to notify user {target_id} for unban: {e}")

@app.on_message(filters.command("unbanall") & filters.user(OWNER_ID))
def unbanall_handler(client: Client, message: Message):
    """
    Unban all users in the database.
    """
    result = db.users.update_many({}, {"$set": {"banned": False}})
    message.reply(f"✅ Unbanned {result.modified_count} users.")

@app.on_message(filters.command("cast") & filters.user(OWNER_ID))
def cast_handler(client: Client, message: Message):
    """
    Broadcast a message to all non-banned users.
    The message is prefixed with an emoji for enhanced UI.
    """
    if len(message.command) < 2:
        message.reply("❌ Usage: /cast <message>")
        return
    cast_message = message.text.split(" ", 1)[1]
    broadcast_text = f"📢 Broadcast:\n\n{cast_message}"
    users = list(get_all_users())
    sent_count = 0
    for user in users:
        user_id = user["_id"]
        if user.get("banned", False):
            continue  # Skip banned users.
        try:
            app.send_message(chat_id=user_id, text=broadcast_text)
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send broadcast to {user_id}: {e}")
    message.reply(f"✅ Broadcast sent to {sent_count} users.")

# ========= User Command Handlers =========
@app.on_message(filters.command("start") & ~filters.user(OWNER_ID))
def start_handler(client: Client, message: Message):
    """Welcome new users. If the user is banned, notify them and stop processing."""
    user_id = message.from_user.id
    register_user(user_id)
    if is_banned(user_id):
        app.send_message(chat_id=user_id, text="🚫 You are banned from contacting support.")
        return
    app.send_message(chat_id=user_id, text="👋 Welcome! You can contact us through this bot. Simply send your message now.")

# ========= General Message Handler for Users =========
@app.on_message(~filters.command(["ban", "unban", "unbanall", "cast", "start"]) & ~filters.user(OWNER_ID))
def user_message_handler(client: Client, message: Message):
    """
    For non-command messages from users.
    Immediately checks if the user is banned. If so, notifies them and does nothing.
    Otherwise, forwards the message to the owner and stores a mapping for replies.
    """
    user_id = message.from_user.id
    register_user(user_id)
    if is_banned(user_id):
        try:
            message.reply("🚫 You are banned from contacting support.")
        except Exception as e:
            logger.error(f"Error replying to banned user {user_id}: {e}")
        return

    try:
        forwarded = app.forward_messages(
            chat_id=OWNER_ID,
            from_chat_id=message.chat.id,
            message_ids=message.id
        )
        forwarded_message = forwarded[0] if isinstance(forwarded, list) else forwarded
        reply_mapping[forwarded_message.id] = user_id
        message.reply("✅ Your message has been sent to support.")
    except Exception as e:
        logger.error(f"Failed to forward message from {user_id}: {e}")
        message.reply("❌ There was an error sending your message.")

# ========= Owner Reply Handler =========
@app.on_message(filters.user(OWNER_ID) & ~filters.command(["ban", "unban", "unbanall", "cast"]))
def owner_reply_handler(client: Client, message: Message):
    """
    When the owner replies to a forwarded message, look up the original sender
    using the stored mapping and send the reply to that user.
    """
    if message.reply_to_message:
        original_user_id = reply_mapping.get(message.reply_to_message.id)
        if original_user_id:
            try:
                app.send_message(chat_id=original_user_id, text=message.text)
                message.reply("✉️ Reply sent.")
                del reply_mapping[message.reply_to_message.id]
            except Exception as e:
                logger.error(f"Failed to send reply to {original_user_id}: {e}")
                message.reply("❌ There was an error sending your reply.")

if __name__ == "__main__":
    logger.info("Bot is starting...")
    app.run()
