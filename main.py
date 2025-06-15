import os
import json
from datetime import datetime
from flask import Flask, request, render_template, jsonify, session
from flask_cors import CORS
from flask_mail import Mail, Message
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core.exceptions import DeadlineExceeded
from google.cloud.firestore_v1 import SERVER_TIMESTAMP
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app, supports_credentials=True)
app.secret_key = os.environ.get('FLASK_SECRET', 'SECRET_KEY')

# Flask-Mail Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_DEBUG'] = True

mail = Mail(app)

# In-memory fallback storage
chat_memory = {}

# Firebase initialization
firebase_credentials_str = os.getenv("FIREBASE_CREDENTIALS_JSON")
if not firebase_credentials_str:
    print("Firebase credentials not found in environment variables")
    raise RuntimeError("Firebase credentials missing")
else:
    try:
        firebase_credentials_dict = json.loads(firebase_credentials_str)
        cred = credentials.Certificate(firebase_credentials_dict)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase initialized successfully.")
    except json.JSONDecodeError as e:
        print(f"Failed to decode Firebase credentials JSON: {e}")
        raise
    except Exception as e:
        print(f"Error initializing firebase: {e}")
        raise

# Load data files
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

# Configure Gemini
api_key = os.environ.get('GEMINI_API_KEY')
if not api_key:
    print("Gemini API key not found in environment variables.")
    model = None
else:
    print("Gemini API key found.")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    print("Gemini model loaded:", model)

# Firebase helper functions
def create_chat_session():
    """Create a new chat session in Firebase"""
    try:
        chat_ref = db.collection('chats').document()
        chat_data = {
            'created_at': SERVER_TIMESTAMP,
            'updated_at': SERVER_TIMESTAMP,
            'status': 'active'
        }
        chat_ref.set(chat_data, timeout=30)
        print(f"Created new chat session: {chat_ref.id}")
        return chat_ref.id
    except DeadlineExceeded:
        print("Firestore Deadline Exceeded while creating chat session. Retrying...")
        try:
            chat_ref = db.collection('chats').document()
            chat_ref.set(chat_data, timeout=30)
            return chat_ref.id
        except Exception as e:
            print(f"Failed to create chat session after retry: {e}")
            fallback_id = f"fallback_{int(datetime.utcnow().timestamp())}"
            print(f"Using fallback chat ID: {fallback_id}")
            return fallback_id
    except Exception as e:
        print(f"Unexpected error while creating chat session: {e}")
        fallback_id = f"fallback_{int(datetime.utcnow().timestamp())}"
        print(f"Using fallback chat ID: {fallback_id}")
        return fallback_id

def ensure_chat_session():
    """Ensure a valid chat session exists"""
    chat_id = session.get('chat_id')
    if not chat_id:
        chat_id = create_chat_session()
        session['chat_id'] = chat_id
    if isinstance(chat_id, (int, float)):
        chat_id = str(chat_id)
        session['chat_id'] = chat_id
    
    return chat_id

def save_message(chat_id, message, is_user=True):
    """Save message to Firebase with fallback to memory"""
    try: 
        if not chat_id:
            print("No chat_id provided")
            return
        chat_id = str(chat_id)
        if not chat_id.startswith('fallback_'):
            messages_ref = db.collection('chats').document(chat_id).collection('messages')
            messages_ref.add({
                'content': message,
                'sender': 'user' if is_user else 'bot',
                'timestamp': SERVER_TIMESTAMP
            }, timeout=30)
            print(f"Message saved to Firebase for chat {chat_id}")
        else:
            raise Exception("Using fallback storage")
            
    except Exception as e:
        print(f"Firebase save failed, using memory fallback: {e}")
        chat_id = str(chat_id)
        if chat_id not in chat_memory:
            chat_memory[chat_id] = []
        chat_memory[chat_id].append({
            'content': message,
            'sender': 'user' if is_user else 'bot',
            'timestamp': datetime.utcnow().isoformat()
        })
        print(f"Message saved to memory for chat {chat_id}")
        
