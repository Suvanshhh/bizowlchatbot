import os
import json
from datetime import datetime
from flask import Flask, request, render_template, jsonify, session
from flask_cors import CORS
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core.exceptions import DeadlineExceeded
from google.cloud.firestore_v1 import SERVER_TIMESTAMP
from dotenv import load_dotenv

app = Flask(__name__)
CORS(app, supports_credentials=True)
app.secret_key = os.environ.get('FLASK_SECRET', 'default-secret-key')

# --- Firebase Initialization ---
load_dotenv()
firebase_credentials_str = os.getenv("FIREBASE_CREDENTIALS_JSON")
if not firebase_credentials_str:
    print("❌ Firebase credentials not found in environment variables!")
    raise RuntimeError("Firebase credentials missing")
else:
    try:
        firebase_credentials_dict = json.loads(firebase_credentials_str)
        cred = credentials.Certificate(firebase_credentials_dict)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("✅ Firebase initialized successfully.")
    except json.JSONDecodeError as e:
        print(f"❌ Failed to decode Firebase credentials JSON: {e}")
        raise
    except Exception as e:
        print(f"❌ Error initializing Firebase: {e}")
        raise

# --- File paths for JSON data in Data folder ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.path.join(BASE_DIR, "Data")
file_map = {
    "general_faqs": os.path.join(DATA_FOLDER, "faqs.json"),
    "idea_validation": os.path.join(DATA_FOLDER, "idea_validation.json"),
    "business_consultancy": os.path.join(DATA_FOLDER, "business_consultancy.json"),
    "business_branding": os.path.join(DATA_FOLDER, "business_branding.json"),
    "business_feasibility": os.path.join(DATA_FOLDER, "business_feasibility.json"),
    "SWOT_analysis": os.path.join(DATA_FOLDER, "SWOT.json"),
    "business_model_canvas": os.path.join(DATA_FOLDER, "business_model_canvas.json"),
    "web_development": os.path.join(DATA_FOLDER, "web_development.json"),
    "logo_design": os.path.join(DATA_FOLDER, "logo_design.json"),
    "press_release": os.path.join(DATA_FOLDER, "press_release.json")
}

# Default messages for each service
default_messages = {
    "greeting": "Hello! Welcome to BizOwl Chatbot. How can I assist you today?",
    "general_faqs": "Explore our General FAQs to learn more about BizOwl.",
    "services": "Explore our services to see how we can help your business grow.",
    "business_planning_and_strategy": "Welcome to Business Planning and Strategy! Let’s build your business foundation.",
    "business_consultancy": "Welcome to Business Consultancy! Explore our FAQs to grow your business.",
    "idea_validation": "Welcome to Idea Validation! Let’s dive into assessing your business idea.",
    "business_branding": "Welcome to Business Branding! Discover FAQs to enhance your brand.",
    "business_feasibility": "Welcome to Business Feasibility! Explore FAQs to evaluate your business.",
    "SWOT_analysis": "Welcome to SWOT Analysis! Let’s analyze your business strengths and weaknesses.",
    "business_model_canvas": "Welcome to Business Model Canvas! FAQs to design your business model.",
    "web_development": "Building a professional website is crucial for any business. Explore our FAQs to learn more about our website development services.",
    "design": "Welcome to Design Services! Explore our design solutions to elevate your brand.",
    "logo_design": "Our Graphic Design Service connects users with professional designers who create high-quality visuals, including logos, banners, social media posts, and marketing materials.",
    "public_relations": "Welcome to Public Relations! Enhance your brand’s visibility with our PR services.",
    "press_release": "Press Release Distribution helps businesses publish and distribute their news to media outlets, journalists, and online platforms, increasing brand awareness and credibility."
}

# Buy Now links for each service
service_buy_links = {
    "business_consultancy": "https://www.bizzowl.com/services/business-consultancy-service",
    "idea_validation": "https://www.bizzowl.com/services/startup-idea-validation-service",
    "business_branding": "https://www.bizzowl.com/services/business-branding-strategy-service",
    "business_feasibility": "https://bizont.com/buy/business-feasibility",
    "SWOT_analysis": "https://www.bizzowl.com/services/swot-analysis-of-a-business",
    "business_model_canvas": "https://www.bizzowl.com/services/business-model-canvas",
    "web_development": "https://www.bizzowl.com/service/web-development-distribution",
    "logo_design": "https://www.bizzowl.com/services/logo-design-distribution/quote-details",
    "press_release": "https://www.bizzowl.com/services/press-release-distribution"
}

