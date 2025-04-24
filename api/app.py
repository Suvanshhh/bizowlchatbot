from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
import google.generativeai as genai

# Flask setup
app = Flask(__name__)
CORS(app)
app.secret_key = "your-secret-key"

# Firebase setup
cred = credentials.Certificate("./firebase-credentials.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Gemini API setup
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-pro')

# Load menu data
with open("./data/menu_data.json") as f:
    menu_data = json.load(f)

# Optional: temp data if needed
try:
    with open("./data/temp_data.json") as f:
        temp_data = json.load(f)
except FileNotFoundError:
    temp_data = {}

# Utility Functions
def save_message(session_id, sender, message):
    doc_ref = db.collection("chat_history").document(session_id)
    doc = doc_ref.get()
    if doc.exists:
        doc_ref.update({"messages": firestore.ArrayUnion([{"sender": sender, "message": message}])})
    else:
        doc_ref.set({"messages": [{"sender": sender, "message": message}]})

def get_session_id():
    if "session_id" not in session:
        session["session_id"] = os.urandom(8).hex()
    return session["session_id"]

@app.route("/", methods=["GET"])
def index():
    return render_template("index1.html", menu_options=menu_data)

@app.route("/get_menu_options", methods=["POST"])
def get_menu_options():
    data = request.get_json()
    selected_option = data.get("selected_option")
    current_node = menu_data
    for key in selected_option:
        current_node = current_node.get("options", {}).get(key, {})
    sub_options = list(current_node.get("options", {}).keys())
    response = current_node.get("response", "")
    return jsonify({"sub_options": sub_options, "response": response})

@app.route("/process_custom_input", methods=["POST"])
def process_custom_input():
    data = request.get_json()
    user_input = data.get("user_input")
    session_id = get_session_id()
    chat = model.start_chat(history=[])
    response = chat.send_message(user_input)
    save_message(session_id, "user", user_input)
    save_message(session_id, "bot", response.text)
    return jsonify({"response": response.text})

@app.route("/save_contact", methods=["POST"])
def save_contact():
    data = request.get_json()
    db.collection("contact_info").add(data)
    return jsonify({"status": "success", "message": "Contact info saved successfully"})

@app.route("/reset", methods=["POST"])
def reset():
    session.pop("session_id", None)
    return jsonify({"status": "success", "message": "Session reset"})

# Export app as "app" for Vercel
app = app
