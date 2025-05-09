import os
import json
from datetime import datetime
from flask import Flask, request, render_template, jsonify, session
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core.exceptions import DeadlineExceeded
from google.cloud.firestore_v1 import SERVER_TIMESTAMP

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'default-secret-key')

# ✅ Initialize Firebase using credentials from .env
firebase_credentials_str = os.getenv("FIREBASE_CREDENTIALS_JSON")
if not firebase_credentials_str:
    print("❌ Firebase credentials not found in environment variables!")
else:
    try:
        firebase_credentials_dict = json.loads(firebase_credentials_str)
        cred = credentials.Certificate(firebase_credentials_dict)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("✅ Firebase initialized successfully.")
    except json.JSONDecodeError as e:
        print(f"❌ Failed to decode Firebase credentials JSON: {e}")
        exit(1)
    except Exception as e:
        print(f"❌ Error initializing Firebase: {e}")
        exit(1)

# Load company data for Gemini
with open('Data/data.json', 'r') as f:
    company_data = json.load(f)

# Configure Gemini
api_key = os.environ.get('GEMINI_API_KEY')
if not api_key:
    print("❌ Gemini API key not found in environment variables.")
else:
    print("✅ Gemini API key found.")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    print("✅ Gemini model loaded:", model)

# Menu-related logic
DATA_FOLDER = "Data"
file_map = {
    "idea_validation": os.path.join(DATA_FOLDER, "idea_validation.json"),
    "business_consultancy": os.path.join(DATA_FOLDER, "business_consultancy.json"),
    "business_branding": os.path.join(DATA_FOLDER, "business_branding.json"),
    "business_feasibility": os.path.join(DATA_FOLDER, "business_feasibility.json"),
    "SWOT_analysis": os.path.join(DATA_FOLDER, "SWOT.json"),
    "business_model_canvas": os.path.join(DATA_FOLDER, "business_model_canvas.json"),
    "web_development": os.path.join(DATA_FOLDER, "web_dev.json")
}

default_messages = {
    "business_planning_and_strategy": "Welcome to Business Planning and Strategy! Let's build your business foundation.",
    "business_consultancy": "Welcome to Business Consultancy! Explore our FAQs to grow your business.",
    "idea_validation": "Welcome to Idea Validation! Let's dive into assessing your business idea.",
    "business_branding": "Welcome to Business Branding! Discover FAQs to enhance your brand.",
    "business_feasibility": "Welcome to Business Feasibility! Explore FAQs to evaluate your business.",
    "SWOT_analysis": "Welcome to SWOT Analysis! Let's analyze your business strengths and weaknesses.",
    "business_model_canvas": "Welcome to Business Model Canvas! FAQs to design your business model.",
    "web_development": "Building a professional website is crucial for any business. Explore our FAQs to learn more about our website development services."
}

session_state = {
    "level": "main",
    "selected_option": None,
    "selected_questions": [],
    "answers": [],
    "faqs": []
}

