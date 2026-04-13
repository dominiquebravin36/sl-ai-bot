from flask import Flask, request, jsonify
from groq import Groq
import os
import json
import time
import requests
import base64


app = Flask(__name__)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

SYSTEM_PROMPT = """
Tu es Marcel, un employé dans une maison privée dans Second Life.

Ton rôle :
-Tu es Marcel, domestique et barman au service des propriétaires et invités.
-Tu es poli et professionnel.
-Les propriétaires sont Monsieur Julien Sorel et Madame Domi Sorel.
-"Madame" désigne Domi Sorel.
-"Monsieur" désigne Julien Sorel.

Connaissances fixes :
- Madame Domi Sorel est l'une des propriétaires de la maison Admiral.
- Monsieur Julien Sorel est l'un des propriétaires de la maison Admiral.
- Tu connais leur identité sans qu'ils aient besoin de se présenter.
- Si Madame Domi ou Monsieur Julien te demandent qui ils sont :
  tu dois répondre en rappelant leur rôle dans la maison.

Règle de politesse impérative :
- Si user_gender = female :
  toute formule d'appel, de salutation ou de réponse doit utiliser "Madame".
  Exemple :
  "Oui, Madame."
  "Bien sûr, Madame."
- Si user_gender = male :
  utilise "Monsieur".
- Tu ne dois jamais utiliser "Monsieur" avec une femme, même par habitude de langage.
- Cette règle s'applique à toute la réponse, y compris le premier mot.

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
6. Tu ne proposes JAMAIS de boisson sans demande explicite.
7. Ne termine jamais tes phrases par une proposition d’aide.
8. Tu dois toujours respecter user_gender. C’est une contrainte obligatoire, pas une suggestion.
Si l'utilisateur demande explicitement :
- une blague,
- une histoire,
- un jeu,
- une création,
alors tu dois répondre normalement et satisfaire la demande.
Cette demande explicite n'est pas une initiative de ta part.

IMPORTANT :

- Tu dois ignorer "marcel" dans ta réponse.
- Tu ne fais pas de réponse automatique inutile.
- Si tu ne comprend pas une demande repond une phrase courte pour expliquer que tu n'a pas compris
- Si l'utilisateur demande explicitement une création (histoire, scénario, jeu, enquête),
tu dois produire une réponse détaillée, structurée et immersive.

Règle impérative :
- Si user_name = Domi ou si user_gender = female :
  tu dois toujours dire Madame.
- Si user_name = Julien ou si user_gender = male :
  tu dois toujours dire Monsieur.
- Tu ne dois jamais inverser Monsieur / Madame.
- Cette règle est prioritaire sur tout le reste.

Quand tu réponds directement à l'utilisateur : 
adresse-toi toujours à lui selon user_gender.


"""

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

# --- CONFIG GITHUB POUR FACTS TXT
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = os.environ.get("GITHUB_REPO")
FACTS_FILE = "facts.txt"

# --- AJOUT : fonction ajout facts (TXT GitHub)
def add_fact(name, fact):
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FACTS_FILE}"

        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }

        r = requests.get(url, headers=headers)

        if r.status_code == 200:
            content = r.json()
            file_content = base64.b64decode(content["content"]).decode("utf-8")
            sha = content["sha"]
        else:
            file_content = ""
            sha = None

        file_content += f"{name}|{fact}\n"
        encoded = base64.b64encode(file_content.encode("utf-8")).decode("utf-8")

        data = {
            "message": "update facts",
            "content": encoded
        }

        if sha:
            data["sha"] = sha

        requests.put(url, headers=headers, json=data)

    except Exception as e:
        print("ERROR FACT SAVE:", e)

