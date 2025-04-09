from flask import Flask
from main import app as bot_client
import threading

web = Flask(__name__)

@web.route("/")
def home():
    return "Bot Running"

def run_bot():
    bot_client.run()

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    web.run(host="0.0.0.0", port=8000)
