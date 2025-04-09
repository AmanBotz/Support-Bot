from flask import Flask
from main import app as bot_client
import threading
import asyncio
import os

web = Flask(__name__)

@web.route("/")
def home():
    return "Bot Running"

async def run_bot():
    await bot_client.start()
    print("Bot client started")
    await bot_client.run()

def start_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_bot())

if __name__ == "__main__":
    # Start bot in separate thread
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    
    # Start Flask web server
    web.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)), use_reloader=False)
