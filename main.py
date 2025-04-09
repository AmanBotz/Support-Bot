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

# Global mapping to link forwarded message IDs (in the owner’s chat)
# to original user IDs.
reply_mapping = {}

def register_user(user_id: int):
    """Register a new user in the database if not already present."""
    if get_user(user_id) is None:
        add_user(user_id)
        logger.info(f"Registered user {user_id}")

def is_banned(user_id: int) -> bool:
    """Check if the user is banned."""
    user = get_user(user_id)
    return user.get("banned", False) if user else False

@app.on_message(filters.command("start"))
def start_handler(client: Client, message: Message):
    """Send a welcome message on /start and register the user."""
    user_id = message.from_user.id
    register_user(user_id)
    app.send_message(
        chat_id=user_id,
        text="👋 Welcome! You can contact us through this bot. Simply send your message now."
    )

@app.on_message(filters.command("ban") & filters.user(OWNER_ID))
def ban_handler(client: Client, message: Message):
    """
    Ban a user either by replying to their message or by providing their user_id.
    Usage:
      - /ban <user_id>
      - Reply to a user's message with /ban
    Only the bot owner (OWNER_ID) can use this.
    """
    # Determine target user ID based on reply or argument.
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

@app.on_message(filters.command("unban") & filters.user(OWNER_ID))
def unban_handler(client: Client, message: Message):
    """
    Unban a user either by replying to their message or by providing their user_id.
    Usage:
      - /unban <user_id>
      - Reply to a user's message with /unban
    Only the bot owner (OWNER_ID) can use this.
    """
    # Determine target user ID based on reply or argument.
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

@app.on_message(filters.command("unbanall") & filters.user(OWNER_ID))
def unbanall_handler(client: Client, message: Message):
    """
    Unban all users.
    Only the bot owner (OWNER_ID) can use this command.
    """
    result = db.users.update_many({}, {"$set": {"banned": False}})
    message.reply(f"✅ Unbanned {result.modified_count} users.")

@app.on_message(filters.command("cast") & filters.user(OWNER_ID))
def cast_handler(client: Client, message: Message):
    """
    Broadcast a message to all users.
    Usage: /cast <message>
    Only the bot owner (OWNER_ID) can use this.
    """
    if len(message.command) < 2:
        message.reply("❌ Usage: /cast <message>")
        return
    # Update broadcast text with an emoji and a prefix.
    cast_message = message.text.split(" ", 1)[1]
    broadcast_text = f"{cast_message}"
    users = list(get_all_users())
    sent_count = 0
    for user in users:
        user_id = user["_id"]
        # Only send to non-banned users.
        if user.get("banned", False):
            continue
        try:
            app.send_message(chat_id=user_id, text=broadcast_text)
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send broadcast to {user_id}: {e}")
    message.reply(f"✅ Broadcast sent to {sent_count} users.")

@app.on_message(~filters.command(["start", "ban", "unban", "unbanall", "cast"]))
def message_handler(client: Client, message: Message):
    """
    Handle incoming messages from users.

    For non-command messages:
    - If the message is from the owner and is a reply to a forwarded message,
      send that reply back to the original user using our reply mapping.
    - Otherwise, forward the message to the owner and store the mapping.
    """
    user_id = message.from_user.id
    register_user(user_id)

    if is_banned(user_id):
        return

    # Owner replying to a forwarded message.
    if user_id == OWNER_ID and message.reply_to_message:
        # Try to get the target user from our stored mapping.
        original_user_id = reply_mapping.get(message.reply_to_message.id)
        if original_user_id:
            try:
                app.send_message(chat_id=original_user_id, text=message.text)
                message.reply("✉️ Reply sent.")
                # Optionally remove mapping after reply.
                del reply_mapping[message.reply_to_message.id]
            except Exception as e:
                logger.error(f"Failed to send reply to {original_user_id}: {e}")
                message.reply("❌ There was an error sending your reply.")
            return

    # Forward a user's message to the owner.
    try:
        forwarded = app.forward_messages(
            chat_id=OWNER_ID,
            from_chat_id=message.chat.id,
            message_ids=message.id
        )
        # Pyrogram may return a list; handle both cases.
        forwarded_message = forwarded[0] if isinstance(forwarded, list) else forwarded
        # Store the mapping: forwarded message ID -> original sender.
        reply_mapping[forwarded_message.id] = user_id
        message.reply("✅ Your message has been sent to support.")
    except Exception as e:
        logger.error(f"Failed to forward message from {user_id}: {e}")
        message.reply("❌ There was an error sending your message.")

if __name__ == "__main__":
    logger.info("Bot is starting...")
    app.run()
