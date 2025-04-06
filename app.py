from flask import Flask, request, jsonify, render_template, session
import os
import google.generativeai as genai
from llama_index.llms.gemini import Gemini
from llama_index.core import VectorStoreIndex, Document
from llama_index.embeddings.gemini import GeminiEmbedding
from dotenv import load_dotenv
import json

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("Missing GEMINI_API_KEY in .env file")

genai.configure(api_key=GEMINI_API_KEY)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")  # Required for session management

embed_model = GeminiEmbedding(model_name="models/embedding-001")
llm = Gemini(model_name="models/gemini-1.5-flash")
index = None

# Specify your JSON file path here
JSON_FILE_PATH = "D:/kanika D/Bizzowl/data.json"

def extract_text_from_json(filepath):
    try:
        with open(filepath, 'r') as file:
            data = json.load(file)
            text = json.dumps(data, indent=4)
        return Document(text=text)
    except Exception as e:
        raise ValueError(f"Error processing JSON file: {str(e)}")

@app.route('/')
def home():
    global index
    try:
        if not os.path.exists(JSON_FILE_PATH):
            return render_template('index.html', error="JSON file not found at specified path")
        
        document = extract_text_from_json(JSON_FILE_PATH)
        index = VectorStoreIndex.from_documents([document], embed_model=embed_model)

        # Initialize session chat history
        if 'chat_history' not in session:
            session['chat_history'] = []

        return render_template('index.html', file_loaded=True, chat_history=session['chat_history'])
    except Exception as e:
        return render_template('index.html', error=str(e))

@app.route('/query', methods=['POST'])
def query():
    if not index:
        return jsonify({'error': 'JSON file could not be processed'}), 400
    
    query_text = request.json.get('query')
    if not query_text:
        return jsonify({'error': 'No query provided'}), 400

    try:
        # Retrieve query engine
        query_engine = index.as_query_engine(llm=llm)
        response = query_engine.query(query_text)

        # Generate tailored response considering chat history
        gemini_model = genai.GenerativeModel("models/gemini-1.5-flash")
        chat_history = session.get('chat_history', [])
        
        prompt = f"Previous conversation: {chat_history}\nUser asked: {query_text}\nContext from JSON: {response}\n"
        prompt += "If the user greets, Respond to greetings. Provide a clear and concise answer based on the JSON file. If the information is not available, respond appropriately.If the user seems frustrated or shows negative sentiment multiple times, reply with 'our customer support will contact you soon or you can contact customer support at : ' and provide contact details mentioned in the json file"

        gemini_response = gemini_model.generate_content(prompt).text

        # Update chat history
        chat_history.append({"user": query_text, "bot": gemini_response})
        session['chat_history'] = chat_history

        return jsonify({'response': gemini_response, 'chat_history': chat_history})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
