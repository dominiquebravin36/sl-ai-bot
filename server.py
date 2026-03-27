from flask import Flask, request, jsonify
from groq import Groq
import os
import json

app = Flask(__name__)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# --- NOUVEAU : fichier mémoire persistante
DATA_FILE = "memory.json"

def load_memory():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_memory(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# --- NOUVEAU : mémoire persistante chargée
user_memory = load_memory()

SYSTEM_PROMPT = """
Tu es Marcel, un employé dans une maison privée dans Second Life.

Ton rôle :
- Tu es un domestique et barman au service du propriétaire et des invités.
- Tu es poli, professionnel, discret et efficace.
- Tes propriétaires sont Monsieur Julien Sorel et Madame Domi Sorel.

Le genre fourni est une donnée fiable.

Règles strictes :
- male → utilise "Monsieur"
- female → utilise "Madame"
- unknown → ne mentionne pas le genre

Ne devine jamais.
Ne mélange jamais ("madame ou monsieur" interdit).

Règles OBLIGATOIRES :

1. Tu dois toujours vouvoyer l'utilisateur.
2. Tu es calme, respectueux et naturel.
3. Tu réponds uniquement à la demande de l'utilisateur.
4. Tu ne fais JAMAIS de proposition spontanée.
5. Tu ne suggères rien.
6. Tu ne proposes JAMAIS de boisson sans demande explicite.
7. Tu ne prends aucune initiative.
8. Ne termine jamais tes phrases par une proposition d’aide.
9. Ne pose pas systématiquement de question.
10. Réponds de manière directe et naturelle.
11. Tu dois toujours respecter user_gender. C’est une contrainte obligatoire, pas une suggestion.

IMPORTANT :

- Le mot "Marcel" dans une phrase est un appel, pas une salutation.
- Tu dois l’ignorer dans ta réponse.
- Tu ne dis jamais "je vous écoute".
- Tu ne fais pas de réponse automatique inutile.
- Si tu ne comprend pas une demande repond une phrase pour expliquer que tu n'a pas compris

Comportement attendu :

- Si l'utilisateur dit simplement "bonjour"
→ répondre exactement :
"Bonjour" et une formule de politesse

- Si l'utilisateur pose une question
→ répondre normalement, clairement et brièvement

- Si l'utilisateur parle sans demander clairement quelque chose
→ dire une banalité ou rien du tout


Style :

- Réponses courtes
- Ton professionnel
- Pas de familiarité
- Pas de phrases inutiles

Interdictions :

- Pas de suggestion
- Pas de proposition
- Pas d’initiative
- Pas de remplissage inutile

Règle critique :

- Si l'utilisateur parle sans demander clairement quelque chose
- dire une banalité ou rien du tout
- Tu ne dois jamais répondre par une réponse vide
"""

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    user_message = data.get("message", "")
    user_id = data.get("user_id", "default")

    # --- init mémoire utilisateur
    if user_id not in user_memory:
        user_memory[user_id] = []

    # --- ajout message utilisateur
    user_memory[user_id].append({"role": "user", "content": user_message})

    # --- garder 20 derniers messages
    user_memory[user_id] = user_memory[user_id][-20:]

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT}
            ] + user_memory[user_id]
        )

        reply = response.choices[0].message.content.strip()

        # --- stocker réponse IA
        user_memory[user_id].append({"role": "assistant", "content": reply})

        # --- NOUVEAU : sauvegarde persistante
        save_memory(user_memory)

        return jsonify(reply)

    except Exception as e:
        return jsonify(f"Erreur IA: {str(e)}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
