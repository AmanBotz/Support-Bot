import asyncio
import logging
from sys import version as pyver

from pyrogram import Client, filters, idle
from pyrogram.errors import FloodWait
from pyrogram.types import Message

import config
import mongo

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Create the bot client using Pyrogram 2.x
app = Client(
    "YukkiBot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
)

# Global dict to map forwarded message IDs to original user IDs
save = {}

# ----- Command Handlers ----- #

@app.on_message(filters.command(["start", "help"]) & filters.private)
async def start_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if await mongo.is_banned_user(user_id):
        return
    await mongo.add_served_user(user_id)
    await message.reply_text(config.PRIVATE_START_MESSAGE)


@app.on_message(filters.command("mode") & filters.user(config.SUDO_USER))
async def mode_handler(client: Client, message: Message):
    if mongo.db is None:
        await message.reply_text("MONGO_DB_URI not defined. Please define it first.")
        return

    if len(message.command) != 2:
        usage = (
            "**Usage:**\n"
            "/mode [group | private]\n\n"
            "**Group**: Forward all incoming messages to the Log Group.\n"
            "**Private**: Forward messages to SUDO users privately."
        )
        await message.reply_text(usage)
        return

    mode = message.command[1].strip().lower()
    if mode == "group":
        await mongo.group_on()
        await message.reply_text("Group Mode Enabled. Messages will be forwarded to the Log Group.")
    elif mode == "private":
        await mongo.group_off()
        await message.reply_text("Private Mode Enabled. Messages will be forwarded to SUDO users.")
    else:
        await message.reply_text("Invalid mode. Please choose 'group' or 'private'.")


@app.on_message(filters.command("block") & filters.user(config.SUDO_USER))
async def block_handler(client: Client, message: Message):
    if mongo.db is None:
        await message.reply_text("MONGO_DB_URI not defined. Please define it first.")
        return

    if not message.reply_to_message or not message.reply_to_message.forward_sender_name:
        await message.reply_text("Reply to a forwarded message to block the user.")
        return

    replied_message_id = message.reply_to_message_id
    try:
        user_id = save[replied_message_id]
    except KeyError:
        await message.reply_text("Failed to retrieve user. Please check logs.")
        return

    if await mongo.is_banned_user(user_id):
        await message.reply_text("User is already blocked.")
    else:
        await mongo.add_banned_user(user_id)
        await message.reply_text("User has been blocked.")
        try:
            await client.send_message(user_id, "You have been blocked from using this bot.")
        except Exception:
            pass


@app.on_message(filters.command("unblock") & filters.user(config.SUDO_USER))
async def unblock_handler(client: Client, message: Message):
    if mongo.db is None:
        await message.reply_text("MONGO_DB_URI not defined. Please define it first.")
        return

    if not message.reply_to_message or not message.reply_to_message.forward_sender_name:
        await message.reply_text("Reply to a forwarded message to unblock the user.")
        return

    replied_message_id = message.reply_to_message_id
    try:
        user_id = save[replied_message_id]
    except KeyError:
        await message.reply_text("Failed to retrieve user. Please check logs.")
        return

    if not await mongo.is_banned_user(user_id):
        await message.reply_text("User is already unblocked.")
    else:
        await mongo.remove_banned_user(user_id)
        await message.reply_text("User has been unblocked.")
        try:
            await client.send_message(user_id, "You have been unblocked from using this bot.")
        except Exception:
            pass


@app.on_message(filters.command("stats") & filters.user(config.SUDO_USER))
async def stats_handler(client: Client, message: Message):
    if mongo.db is None:
        await message.reply_text("MONGO_DB_URI not defined. Please define it first.")
        return

    served_users = len(await mongo.get_served_users())
    banned_count = await mongo.get_banned_count()
    stats_text = (
        f"**Bot Stats:**\n"
        f"Python: {pyver.split()[0]}\n"
        f"Pyrogram: {Client.__version__}\n"
        f"Served Users: {served_users}\n"
        f"Banned Users: {banned_count}"
    )
    await message.reply_text(stats_text)


@app.on_message(filters.command("broadcast") & filters.user(config.SUDO_USER))
async def broadcast_handler(client: Client, message: Message):
    if mongo.db is None:
        await message.reply_text("MONGO_DB_URI not defined. Please define it first.")
        return

    # Determine if message is a reply or a text command
    if message.reply_to_message:
        try:
            msg_id = message.reply_to_message.message_id
            from_chat = message.chat.id
        except Exception:
            await message.reply_text("Failed to retrieve message.")
            return
    else:
        if len(message.command) < 2:
            await message.reply_text("Usage: /broadcast [MESSAGE] or reply to a message")
            return
        msg_text = message.text.split(maxsplit=1)[1]

    served_users = [int(user["user_id"]) for user in await mongo.get_served_users()]
    broadcast_count = 0
    for user_id in served_users:
        try:
            if message.reply_to_message:
                await client.forward_messages(user_id, from_chat, msg_id)
            else:
                await client.send_message(user_id, msg_text)
            broadcast_count += 1
        except FloodWait as e:
            await asyncio.sleep(e.x)
        except Exception as e:
            logger.error(f"Failed to send message to {user_id}: {e}")
    await message.reply_text(f"Broadcast sent to {broadcast_count} users.")


@app.on_message(filters.private & ~filters.edited)
async def private_message_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if await mongo.is_banned_user(user_id):
        return

    # If from a SUDO user replying to a forwarded message
    if user_id in config.SUDO_USER and message.reply_to_message:
        try:
            target_user_id = save[message.reply_to_message_id]
        except KeyError:
            await message.reply_text("Failed to retrieve user info.")
            return
        try:
            await client.copy_message(target_user_id, message.chat.id, message.message_id)
        except Exception:
            await message.reply_text("Failed to deliver the message. Check logs.")
        return

    # Forward messages from normal users based on mode
    try:
        if await mongo.is_group():
            forwarded = await client.forward_messages(config.LOG_GROUP_ID, message.chat.id, message.message_id)
            save[forwarded.message_id] = user_id
        else:
            for admin in config.SUDO_USER:
                forwarded = await client.forward_messages(admin, message.chat.id, message.message_id)
                save[forwarded.message_id] = user_id
    except Exception as e:
        logger.error(f"Error forwarding message from user {user_id}: {e}")


@app.on_message(filters.group & ~filters.edited & filters.user(config.SUDO_USER))
async def group_message_handler(client: Client, message: Message):
    if message.reply_to_message and message.text not in ["/unblock", "/block", "/broadcast"]:
        if not message.reply_to_message.forward_sender_name:
            await message.reply_text("Reply to a forwarded message to process the command.")
            return
        try:
            target_user_id = save[message.reply_to_message_id]
        except KeyError:
            await message.reply_text("Failed to retrieve user info.")
            return
        try:
            await client.copy_message(target_user_id, message.chat.id, message.message_id)
        except Exception:
            await message.reply_text("Failed to deliver the message. Check logs.")


# ----- Main Entrypoint ----- #

async def main():
    await app.start()
    logger.info("Bot started successfully!")
    await idle()
    await app.stop()

if __name__ == "__main__":
    asyncio.run(main())