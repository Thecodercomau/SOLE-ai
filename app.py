import os, json, requests
from flask import Flask, render_template, request, jsonify
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.secret_key = 'sneaker-studio-dev-key' 
GROQ_API_KEY      = os.environ.get("GROQ_API_KEY")
GROQ_MODEL        = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
HCAPTCHA_SITE_KEY = os.environ.get("HCAPTCHA_SITE_KEY", "")
HCAPTCHA_SECRET   = os.environ.get("HCAPTCHA_SECRET", "")
HCAPTCHA_VERIFY_URL = "https://api.hcaptcha.com/siteverify"
groq_client       = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

DESIGN_PROMPT = """You are an expert sneaker designer. Generate a detailed concept based on:
Style: {style}, Primary Color: {primary_color}, Accent Color: {accent_color},
Material: {material}, Occasion: {occasion}, Inspiration: {inspiration}

Respond with raw JSON only — no markdown, no explanation.
{{"name":"2-4 word creative name","tagline":"punchy tagline max 10 words",
"description":"2-3 sentence design description","materials":["mat1","mat2","mat3"],
"colorways":[{{"name":"colorway name","sole":"#hex","upper":"#hex","accent":"#hex",
"lace":"#hex","tongue":"#hex"}}],"features":["feat1","feat2","feat3","feat4"],
"sole_type":"sole tech description","target_audience":"who this is for",
"retail_price":"$XXX","style_tags":["tag1","tag2","tag3"]}}
Generate exactly 3 colorways. All hex codes must be valid #RRGGBB."""

def get_prefs(data):
    fields = [("style","casual"),("primary_color","white"),("accent_color","black"),
              ("material","leather"),("occasion","everyday"),("inspiration","")]
    return {k: data.get(k, d) for k, d in fields}


def generate_concept(prefs):
    if not groq_client:
        raise RuntimeError("GROQ_API_KEY not set.")
    chat = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": "Sneaker design expert. Pure JSON only."},
            {"role": "user",   "content": DESIGN_PROMPT.format(**prefs)},
        ],
        temperature=0.85, max_tokens=1200, reasoning_effort="low",
    )
    raw = chat.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"): raw = raw[4:]
    return json.loads(raw.strip().rstrip("```").strip())


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/studio')
def studio():
    return render_template('studio.html', hcaptcha_site_key=HCAPTCHA_SITE_KEY)

@app.route("/history")
def history():
    return render_template('history.html', designs=[])

@app.route("/generate", methods=["POST"])
def generate():
    data  = request.get_json(silent=True) or request.form
    token = data.get("h-captcha-response")
    if not isinstance(token, str) or not token.strip():
        return jsonify({"error": "Please complete the CAPTCHA."}), 400
    if not HCAPTCHA_SITE_KEY or not HCAPTCHA_SECRET:
        app.logger.error("hCaptcha is not configured.")
        return jsonify({"error": "CAPTCHA verification is not configured."}), 503
    try:
        captcha_valid = verify_hcaptcha(token)
    except (requests.RequestException, ValueError) as exc:
        app.logger.warning("hCaptcha verification failed: %s", exc)
        return jsonify({"error": "CAPTCHA verification is temporarily unavailable. Please try again."}), 503
    if not captcha_valid:
        return jsonify({"error": "CAPTCHA verification failed."}), 400
    prefs = get_prefs(data)
    try:
        concept = generate_concept(prefs)
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Malformed AI response: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"Concept generation failed: {e}"}), 500
    return jsonify({"success": True, "concept": concept, "prefs": prefs})

def verify_hcaptcha(token):
    response = requests.post(
        HCAPTCHA_VERIFY_URL,
        data={
            "secret": HCAPTCHA_SECRET,
            "response": token,
            "remoteip": request.remote_addr,
        },
        timeout=10,
    )
    response.raise_for_status()
    verification = response.json()
    if not isinstance(verification, dict) or not isinstance(verification.get("success"), bool):
        raise ValueError("hCaptcha returned an invalid verification response.")
    return verification["success"]

if __name__ == "__main__":
    app.run(debug=True, port=5000)
