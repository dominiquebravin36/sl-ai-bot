from flask import Flask, request, jsonify

app = Flask(__name__)

active_users = {}

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)

    user_id = data.get("user_id")
    user_name = data.get("user_name")
    message = data.get("message")
    bot_name = data.get("bot_name", "robot")

    msg_lower = message.lower()

    if bot_name in msg_lower:
        active_users[user_id] = True
        return jsonify(f"{user_name}, je t'écoute.")

    if "tais-toi" in msg_lower:
        active_users.pop(user_id, None)
        return jsonify("...")

    if user_id not in active_users:
        return jsonify("")

    return jsonify("Je fonctionne sans IA pour test.")

@app.route("/")
def home():
    return "SL AI BOT RUNNING"
