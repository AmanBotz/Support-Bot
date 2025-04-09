from flask import Flask
from main import app as bot_client
import threading

app = Flask(__name__)

@app.route("/")
def home():
    return "Support Bot Running"

def run_bot():
    bot_client.run()

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=8000)
