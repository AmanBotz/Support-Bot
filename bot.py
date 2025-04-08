import os
import logging
from typing import Dict, Optional
from flask import Flask, request
from telegram import Update, Message, Bot, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    CallbackContext
)
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# MongoDB configuration
client = MongoClient(os.getenv("MONGO_URI"))
db = client.feedback_bot
users_collection = db.users
banned_collection = db.banned
messages_collection = db.messages

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID")) if os.getenv("GROUP_CHAT_ID") else None
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
            "You can simply type your message here and it will be forwarded to our team.\n\n"
            "Use /help to see available commands"
        )
    except Exception as e:
        logger.error(f"Start command error: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "❓ **Help Menu** ❓\n\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n\n"
        "Just type your message to send feedback!"
    )
    if is_admin(update.effective_user.id):
        help_text += "\n\n**Admin Commands:**\n/ban <user_id> - Ban user\n/unban <user_id> - Unban user\n/broadcast <message> - Send message to all users"
    
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        message = update.effective_message

        if banned_collection.find_one({"user_id": user.id}):
            await message.reply_text("🚫 You are banned from using this bot.")
            return

        if message.text.startswith('/'):
            return

        # Store message in database
        msg_data = {
            "user_id": user.id,
            "message": message.text,
            "timestamp": message.date,
            "status": "received"
        }
        messages_collection.insert_one(msg_data)

        # Forward to admin channel
        forward_text = (
            f"📨 New feedback from {user.mention_html()}\n"
            f"User ID: {user.id}\n\n"
            f"{message.text}"
        )
        if GROUP_CHAT_ID:
            sent_msg = await context.bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=forward_text,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🚫 Ban User", callback_data=f"ban_{user.id}")]
                ])
            )
        else:
            sent_msg = await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=forward_text,
                parse_mode="HTML"
            )

        # Update message record with forwarded ID
        messages_collection.update_one(
            {"_id": msg_data["_id"]},
            {"$set": {
                "forwarded_message_id": sent_msg.message_id,
                "status": "forwarded"
            }}
        )

        await message.reply_text("✅ Your message has been forwarded to our team!")

    except PyMongoError as e:
        logger.error(f"MongoDB error: {e}")
        await message.reply_text("⚠️ Error processing your message. Please try again later.")
    except Exception as e:
        logger.error(f"Message handling error: {e}")
        await message.reply_text("⚠️ An error occurred. Please try again later.")

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not is_admin(update.effective_user.id):
            return

        reply_to = update.message.reply_to_message
        if not reply_to:
            return

        # Find original message
        original_message = messages_collection.find_one({
            "forwarded_message_id": reply_to.message_id
        })

        if not original_message:
            return

        # Send reply to user
        await context.bot.send_message(
            chat_id=original_message["user_id"],
            text=f"📩 Admin Response:\n\n{update.message.text}"
        )
        await update.message.reply_text("✅ Reply sent to user!")

        # Update message status
        messages_collection.update_one(
            {"_id": original_message["_id"]},
            {"$set": {"status": "replied"}}
        )

    except Exception as e:
        logger.error(f"Admin reply error: {e}")
        await update.message.reply_text("❌ Failed to send reply. User might have blocked the bot.")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized access!")
        return

    try:
        user_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ Usage: /ban <user_id>")
        return

    if banned_collection.find_one({"user_id": user_id}):
        await update.message.reply_text("ℹ️ User is already banned!")
        return

    banned_collection.insert_one({"user_id": user_id})
    await update.message.reply_text(f"✅ User {user_id} has been banned!")

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized access!")
        return

    try:
        user_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ Usage: /unban <user_id>")
        return

    if not banned_collection.find_one({"user_id": user_id}):
        await update.message.reply_text("ℹ️ User is not banned!")
        return

    banned_collection.delete_one({"user_id": user_id})
    await update.message.reply_text(f"✅ User {user_id} has been unbanned!")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized access!")
        return

    if not context.args:
        await update.message.reply_text("⚠️ Usage: /broadcast <message>")
        return

    message_text = " ".join(context.args)
    users = users_collection.find()
    success = 0
    failed = 0

    await update.message.reply_text("⏳ Starting broadcast...")

    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user["user_id"],
                text=f"📢 Admin Broadcast:\n\n{message_text}"
            )
            success += 1
        except Exception as e:
            logger.error(f"Broadcast failed to {user['user_id']}: {e}")
            failed += 1

    await update.message.reply_text(
        f"📊 Broadcast completed!\n"
        f"✅ Success: {success}\n"
        f"❌ Failed: {failed}"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("ban_"):
        user_id = int(query.data.split("_")[1])
        if not is_admin(query.from_user.id):
            await query.message.reply_text("❌ Unauthorized action!")
            return

        if banned_collection.find_one({"user_id": user_id}):
            await query.message.reply_text("ℹ️ User is already banned!")
            return

        banned_collection.insert_one({"user_id": user_id})
        await query.message.reply_text(f"✅ User {user_id} has been banned!")

if __name__ == "__main__":
    # Create bot application
    application = ApplicationBuilder().token(TOKEN).build()

    # Add handlers
    handlers = [
        CommandHandler("start", start),
        CommandHandler("help", help_command),
        CommandHandler("ban", ban_user),
        CommandHandler("unban", unban_user),
        CommandHandler("broadcast", broadcast),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
        MessageHandler(filters.REPLY & filters.Chat(GROUP_CHAT_ID), handle_admin_reply),
        CallbackQueryHandler(button_handler)
    ]

    for handler in handlers:
        application.add_handler(handler)

    # Flask routes
    @app.route('/')
    def home():
        return "Feedback Bot is running!", 200

    @app.route('/webhook', methods=['POST'])
    def webhook():
        update = Update.de_json(request.get_json(), application.bot)
        application.update_queue.put(update)
        return 'ok', 200

    # Start the bot
    if os.environ.get('KOYEB'):
        app.run(host='0.0.0.0', port=PORT)
    else:
        application.run_polling()