def save_contact_info(chat_id, contact_data):
    """Save contact information to Firebase"""
    try:
        if not chat_id or chat_id.startswith('fallback_'):
            print("Cannot save contact info for fallback chat session")
            return
            
        chat_ref = db.collection('chats').document(chat_id)
        chat_ref.update({
            'contact_info': contact_data,
            'updated_at': SERVER_TIMESTAMP
        }, timeout=30)
        print(f"Contact info saved for chat {chat_id}")
    except Exception as e:
        print(f"Error saving contact info: {e}")
        
def get_chat_history(chat_id, max_messages=15):
    """Get recent chat history with fallback to memory"""
    try:
        if not chat_id:
            return ""
        chat_id = str(chat_id)
        if not chat_id.startswith('fallback_'):
            messages_ref = db.collection('chats').document(chat_id).collection('messages')
            query = messages_ref.order_by('timestamp').limit_to_last(max_messages)
            docs = query.get()
            
            history = []
            for doc in docs:
                msg = doc.to_dict()
                sender = msg.get('sender', 'user')
                content = msg.get('content', '').strip()
                
                if content:  
                    role = 'User' if sender == 'user' else 'Assistant'
                    history.append(f"{role}: {content}")
            
            result = "\n".join(history) if history else ""
            print(f"Retrieved {len(history)} messages from Firebase for chat {chat_id}")
            return result
        else:
            raise Exception("Using fallback storage")
            
    except Exception as e:
        print(f"Firebase fetch failed, using memory fallback: {e}")
        chat_id = str(chat_id)
        if chat_id in chat_memory:
            messages = chat_memory[chat_id][-max_messages:]
            history = []
            for msg in messages:
                content = msg.get('content', '').strip()
                if content:
                    role = 'User' if msg['sender'] == 'user' else 'Assistant'
                    history.append(f"{role}: {content}")
            result = "\n".join(history) if history else ""
            print(f"Retrieved {len(history)} messages from memory for chat {chat_id}")
            return result
        
        print(f"No chat history found for chat {chat_id}")
        return ""

# Gemini Prompt Creation
def create_gemini_prompt(user_query, chat_history):
    """Create a comprehensive prompt for Gemini with chat context"""
    context_section = f"\nCONVERSATION CONTEXT:\n{chat_history}\n" if chat_history else "\nCONVERSATION CONTEXT:\nThis is the start of our conversation.\n"
    
    prompt = f"""
You are BizOwl Assistant — a helpful, knowledgeable chatbot that helps users understand and select the best service from the company based on their needs.

You are provided with structured company service data below. You must ONLY use this data to respond.

COMPANY SERVICE DATA:
{json.dumps(company_data, indent=2)}
{context_section}
YOUR OBJECTIVE:
Your job is to:
1. Help the user identify which company service(s) fits their business goal or query.
2. Ask helpful questions if the user's request is vague about business services (e.g., "I don't know which service to choose").
3. If the user describes a business idea, analyze it and recommend one or more services from the data that best fit.
4. If multiple services are relevant, explain each briefly and help them choose.
5. If the question is completely unrelated to business or our services (like weather, sports, general knowledge, personal questions), respond politely: 
   "I'm BizOwl Assistant, and I'm here to help you with our business services. Is there anything about our services I can help you with today?"
6. ONLY offer to schedule a call if the user is asking about our services but needs detailed guidance that goes beyond what you can provide from the data.
7. Be polite, if the user shows too much negative emotion, apologize/maintain friendly tone.
8. Use the conversation context to provide relevant and personalized responses.

RESPONSE GUIDELINES FOR DIFFERENT QUESTION TYPES:
- Business-related questions about our services: Provide detailed help and recommendations
- Vague business questions: Ask clarifying questions to understand their needs
- Completely unrelated questions (weather, sports, etc.): Politely redirect to business services
- Technical questions beyond our service scope: Briefly acknowledge and redirect to our services
- General greetings: Respond warmly and introduce our services

IMPORTANT RULES:
- Never make up services or offer responses not grounded in the data.
- Be polite, concise, and focused on helping the user take the next step.
- Keep responses conversational and suitable for voice interaction.
- Avoid excessive formatting or special characters in responses.
- Reference previous parts of the conversation when relevant to provide continuity.
- Don't offer to schedule calls for completely unrelated questions - just redirect politely.

CURRENT USER MESSAGE:
{user_query}
"""
    return prompt