# Load JSON data for FAQs
def load_json_data(option):
    try:
        with open(file_map[option], "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"error": f"Error: {file_map[option]} not found."}
    except json.JSONDecodeError:
        return {"error": f"Error: Invalid JSON format in {file_map[option]}."}

# Load company data for Gemini API
try:
    with open(os.path.join(DATA_FOLDER, 'data.json'), 'r') as f:
        company_data = json.load(f)
    print("✅ Company data loaded successfully.")
except Exception as e:
    print(f"❌ Error loading company data: {e}")
    raise

# --- Configure Gemini ---
api_key = os.environ.get('GEMINI_API_KEY')
if not api_key:
    print("❌ Gemini API key not found in environment variables.")
    model = None
else:
    print("✅ API key found.")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.0-pro')
    print("✅ Generated model successfully.")

# --- Firebase Helper Functions ---
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

# --- Gemini Prompt Creation ---
def create_gemini_prompt(user_query):
    prompt = f"""
You are a customer support AI assistant for a company. You must ONLY answer questions using the information provided below. Do not make up or infer information that is not explicitly stated in the provided data.

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

# --- Routes ---
@app.route('/')
def index():
    print("Route / called")
    if 'chat_id' not in session:
        print("No chat_id in session, creating...")
        chat_id = create_chat_session()
        print(f"Created chat_id: {chat_id}")
        if not chat_id:
            print("Failed to create chat session. Proceeding without chat_id.")
        session['chat_id'] = chat_id
    # Initialize session state for menu
    session['level'] = "greeting"
    session['selected_option'] = None
    session['selected_questions'] = []
    session['answers'] = []
    session['faqs'] = []
    
    menu_options = [
        {"id": "general_faqs", "text": "General FAQs"},
        {"id": "services", "text": "Services"}
    ]
    save_message(session.get('chat_id'), default_messages["greeting"], is_user=False)
    return render_template('index1.html', menu_options=menu_options, message=default_messages["greeting"])

@app.route('/get_menu_options', methods=['POST'])
def get_menu_options():
    """Handle menu navigation based on user selection."""
    data = request.json
    selected_option = data.get('option')
    current_path = data.get('path', [])

    save_message(session.get('chat_id'), selected_option, is_user=True)

    if session['level'] == "greeting":
        if selected_option == "general_faqs":
            session['level'] = "faq"
            session['selected_option'] = selected_option
            session['faqs'] = load_json_data("general_faqs")
            if "error" in session['faqs']:
                bot_response = session['faqs']["error"]
                save_message(session.get('chat_id'), bot_response, is_user=False)
                return jsonify({
                    "options": [{"id": "back", "text": "Back to Main Menu"}],
                    "bot_response": bot_response,
                    "path": current_path + [selected_option]
                })
            available_faqs = [faq for faq in session['faqs'] if faq["question"] not in session['selected_questions']]
            options = [{"id": faq["question"], "text": faq["question"]} for faq in available_faqs]
            options.append({"id": "back", "text": "Back to Main Menu"})
            bot_response = default_messages["general_faqs"]
            save_message(session.get('chat_id'), bot_response, is_user=False)
            return jsonify({
                "options": options,
                "bot_response": bot_response,
                "path": current_path + [selected_option]
            })
        elif selected_option == "services":
            session['level'] = "main"
            menu_options = [
                {"id": "business_planning_and_strategy", "text": "Business Planning and Strategy"},
                {"id": "web_development", "text": "Web Development"},
                {"id": "design", "text": "Design"},
                {"id": "public_relations", "text": "Public Relations"},
                {"id": "back", "text": "Back to Main Menu"}
            ]
            bot_response = default_messages["services"]
            save_message(session.get('chat_id'), bot_response, is_user=False)
            return jsonify({
                "options": menu_options,
                "bot_response": bot_response,
                "path": current_path + [selected_option]
            })

    elif session['level'] == "main":
        if selected_option == "back":
            session['level'] = "greeting"
            menu_options = [
                {"id": "general_faqs", "text": "General FAQs"},
                {"id": "services", "text": "Services"}
            ]
            bot_response = default_messages["greeting"]
            save_message(session.get('chat_id'), bot_response, is_user=False)
            return jsonify({
                "options": menu_options,
                "bot_response": bot_response,
                "path": []
            })
        elif selected_option == "business_planning_and_strategy":
            session['level'] = "business_planning_and_strategy"
            menu_options = [
                {"id": "business_consultancy", "text": "Business Consultancy"},
                {"id": "idea_validation", "text": "Idea Validation"},
                {"id": "business_branding", "text": "Business Branding"},
                {"id": "business_feasibility", "text": "Business Feasibility"},
                {"id": "SWOT_analysis", "text": "SWOT Analysis"},
                {"id": "business_model_canvas", "text": "Business Model Canvas"},
                {"id": "back", "text": "Back to Services"}
            ]
            bot_response = default_messages["business_planning_and_strategy"]
            save_message(session.get('chat_id'), bot_response, is_user=False)
            return jsonify({
                "options": menu_options,
                "bot_response": bot_response,
                "path": current_path + [selected_option]
            })
        elif selected_option == "web_development":
            session['level'] = "faq"
            session['selected_option'] = selected_option
            session['faqs'] = load_json_data(selected_option)
            if "error" in session['faqs']:
                bot_response = session['faqs']["error"]
                save_message(session.get('chat_id'), bot_response, is_user=False)
                return jsonify({
                    "options": [{"id": "back", "text": "Back to Services"}],
                    "bot_response": bot_response,
                    "path": current_path + [selected_option]
                })
            available_faqs = [faq for faq in session['faqs'] if faq["question"] not in session['selected_questions']]
            options = [{"id": faq["question"], "text": faq["question"]} for faq in available_faqs]
            options.append({"id": "buy_now", "text": "Buy Now"})
            options.append({"id": "back", "text": "Back to Services"})
            bot_response = default_messages["web_development"]
            save_message(session.get('chat_id'), bot_response, is_user=False)
            return jsonify({
                "options": options,
                "bot_response": bot_response,
                "path": current_path + [selected_option]
            })
        elif selected_option == "design":
            session['level'] = "design"
            menu_options = [
                {"id": "logo_design", "text": "Logo Design"},
                {"id": "back", "text": "Back to Services"}
            ]
            bot_response = default_messages["design"]
            save_message(session.get('chat_id'), bot_response, is_user=False)
            return jsonify({
                "options": menu_options,
                "bot_response": bot_response,
                "path": current_path + [selected_option]
            })
        elif selected_option == "public_relations":
            session['level'] = "public_relations"
            menu_options = [
                {"id": "press_release", "text": "Press Release"},
                {"id": "back", "text": "Back to Services"}
            ]
            bot_response = default_messages["public_relations"]
            save_message(session.get('chat_id'), bot_response, is_user=False)
            return jsonify({
                "options": menu_options,
                "bot_response": bot_response,
                "path": current_path + [selected_option]
            })

    elif session['level'] == "business_planning_and_strategy":
        if selected_option == "back":
            session['level'] = "main"
            menu_options = [
                {"id": "business_planning_and_strategy", "text": "Business Planning and Strategy"},
                {"id": "web_development", "text": "Web Development"},
                {"id": "design", "text": "Design"},
                {"id": "public_relations", "text": "Public Relations"},
                {"id": "back", "text": "Back to Main Menu"}
            ]
            bot_response = default_messages["services"]
            save_message(session.get('chat_id'), bot_response, is_user=False)
            return jsonify({
                "options": menu_options,
                "bot_response": bot_response,
                "path": current_path[:-1]
            })
        elif selected_option in file_map:
            session['level'] = "faq"
            session['selected_option'] = selected_option
            session['faqs'] = load_json_data(selected_option)
            if "error" in session['faqs']:
                bot_response = session['faqs']["error"]
                save_message(session.get('chat_id'), bot_response, is_user=False)
                return jsonify({
                    "options": [{"id": "back", "text": "Back to Services"}],
                    "bot_response": bot_response,
                    "path": current_path + [selected_option]
                })
            available_faqs = [faq for faq in session['faqs'] if faq["question"] not in session['selected_questions']]
            options = [{"id": faq["question"], "text": faq["question"]} for faq in available_faqs]
            options.append({"id": "buy_now", "text": "Buy Now"})
            options.append({"id": "back", "text": "Back to Services"})
            bot_response = default_messages[selected_option]
            save_message(session.get('chat_id'), bot_response, is_user=False)
            return jsonify({
                "options": options,
                "bot_response": bot_response,
                "path": current_path + [selected_option]
            })

    elif session['level'] == "design":
        if selected_option == "back":
            session['level'] = "main"
            menu_options = [
                {"id": "business_planning_and_strategy", "text": "Business Planning and Strategy"},
                {"id": "web_development", "text": "Web Development"},
                {"id": "design", "text": "Design"},
                {"id": "public_relations", "text": "Public Relations"},
                {"id": "back", "text": "Back to Main Menu"}
            ]
            bot_response = default_messages["services"]
            save_message(session.get('chat_id'), bot_response, is_user=False)
            return jsonify({
                "options": menu_options,
                "bot_response": bot_response,
                "path": current_path[:-1]
            })
        elif selected_option == "logo_design":
            session['level'] = "faq"
            session['selected_option'] = selected_option
            session['faqs'] = load_json_data(selected_option)
            if "error" in session['faqs']:
                bot_response = session['faqs']["error"]
                save_message(session.get('chat_id'), bot_response, is_user=False)
                return jsonify({
                    "options": [{"id": "back", "text": "Back to Services"}],
                    "bot_response": bot_response,
                    "path": current_path + [selected_option]
                })
            available_faqs = [faq for faq in session['faqs'] if faq["question"] not in session['selected_questions']]
            options = [{"id": faq["question"], "text": faq["question"]} for faq in available_faqs]
            options.append({"id": "buy_now", "text": "Buy Now"})
            options.append({"id": "back", "text": "Back to Services"})
            bot_response = default_messages["logo_design"]
            save_message(session.get('chat_id'), bot_response, is_user=False)
            return jsonify({
                "options": options,
                "bot_response": bot_response,
                "path": current_path + [selected_option]
            })

    elif session['level'] == "public_relations":
        if selected_option == "back":
            session['level'] = "main"
            menu_options = [
                {"id": "business_planning_and_strategy", "text": "Business Planning and Strategy"},
                {"id": "web_development", "text": "Web Development"},
                {"id": "design", "text": "Design"},
                {"id": "public_relations", "text": "Public Relations"},
                {"id": "back", "text": "Back to Main Menu"}
            ]
            bot_response = default_messages["services"]
            save_message(session.get('chat_id'), bot_response, is_user=False)
            return jsonify({
                "options": menu_options,
                "bot_response": bot_response,
                "path": current_path[:-1]
            })
        elif selected_option == "press_release":
            session['level'] = "faq"
            session['selected_option'] = selected_option
            session['faqs'] = load_json_data(selected_option)
            if "error" in session['faqs']:
                bot_response = session['faqs']["error"]
                save_message(session.get('chat_id'), bot_response, is_user=False)
                return jsonify({
                    "options": [{"id": "back", "text": "Back to Services"}],
                    "bot_response": bot_response,
                    "path": current_path + [selected_option]
                })
            available_faqs = [faq for faq in session['faqs'] if faq["question"] not in session['selected_questions']]
            options = [{"id": faq["question"], "text": faq["question"]} for faq in available_faqs]
            options.append({"id": "buy_now", "text": "Buy Now"})
            options.append({"id": "back", "text": "Back to Services"})
            bot_response = default_messages["press_release"]
            save_message(session.get('chat_id'), bot_response, is_user=False)
            return jsonify({
                "options": options,
                "bot_response": bot_response,
                "path": current_path + [selected_option]
            })

    elif session['level'] == "faq":
        if selected_option == "back":
            if session['selected_option'] == "general_faqs":
                session['level'] = "greeting"
                menu_options = [
                    {"id": "general_faqs", "text": "General FAQs"},
                    {"id": "services", "text": "Services"}
                ]
                bot_response = default_messages["greeting"]
            elif session['selected_option'] == "web_development":
                session['level'] = "main"
                menu_options = [
                    {"id": "business_planning_and_strategy", "text": "Business Planning and Strategy"},
                    {"id": "web_development", "text": "Web Development"},
                    {"id": "design", "text": "Design"},
                    {"id": "public_relations", "text": "Public Relations"},
                    {"id": "back", "text": "Back to Main Menu"}
                ]
                bot_response = default_messages["services"]
            elif session['selected_option'] == "logo_design":
                session['level'] = "design"
                menu_options = [
                    {"id": "logo_design", "text": "Logo Design"},
                    {"id": "back", "text": "Back to Services"}
                ]
                bot_response = default_messages["design"]
            elif session['selected_option'] == "press_release":
                session['level'] = "public_relations"
                menu_options = [
                    {"id": "press_release", "text": "Press Release"},
                    {"id": "back", "text": "Back to Services"}
                ]
                bot_response = default_messages["public_relations"]
            else:
                session['level'] = "business_planning_and_strategy"
                menu_options = [
                    {"id": "business_consultancy", "text": "Business Consultancy"},
                    {"id": "idea_validation", "text": "Idea Validation"},
                    {"id": "business_branding", "text": "Business Branding"},
                    {"id": "business_feasibility", "text": "Business Feasibility"},
                    {"id": "SWOT_analysis", "text": "SWOT Analysis"},
                    {"id": "business_model_canvas", "text": "Business Model Canvas"},
                    {"id": "back", "text": "Back to Services"}
                ]
                bot_response = default_messages["business_planning_and_strategy"]
            save_message(session.get('chat_id'), bot_response, is_user=False)
            return jsonify({
                "options": menu_options,
                "bot_response": bot_response,
                "path": [] if session['level'] == "greeting" else current_path[:-1]
            })
        elif selected_option == "buy_now" and session['selected_option'] in service_buy_links:
            redirect_url = service_buy_links[session['selected_option']]
            bot_response = f"Redirecting to purchase {session['selected_option']}..."
            save_message(session.get('chat_id'), bot_response, is_user=False)
            return jsonify({
                "options": [],
                "bot_response": bot_response,
                "path": current_path,
                "redirect_url": redirect_url
            })
        else:
            faq = next((f for f in session['faqs'] if f["question"] == selected_option), None)
            if faq:
                session['selected_questions'].append(faq["question"])
                session['answers'].append({"question": faq["question"], "answer": faq["answer"]})
                available_faqs = [f for f in session['faqs'] if f["question"] not in session['selected_questions']]
                options = [{"id": f["question"], "text": f["question"]} for f in available_faqs]
                if session['selected_option'] in service_buy_links:
                    options.append({"id": "buy_now", "text": "Buy Now"})
                options.append({"id": "back", "text": "Back to Main Menu" if session['selected_option'] == "general_faqs" else "Back to Services"})
                bot_response = faq["answer"]
                if not available_faqs:
                    bot_response += "\nNo more questions available in this category."
                save_message(session.get('chat_id'), bot_response, is_user=False)
                return jsonify({
                    "options": options,
                    "bot_response": bot_response,
                    "path": current_path
                })

    bot_response = "Something went wrong."
    save_message(session.get('chat_id'), bot_response, is_user=False)
    return jsonify({"options": [], "bot_response": bot_response, "path": current_path})

@app.route('/process_custom_input', methods=['POST'])
def process_custom_input():
    user_input = request.json.get('input', '')

    save_message(session.get('chat_id'), user_input, is_user=True)

    response_text = "I apologize, but our system is experiencing technical difficulties."
    if model:
        try:
            prompt = create_gemini_prompt(user_input)
            print("\n🔹 Prompt sent to Gemini:\n", prompt)
            response_obj = model.generate_content(prompt)
            print("\n🔸 Gemini Response Object:\n", response_obj)
            response_text = response_obj.text
        except Exception as e:
            print("❌ Error in Gemini API call:", e)

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
    session['level'] = "greeting"
    session['selected_option'] = None
    session['selected_questions'] = []
    session['answers'] = []
    session['faqs'] = []
    menu_options = [
        {"id": "general_faqs", "text": "General FAQs"},
        {"id": "services", "text": "Services"}
    ]
    bot_response = default_messages["greeting"]
    save_message(session.get('chat_id'), bot_response, is_user=False)
    return jsonify({'options': menu_options, 'bot_response': bot_response, 'path': []})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)