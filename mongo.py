import os
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, ConnectionFailure

# Read MongoDB URI with fallback
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")

def get_database():
    """Return MongoDB database connection with error handling"""
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.server_info()  Test connection
        return client["telegram_support_bot"]
    except ConnectionFailure as e:
        raise RuntimeError(f"Failed to connect to MongoDB: {e}") from e

def add_user(user_id: int):
    """Upsert user with atomic operation"""
    db = get_database()
    db.users.update_one(
        {"_id": user_id},
        {"$setOnInsert": {"banned": False}},
        upsert=True
    )

def get_user(user_id: int):
    db = get_database()
    return db.users.find_one({"_id": user_id})

def update_user_ban_status(user_id: int, banned: bool):
    db = get_database()
    db.users.update_one(
        {"_id": user_id},
        {"$set": {"banned": banned}},
        upsert=True
    )

def get_all_users():
    db = get_database()
    return db.users.find()
