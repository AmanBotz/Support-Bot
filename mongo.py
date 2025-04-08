from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_DB_URI

db = None
if MONGO_DB_URI:
    client = AsyncIOMotorClient(MONGO_DB_URI)
    db = client.ChatBot
    usersdb = db.users
    blockeddb = db.block
    modedb = db.mode

    # In-memory cache for mode settings
    modelist = {}

    # ----- Served Users ----- #
    async def is_served_user(user_id: int) -> bool:
        return bool(await usersdb.find_one({"user_id": user_id}))

    async def get_served_users() -> list:
        users_list = []
        async for user in usersdb.find({"user_id": {"$gt": 0}}):
            users_list.append(user)
        return users_list

    async def add_served_user(user_id: int):
        if await is_served_user(user_id):
            return
        await usersdb.insert_one({"user_id": user_id})

    # ----- Banned Users ----- #
    async def get_banned_users() -> list:
        results = []
        async for user in blockeddb.find({"user_id": {"$gt": 0}}):
            results.append(user["user_id"])
        return results

    async def get_banned_count() -> int:
        users = blockeddb.find({"user_id": {"$gt": 0}})
        users = await users.to_list(length=100000)
        return len(users)

    async def is_banned_user(user_id: int) -> bool:
        return bool(await blockeddb.find_one({"user_id": user_id}))

    async def add_banned_user(user_id: int):
        if await is_banned_user(user_id):
            return
        await blockeddb.insert_one({"user_id": user_id})

    async def remove_banned_user(user_id: int):
        if not await is_banned_user(user_id):
            return
        await blockeddb.delete_one({"user_id": user_id})

    # ----- Forward Mode ----- #
    async def is_group() -> bool:
        chat_id = 123  # default key for storing mode
        mode = modelist.get(chat_id)
        if mode is None:
            record = await modedb.find_one({"chat_id": chat_id})
            if record is None:
                modelist[chat_id] = False
                return False
            modelist[chat_id] = True
            return True
        return mode

    async def group_on():
        chat_id = 123
        modelist[chat_id] = True
        record = await modedb.find_one({"chat_id": chat_id})
        if record is None:
            await modedb.insert_one({"chat_id": chat_id})

    async def group_off():
        chat_id = 123
        modelist[chat_id] = False
        record = await modedb.find_one({"chat_id": chat_id})
        if record is not None:
            await modedb.delete_one({"chat_id": chat_id})

else:
    async def is_group() -> bool:
        return False

    async def is_banned_user(user_id: int) -> bool:
        return False

    async def add_served_user(user_id: int):
        return