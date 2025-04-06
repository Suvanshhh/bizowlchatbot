import os
import json
from flask import Flask, request, render_template, jsonify
import google.generativeai as genai

app = Flask(__name__)

# File paths for JSON data in Data folder
DATA_FOLDER = "Data"
file_map = {
    "idea_validation": os.path.join(DATA_FOLDER, "idea_validation.json"),
    "business_consultancy": os.path.join(DATA_FOLDER, "business_consultancy.json"),
    "business_branding": os.path.join(DATA_FOLDER, "business_branding.json"),
    "business_feasibility": os.path.join(DATA_FOLDER, "business_feasibility.json"),
    "SWOT_analysis": os.path.join(DATA_FOLDER, "SWOT.json"),
    "business_model_canvas": os.path.join(DATA_FOLDER, "business_model_canvas.json")
}

# Default messages for each service
default_messages = {
    "business_planning_and_strategy": "Welcome to Business Planning and Strategy! Let’s build your business foundation.",
    "business_consultancy": "Welcome to Business Consultancy! Explore our FAQs to grow your business.",
    "idea_validation": "Welcome to Idea Validation! Let’s dive into assessing your business idea.",
    "business_branding": "Welcome to Business Branding! Discover FAQs to enhance your brand.",
    "business_feasibility": "Welcome to Business Feasibility! Explore FAQs to evaluate your business.",
    "SWOT_analysis": "Welcome to SWOT Analysis! Let’s analyze your business strengths and weaknesses.",
    "business_model_canvas": "Welcome to Business Model Canvas! FAQs to design your business model.",
    "web_development": "Welcome to Web Development! Filter your project requirements below."
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
with open(os.path.join(DATA_FOLDER, 'data.json'), 'r') as f:
    company_data = json.load(f)

# Configure Gemini API
api_key = os.environ.get('GEMINI_API_KEY')
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-1.5-flash')

def create_gemini_prompt(user_query):
    """
    Create a prompt for Gemini that instructs it to only answer questions
    based on the provided company data.
    """
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

# Simulate session state using a simple dictionary (in a real app, use Flask-Session or a database)
session_state = {
    "level": "main",
    "selected_option": None,
    "selected_questions": [],
    "answers": [],
    "faqs": []
}

@app.route('/')
def index():
    """Render the main chat interface."""
    session_state["level"] = "main"
    session_state["selected_option"] = None
    session_state["selected_questions"] = []
    session_state["answers"] = []
    session_state["faqs"] = []
    
    menu_options = [
        {"id": "business_planning_and_strategy", "text": "Business Planning and Strategy"},
        {"id": "web_development", "text": "Web Development"}
    ]
    return render_template('index1.html', menu_options=menu_options, message="Hello! How can I assist you today?")

@app.route('/get_menu_options', methods=['POST'])
def get_menu_options():
    """Handle menu navigation based on user selection."""
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
            return jsonify({
                "options": menu_options,
                "bot_response": default_messages["business_planning_and_strategy"],
                "path": current_path + [selected_option]
            })
        elif selected_option == "web_development":
            session_state["level"] = "service"
            session_state["selected_option"] = "web_development"
            return jsonify({
                "options": [{"id": "back", "text": "Back to Main Menu"}],
                "bot_response": default_messages["web_development"] + " (Use /filter to set preferences)",
                "path": current_path + [selected_option]
            })

    elif session_state["level"] == "business_planning_and_strategy":
        if selected_option == "back":
            session_state["level"] = "main"
            menu_options = [
                {"id": "business_planning_and_strategy", "text": "Business Planning and Strategy"},
                {"id": "web_development", "text": "Web Development"}
            ]
            return jsonify({
                "options": menu_options,
                "bot_response": "Hello! How can I assist you today?",
                "path": []
            })
        elif selected_option in file_map:
            session_state["level"] = "service"
            session_state["selected_option"] = selected_option
            session_state["faqs"] = load_json_data(selected_option)
            if "error" in session_state["faqs"]:
                return jsonify({
                    "options": [{"id": "back", "text": "Back to Main Menu"}],
                    "bot_response": session_state["faqs"]["error"],
                    "path": current_path + [selected_option]
                })
            available_faqs = [faq for faq in session_state["faqs"] if faq["question"] not in session_state["selected_questions"]]
            options = [{"id": faq["question"], "text": faq["question"]} for faq in available_faqs]
            options.append({"id": "back", "text": "Back to Main Menu"})
            return jsonify({
                "options": options,
                "bot_response": default_messages[selected_option],
                "path": current_path + [selected_option]
            })

    elif session_state["level"] == "service":
        if selected_option == "back":
            if session_state["selected_option"] == "web_development":
                session_state["level"] = "main"
                menu_options = [
                    {"id": "business_planning_and_strategy", "text": "Business Planning and Strategy"},
                    {"id": "web_development", "text": "Web Development"}
                ]
                return jsonify({
                    "options": menu_options,
                    "bot_response": "Hello! How can I assist you today?",
                    "path": []
                })
            else:
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
                return jsonify({
                    "options": menu_options,
                    "bot_response": default_messages["business_planning_and_strategy"],
                    "path": current_path[:-1]
                })
        elif session_state["selected_option"] != "web_development":
            faq = next((f for f in session_state["faqs"] if f["question"] == selected_option), None)
            if faq:
                session_state["selected_questions"].append(faq["question"])
                session_state["answers"].append({"question": faq["question"], "answer": f["answer"]})
                available_faqs = [f for f in session_state["faqs"] if f["question"] not in session_state["selected_questions"]]
                options = [{"id": f["question"], "text": f["question"]} for f in available_faqs]
                options.append({"id": "back", "text": "Back to Main Menu"})
                response = f"**Question:** {faq['question']}\n**Answer:** {faq['answer']}"
                if not available_faqs:
                    response += "\nNo more questions available in this category."
                return jsonify({
                    "options": options,
                    "bot_response": response,
                    "path": current_path
                })

    return jsonify({"options": [], "bot_response": "Something went wrong.", "path": current_path})

@app.route('/process_custom_input', methods=['POST'])
def process_custom_input():
    """Process custom user input using Gemini API and company data."""
    user_input = request.json.get('input', '')
    
    # Handle web development filter
    if session_state["selected_option"] == "web_development" and user_input.startswith("/filter"):
        try:
            _, type_budget = user_input.split(" ", 1)
            website_type, budget = type_budget.split(" $")
            response = f"Filtered: {website_type} website with ${budget} budget."
        except ValueError:
            response = "Please use format: /filter [type] $[budget] (e.g., /filter E-commerce $1000)"
        return jsonify({"response": response})
    
    # Use Gemini API for other inputs
    try:
        prompt = create_gemini_prompt(user_input)
        gemini_response = model.generate_content(prompt)
        response = gemini_response.text
    except Exception as e:
        response = "I apologize, but our system is experiencing technical difficulties. Our customer support team will contact you soon."
    
    return jsonify({'response': response})

@app.route('/save_contact', methods=['POST'])
def save_contact():
    """Save customer contact information for follow-up."""
    contact_info = request.json
    
    return jsonify({
        'success': True,
        'message': "Thank you! Our customer support team will contact you shortly."
    })

@app.route('/reset', methods=['POST'])
def reset():
    """Reset the conversation to the initial state."""
    session_state["level"] = "main"
    session_state["selected_option"] = None
    session_state["selected_questions"] = []
    session_state["answers"] = []
    session_state["faqs"] = []
    menu_options = [
        {"id": "business_planning_and_strategy", "text": "Business Planning and Strategy"},
        {"id": "web_development", "text": "Web Development"}
    ]
    return jsonify({'options': menu_options, 'bot_response': "Hello! How can I assist you today?", "path": []})

if __name__ == '__main__':
    app.run(debug=True)