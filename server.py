from flask import Flask, request, jsonify

app = Flask(__name__)

# Mémoire des utilisateurs actifs
active_users = {}

@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        # Lecture sécurisée du JSON
        data = request.get_json(force=True, silent=True)

        if not data:
            return jsonify("Erreur: JSON vide")

        user_id = data.get("user_id", "unknown")
        user_name = data.get("user_name", "inconnu")
        message = data.get("message", "")
        bot_name = data.get("bot_name", "robot")

        msg_lower = (message or "").lower()

        # Activation
        if bot_name in msg_lower:
            active_users[user_id] = True
            return jsonify(f"{user_name}, je t'écoute.")

        # Désactivation
        if "tais-toi" in msg_lower:
            active_users.pop(user_id, None)
            return jsonify("...")

        # Si pas actif → ignore
        if user_id not in active_users:
            return jsonify("")

        # Réponse test (sans IA)
        return jsonify("Je fonctionne sans IA pour test.")

    except Exception as e:
        return jsonify("Erreur serveur interne: " + str(e))


@app.route("/")
def home():
    return "SL AI BOT RUNNING"
    # merde a celui qui lira...
