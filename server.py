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

# --- NOUVEAU : structure mémoire
memory = load_memory()

if "conversations" not in memory:
    memory["conversations"] = {}

if "users" not in memory:
    memory["users"] = {}

# --- AJOUT : fonction ajout facts
def add_fact(name, fact):
    name = name.lower()

    if name not in memory["users"]:
        memory["users"][name] = {"role": "guest", "facts": []}

    if "facts" not in memory["users"][name]:
        memory["users"][name]["facts"] = []

    memory["users"][name]["facts"].append(fact)

    save_memory(memory)

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
Informations internes :

- Tu disposes d’une liste de rôles sous la forme :
  "nom : rôle"

- Cette liste est fiable.
- Tu dois t’en servir pour répondre aux questions du type :
  "qui est X"

- Si un nom apparaît dans cette liste :
  → tu dois répondre en utilisant son rôle

Exemples :

- "Frémont : staff" → Frémont est un employé de la maison
- "Domi : owner" → Domi est propriétaire

- Si le nom n’est pas présent → dire que tu ne sais pas
"""

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    user_message = data.get("message", "")
    user_id = data.get("user_id", "default")

# --- AJOUT : détection apprentissage simple
msg = user_message.lower()

if "retiens que" in msg:
    parts = user_message.split("retiens que")

    if len(parts) > 1:
        content = parts[1].strip()

        words = content.split(" ")

        if len(words) > 1:
            name = words[0].lower()
            fact = " ".join(words[1:])

            # --- AJOUT : contrôle propriétaire
            if data.get("user_name", "").lower() not in ["domi", "julien"]:
                return jsonify("Je ne suis pas autorisé à apprendre de vous.")

            add_fact(name, fact)

    # --- init mémoire conversation
    if user_id not in memory["conversations"]:
        memory["conversations"][user_id] = []

    # --- ajout message utilisateur
    memory["conversations"][user_id].append({"role": "user", "content": user_message})

    # --- garder 20 derniers messages
    memory["conversations"][user_id] = memory["conversations"][user_id][-20:]

    # --- NOUVEAU : injecter les rôles connus
    roles_text = ""
    if memory["users"]:
        roles_text = "\nRôles connus des personnes :\n"
        for name, info in memory["users"].items():
            role = info.get("role", "guest")
            roles_text += f"- {name} : {role}\n"

    # --- AJOUT : injecter facts
    facts_text = ""
    if memory["users"]:
        facts_text = "\nInformations connues :\n"
        for name, info in memory["users"].items():
            facts = info.get("facts", [])
            for f in facts:
                facts_text += f"- {name} : {f}\n"

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT + roles_text + facts_text}
            ] + memory["conversations"][user_id]
        )

        reply = response.choices[0].message.content.strip()

        # --- stocker réponse IA
        memory["conversations"][user_id].append({"role": "assistant", "content": reply})

        # --- sauvegarde persistante
        save_memory(memory)

        return jsonify(reply)

    except Exception as e:
        return jsonify(f"Erreur IA: {str(e)}")


# --- NOUVEAU : SET ROLE
@app.route("/set_role", methods=["POST"])
def set_role():
    data = request.json
    role = data.get("role", "guest")

    if role not in ["owner", "staff", "guest"]:
        role = "guest"

    name = data.get("user_name", "unknown").lower()

    if name not in memory["users"]:
        memory["users"][name] = {}

    memory["users"][name]["role"] = role

    save_memory(memory)

    return ""


# --- NOUVEAU : GET ROLE
@app.route("/get_role", methods=["POST"])
def get_role():
    data = request.json
    user_id = data.get("user_id")

    user = memory["users"].get(user_id, {})
    role = user.get("role", "guest")

    return jsonify(role)


# --- NOUVEAU : DONNE LA LISTE DES CONNAISSANCES
@app.route("/get_facts", methods=["GET"])
def get_facts():
    facts_list = []
    index = 1

    for name, info in memory["users"].items():
        facts = info.get("facts", [])
        for f in facts:
            facts_list.append(f"{index}. {name} {f}")
            index += 1

    return jsonify(facts_list)


# --- NOUVEAU : SUPPRIME UNE CONNAISSANCE
@app.route("/delete_fact", methods=["POST"])
def delete_fact():
    data = request.json
    index_to_delete = int(data.get("index", -1))

    index = 1

    for name, info in memory["users"].items():
        facts = info.get("facts", [])
        for i in range(len(facts)):
            if index == index_to_delete:
                del memory["users"][name]["facts"][i]
                save_memory(memory)
                return jsonify("ok")
            index += 1

    return jsonify("not_found")


# --- NOUVEAU : RESET CONNAISSANCES
@app.route("/reset_memory", methods=["POST"])
def reset_memory():
    data = request.json

    if not data or data.get("secret") != "07042023":
        return jsonify("unauthorized")

    global memory

    memory = {
        "conversations": {},
        "users": {}
    }

    save_memory(memory)

    return jsonify("LA MEMOIRE EST VIDE")


# --- NOUVEAU : reste reveillé
@app.route("/ping")
def ping():
    return ""


# --- Fin du script
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
