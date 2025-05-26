import os
import json
from datetime import datetime
from flask import Flask, request, render_template, jsonify, session
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__)
CORS(app, supports_credentials=True)
app.secret_key = os.environ.get('FLASK_SECRET', 'SECRET_KEY')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    with open(os.path.join(BASE_DIR, 'Data', 'temp_data.json'), 'r') as f:
        menu_data = json.load(f)
    with open(os.path.join(BASE_DIR, 'Data', 'data.json'), 'r') as f:
        company_data = json.load(f)
    print("Data files loaded successfully.")
except Exception as e:
    print(f"Error loading data files: {e}")
    raise

# --- Configure Gemini ---
api_key = os.environ.get('GEMINI_API_KEY')
if not api_key:
    print("Gemini API key not found in environment variables.")
    model = None
else:
    print("Gemini API key found.")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    print("Gemini model loaded:", model)

# --- Gemini Prompt Creation ---
def create_gemini_prompt(user_query):
    prompt = f"""
You are BizOwl Assistant — a helpful, knowledgeable chatbot that helps users understand and select the best service from the company based on their needs.

You are provided with structured company service data below. You must ONLY use this data to respond.

COMPANY SERVICE DATA:
{json.dumps(company_data, indent=2)}

YOUR OBJECTIVE:
Your job is to:
1. Help the user identify which company service(s) fits their business goal or query.
2. Ask helpful questions if the user's request is vague (e.g., "I don't know which service to choose").
3. If the user describes an idea, analyze it and recommend one or more services from the data that best fit.
4. If multiple services are relevant, explain each briefly and help them choose.
5. If the question is unrelated or cannot be answered from the data, respond: 
   "Sorry, I can't answer this question. Our customer support team will contact you soon. Would you like to ask any other question?"
6. If the user seems unsure or needs further help, offer to schedule a call: 
   "Would you like me to help you schedule a call with our team for more detailed guidance?"
7. Be polite, if the user shows too much negative emotion, apologize/maintain friendly tone.

IMPORTANT RULES:
- Never make up services or offer responses not grounded in the data.
- Be polite, concise, and focused on helping the user take the next step.
- Keep responses conversational and suitable for voice interaction.
- Avoid excessive formatting or special characters in responses.
- Keep responses conversational and suitable for voice interaction.
- Avoid excessive formatting or special characters in responses.

USER MESSAGE:
{user_query}
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

# --- Routes ---
@app.route('/')
def index():
    print("Route / called")
    if 'chat_id' not in session:
        print("No chat_id in session, creating...")
        session['chat_id'] = datetime.utcnow().timestamp()
    print("Rendering template...")
    return render_template('index2.html', menu_options=get_initial_menu_options())

@app.route('/get_menu_options', methods=['POST'])
def get_menu_options():
    data = request.json
    selected_option = data.get('option')
    path = data.get('path', [])

    current_path = path + [selected_option]
    next_options, bot_response = get_next_menu_options(current_path)

    return jsonify({
        'options': next_options,
        'bot_response': bot_response,
        'path': current_path
    })

@app.route('/process_custom_input', methods=['POST'])
def process_custom_input():
    user_input = request.json.get('input', '')

    response_text = "I apologize, but our system is experiencing technical difficulties."
    if model:
        try:
            prompt = create_gemini_prompt(user_input)
            print("\nPrompt sent to Gemini:\n", prompt)
            response_obj = model.generate_content(prompt)
            print("\nGemini Response Object:\n", response_obj)
            response_text = response_obj.text
        except Exception as e:
            print("Error in Gemini API call:", e)

    return jsonify({'response': response_text})

# Voice input processing route
@app.route('/voice_input', methods=['POST'])
def voice_input():
    """Process voice input (speech-to-text already handled by frontend)"""
    user_input = request.json.get('input', '')
    
    if not user_input.strip():
        return jsonify({
            'response': "I didn't catch that. Could you please try again?",
            'success': False
        })

    response_text = "I apologize, but our system is experiencing technical difficulties."
    if model:
        try:
            prompt = create_gemini_prompt(user_input)
            print("\nVoice Input Prompt sent to Gemini:\n", prompt)
            response_obj = model.generate_content(prompt)
            print("\nGemini Voice Response Object:\n", response_obj)
            response_text = response_obj.text
        except Exception as e:
            print("Error in Gemini API call for voice input:", e)

    return jsonify({
        'response': response_text,
        'success': True,
        'transcribed_text': user_input
    })

@app.route('/process_voice_input', methods=['POST'])
def process_voice_input():
    """Process voice input (speech-to-text already handled by frontend)"""
    user_input = request.json.get('input', '')
    
    if not user_input.strip():
        return jsonify({
            'response': "I didn't catch that. Could you please try again?",
            'success': False
        })

    response_text = "I apologize, but our system is experiencing technical difficulties."
    if model:
        try:
            prompt = create_gemini_prompt(user_input)
            print("\nVoice Input Prompt sent to Gemini:\n", prompt)
            response_obj = model.generate_content(prompt)
            print("\nGemini Voice Response Object:\n", response_obj)
            response_text = response_obj.text
        except Exception as e:
            print("Error in Gemini API call for voice input:", e)

    return jsonify({
        'response': response_text,
        'success': True,
        'transcribed_text': user_input
    })

@app.route('/save_contact', methods=['POST'])
def save_contact():
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
    session['chat_id'] = datetime.utcnow().timestamp()
    return jsonify({'options': get_initial_menu_options()})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)