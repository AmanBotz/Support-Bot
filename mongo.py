import os
from pymongo import MongoClient
from pymongo.collection import Collection
from typing import Dict, Any

class Database:
    def __init__(self):
        self.client = MongoClient(os.getenv("MONGO_URI"))
        self.db = self.client["support_bot"]
        self.users: Collection = self.db.users
        self.chats: Collection = self.db.chats
        
    def get_user(self, user_id: int) -> Dict[str, Any]:
        return self.users.find_one({"_id": user_id})
    
    def add_user(self, user_id: int, name: str):
        if not self.get_user(user_id):
            self.users.insert_one({
                "_id": user_id,
                "name": name,
                "banned": False
            })
    
    def update_banned(self, user_id: int, banned: bool):
        self.users.update_one(
            {"_id": user_id},
            {"$set": {"banned": banned}}
        )
    
    def get_all_users(self):
        return list(self.users.find({"banned": False}))
    
    def add_chat(self, user_id: int, message_id: int, is_user: bool):
        self.chats.insert_one({
            "user_id": user_id,
            "message_id": message_id,
            "is_user": is_user
        })
