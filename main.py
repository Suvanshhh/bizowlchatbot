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

#menu data
with open('Data/temp_data.json', 'r') as f:
    menu_data = json.load(f)

#bizzowl info
with open('Data/data.json', 'r') as f:
    company_data = json.load(f)

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
    """Extract initial menu options from the nested menu structure."""
    try:
        greeting = menu_data.get('menu', {}).get('greeting', {})
        options = greeting.get('options', {})
        menu_options = []
        for key, value in options.items():
            menu_options.append({
                'id': key,
                'text': key
            })
        
        return menu_options
    except Exception as e:
        print(f"Error getting initial menu options: {e}")
        return []

def get_next_menu_options(path):
    """Get the next menu options based on the selected path."""
    try:
        # Start navigation from the greeting level
        current = menu_data.get('menu', {}).get('greeting', {})
        
        # Navigate through the path
        for step in path:
            # Get available options at this level
            options = current.get('options', {})
            
            # Move to the next level based on the step
            if step in options:
                current = options[step]
            else:
                # If step not found, break the traversal
                break
        
        # Get options from the current node
        options_dict = current.get('options', {})
        
        menu_options = []
        for key, value in options_dict.items():
            menu_options.append({
                'id': key,
                'text': key
            })

        message = current.get('message', '')
        
        return menu_options, message
    except Exception as e:
        print(f"Error getting next menu options: {e}")
        return [], ""

# Routes
@app.route('/')
def index():
    """Render the main chat interface."""
    initial_options = get_initial_menu_options()
    return render_template('index1.html', menu_options=initial_options)

@app.route('/get_menu_options', methods=['POST'])
def get_menu_options():
    """Return the next menu options based on the selected option."""
    data = request.json
    selected_option = data.get('option')
    selected_text = data.get('text', '')
    path = data.get('path', [])

    current_path = path + [selected_text]

    next_options, bot_response = get_next_menu_options(current_path)
    
    response = {
        'options': next_options,
        'bot_response': bot_response,
        'path': current_path
    }
    
    return jsonify(response)

@app.route('/process_custom_input', methods=['POST'])
def process_custom_input():
    user_input = request.json.get('input', '')
    
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

@app.route('/reset', methods=['POST'])
def reset():
    """Reset the conversation to the initial state."""
    initial_options = get_initial_menu_options()
    return jsonify({'options': initial_options})

if __name__ == '__main__':
    app.run(debug=True)