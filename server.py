from flask import Flask

app = Flask(__name__)

@app.route("/")
def index():
    return "Telegram Support Bot is running."

if __name__ == "__main__":
    # Runs a basic Flask server on port 8000.
    app.run(host="0.0.0.0", port=8000)
