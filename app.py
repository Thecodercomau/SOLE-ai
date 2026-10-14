import os, json, requests
from flask import Flask, render_template, request, jsonify
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.secret_key = 'sneaker-studio-dev-key' 
GROQ_API_KEY      = os.environ.get("GROQ_API_KEY")
GROQ_MODEL        = os.environ.get("GROQ_MODEL", "")
HCAPTCHA_SITE_KEY = os.environ.get("HCAPTCHA_SITE_KEY", "")
HCAPTCHA_SECRET   = os.environ.get("HCAPTCHA_SECRET", "")
HCAPTCHA_VERIFY_URL = "https://api.hcaptcha.com/siteverify"
HF_API_KEY = os.environ.get("HF_API_KEY", "")
HF_IMAGE_URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
groq_client       = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

DESIGN_PROMPT = """You are an expert sneaker designer. Generate a detailed concept based on:
Style: {style}, Primary Color: {primary_color}, Accent Color: {accent_color},
Material: {material}, Occasion: {occasion}, Inspiration: {inspiration}

Respond with raw JSON only — no markdown, no explanation.
{{"name":"2-4 word creative name","tagline":"punchy tagline max 10 words","description":"2-3 sentence design description","materials":["mat1","mat2","mat3"],"colorways":[{{"name":"colorway name","sole":"#hex","upper":"#hex","accent":"#hex","lace":"#hex","tongue":"#hex"}}],"features":["feat1","feat2","feat3","feat4"],"sole_type":"sole tech description","target_audience":"who this is for","retail_price":"$XXX","style_tags":["tag1","tag2","tag3"]}}
Generate exactly 3 colorways: user colors first, then 2 creative variations. All hex codes must be valid #RRGGBB."""


def get_prefs(data):
    fields = [("style","casual"),("primary_color","white"),("accent_color","black"),
              ("material","leather"),("occasion","everyday"),("inspiration","")]
    return {k: data.get(k, d) for k, d in fields}


def verify_hcaptcha(token):
    try:
        r = requests.post(HCAPTCHA_VERIFY_URL,
                          data={"secret": HCAPTCHA_SECRET, "response": token}, timeout=5)
        return r.json().get("success", False)
    except Exception:
        return False


def hex_to_color_name(h):
    h = h.lstrip("#").lower()
    try: r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
    except: return h
    mx, mn = max(r,g,b), min(r,g,b)
    br, sat = mx/255, (mx-mn)/mx if mx else 0
    if br < 0.15: return "black"
    if br > 0.88 and sat < 0.15: return "white"
    if sat < 0.18: return "dark gray" if br < 0.4 else "gray" if br < 0.65 else "light gray"
    if mx == r: return ("orange" if g > 120 else "dark orange") if g > b+60 else "magenta" if b > g+40 else "red"
    if mx == g: return "yellow-green" if r > b+60 else "cyan-green" if b > r+40 else "green"
    if mx == b: return "purple" if r > g+60 else "cyan" if g > r+40 else "blue"
    return "colorful"


def generate_concept(prefs):
    if not groq_client:
        raise RuntimeError("GROQ_API_KEY not set.")
    chat = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": "Sneaker design expert. Pure JSON only."},
            {"role": "user",   "content": DESIGN_PROMPT.format(**prefs)},
        ],
        temperature=0.85, max_tokens=1200,
    )
    raw = chat.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"): raw = raw[4:]
    return json.loads(raw.strip().rstrip("```").strip())


def generate_sneaker_image(prompt):
    if not HF_API_KEY:
        return None
    try:
        r = requests.post(HF_IMAGE_URL,
            headers={"Authorization": f"Bearer {HF_API_KEY}", "Content-Type": "application/json"},
            json={"inputs": prompt}, timeout=60)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
            mime = r.headers["content-type"].split(";")[0].strip()
            return f"data:{mime};base64,{base64.b64encode(r.content).decode()}"
    except Exception:
        pass
    return None


def build_image_prompt(prefs):
    p = hex_to_color_name(prefs["primary_color"])
    a = hex_to_color_name(prefs["accent_color"])
    prompt = (f"Professional product photography of a {prefs['style']} sneaker, "
              f"{p} {prefs['material']} upper, {a} accent, {a} heel, white sole, "
              f"side view, white background, sharp focus, 8k, shoe only")
    if prefs.get("inspiration"):
        prompt += f", {prefs['inspiration']} theme"
    return prompt


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/studio")
def studio():
    return render_template("studio.html", hcaptcha_site_key=HCAPTCHA_SITE_KEY)


@app.route("/history")
def history():
    return render_template("history.html", designs=[])


@app.route("/generate", methods=["POST"])
def generate():
    data  = request.get_json(silent=True) or request.form
    token = data.get("h-captcha-response", "")
    if not token:
        return jsonify({"error": "Please complete the CAPTCHA."}), 400
    if not verify_hcaptcha(token):
        return jsonify({"error": "CAPTCHA verification failed."}), 400
    prefs = get_prefs(data)
    try:
        concept = generate_concept(prefs)
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Malformed AI response: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"Concept generation failed: {e}"}), 500
    concept["image_prompt"] = build_image_prompt(prefs)
    return jsonify({"success": True, "concept": concept, "prefs": prefs})


@app.route("/generate-image", methods=["POST"])
def generate_image():
    data   = request.get_json(silent=True) or {}
    prompt = data.get("image_prompt", "")
    if not prompt:
        return jsonify({"error": "No image prompt."}), 400
    if not HF_API_KEY:
        return jsonify({"error": "HF_API_KEY not configured."}), 503
    image_url = generate_sneaker_image(prompt)
    if not image_url:
        return jsonify({"error": "Image generation failed. Try again."}), 500
    return jsonify({"success": True, "image_url": image_url})


if __name__ == "__main__":
    app.run(debug=True, port=5000)


