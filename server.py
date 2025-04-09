from flask import Flask
from main import app as bot_client
import threading
import os

web = Flask(__name__)

@web.route("/")
def home():
    return "Support Bot Running"

def run_bot():
    bot_client.start()
    print("Bot client started")
    bot_client.run()

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    web.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
