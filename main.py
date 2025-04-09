import os
from pyrogram import Client, filters, types
from pyrogram.types import Message
from mongo import Database

app = Client(
    "support_bot",
    api_id=int(os.getenv("API_ID")),
    api_hash=os.getenv("API_HASH"),
    bot_token=os.getenv("BOT_TOKEN")
)

db = Database()
try:
    OWNER_ID = int(os.getenv("OWNER_ID"))
except (ValueError, TypeError):
    raise ValueError("OWNER_ID environment variable must be set to a valid integer")

# Store temporary replies {owner_msg_id: user_id}
reply_cache = {}

@app.on_message(filters.command("start"))
async def start(client: Client, message: Message):
    user = message.from_user
    user_data = db.get_user(user.id)
    if not user_data:
        db.add_user(user.id, user.first_name)
    
    await message.reply("Welcome! Send us your message directly and we'll respond ASAP.")

@app.on_message(filters.command("ban") & filters.user(OWNER_ID))
async def ban(client: Client, message: Message):
    try:
        user_id = int(message.command[1])
        if not db.get_user(user_id):
            await message.reply(f"User {user_id} not found.")
            return
        db.update_banned(user_id, True)
        await message.reply(f"User {user_id} banned")
    except (IndexError, ValueError):
        await message.reply("Usage: /ban <user_id>")

@app.on_message(filters.command("unban") & filters.user(OWNER_ID))
async def unban(client: Client, message: Message):
    try:
        user_id = int(message.command[1])
        if not db.get_user(user_id):
            await message.reply(f"User {user_id} not found.")
            return
        db.update_banned(user_id, False)
        await message.reply(f"User {user_id} unbanned")
    except (IndexError, ValueError):
        await message.reply("Usage: /unban <user_id>")

@app.on_message(filters.command("cast") & filters.user(OWNER_ID))
async def cast(client: Client, message: Message):
    text = " ".join(message.command[1:])
    users = db.get_all_users()
    
    success_count = 0
    for user in users:
        try:
            await client.send_message(user["_id"], text)
            success_count += 1
        except Exception:
            continue
    
    await message.reply(f"Broadcast sent to {success_count} out of {len(users)} users")

@app.on_message(filters.private & ~filters.command() & ~filters.user(OWNER_ID))
async def user_message(client: Client, message: Message):
    user = message.from_user
    user_data = db.get_user(user.id)
    if not user_data:
        # Optionally add the user if not present
        db.add_user(user.id, user.first_name)
        user_data = db.get_user(user.id)
    if user_data.get("banned"):
        return
    
    forwarded = await message.forward(OWNER_ID)
    reply_cache[forwarded.id] = user.id
    db.add_chat(user.id, message.id, is_user=True)

@app.on_message(filters.private & filters.user(OWNER_ID) & filters.reply)
async def owner_reply(client: Client, message: Message):
    replied = message.reply_to_message
    if not replied or replied.id not in reply_cache:
        return
    
    # Remove the entry from the cache once processed
    user_id = reply_cache.pop(replied.id, None)
    if not user_id:
        return
    
    user_data = db.get_user(user_id)
    if not user_data or user_data.get("banned"):
        return
    
    # Send the owner’s reply to the user
    await client.send_message(user_id, message.text if message.text else "")
    db.add_chat(user_id, message.id, is_user=False)

if __name__ == "__main__":
    print("Bot started...")
    app.run()