def get_initial_menu_options():
    """Get initial menu options from data"""
    try:
        return [{'id': k, 'text': k} for k in menu_data.get('menu', {}).get('greeting', {}).get('options', {}).keys()]
    except Exception as e:
        print(f"Error getting initial menu options: {e}")
        return []

def get_next_menu_options(path):
    """Get next menu options based on current path"""
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

def generate_ai_response(user_input, chat_id):
    """Generate AI response using Gemini with proper error handling"""
    if not model:
        return "I apologize, but our AI system is currently unavailable. Our support team will contact you soon."
    
    try:
        chat_history = get_chat_history(chat_id)
        prompt = create_gemini_prompt(user_input, chat_history)
        
        print(f"\nPrompt sent to Gemini for chat {chat_id}:")
        print("=" * 50)
        print(prompt)
        print("=" * 50)
        
        response_obj = model.generate_content(prompt)
        response_text = response_obj.text
        
        print(f"\nGemini Response for chat {chat_id}:")
        print("-" * 30)
        print(response_text)
        print("-" * 30)
        
        return response_text
        
    except Exception as e:
        print(f"Error generating AI response: {e}")
        return "I apologize, but I'm having trouble processing your request right now. Could you please try again in a few moments or let us know if you need human assistance?"

def send_contact_email(contact_data, chat_id):
    """Send email notification for contact requests"""
    try:
        name = contact_data.get('name', 'Unknown')
        email_addr = contact_data.get('email', 'Not provided')
        phone = contact_data.get('phone', 'Not provided')
        issue = contact_data.get('issue', '')
        chat_history = get_chat_history(chat_id)

        subject = "New Call Request from BizOwl Chatbot"
        body = f"""
A user has requested a call through the BizOwl chatbot.

Name: {name}
Email: {email_addr}
Phone: {phone}
Issue: {issue}

Chat History:
{chat_history}

Chat ID: {chat_id}
Request Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
        """

        msg = Message(
            subject=subject,
            sender=app.config['MAIL_USERNAME'],
            recipients=[os.environ.get('ADMIN_EMAIL', app.config['MAIL_USERNAME'])]
        )
        msg.body = body

        mail.send(msg)
        print(f"Contact email sent successfully for chat {chat_id}")
        return True
    except Exception as e:
        print(f"Error sending contact email: {e}")
        return False

# Routes
@app.route('/')
def index():
    """Main page route"""
    chat_id = ensure_chat_session()
    print(f"Index route - using chat session: {chat_id}")
    return render_template('index2.html', menu_options=get_initial_menu_options())

@app.route('/get_menu_options', methods=['POST'])
def get_menu_options():
    """Handle menu option selection"""
    data = request.json
    selected_option = data.get('option')
    path = data.get('path', [])

    current_path = path + [selected_option]
    next_options, bot_response = get_next_menu_options(current_path)

    # Save menu interaction to chat history
    chat_id = ensure_chat_session()
    save_message(chat_id, f"Selected menu option: {selected_option}", is_user=True)
    if bot_response:
        save_message(chat_id, bot_response, is_user=False)

    return jsonify({
        'options': next_options,
        'bot_response': bot_response,
        'path': current_path
    })

@app.route('/process_custom_input', methods=['POST'])
def process_custom_input():
    """Process custom text input from user"""
    user_input = request.json.get('input', '').strip()
    
    if not user_input:
        return jsonify({'response': "I didn't receive any input. Could you please try again?"})
    
    chat_id = ensure_chat_session()
    print(f"Processing custom input for chat {chat_id}: {user_input}")
    
    # Save user message
    save_message(chat_id, user_input, is_user=True)
    
    # Generate AI response
    response_text = generate_ai_response(user_input, chat_id)
    
    # Save bot response
    save_message(chat_id, response_text, is_user=False)

    return jsonify({'response': response_text})

