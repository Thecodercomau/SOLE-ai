"""Lesson 6 — Managing History and Finalizing the Sneaker Studio
Goal: Session-based history — every design is saved, shown on /history,
      with AI images, colorway swatches, and a Clear All button.
      This is the complete, fully working app.
Run: python app.py  →  visit http://localhost:5000
"""
import os, re, json, time, uuid, base64, requests
from datetime import datetime
from urllib.parse import quote
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "sneaker-studio-dev-key")

GROQ_API_KEY        = os.environ.get("GROQ_API_KEY", "")
HF_API_KEY          = os.environ.get("HF_API_KEY", "")
HCAPTCHA_SITE_KEY   = os.environ.get("HCAPTCHA_SITE_KEY", "10000000-ffff-ffff-ffff-000000000001")
HCAPTCHA_SECRET     = os.environ.get("HCAPTCHA_SECRET",   "0x0000000000000000000000000000000000000000")
HCAPTCHA_VERIFY_URL = "https://api.hcaptcha.com/siteverify"
# Images: try these providers in order (comma-separated, first success wins).
# NOTE: text-to-image models on the old "hf-inference" provider are retired
# (HTTP 410). The router route below is the current one, but it needs
# Inference Providers credits on the Hugging Face account.
IMAGE_PROVIDERS     = os.environ.get("IMAGE_PROVIDERS", "pollinations,huggingface")
HF_IMAGE_URL        = os.environ.get(
    "HF_IMAGE_URL",
    "https://router.huggingface.co/nscale/v1/images/generations",
)
HF_IMAGE_MODEL      = os.environ.get("HF_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")
HF_IMAGE_TIMEOUT    = 90
POLLINATIONS_URL    = "https://image.pollinations.ai/prompt/{prompt}"
POLLINATIONS_TOKEN  = os.environ.get("POLLINATIONS_TOKEN", "")
POLLINATIONS_TIMEOUT = 120
IMAGE_DIR           = os.path.join(app.static_folder, "img")
groq_client         = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

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
        model="openai/gpt-oss-120b",
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


def _upstream_error(r):
    """Short, human-readable reason from a failed provider response."""
    try:
        err = r.json().get("error") or r.json().get("message")
        if err: return str(err)[:160]
    except Exception:
        pass
    return (r.text or "").strip()[:160] or "no response body"


def _hf_image(prompt):
    """Hugging Face Inference Providers (requires HF credits)."""
    r = requests.post(HF_IMAGE_URL,
        headers={"Authorization": f"Bearer {HF_API_KEY}",
                 "Content-Type": "application/json",
                 "Accept": "image/png"},
        json={"model": HF_IMAGE_MODEL, "prompt": prompt,
              "response_format": "b64_json"},
        timeout=HF_IMAGE_TIMEOUT)
    ctype = r.headers.get("content-type", "")
    if r.status_code == 200 and ctype.startswith("image"):
        return r.content, ctype.split(";")[0].strip(), None
    if r.status_code == 200:
        try:
            item = (r.json().get("data") or [{}])[0]
            if item.get("b64_json"):
                return base64.b64decode(item["b64_json"]), "image/png", None
            if item.get("url"):
                img = requests.get(item["url"], timeout=60)
                if img.status_code == 200:
                    imime = img.headers.get("content-type", "image/png").split(";")[0].strip()
                    return img.content, imime, None
            return None, None, "response contained no image"
        except Exception as e:
            return None, None, f"unreadable response: {e}"
    return None, None, f"HTTP {r.status_code} — {_upstream_error(r)}"


def _pollinations_image(prompt):
    """Keyless provider. Free tier allows one image per 45s per IP."""
    url = POLLINATIONS_URL.format(prompt=quote(prompt, safe=""))
    params = {"width": 1024, "height": 1024, "nologo": "true", "model": "flux"}
    if POLLINATIONS_TOKEN:
        params["token"] = POLLINATIONS_TOKEN

    for attempt in (1, 2):
        r = requests.get(url, params=params, timeout=POLLINATIONS_TIMEOUT)
        ctype = r.headers.get("content-type", "")
        if r.status_code == 200 and ctype.startswith("image"):
            return r.content, ctype.split(";")[0].strip(), None
        msg = _upstream_error(r)
        wait = _retry_after(msg)
        if attempt == 1 and wait is not None:
            print(f"[image] Pollinations rate limited, retrying in {wait}s")
            time.sleep(wait)
            continue
        return None, None, f"HTTP {r.status_code} — {msg}"


