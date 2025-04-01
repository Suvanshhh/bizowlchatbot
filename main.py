import os
import json
from flask import Flask, request, render_template, jsonify
import google.generativeai as genai

app = Flask(__name__)

#menu data
with open('temp_data.json', 'r') as f:
    menu_data = json.load(f)

#bizzowl info
with open('data.json', 'r') as f:
    company_data = json.load(f)

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
        for step in path:
            current = current.get('options', {}).get(step, {})

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
    """Process custom user input using Gemini API and company data."""
    user_input = request.json.get('input', '')
    
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
    initial_options = get_initial_menu_options()
    return jsonify({'options': initial_options})

if __name__ == '__main__':
    app.run(debug=True)