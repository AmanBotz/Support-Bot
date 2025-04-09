from flask import Flask
from main import app as bot_client
import threading
import asyncio
import os

web = Flask(__name__)

@web.route("/")
def home():
    return "Bot Running"

async def bot_main():
    await bot_client.start()
    print("🤖 Bot successfully started")
    await asyncio.Event().wait()  # Run forever

def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(bot_main())

if __name__ == "__main__":
    # Start bot in separate thread
    threading.Thread(target=run_bot, daemon=True).start()
    
    # Start Flask web server
    web.run(host="0.0.0.0", port=os.getenv("PORT", 8000), use_reloader=False)