@app.route('/voice_input', methods=['POST'])
def voice_input():
    """Process voice input (speech-to-text handled by frontend)"""
    user_input = request.json.get('input', '').strip()
    
    if not user_input:
        return jsonify({
            'response': "I didn't catch that. Could you please try again?",
            'success': False,
            'transcribed_text': ''
        })

    chat_id = ensure_chat_session()
    print(f"Processing voice input for chat {chat_id}: {user_input}")
    
    save_message(chat_id, user_input, is_user=True)
    
    # Generate AI response
    response_text = generate_ai_response(user_input, chat_id)
    
    # Save bot response
    save_message(chat_id, response_text, is_user=False)

    return jsonify({
        'response': response_text,
        'success': True,
        'transcribed_text': user_input
    })

@app.route('/process_voice_input', methods=['POST'])
def process_voice_input():
    """Alternative voice input processing route for compatibility"""
    return voice_input()

@app.route('/test_mail')
def test_mail():
    """Test email functionality"""
    try:
        msg = Message(
            "Test Email from BizOwl Chatbot", 
            recipients=[os.environ.get('ADMIN_EMAIL', app.config['MAIL_USERNAME'])]
        )
        msg.body = "This is a test email from the BizOwl Flask application."
        mail.send(msg)
        return jsonify({'success': True, 'message': 'Test email sent successfully!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/save_contact', methods=['POST'])
def save_contact():
    """Save user contact information and send email notification"""
    contact_data = request.json
    chat_id = session.get('chat_id')
    
    if not chat_id:
        return jsonify({
            'success': False,
            'message': "Session error. Please refresh and try again."
        }), 400
    
    # Save to Firebase if possible
    if contact_data:
        save_contact_info(chat_id, contact_data)
        
        # Log the contact submission
        contact_msg = f"Contact information submitted: {contact_data.get('name', 'Unknown')} - {contact_data.get('email', 'No email')} - {contact_data.get('phone', 'No phone')}"
        save_message(chat_id, contact_msg, is_user=True)
        
        # Send email notification
        email_sent = send_contact_email(contact_data, chat_id)
        
        response_message = "Thank you! Our customer support team will contact you shortly."
        if not email_sent:
            response_message += " (Note: There was an issue with email notification, but your request has been saved.)"
        
        save_message(chat_id, response_message, is_user=False)
        
        return jsonify({
            'success': True,
            'message': response_message
        })
    
    return jsonify({
        'success': False,
        'message': "Invalid contact information provided."
    }), 400

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'firebase_connected': db is not None,
        'gemini_available': model is not None,
        'mail_configured': app.config.get('MAIL_USERNAME') is not None
    }), 200

@app.route('/reset', methods=['POST'])
def reset():
    """Reset chat session"""
    old_chat_id = session.get('chat_id')
    print(f"Resetting chat session. Old ID: {old_chat_id}")
    
    # Clear session
    session.pop('chat_id', None)
    
    # Create new chat session
    new_chat_id = create_chat_session()
    session['chat_id'] = new_chat_id
    
    print(f"New chat session created: {new_chat_id}")
    
    return jsonify({
        'success': True,
        'options': get_initial_menu_options(),
        'message': 'Chat session reset successfully'
    })

@app.route('/debug/chat_history')
def debug_chat_history():
    """Debug endpoint to view current chat history"""
    chat_id = session.get('chat_id')
    if not chat_id:
        return jsonify({'error': 'No active chat session'})
    
    history = get_chat_history(chat_id, max_messages=50)
    return jsonify({
        'chat_id': chat_id,
        'history': history,
        'memory_chats': list(chat_memory.keys()) if chat_memory else []
    })

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Flask app on port {port}")
    print(f"Firebase initialized: {db is not None}")
    print(f"Gemini model available: {model is not None}")
    print(f"Mail configured: {app.config.get('MAIL_USERNAME') is not None}")
    app.run(host='0.0.0.0', port=port, debug=True)