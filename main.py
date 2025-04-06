import streamlit as st
import json

# Function to load JSON data from external files (only for services with FAQs)
def load_json_data(option):
    file_map = {
        "idea_validation": "idea_validation.json",
        "business_consultancy": "business_consultancy.json",
        "business_branding": "business_branding.json",
        "business_feasibility": "business_feasibility.json",
        "SWOT_analysis": "SWOT.json",
        "business_model_canvas": "business_model_canvas.json"
    }
    try:
        with open(file_map[option], "r") as f:
            return json.load(f)
    except FileNotFoundError:
        st.error(f"Error: {file_map[option]} not found.")
        return []
    except json.JSONDecodeError:
        st.error(f"Error: Invalid JSON format in {file_map[option]}.")
        return []

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

# Dummy filter function for Web Development
def display_filter():
    st.write("**Filter your web development project:**")
    type = st.selectbox("Website Type", ["E-commerce", "Portfolio", "Blog"], key="web_type")
    budget = st.slider("Budget ($)", 500, 10000, 1000, key="web_budget")
    if st.button("Apply Filter", key="web_filter"):
        st.write(f"Filtered: {type} website with ${budget} budget.")

# Main Streamlit app
def main():
    # Greeting message
    st.title("Welcome to BizOwl Chatbot")
    st.write("Hello! How can I assist you today?")

    # Initialize session state
    if 'level' not in st.session_state:
        st.session_state.level = "main"
    if 'selected_option' not in st.session_state:
        st.session_state.selected_option = None
    if 'selected_questions' not in st.session_state:
        st.session_state.selected_questions = []
    if 'answers' not in st.session_state:
        st.session_state.answers = []
    if 'faqs' not in st.session_state:
        st.session_state.faqs = []

    # Main menu
    if st.session_state.level == "main":
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Business Planning and Strategy"):
                st.session_state.level = "business_planning_and_strategy"
                st.rerun()
        with col2:
            if st.button("Web Development"):
                st.session_state.selected_option = "web_development"
                st.session_state.level = "service"
                st.rerun()

    # Business Planning and Strategy sub-menu
    elif st.session_state.level == "business_planning_and_strategy":
        st.write(default_messages["business_planning_and_strategy"])
        # Using two rows of 3 columns for better layout
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Business Consultancy"):
                st.session_state.selected_option = "business_consultancy"
                st.session_state.selected_questions = []
                st.session_state.answers = []
                st.session_state.faqs = load_json_data("business_consultancy")
                st.session_state.level = "service"
                st.rerun()
        with col2:
            if st.button("Idea Validation"):
                st.session_state.selected_option = "idea_validation"
                st.session_state.selected_questions = []
                st.session_state.answers = []
                st.session_state.faqs = load_json_data("idea_validation")
                st.session_state.level = "service"
                st.rerun()
        with col3:
            if st.button("Business Branding"):
                st.session_state.selected_option = "business_branding"
                st.session_state.selected_questions = []
                st.session_state.answers = []
                st.session_state.faqs = load_json_data("business_branding")
                st.session_state.level = "service"
                st.rerun()
        
        col4, col5, col6 = st.columns(3)
        with col4:
            if st.button("Business Feasibility"):
                st.session_state.selected_option = "business_feasibility"
                st.session_state.selected_questions = []
                st.session_state.answers = []
                st.session_state.faqs = load_json_data("business_feasibility")
                st.session_state.level = "service"
                st.rerun()
        with col5:
            if st.button("SWOT Analysis"):
                st.session_state.selected_option = "SWOT_analysis"  # Fixed key mismatch
                st.session_state.selected_questions = []
                st.session_state.answers = []
                st.session_state.faqs = load_json_data("SWOT_analysis")
                st.session_state.level = "service"
                st.rerun()
        with col6:
            if st.button("Business Model Canvas"):
                st.session_state.selected_option = "business_model_canvas"
                st.session_state.selected_questions = []
                st.session_state.answers = []
                st.session_state.faqs = load_json_data("business_model_canvas")
                st.session_state.level = "service"
                st.rerun()
        
        if st.button("Back to Main Menu"):
            st.session_state.level = "main"
            st.session_state.selected_option = None
            st.session_state.selected_questions = []
            st.session_state.answers = []
            st.session_state.faqs = []
            st.rerun()

    # Service level
    elif st.session_state.level == "service":
        st.write(default_messages[st.session_state.selected_option])
        
        # Handle services with FAQs
        if st.session_state.selected_option in [
            "business_consultancy", "idea_validation", "business_branding",
            "business_feasibility", "SWOT_analysis", "business_model_canvas"
        ]:
            faqs = st.session_state.faqs
            
            if st.session_state.answers:
                st.write("**Previous Questions and Answers:**")
                for answer in st.session_state.answers:
                    st.write(f"**Question:** {answer['question']}")
                    st.write(f"**Answer:** {answer['answer']}")
                    st.write("---")

            available_faqs = [faq for faq in faqs if faq["question"] not in st.session_state.selected_questions]
            
            if available_faqs:
                st.write("Choose a question:")
                for faq in available_faqs:
                    if st.button(faq["question"], key=faq["question"]):
                        st.session_state.selected_questions.append(faq["question"])
                        st.session_state.answers.append({"question": faq["question"], "answer": faq["answer"]})
                        st.rerun()
            else:
                st.write("No more questions available in this category.")
        
        # Handle Web Development with filter
        elif st.session_state.selected_option == "web_development":
            display_filter()

        # Option to go back to main menu
        if st.button("Back to Main Menu"):
            st.session_state.level = "main"
            st.session_state.selected_option = None
            st.session_state.selected_questions = []
            st.session_state.answers = []
            st.session_state.faqs = []
            st.rerun()

if __name__ == "__main__":
    main()