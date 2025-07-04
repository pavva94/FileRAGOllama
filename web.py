import streamlit as st
import requests
import json
import os
from typing import List, Dict, Optional
import time

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# Page configuration
st.set_page_config(
    page_title="RAG Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .section-header {
        font-size: 1.5rem;
        color: #2c3e50;
        margin-top: 2rem;
        margin-bottom: 1rem;
        border-bottom: 2px solid #3498db;
        padding-bottom: 0.5rem;
    }
    .upload-section {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .question-section {
        background-color: #e8f4f8;
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .success-message {
        color: #27ae60;
        font-weight: bold;
    }
    .error-message {
        color: #e74c3c;
        font-weight: bold;
    }
    .model-info {
        background-color: #fff3cd;
        padding: 1rem;
        border-radius: 5px;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)


# Helper functions
def get_api_health():
    """Check API health and get model information"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except requests.RequestException:
        return None


def get_available_models():
    """Get list of available Ollama models"""
    try:
        response = requests.get(f"{API_BASE_URL}/ollama/models", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("available_models", []), data.get("current_model", "")
        else:
            return [], ""
    except requests.RequestException:
        return [], ""


def upload_file(file, selected_model):
    """Upload file to the API"""
    try:
        files = {"file": (file.name, file, file.type)}
        response = requests.post(f"{API_BASE_URL}/upload", files=files, timeout=60)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Upload failed: {response.text}"}
    except requests.RequestException as e:
        return {"error": f"Upload failed: {str(e)}"}


def get_uploaded_files():
    """Get list of uploaded files"""
    try:
        response = requests.get(f"{API_BASE_URL}/files", timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            return []
    except requests.RequestException:
        return []


def delete_file(file_id):
    """Delete a file"""
    try:
        response = requests.delete(f"{API_BASE_URL}/files/{file_id}", timeout=10)
        return response.status_code == 200
    except requests.RequestException:
        return False


def ask_question(question, max_results=5):
    """Ask a question to the RAG system"""
    try:
        payload = {
            "question": question,
            "max_results": max_results
        }
        response = requests.post(
            f"{API_BASE_URL}/ask",
            json=payload,
            timeout=120
        )
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Question failed: {response.text}"}
    except requests.RequestException as e:
        return {"error": f"Question failed: {str(e)}"}


def pull_model(model_name):
    """Pull a model from Ollama"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/ollama/pull",
            params={"model_name": model_name},
            timeout=300
        )
        return response.status_code == 200
    except requests.RequestException:
        return False


# Initialize session state
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


# Main app
def main():
    # Header
    st.markdown('<h1 class="main-header">🤖 RAG Assistant</h1>', unsafe_allow_html=True)
    st.markdown("**Upload documents, ask questions, and get AI-powered answers!**")

    # Sidebar for system status and settings
    with st.sidebar:
        st.header("📊 System Status")

        # Check API health
        health_data = get_api_health()
        if health_data:
            if health_data.get("status") == "healthy":
                st.success("✅ API is healthy")
            else:
                st.warning("⚠️ API is degraded")

            st.info(f"**Ollama Status:** {health_data.get('ollama_status', 'Unknown')}")
            st.info(f"**Current Model:** {health_data.get('ollama_model', 'Unknown')}")
        else:
            st.error("❌ Cannot connect to API")
            st.stop()

        st.header("⚙️ Settings")
        max_results = st.slider("Max search results", 1, 10, 5)

        # Refresh button
        if st.button("🔄 Refresh Status"):
            st.rerun()

    # Main content area
    col1, col2 = st.columns([1, 1])

    with col1:
        # Model selection section
        st.markdown('<div class="section-header">🎯 Model Selection</div>', unsafe_allow_html=True)

        available_models, current_model = get_available_models()

        if available_models:
            model_names = [model["name"] for model in available_models]
            try:
                current_index = model_names.index(current_model) if current_model in model_names else 0
            except ValueError:
                current_index = 0

            selected_model = st.selectbox(
                "Choose a model:",
                options=model_names,
                index=current_index,
                help="Select the Ollama model to use for answering questions"
            )

            # Show model info
            selected_model_info = next((m for m in available_models if m["name"] == selected_model), None)
            if selected_model_info:
                st.markdown(f'<div class="model-info">', unsafe_allow_html=True)
                st.write(f"**Model:** {selected_model_info['name']}")
                if selected_model_info.get('size'):
                    st.write(f"**Size:** {selected_model_info['size'] / (1024 ** 3):.1f} GB")
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.error("No models available. Please ensure Ollama is running and has models installed.")

            # Option to pull llama3.2:latest
            st.subheader("📥 Pull Model")
            if st.button("Pull llama3.2:latest"):
                with st.spinner("Pulling model... This may take several minutes."):
                    if pull_model("llama3.2:latest"):
                        st.success("Model pulled successfully!")
                        st.rerun()
                    else:
                        st.error("Failed to pull model.")

        # File upload section
        st.markdown('<div class="section-header">📁 File Upload</div>', unsafe_allow_html=True)

        with st.container():
            st.markdown('<div class="upload-section">', unsafe_allow_html=True)

            uploaded_file = st.file_uploader(
                "Choose a file to upload",
                type=['txt', 'pdf', 'md', 'docx'],
                help="Upload documents to add to the knowledge base"
            )

            if uploaded_file is not None:
                if st.button("📤 Upload File"):
                    with st.spinner("Uploading and processing file..."):
                        result = upload_file(uploaded_file, selected_model if 'selected_model' in locals() else "")

                        if "error" in result:
                            st.error(result["error"])
                        else:
                            st.success(f"✅ File uploaded successfully!")
                            st.success(f"**File ID:** {result['file_id']}")
                            st.success(f"**Chunks created:** {result['chunk_count']}")
                            time.sleep(1)
                            st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)

        # Uploaded files management
        st.markdown('<div class="section-header">📋 Uploaded Files</div>', unsafe_allow_html=True)

        uploaded_files = get_uploaded_files()

        if uploaded_files:
            for file in uploaded_files:
                with st.expander(f"📄 {file['filename']}"):
                    st.write(f"**File ID:** {file['id']}")
                    st.write(f"**Upload Date:** {file['upload_date']}")
                    st.write(f"**Size:** {file['file_size']} bytes")
                    st.write(f"**Chunks:** {file['chunk_count']}")

                    if st.button(f"🗑️ Delete", key=f"delete_{file['id']}"):
                        if delete_file(file['id']):
                            st.success("File deleted successfully!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Failed to delete file.")
        else:
            st.info("No files uploaded yet.")

    with col2:
        # Question and answer section
        st.markdown('<div class="section-header">❓ Ask Questions</div>', unsafe_allow_html=True)

        with st.container():
            st.markdown('<div class="question-section">', unsafe_allow_html=True)

            # Question input
            question = st.text_area(
                "What would you like to know?",
                placeholder="Enter your question here...",
                height=100,
                help="Ask questions about your uploaded documents"
            )

            col_ask, col_clear = st.columns([3, 1])

            with col_ask:
                ask_button = st.button("🔍 Ask Question", type="primary")

            with col_clear:
                if st.button("🗑️ Clear Chat"):
                    st.session_state.chat_history = []
                    st.rerun()

            if ask_button and question.strip():
                if not uploaded_files:
                    st.warning("Please upload some documents first!")
                else:
                    with st.spinner("Searching for answers..."):
                        result = ask_question(question.strip(), max_results)

                        if "error" in result:
                            st.error(result["error"])
                        else:
                            # Add to chat history
                            st.session_state.chat_history.append({
                                "question": question.strip(),
                                "answer": result["answer"],
                                "sources": result["sources"]
                            })
                            st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)

        # Chat history
        if st.session_state.chat_history:
            st.markdown('<div class="section-header">💬 Chat History</div>', unsafe_allow_html=True)

            for i, chat in enumerate(reversed(st.session_state.chat_history)):
                with st.expander(
                        f"Q: {chat['question'][:50]}..." if len(chat['question']) > 50 else f"Q: {chat['question']}",
                        expanded=(i == 0)):
                    st.markdown(f"**Question:** {chat['question']}")
                    st.markdown(f"**Answer:** {chat['answer']}")

                    if chat['sources']:
                        st.markdown("**Sources:**")
                        for source in chat['sources']:
                            st.markdown(f"- 📄 {source}")
                    else:
                        st.markdown("**Sources:** No sources found")


if __name__ == "__main__":
    main()