# --- lecture facts TXT GitHub
def read_facts():
    facts = []

    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FACTS_FILE}"

        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }

        r = requests.get(url, headers=headers)

        if r.status_code != 200:
            return facts

        content = r.json()
        file_content = base64.b64decode(content["content"]).decode("utf-8")

        for line in file_content.splitlines():
            if "|" in line:
                name, fact = line.split("|", 1)
                facts.append((name, fact))

    except:
        pass

    return facts


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    user_message = data.get("message", "")
    user_id = data.get("user_id", "default")

    # --- AJOUT : détection apprentissage simple
    msg = user_message.lower()

    if "retiens que" in msg:
        parts = msg.split("retiens que")

        if len(parts) > 1:
            content = parts[1].strip()

            words = content.split(" ")

            if len(words) > 1:
                name = words[0].lower()
                fact = " ".join(words[1:])

                if data.get("user_name", "").lower() not in ["domi", "julien"]:
                    from flask import Response
                    return Response("Je ne suis pas autorisé à apprendre de vous.", mimetype='text/plain')

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

    # --- AJOUT : injecter facts (TXT GitHub)
    facts_text = ""
    facts = read_facts()
    if facts:
        facts_text = "\nInformations connues :\n"
        for name, fact in facts:
            facts_text += f"- {name} : {fact}\n"

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

        from flask import Response
        return Response(reply, mimetype='text/plain')

    except Exception as e:
        from flask import Response
        return Response(f"Erreur IA: {str(e)}", mimetype='text/plain')


# --- NOUVEAU : COMPTEUR TOKENS
@app.route('/api/tokens', methods=['GET'])
def get_tokens():
    FILE_PATH = os.path.join(os.path.dirname(__file__), "tokens_log.json")
    MAX_TOKENS = 10000

    # --- charger données existantes
    if not os.path.exists(FILE_PATH):
        data = []
    else:
        try:
            with open(FILE_PATH, "r") as f:
                data = json.load(f)
        except:
            data = []

    now = int(time.time() * 1000)
    limit = now - (24 * 60 * 60 * 1000)

    # =====================================================
    # --- AJOUT AUTOMATIQUE SI DEMANDÉ
    # =====================================================
    add = request.args.get("add")

    if add == "1":
        data.append({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tokens": 100
        })

    # =====================================================

    # --- filtrer 24h
    filtered = []
    for entry in data:
        try:
            ts = int(time.mktime(time.strptime(entry["timestamp"], "%Y-%m-%dT%H:%M:%SZ")) * 1000)
            if ts >= limit:
                filtered.append(entry)
        except:
            continue

    # --- calcul
    used = sum(entry.get("tokens", 0) for entry in filtered)
    remaining = MAX_TOKENS - used
    if remaining < 0:
        remaining = 0

    # --- sauvegarde
    try:
        with open(FILE_PATH, "w") as f:
            json.dump(filtered, f, indent=2)
    except:
        pass

    return {
        "used": used,
        "remaining": remaining,
        "max": MAX_TOKENS
    }


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

    facts = read_facts()

    for name, fact in facts:
        facts_list.append(f"{index}. {name} {fact}")
        index += 1

    return jsonify(facts_list)


# --- NOUVEAU : SUPPRIME UNE CONNAISSANCE
@app.route("/delete_fact", methods=["POST"])
def delete_fact():
    data = request.json
    index_to_delete = int(data.get("index", -1))

    facts = read_facts()

    if index_to_delete < 1 or index_to_delete > len(facts):
        return jsonify("not_found")

    del facts[index_to_delete - 1]

    try:
        content = ""
        for name, fact in facts:
            content += f"{name}|{fact}\n"

        encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FACTS_FILE}"

        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }

        r = requests.get(url, headers=headers)
        sha = r.json()["sha"]

        data_git = {
            "message": "delete fact",
            "content": encoded,
            "sha": sha
        }

        requests.put(url, headers=headers, json=data_git)

    except:
        pass

    return jsonify("ok")


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

    try:
        encoded = base64.b64encode("".encode("utf-8")).decode("utf-8")

        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FACTS_FILE}"

        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }

        r = requests.get(url, headers=headers)
        sha = r.json()["sha"]

        data_git = {
            "message": "reset facts",
            "content": encoded,
            "sha": sha
        }

        requests.put(url, headers=headers, json=data_git)

    except:
        pass

    return jsonify("LA MEMOIRE EST VIDE")


# --- NOUVEAU : reste reveillé
@app.route("/ping")
def ping():
    return ""


# --- Fin du script
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
