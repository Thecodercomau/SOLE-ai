from flask import Flask, render_template
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.secret_key = 'sneaker-studio-dev-key' 

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/studio')
def studio():
    return render_template('studio.html', hcaptcha_site_key="")

@app.route("/history")
def history():
    return render_template('history.html', designs=[])