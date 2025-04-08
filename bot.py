import os
import logging
from flask import Flask, request
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler
)
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# MongoDB Connection
try:
    client = MongoClient(os.getenv("MONGO_URI"))
    db = client.feedback_bot
    users_collection = db.users
    banned_collection = db.banned
    messages_collection = db.messages
    logger.info("✅ MongoDB connection established")
except ConnectionFailure as e:
    logger.error("❌ MongoDB connection failed: %s", e)
    raise

TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")
PORT = int(os.getenv("PORT", 8000))

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        if banned_collection.find_one({"user_id": user.id}):
            await update.message.reply_text("🚫 You are banned from using this bot.")
            return

        users_collection.update_one(
            {"user_id": user.id},
            {"$set": {
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name
            }},
            upsert=True
        )

        await update.message.reply_text(
            f"👋 Hello {user.first_name}!\n\n"
            "Welcome to Feedback Bot!\n\n"
            "Simply type your message to send feedback.\n"
            "Use /help for commands list"
        )
    except Exception as e:
        logger.error(f"Start error: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "❓ **Help Menu** ❓\n\n"
        "/start - Initialize bot\n"
        "/help - Show this menu\n"
        "Just type to send feedback!"
    )
    if is_admin(update.effective_user.id):
        help_text += (
            "\n\n**Admin Commands:**\n"
            "/ban <user_id> - Ban user\n"
            "/unban <user_id> - Unban user\n"
            "/broadcast <message> - Send to all users"
        )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        message = update.effective_message

        if banned_collection.find_one({"user_id": user.id}):
            await message.reply_text("🚫 You are banned.")
            return

        if message.text.startswith('/'):
            return

        msg_data = {
            "user_id": user.id,
            "message": message.text,
            "timestamp": message.date,
            "status": "received"
        }
        messages_collection.insert_one(msg_data)

        forward_text = (
            f"📨 New feedback from {user.mention_html()}\n"
            f"User ID: `{user.id}`\n\n"
            f"{message.text}"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚫 Ban User", callback_data=f"ban_{user.id}")]
        ]) if GROUP_CHAT_ID else None

        sent_msg = await context.bot.send_message(
            chat_id=GROUP_CHAT_ID or ADMIN_ID,
            text=forward_text,
            parse_mode="HTML",
            reply_markup=markup
        )

        messages_collection.update_one(
            {"_id": msg_data["_id"]},
            {"$set": {
                "forwarded_message_id": sent_msg.message_id,
                "status": "forwarded"
            }}
        )

        await message.reply_text("✅ Message forwarded to admin!")

    except Exception as e:
        logger.error(f"Message error: {e}")
        await message.reply_text("⚠️ Error processing message")

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not is_admin(update.effective_user.id):
            return

        reply_to = update.message.reply_to_message
        if not reply_to:
            return

        original = messages_collection.find_one({
            "forwarded_message_id": reply_to.message_id
        })
        if not original:
            return

        await context.bot.send_message(
            chat_id=original["user_id"],
            text=f"📩 Admin Response:\n\n{update.message.text}"
        )
        await update.message.reply_text("✅ Reply sent!")
        
        messages_collection.update_one(
            {"_id": original["_id"]},
            {"$set": {"status": "replied"}}
        )

    except Exception as e:
        logger.error(f"Reply error: {e}")
        await update.message.reply_text("❌ Failed to send reply")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized!")
        return

    try:
        user_id = int(context.args[0])
        if banned_collection.find_one({"user_id": user_id}):
            await update.message.reply_text("ℹ️ Already banned")
            return

        banned_collection.insert_one({"user_id": user_id})
        await update.message.reply_text(f"✅ Banned {user_id}")
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ Usage: /ban <user_id>")

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized!")
        return

    try:
        user_id = int(context.args[0])
        if not banned_collection.find_one({"user_id": user_id}):
            await update.message.reply_text("ℹ️ Not banned")
            return

        banned_collection.delete_one({"user_id": user_id})
        await update.message.reply_text(f"✅ Unbanned {user_id}")
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ Usage: /unban <user_id>")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized!")
        return

    if not context.args:
        await update.message.reply_text("⚠️ Usage: /broadcast <message>")
        return

    message = " ".join(context.args)
    users = users_collection.find()
    success = 0
    failed = 0

    await update.message.reply_text("⏳ Broadcasting...")

    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user["user_id"],
                text=f"📢 Admin Broadcast:\n\n{message}"
            )
            success += 1
        except Exception as e:
            logger.error(f"Broadcast fail {user['user_id']}: {e}")
            failed += 1

    await update.message.reply_text(
        f"📊 Broadcast Results:\n✅ {success} | ❌ {failed}"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("ban_"):
        user_id = int(query.data.split("_")[1])
        if not is_admin(query.from_user.id):
            await query.message.reply_text("❌ Unauthorized!")
            return

        if banned_collection.find_one({"user_id": user_id}):
            await query.message.reply_text("ℹ️ Already banned")
            return

        banned_collection.insert_one({"user_id": user_id})
        await query.message.reply_text(f"✅ Banned {user_id}")

def setup_handlers(application):
    handlers = [
        CommandHandler("start", start),
        CommandHandler("help", help_command),
        CommandHandler("ban", ban_user),
        CommandHandler("unban", unban_user),
        CommandHandler("broadcast", broadcast),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
        CallbackQueryHandler(button_handler)
    ]
    
    if GROUP_CHAT_ID:
        handlers.append(
            MessageHandler(
                filters.Chat(GROUP_CHAT_ID) & filters.REPLY & filters.TEXT,
                handle_admin_reply
            )
        )
    
    for handler in handlers:
        application.add_handler(handler)

if __name__ == "__main__":
    application = ApplicationBuilder().token(TOKEN).build()
    setup_handlers(application)

    @app.route('/')
    def home():
        return "Bot Running", 200

    @app.route('/webhook', methods=['POST'])
    def webhook():
        update = Update.de_json(request.get_json(), application.bot)
        application.update_queue.put(update)
        return 'ok', 200

    if os.getenv("KOYEB"):
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=f"https://{os.getenv('KOYEB_APP_NAME')}.koyeb.app/{TOKEN}"
        )
    else:
        application.run_polling()
