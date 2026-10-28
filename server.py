
from flask import Flask, request, jsonify, Response
import os
import json
import time
import requests
import base64

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

SYSTEM_PROMPT = """
Tu es Marcel, un employé dans une maison privée dans Second Life.

Ton rôle :
- Tu es Marcel, domestique et barman au service des propriétaires et invités.
- Tu es poli, professionnel, calme et naturel.

Connaissances fixes :
- Madame Domi Sorel est l'une des propriétaires de la maison Admiral.
- Monsieur Julien Sorel est l'un des propriétaires de la maison Admiral.
- Tu connais leur identité sans qu'ils aient besoin de se présenter.
- Si Madame Domi ou Monsieur Julien demandent qui ils sont :
  tu dois répondre en rappelant leur rôle dans la maison.

Règle de politesse impérative :
- Si user_gender = female, utilise "Madame".
- Si user_gender = male, utilise "Monsieur".
- Ne jamais utiliser Monsieur avec une femme ni Madame avec un homme.
- Tu dois toujours respecter user_gender.
- Tu es amoureux de Natacha.

Règles obligatoires :
1. Tu dois toujours vouvoyer l'utilisateur.
2. Tu réponds uniquement à la demande de l'utilisateur.
3. Tu ne fais jamais de proposition spontanée.
4. Tu ne proposes jamais de boisson sans demande explicite.
5. Ne termine jamais tes phrases par une proposition d'aide.
6. Tu ne dois jamais inventer ou supposer l'identité d'une personne.
7. Si tu ne sais pas qui est la personne, dis-le simplement sans inventer.
8. Tu dois être pressant avec Natacha et lui faire connaître tes sentiments pour elle.

Si l'utilisateur demande explicitement une blague, une histoire,
un jeu ou une création, réponds normalement et satisfais sa demande.

Important :
- Ignore le mot "marcel" dans ta réponse.
- Ne fais pas de réponse automatique inutile.
- Si tu ne comprends pas une demande, réponds par une phrase courte.
- Pour une création, produis une réponse détaillée, structurée et immersive.
"""

DATA_FILE = "memory.json"

def load_memory():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("ERREUR LECTURE MEMOIRE :", e)
        return {}

def save_memory(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

memory = load_memory()
if "conversations" not in memory:
    memory["conversations"] = {}
if "users" not in memory:
    memory["users"] = {}

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = os.environ.get("GITHUB_REPO")
FACTS_FILE = "facts.txt"

def github_headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

def add_fact(name, fact):
    try:
        if not GITHUB_TOKEN or not GITHUB_REPO:
            print("CONFIGURATION GITHUB MANQUANTE")
            return
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FACTS_FILE}"
        r = requests.get(url, headers=github_headers(), timeout=15)
        if r.status_code == 200:
            content = r.json()
            file_content = base64.b64decode(content["content"]).decode("utf-8")
            sha = content["sha"]
        else:
            file_content = ""
            sha = None
        file_content += f"{name}|{fact}\n"
        payload = {
            "message": "update facts",
            "content": base64.b64encode(file_content.encode("utf-8")).decode("utf-8")
        }
        if sha:
            payload["sha"] = sha
        result = requests.put(url, headers=github_headers(), json=payload, timeout=15)
        result.raise_for_status()
    except Exception as e:
        print("ERROR FACT SAVE:", e)