def _retry_after(message):
    """Read 'Retry after 16s' out of a provider rate-limit message."""
    m = re.search(r"retry after (\d+)\s*s", message or "", re.I)
    return min(int(m.group(1)), 45) if m else None


def generate_sneaker_image(prompt):
    """Try each provider in order. Returns (bytes, mime, error)."""
    available = {
        "huggingface": ("Hugging Face", _hf_image),
        "pollinations": ("Pollinations", _pollinations_image),
    }
    order = [p.strip().lower() for p in IMAGE_PROVIDERS.split(",") if p.strip()]
    providers = [available[name] for name in order if name in available]
    if not providers:
        providers = [available["pollinations"]]

    errors = []
    for name, fn in providers:
        if name == "Hugging Face" and not HF_API_KEY:
            errors.append("Hugging Face: HF_API_KEY not configured")
            continue
        try:
            data, mime, err = fn(prompt)
        except requests.Timeout:
            errors.append(f"{name}: timed out")
            continue
        except Exception as e:
            errors.append(f"{name}: {e}")
            continue
        if data:
            print(f"[image] {name} ok ({len(data)} bytes)")
            return data, mime, None
        print(f"[image] {name} failed: {err}")
        errors.append(f"{name}: {err}")
    return None, None, "; ".join(errors)


def friendly_image_error(error):
    """Turn provider noise into a line the studio can display."""
    e = (error or "").lower()
    if "no remaining credits" in e:
        hint = "Hugging Face has no image credits — add credits or keep the free provider enabled."
    elif "free_limit" in e or "free limit" in e or "rate limit" in e:
        hint = "The free image service is rate limited — wait a minute, then hit Regenerate Image."
    elif "timed out" in e:
        hint = "The image provider timed out. Try again."
    elif "not configured" in e:
        hint = "No image provider is configured."
    else:
        hint = "The image provider refused the request."
    return f"Image generation failed. {hint}"


def save_image(data, mime):
    """Write the image under static/img and return its public URL."""
    ext = {"image/png": "png", "image/webp": "webp", "image/gif": "gif"}.get(mime, "jpg")
    os.makedirs(IMAGE_DIR, exist_ok=True)
    filename = f"{uuid.uuid4().hex[:12]}.{ext}"
    with open(os.path.join(IMAGE_DIR, filename), "wb") as f:
        f.write(data)
    return url_for("static", filename=f"img/{filename}")


def build_image_prompt(prefs):
    p = hex_to_color_name(prefs["primary_color"])
    a = hex_to_color_name(prefs["accent_color"])
    prompt = (f"Professional product photography of a {prefs['style']} sneaker, "
              f"{p} {prefs['material']} upper, {a} accent, {a} heel, white sole, "
              f"side view, white background, sharp focus, 8k, shoe only")
    if prefs.get("inspiration"):
        prompt += f", {prefs['inspiration']} theme"
    return prompt


def save_to_history(concept, prefs, image_url=None):
    session.setdefault("history", [])
    entry = {
        "id":        str(uuid.uuid4())[:8],
        "timestamp": datetime.now().strftime("%b %d, %Y · %I:%M %p"),
        "concept":   concept,
        "prefs":     prefs,
        "image_url": image_url,
    }
    session["history"] = ([entry] + session["history"])[:20]
    return entry["id"]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/studio")
def studio():
    return render_template("studio.html", hcaptcha_site_key=HCAPTCHA_SITE_KEY)


@app.route("/history")
def history():
    return render_template("history.html", designs=session.get("history", []))


@app.route("/clear-history", methods=["POST"])
def clear_history():
    session.pop("history", None)
    return redirect(url_for("history"))


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
    history_id = save_to_history(concept, prefs)
    return jsonify({"success": True, "concept": concept, "prefs": prefs, "history_id": history_id})


@app.route("/generate-image", methods=["POST"])
def generate_image():
    data       = request.get_json(silent=True) or {}
    prompt     = data.get("image_prompt", "")
    history_id = data.get("history_id", "")
    if not prompt:
        return jsonify({"error": "No image prompt."}), 400
    data, mime, error = generate_sneaker_image(prompt)
    if not data:
        print(f"[image] all providers failed: {error}")
        return jsonify({"error": friendly_image_error(error), "detail": error}), 502
    image_url = save_image(data, mime)
    if history_id and "history" in session:
        for entry in session["history"]:
            if entry["id"] == history_id:
                entry["image_url"] = image_url
                break
        session.modified = True
    return jsonify({"success": True, "image_url": image_url})


if __name__ == "__main__":
    app.run(debug=True, port=5000)


