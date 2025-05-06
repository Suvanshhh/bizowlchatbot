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
firebase_credentials_str = os.getenv("FIREBASE_CREDENTIALS_JSON")  # Corrected the variable name
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
        exit(1)  # Exit the program if Firebase initialization fails
    except Exception as e:
        print(f"❌ Error initializing Firebase: {e}")
        exit(1)  # Exit the program if Firebase initialization fails

# Load data files
try:
    with open('Data/temp_data.json', 'r') as f:
        menu_data = json.load(f)
    with open('Data/data.json', 'r') as f:
        company_data = json.load(f)
    print("✅ Data files loaded successfully.")
except Exception as e:
    print(f"❌ Error loading data files: {e}")
    exit(1)

# Configure Gemini
api_key = os.environ.get('GEMINI_API_KEY')
if not api_key:
    print("❌ Gemini API key not found in environment variables.")
else:
    print("✅ Gemini API key found.")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    print("✅ Gemini model loaded:", model)

# ✅ Firebase Helper Functions (Upgraded)
def create_chat_session():
    chat_ref = db.collection('chats').document()
    chat_data = {
        'created_at': SERVER_TIMESTAMP,
        'updated_at': SERVER_TIMESTAMP,
        'status': 'active'
    }
    try:
        chat_ref.set(chat_data, timeout=30)
        return chat_ref.id
    except DeadlineExceeded:
        print("⚠️ Firestore DeadlineExceeded while creating chat session. Retrying once...")
        try:
            chat_ref.set(chat_data, timeout=30)
            return chat_ref.id
        except Exception as e:
            print(f"❌ Failed to create chat session after retry: {e}")
            return None
    except Exception as e:
        print(f"❌ Unexpected error while creating chat session: {e}")
        return None

def save_message(chat_id, message, is_user=True):
    try:
        if not chat_id:
            print("⚠️ No chat_id provided, skipping save_message.")
            return
        messages_ref = db.collection('chats').document(chat_id).collection('messages')
        messages_ref.add({
            'content': message,
            'sender': 'user' if is_user else 'bot',
            'timestamp': SERVER_TIMESTAMP
        }, timeout=30)
    except Exception as e:
        print(f"❌ Error saving message: {e}")

def save_contact_info(chat_id, contact_data):
    try:
        if not chat_id:
            print("⚠️ No chat_id provided, skipping save_contact_info.")
            return
        chat_ref = db.collection('chats').document(chat_id)
        chat_ref.update({
            'contact_info': contact_data,
            'updated_at': SERVER_TIMESTAMP
        }, timeout=30)
    except Exception as e:
        print(f"❌ Error saving contact info: {e}")

# Gemini Prompt Creation
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

def get_initial_menu_options():
    try:
        return [{'id': k, 'text': k} for k in menu_data.get('menu', {}).get('greeting', {}).get('options', {}).keys()]
    except Exception as e:
        print(f"❌ Error getting initial menu options: {e}")
        return []

def get_next_menu_options(path):
    try:
        current = menu_data.get('menu', {}).get('greeting', {})
        for step in path:
            current = current.get('options', {}).get(step, {})
        return [
            {'id': k, 'text': k}
            for k in current.get('options', {}).keys()
        ], current.get('message', '')
    except Exception as e:
        print(f"❌ Error getting next menu options: {e}")
        return [], ""

# Routes
@app.route('/')
def index():
    if 'chat_id' not in session:
        chat_id = create_chat_session()
        if not chat_id:
            print("⚠️ Failed to create chat session. Proceeding without chat_id.")
        session['chat_id'] = chat_id
    return render_template('index1.html', menu_options=get_initial_menu_options())

@app.route('/get_menu_options', methods=['POST'])
def get_menu_options():
    data = request.json
    selected_option = data.get('option')
    path = data.get('path', [])

    save_message(session.get('chat_id'), selected_option, is_user=True)

    current_path = path + [selected_option]
    next_options, bot_response = get_next_menu_options(current_path)

    if bot_response:
        save_message(session.get('chat_id'), bot_response, is_user=False)

    return jsonify({
        'options': next_options,
        'bot_response': bot_response,
        'path': current_path
    })

@app.route('/process_custom_input', methods=['POST'])
def process_custom_input():
    user_input = request.json.get('input', '')

    save_message(session.get('chat_id'), user_input, is_user=True)

    try:
        prompt = create_gemini_prompt(user_input)
        print("\n🔹 Prompt sent to Gemini:\n", prompt)

        response_obj = model.generate_content(prompt)
        print("\n🔸 Gemini Response Object:\n", response_obj)

        response_text = response_obj.text
    except Exception as e:
        print("❌ Error in Gemini API call:", e)
        response_text = "I apologize, but our system is experiencing technical difficulties."

    save_message(session.get('chat_id'), response_text, is_user=False)

    return jsonify({'response': response_text})

@app.route('/save_contact', methods=['POST'])
def save_contact():
    contact_info = request.json
    save_contact_info(session.get('chat_id'), contact_info)
    return jsonify({
        'success': True,
        'message': "Thank you! Our customer support team will contact you shortly."
    })

@app.route('/health')
def health():
    return "OK", 200


@app.route('/reset', methods=['POST'])
def reset():
    session.pop('chat_id', None)
    chat_id = create_chat_session()
    if not chat_id:
        print("⚠️ Failed to create new chat session during reset.")
    session['chat_id'] = chat_id
    return jsonify({'options': get_initial_menu_options()})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