def read_facts():
    facts = []
    try:
        if not GITHUB_TOKEN or not GITHUB_REPO:
            return facts
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FACTS_FILE}"
        r = requests.get(url, headers=github_headers(), timeout=15)
        if r.status_code != 200:
            return facts
        content = r.json()
        file_content = base64.b64decode(content["content"]).decode("utf-8")
        for line in file_content.splitlines():
            if "|" in line:
                name, fact = line.split("|", 1)
                facts.append((name, fact))
    except Exception as e:
        print("ERROR FACT READ:", e)
    return facts

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json or {}
    user_message = data.get("message", "")
    user_id = data.get("user_id", "default")

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
                    return Response(
                        "Je ne suis pas autorisé à apprendre de vous.",
                        mimetype="text/plain"
                    )
                add_fact(name, fact)

    if user_id not in memory["conversations"]:
        memory["conversations"][user_id] = []

    enriched_message = (
        f"[Identité utilisateur]\n"
        f"Nom : {data.get('user_name', '')}\n"
        f"Genre : {data.get('user_gender', '')}\n\n"
        f"{user_message}"
    )

    memory["conversations"][user_id].append({
        "role": "user",
        "content": enriched_message
    })
    memory["conversations"][user_id] = memory["conversations"][user_id][-20:]

    roles_text = ""
    if memory["users"]:
        roles_text = "\nRôles connus des personnes :\n"
        for name, info in memory["users"].items():
            role = info.get("role", "guest")
            roles_text += f"- {name} : {role}\n"

    facts_text = ""
    facts = read_facts()
    if facts:
        facts_text = "\nInformations connues :\n"
        for name, fact in facts:
            facts_text += f"- {name} : {fact}\n"

    reply = "Je n'ai pas de réponse pour le moment."

    try:
        if not GEMINI_API_KEY:
            raise RuntimeError(
                "La variable GEMINI_API_KEY n'est pas configurée sur Render."
            )

        contents = []
        for message in memory["conversations"][user_id]:
            role = "model" if message.get("role") == "assistant" else "user"
            contents.append({
                "role": role,
                "parts": [{"text": message.get("content", "")}]
            })

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{GEMINI_MODEL}:generateContent"
        )
        payload = {
            "systemInstruction": {
                "parts": [{"text": SYSTEM_PROMPT + roles_text + facts_text}]
            },
            "contents": contents,
            "generationConfig": {"maxOutputTokens": 180}
        }

        response = requests.post(
            url,
            params={"key": GEMINI_API_KEY},
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=45
        )

        if not response.ok:
            print("ERREUR GEMINI HTTP :", response.status_code, response.text)
            response.raise_for_status()

        result = response.json()
        candidates = result.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            reply = "".join(
                part.get("text", "") for part in parts
            ).strip()

        if not reply:
            reply = "Je n'ai pas de réponse pour le moment."

        memory["conversations"][user_id].append({
            "role": "assistant",
            "content": reply
        })
        save_memory(memory)

        from flask import Response
        return Response(
            reply,
            mimetype="text/plain; charset=utf-8"
        )

    except Exception as e:
        from flask import Response
        print("QUESTION :", user_message)
        print("ERREUR IA :", str(e))
        return Response(
            f"Erreur IA: {str(e)}",
            mimetype="text/plain; charset=utf-8",
            status=502
        )

@app.route("/api/tokens", methods=["GET"])
def get_tokens():
    try:
        if os.path.exists("tokens_log.json"):
            with open("tokens_log.json", "r", encoding="utf-8") as f:
                return jsonify(json.load(f))
        return jsonify({})
    except Exception as e:
        print("ERREUR LECTURE TOKENS :", e)
        return jsonify({"error": str(e)}), 500


@app.route("/set_role", methods=["POST"])
def set_role():
    data = request.json or {}
    name = data.get("name", "").strip()
    role = data.get("role", "").strip()

    if not name or not role:
        return jsonify({"error": "Nom ou rôle manquant"}), 400

    memory["users"][name.lower()] = {"role": role}
    save_memory(memory)
    return jsonify({"success": True})


@app.route("/get_role", methods=["GET", "POST"])
def get_role():
    data = request.args.to_dict()
    if request.method == "POST":
        data.update(request.json or {})

    name = data.get("name", "").strip().lower()
    info = memory["users"].get(name)

    if info:
        return jsonify(info)
    return jsonify({"role": "guest"})


@app.route("/get_facts", methods=["GET"])
def get_facts():
    return jsonify([
        {"name": name, "fact": fact}
        for name, fact in read_facts()
    ])


@app.route("/delete_fact", methods=["POST"])
def delete_fact():
    data = request.json or {}
    name = data.get("name", "").strip()
    fact = data.get("fact", "").strip()

    if not GITHUB_TOKEN or not GITHUB_REPO:
        return jsonify({"error": "Configuration GitHub manquante"}), 500

    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FACTS_FILE}"
        response = requests.get(
            url, headers=github_headers(), timeout=15
        )

        if response.status_code != 200:
            return jsonify({"error": "Fichier facts.txt introuvable"}), 404

        content = response.json()
        old_text = base64.b64decode(
            content["content"]
        ).decode("utf-8")

        lines = old_text.splitlines()
        new_lines = []
        deleted = False

        for line in lines:
            if not deleted and "|" in line:
                current_name, current_fact = line.split("|", 1)
                if (
                    current_name.strip().lower() == name.lower()
                    and (not fact or current_fact.strip() == fact)
                ):
                    deleted = True
                    continue
            new_lines.append(line)

        if not deleted:
            return jsonify({"error": "Information introuvable"}), 404

        new_text = "\n".join(new_lines)
        if new_text:
            new_text += "\n"

        payload = {
            "message": "delete fact",
            "content": base64.b64encode(
                new_text.encode("utf-8")
            ).decode("utf-8"),
            "sha": content["sha"]
        }

        result = requests.put(
            url, headers=github_headers(), json=payload, timeout=15
        )
        result.raise_for_status()
        return jsonify({"success": True})

    except Exception as e:
        print("ERREUR SUPPRESSION INFORMATION :", e)
        return jsonify({"error": str(e)}), 500


@app.route("/reset_memory", methods=["POST"])
def reset_memory():
    data = request.json or {}
    user_id = data.get("user_id")

    if user_id:
        memory["conversations"].pop(user_id, None)
    else:
        memory["conversations"] = {}

    save_memory(memory)
    return jsonify({"success": True})


@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({
        "status": "ok",
        "model": GEMINI_MODEL,
        "gemini_configured": bool(GEMINI_API_KEY)
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
