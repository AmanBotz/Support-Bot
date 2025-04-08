from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler
)
from bot import (
    users_collection,
    banned_collection,
    messages_collection,
    is_admin,
    ADMIN_ID,
    GROUP_CHAT_ID
)
import logging

logger = logging.getLogger(__name__)

# Admin command verification
async def verify_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ This command is for admins only!")
        return False
    return True

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await verify_admin(update, context):
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
    if not await verify_admin(update, context):
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
    if not await verify_admin(update, context):
        return

    if not context.args:
        await update.message.reply_text("⚠️ Usage: /broadcast <message>")
        return

    message = " ".join(context.args)
    users = users_collection.find()
    success = 0
    failed = 0

    await update.message.reply_text("⏳ Starting broadcast...")

    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user["user_id"],
                text=f"📢 Admin Broadcast:\n\n{message}"
            )
            success += 1
        except Exception as e:
            logger.error(f"Failed to send to {user['user_id']}: {e}")
            failed += 1

    await update.message.reply_text(
        f"📊 Broadcast completed!\n"
        f"✅ Success: {success}\n"
        f"❌ Failed: {failed}"
    )

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    reply_to = update.message.reply_to_message
    if not reply_to:
        return

    # Find original message in database
    original_message = messages_collection.find_one({
        "forwarded_message_id": reply_to.message_id
    })

    if not original_message:
        return

    try:
        await context.bot.send_message(
            chat_id=original_message["user_id"],
            text=f"📩 Admin Response:\n\n{update.message.text}"
        )
        await update.message.reply_text("✅ Reply sent to user!")
    except Exception as e:
        logger.error(f"Failed to send reply: {e}")
        await update.message.reply_text("❌ Failed to send reply. User might have blocked the bot.")

def get_admin_handlers():
    return [
        CommandHandler("ban", ban_user),
        CommandHandler("unban", unban_user),
        CommandHandler("broadcast", broadcast),
        MessageHandler(
            filters.Chat(int(GROUP_CHAT_ID)) & filters.REPLY & filters.TEXT,
            handle_admin_reply
        )
    ]
