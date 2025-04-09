import os
from pymongo import MongoClient

# Read the MongoDB URI from environment variables or use the local default.
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client["telegram_support_bot"]

def get_database():
    """Return the MongoDB database object."""
    return db

def add_user(user_id: int):
    """Insert a new user into the users collection if they do not already exist."""
    if db.users.find_one({"_id": user_id}) is None:
        db.users.insert_one({"_id": user_id, "banned": False})

def get_user(user_id: int):
    """Retrieve a user's record from the users collection."""
    return db.users.find_one({"_id": user_id})

def update_user_ban_status(user_id: int, ban: bool):
    """Update the ban status of a user."""
    db.users.update_one({"_id": user_id}, {"$set": {"banned": ban}}, upsert=True)

def get_all_users():
    """Retrieve all user records."""
    return db.users.find()
