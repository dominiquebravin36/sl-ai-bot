from flask import Flask, request, Response
import requests
import os
import json

app = Flask(__name__)

HF_TOKEN = os.environ.get("HF_TOKEN")
MODEL_URL = "https://api-inference.huggingface.co/models/google/flan-t5-large"

headers = {
    "Authorization": f"Bearer {HF_TOKEN}"
}

active_users = {}

def query_hf(prompt):
    response = requests.post(
        MODEL_URL,
        headers=headers,
        json={"inputs": prompt}
    )
    result = response.json()

    if isinstance(result, list):
        return result[0]["generated_text"]
    return "Erreur IA"

def respond(text):
    return Response(
        json.dumps(text, ensure_ascii=False),
        content_type="application/json; charset=utf-8"
    )

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json

    user_id = data.get("user_id")
    user_name = data.get("user_name")
    message = data.get("message")
    bot_name = data.get("bot_name", "robot")

    msg_lower = message.lower()

    if bot_name in msg_lower:
        active_users[user_id] = True
        return respond(f"{user_name}, je t'écoute.")

    if "tais-toi" in msg_lower:
        active_users.pop(user_id, None)
        return respond("...")

    if user_id not in active_users:
        return respond("")

    prompt = f"""
Tu es un personnage dans Second Life.
Réponds en français, naturellement et brièvement.

Utilisateur: {message}
IA:
"""

    answer = query_hf(prompt)
    answer = answer.replace(prompt, "").strip()

    return respond(answer[:1000])

@app.route("/")
def home():
    return "SL AI BOT RUNNING"
# force rebuild
