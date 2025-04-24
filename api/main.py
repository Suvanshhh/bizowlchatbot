import os
import json
from datetime import datetime
from flask import Flask, request, render_template, jsonify, session
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import SERVER_TIMESTAMP  # ✅ Added this line

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'default-secret-key')

# Initialize Firebase
cred = credentials.Certificate("C:/Users/KIIT/Desktop/firebase-credentials/firebase-credentials.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Load data files
with open('Data/temp_data.json', 'r') as f:
    menu_data = json.load(f)

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

# ✅ Firebase Helper Functions (Updated)
def create_chat_session():
    chat_ref = db.collection('chats').document()
    chat_data = {
        'created_at': SERVER_TIMESTAMP,
        'updated_at': SERVER_TIMESTAMP,
        'status': 'active'
    }
    chat_ref.set(chat_data)
    return chat_ref.id

def save_message(chat_id, message, is_user=True):
    messages_ref = db.collection('chats').document(chat_id).collection('messages')
    messages_ref.add({
        'content': message,
        'sender': 'user' if is_user else 'bot',
        'timestamp': SERVER_TIMESTAMP
    })

def save_contact_info(chat_id, contact_data):
    chat_ref = db.collection('chats').document(chat_id)
    chat_ref.update({
        'contact_info': contact_data,
        'updated_at': SERVER_TIMESTAMP
    })

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
        print(f"Error getting initial menu options: {e}")
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
        print(f"Error getting next menu options: {e}")
        return [], ""

# Routes
@app.route('/')
def index():
    if 'chat_id' not in session:
        session['chat_id'] = create_chat_session()
    return render_template('index1.html', menu_options=get_initial_menu_options())

@app.route('/get_menu_options', methods=['POST'])
def get_menu_options():
    data = request.json
    selected_option = data.get('option')
    path = data.get('path', [])
    
    save_message(session['chat_id'], selected_option, is_user=True)
    
    current_path = path + [selected_option]
    next_options, bot_response = get_next_menu_options(current_path)
    
    if bot_response:
        save_message(session['chat_id'], bot_response, is_user=False)
    
    return jsonify({
        'options': next_options,
        'bot_response': bot_response,
        'path': current_path
    })

@app.route('/process_custom_input', methods=['POST'])
def process_custom_input():
    user_input = request.json.get('input', '')

    save_message(session['chat_id'], user_input, is_user=True)

    try:
        prompt = create_gemini_prompt(user_input)
        print("\n🔹 Prompt sent to Gemini:\n", prompt)

        response_obj = model.generate_content(prompt)
        print("\n🔸 Gemini Response Object:\n", response_obj)

        response_text = response_obj.text
    except Exception as e:
        print("❌ Error in Gemini API call:", e)
        response_text = "I apologize, but our system is experiencing technical difficulties."

    save_message(session['chat_id'], response_text, is_user=False)

    return jsonify({'response': response_text})

@app.route('/save_contact', methods=['POST'])
def save_contact():
    contact_info = request.json
    save_contact_info(session['chat_id'], contact_info)
    return jsonify({
        'success': True,
        'message': "Thank you! Our customer support team will contact you shortly."
    })

@app.route('/reset', methods=['POST'])
def reset():
    session.pop('chat_id', None)
    session['chat_id'] = create_chat_session()
    return jsonify({'options': get_initial_menu_options()})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
