from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

HF_TOKEN = os.environ.get("HF_TOKEN")

MODEL_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct"

headers = {
    "Authorization": f"Bearer {HF_TOKEN}"
}

# Mémoire des utilisateurs actifs
active_users = {}

def query_hf(prompt):
    try:
        response = requests.post(
            MODEL_URL,
            headers=headers,
            json={"inputs": prompt},
            timeout=20
        )

        result = response.json()

        if isinstance(result, list):
            return result[0].get("generated_text", "Réponse vide")

        return "Je réfléchis..."

    except Exception as e:
        return "Erreur IA"

@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(force=True, silent=True)

        if not data:
            return jsonify("")

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

        # Si pas actif
        if user_id not in active_users:
            return jsonify("")

        prompt = f"""
Tu es Marcel, un personnage dans Second Life.
Tu parles en français, naturellement, de manière courte et sympa.

Utilisateur: {message}
Marcel:
"""

        answer = query_hf(prompt)

        # Nettoyage
        answer = answer.replace(prompt, "").strip()

        return jsonify(answer[:1000])

    except:
        return jsonify("")

@app.route("/")
def home():
    return "SL AI BOT RUNNING"