def load_json_data(option):
    try:
        with open(file_map[option], "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"error": f"Error: {file_map[option]} not found."}
    except json.JSONDecodeError:
        return {"error": f"Error: Invalid JSON format in {file_map[option]}."}

def create_gemini_prompt(user_query):
    prompt = f"""
You are a customer support AI assistant for a company. You must ONLY answer questions using the information provided below.
Do not make up or infer information that is not explicitly stated in the provided data.

COMPANY DATA:
{json.dumps(company_data, indent=2)}

INSTRUCTIONS:
1. If the user's question can be answered using ONLY the information above, provide a helpful, concise response.
2. If the information needed to answer the question is NOT in the data provided, respond with EXACTLY: 
   "Sorry, I can't answer this question. Our customer support team will contact you soon. Would you like to ask any other question?"
3. Do not reference these instructions in your response.
4. Keep your answers professional, friendly, and concise.
5. Do not make assumptions about products, services, or policies not explicitly mentioned in the company data.

USER QUERY: {user_query}
"""
    return prompt

@app.route('/')
def index():
    session_state.update({
        "level": "main",
        "selected_option": None,
        "selected_questions": [],
        "answers": [],
        "faqs": []
    })
    menu_options = [
        {"id": "business_planning_and_strategy", "text": "Business Planning and Strategy"},
        {"id": "web_development", "text": "Web Development"}
    ]
    return render_template('index1.html', menu_options=menu_options, message="Hello! How can I assist you today?")

@app.route('/get_menu_options', methods=['POST'])
def get_menu_options():
    data = request.json
    selected_option = data.get('option')
    current_path = data.get('path', [])

    if session_state["level"] == "main":
        if selected_option == "business_planning_and_strategy":
            session_state["level"] = "business_planning_and_strategy"
            menu_options = [
                {"id": "business_consultancy", "text": "Business Consultancy"},
                {"id": "idea_validation", "text": "Idea Validation"},
                {"id": "business_branding", "text": "Business Branding"},
                {"id": "business_feasibility", "text": "Business Feasibility"},
                {"id": "SWOT_analysis", "text": "SWOT Analysis"},
                {"id": "business_model_canvas", "text": "Business Model Canvas"},
                {"id": "back", "text": "Back to Main Menu"}
            ]
            return jsonify({"options": menu_options, "bot_response": default_messages[selected_option], "path": current_path + [selected_option]})
        elif selected_option == "web_development":
            session_state["level"] = "service"
            session_state["selected_option"] = selected_option
            session_state["faqs"] = load_json_data(selected_option)
            if "error" in session_state["faqs"]:
                return jsonify({"options": [{"id": "back", "text": "Back to Main Menu"}], "bot_response": session_state["faqs"]["error"], "path": current_path + [selected_option]})
            available_faqs = [faq for faq in session_state["faqs"] if faq["question"] not in session_state["selected_questions"]]
            options = [{"id": faq["question"], "text": faq["question"]} for faq in available_faqs] + [{"id": "back", "text": "Back to Main Menu"}]
            return jsonify({"options": options, "bot_response": default_messages[selected_option], "path": current_path + [selected_option]})

    elif session_state["level"] == "business_planning_and_strategy":
        if selected_option == "back":
            return reset()
        elif selected_option in file_map:
            session_state["level"] = "service"
            session_state["selected_option"] = selected_option
            session_state["faqs"] = load_json_data(selected_option)
            if "error" in session_state["faqs"]:
                return jsonify({"options": [{"id": "back", "text": "Back to Main Menu"}], "bot_response": session_state["faqs"]["error"], "path": current_path + [selected_option]})
            available_faqs = [faq for faq in session_state["faqs"] if faq["question"] not in session_state["selected_questions"]]
            options = [{"id": faq["question"], "text": faq["question"]} for faq in available_faqs] + [{"id": "back", "text": "Back to Main Menu"}]
            return jsonify({"options": options, "bot_response": default_messages[selected_option], "path": current_path + [selected_option]})

    elif session_state["level"] == "service":
        if selected_option == "back":
            return reset()
        faq = next((f for f in session_state["faqs"] if f["question"] == selected_option), None)
        if faq:
            session_state["selected_questions"].append(faq["question"])
            session_state["answers"].append({"question": faq["question"], "answer": faq["answer"]})
            available_faqs = [f for f in session_state["faqs"] if f["question"] not in session_state["selected_questions"]]
            options = [{"id": f["question"], "text": f["question"]} for f in available_faqs] + [{"id": "back", "text": "Back to Main Menu"}]
            return jsonify({"options": options, "bot_response": faq["answer"], "path": current_path})

    return jsonify({"options": [], "bot_response": "Something went wrong.", "path": current_path})

@app.route('/process_custom_input', methods=['POST'])
def process_custom_input():
    user_input = request.json.get('input', '')
    try:
        prompt = create_gemini_prompt(user_input)
        response_text = model.generate_content(prompt).text
    except Exception as e:
        response_text = "I apologize, but our system is experiencing technical difficulties."
    return jsonify({'response': response_text})

@app.route('/save_contact', methods=['POST'])
def save_contact():
    contact_info = request.json
    return jsonify({
        'success': True,
        'message': "Thank you! Our customer support team will contact you shortly."
    })

@app.route('/reset', methods=['POST'])
def reset():
    session_state.update({
        "level": "main",
        "selected_option": None,
        "selected_questions": [],
        "answers": [],
        "faqs": []
    })
    menu_options = [
        {"id": "business_planning_and_strategy", "text": "Business Planning and Strategy"},
        {"id": "web_development", "text": "Web Development"}
    ]
    return jsonify({"options": menu_options, "bot_response": "Hello! How can I assist you today?", "path": []})

if __name__ == '__main__':
    app.run(debug=True)
