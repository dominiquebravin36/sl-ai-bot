from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

HF_TOKEN = os.environ.get("HF_TOKEN")
MODEL_URL = "https://api-inference.huggingface.co/models/google/flan-t5-base"

headers = {
    "Authorization": f"Bearer {HF_TOKEN}"
}

# mémoire des utilisateurs (conversation courte)
memory = {}

MAX_HISTORY = 5  # nombre de messages gardés

def query_hf(prompt):
    try:
        response = requests.post(
            MODEL_URL,
            headers=headers,
            json={"inputs": prompt},
            timeout=25
        )

        result = response.json()

        # debug silencieux
        if isinstance(result, dict) and "error" in result:
            return "Hmm… attends une seconde."

        if isinstance(result, list):
            return result[0].get("generated_text", "").strip()

        return "Je n'ai pas compris."

    except:
        return "Petit bug, réessaie."

@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(force=True, silent=True)

        if not data:
            return jsonify("")

        user_id = data.get("user_id", "unknown")
        user_name = data.get("user_name", "ami")
        message = data.get("message", "")
        bot_name = data.get("bot_name", "marcel")

        msg_lower = (message or "").lower()

        # activation
        if bot_name in msg_lower:
            memory[user_id] = []
            return jsonify(f"{user_name}, je t'écoute.")

        # désactivation
        if "tais-toi" in msg_lower:
            memory.pop(user_id, None)
            return jsonify("...")

        # pas actif
        if user_id not in memory:
            return jsonify("")

        # ajout à la mémoire
        memory[user_id].append(f"Utilisateur: {message}")

        # limite mémoire
        memory[user_id] = memory[user_id][-MAX_HISTORY:]

        # construction du contexte
        history = "\n".join(memory[user_id])

        prompt = f"""
Tu es Marcel, un personnage dans Second Life.
Tu es sympa, naturel, et tu réponds en français de manière courte.

Conversation :
{history}

Marcel:
"""

        answer = query_hf(prompt)

        # nettoyage
        answer = answer.replace(prompt, "").strip()

        # ajoute réponse à mémoire
        memory[user_id].append(f"Marcel: {answer}")

        return jsonify(answer[:800])

    except Exception as e:
        return jsonify("")

@app.route("/")
def home():
    return "SL AI BOT RUNNING"
