import os
from pyrogram import Client, filters, types
from pyrogram.types import Message
from mongo import Database

app = Client(
    "support_bot",
    api_id=os.getenv("API_ID"),
    api_hash=os.getenv("API_HASH"),
    bot_token=os.getenv("BOT_TOKEN")
)

db = Database()
OWNER_ID = int(os.getenv("OWNER_ID"))

# Store temporary replies {owner_msg_id: user_id}
reply_cache = {}

@app.on_message(filters.command("start"))
async def start(client: Client, message: Message):
    user = message.from_user
    if not db.get_user(user.id):
        db.add_user(user.id, user.first_name)
    
    await message.reply("Welcome! Send us your message directly and we'll respond ASAP.")

@app.on_message(filters.command("ban") & filters.user(OWNER_ID))
async def ban(client: Client, message: Message):
    try:
        user_id = int(message.command[1])
        db.update_banned(user_id, True)
        await message.reply(f"User {user_id} banned")
    except (IndexError, ValueError):
        await message.reply("Usage: /ban <user_id>")

@app.on_message(filters.command("unban") & filters.user(OWNER_ID))
async def unban(client: Client, message: Message):
    try:
        user_id = int(message.command[1])
        db.update_banned(user_id, False)
        await message.reply(f"User {user_id} unbanned")
    except (IndexError, ValueError):
        await message.reply("Usage: /unban <user_id>")

@app.on_message(filters.command("cast") & filters.user(OWNER_ID))
async def cast(client: Client, message: Message):
    text = " ".join(message.command[1:])
    users = db.get_all_users()
    
    for user in users:
        try:
            await client.send_message(user["_id"], text)
        except:
            continue
    
    await message.reply(f"Broadcast sent to {len(users)} users")

@app.on_message(filters.private & ~filters.command & ~filters.user(OWNER_ID))
async def user_message(client: Client, message: Message):
    user = message.from_user
    if db.get_user(user.id).get("banned"):
        return
    
    forwarded = await message.forward(OWNER_ID)
    reply_cache[forwarded.id] = user.id
    db.add_chat(user.id, message.id, is_user=True)

@app.on_message(filters.private & filters.user(OWNER_ID) & filters.reply)
async def owner_reply(client: Client, message: Message):
    replied = message.reply_to_message
    if replied.id not in reply_cache:
        return
    
    user_id = reply_cache[replied.id]
    if db.get_user(user_id).get("banned"):
        return
    
    await client.send_message(user_id, message.text)
    db.add_chat(user_id, message.id, is_user=False)

if __name__ == "__main__":
    print("Bot started...")
    app.run()
