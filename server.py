from flask import Flask, request, jsonify
import os
from groq import Groq

app = Flask(__name__)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

memory = {}
MAX_HISTORY = 6

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

        # Activation
        if bot_name in msg_lower:
            memory[user_id] = []
            return jsonify(f"{user_name}, je t'écoute.")

        # Désactivation
        if "tais-toi" in msg_lower:
            memory.pop(user_id, None)
            return jsonify("...")

        # Ignore si pas actif
        if user_id not in memory:
            return jsonify("")

        # Mémoire utilisateur
        memory[user_id].append({"role": "user", "content": message})
        memory[user_id] = memory[user_id][-MAX_HISTORY:]

        messages = [
            {
                "role": "system",
                "content": "Tu es Marcel, un personnage sympa dans Second Life. Tu réponds en français, de manière naturelle, courte et vivante."
            }
        ] + memory[user_id]

        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=messages,
            temperature=0.7
        )

        answer = response.choices[0].message.content.strip()

        memory[user_id].append({"role": "assistant", "content": answer})

        return jsonify(answer[:800])

    except Exception as e:
        return jsonify("Erreur IA")

@app.route("/")
def home():
    return "SL AI BOT RUNNING"
