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
    app.send_message(chat_id=user_id, text="Welcome! You can contact us through this bot. Simply send your message now.")

@app.on_message(filters.command("ban") & filters.user(OWNER_ID))
def ban_handler(client: Client, message: Message):
    """
    Ban a user.
    Usage: /ban <user_id>
    Only the bot owner (OWNER_ID) can use this.
    """
    if len(message.command) < 2:
        message.reply("Usage: /ban <user_id>")
        return
    try:
        target_id = int(message.command[1])
        update_user_ban_status(target_id, True)
        message.reply(f"User {target_id} has been banned.")
    except ValueError:
        message.reply("Invalid user_id.")

@app.on_message(filters.command("unban") & filters.user(OWNER_ID))
def unban_handler(client: Client, message: Message):
    """
    Unban a user.
    Usage: /unban <user_id>
    Only the bot owner (OWNER_ID) can use this.
    """
    if len(message.command) < 2:
        message.reply("Usage: /unban <user_id>")
        return
    try:
        target_id = int(message.command[1])
        update_user_ban_status(target_id, False)
        message.reply(f"User {target_id} has been unbanned.")
    except ValueError:
        message.reply("Invalid user_id.")

@app.on_message(filters.command("cast") & filters.user(OWNER_ID))
def cast_handler(client: Client, message: Message):
    """
    Broadcast a message to all users.
    Usage: /cast <message>
    Only the bot owner (OWNER_ID) can use this.
    """
    if len(message.command) < 2:
        message.reply("Usage: /cast <message>")
        return
    cast_message = message.text.split(" ", 1)[1]
    users = list(get_all_users())
    sent_count = 0
    for user in users:
        user_id = user["_id"]
        # Only send to users not banned.
        if user.get("banned", False):
            continue
        try:
            app.send_message(chat_id=user_id, text=f"Broadcast: {cast_message}")
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send message to {user_id}: {e}")
    message.reply(f"Broadcast message sent to {sent_count} users.")

@app.on_message(~filters.command(["start", "ban", "unban", "cast"]))
def message_handler(client: Client, message: Message):
    """
    Handle incoming messages from users.
    
    - If the sender is banned the bot ignores their message.
    - For non-command messages:
      - If the message is from the owner and is a reply to a forwarded message, it sends that reply back to the original user.
      - Otherwise, the user’s message is forwarded to the owner.
    """
    user_id = message.from_user.id
    register_user(user_id)
    
    if is_banned(user_id):
        return

    # Owner replying to a forwarded message.
    if user_id == OWNER_ID and message.reply_to_message and message.reply_to_message.forward_from:
        target_id = message.reply_to_message.forward_from.id
        try:
            app.send_message(chat_id=target_id, text=message.text)
            message.reply("Reply sent.")
        except Exception as e:
            logger.error(f"Failed to send reply to {target_id}: {e}")
        return

    # Forward a user's message to the owner.
    try:
        app.forward_messages(chat_id=OWNER_ID, from_chat_id=message.chat.id, message_ids=message_id)
        message.reply("Your message has been sent to support.")
    except Exception as e:
        logger.error(f"Failed to forward message from {user_id}: {e}")
        message.reply("There was an error sending your message.")

if __name__ == "__main__":
    logger.info("Bot is starting...")
    app.run()
