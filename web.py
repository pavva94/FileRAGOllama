import streamlit as st
import requests
import json
from datetime import datetime
import os
from pathlib import Path
import time

# Configuration - Updated for Docker
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# Page configuration
st.set_page_config(
    page_title="Simple RAG System",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 2rem 0;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        margin: -1rem -1rem 2rem -1rem;
        border-radius: 0 0 10px 10px;
    }

    .stAlert {
        margin-top: 1rem;
    }

    .file-info {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
    }

    .answer-container {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #667eea;
        margin: 1rem 0;
    }

    .source-tag {
        background-color: #e3f2fd;
        padding: 0.25rem 0.5rem;
        border-radius: 15px;
        font-size: 0.8rem;
        margin: 0.2rem;
        display: inline-block;
    }

    .confidence-score {
        font-weight: bold;
        color: #4caf50;
    }

    .model-status {
        padding: 0.5rem;
        border-radius: 5px;
        text-align: center;
        font-weight: bold;
    }

    .model-running {
        background-color: #d4edda;
        color: #155724;
    }

    .model-not-running {
        background-color: #f8d7da;
        color: #721c24;
    }

    .docker-info {
        background-color: #e3f2fd;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 4px solid #2196f3;
    }

    .chat-container {
        background-color: #ffffff;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
        border: 1px solid #e0e0e0;
    }
</style>
""", unsafe_allow_html=True)


# Helper functions
def check_api_connection():
    """Check if API is accessible"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        return response.status_code == 200, response.json() if response.status_code == 200 else None
    except requests.RequestException as e:
        return False, str(e)


def upload_file_to_api(file_content, filename):
    """Upload file to API"""
    try:
        files = {"file": (filename, file_content, "application/octet-stream")}
        response = requests.post(f"{API_BASE_URL}/upload", files=files, timeout=120)

        if response.status_code == 200:
            return True, response.json()
        else:
            return False, response.json().get("detail", "Unknown error")
    except requests.RequestException as e:
        return False, f"Connection error: {str(e)}"


def get_files_from_api():
    """Get files from API"""
    try:
        response = requests.get(f"{API_BASE_URL}/files", timeout=15)
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, response.json().get("detail", "Unknown error")
    except requests.RequestException as e:
        return False, f"Connection error: {str(e)}"


def delete_file_from_api(file_id):
    """Delete file from API"""
    try:
        response = requests.delete(f"{API_BASE_URL}/files/{file_id}", timeout=15)
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, response.json().get("detail", "Unknown error")
    except requests.RequestException as e:
        return False, f"Connection error: {str(e)}"


def ask_question_to_api(question, max_results=5):
    """Ask question to API"""
    try:
        data = {
            "question": question,
            "max_results": max_results
        }
        response = requests.post(f"{API_BASE_URL}/ask", json=data, timeout=60)

        if response.status_code == 200:
            return True, response.json()
        else:
            return False, response.json().get("detail", "Unknown error")
    except requests.RequestException as e:
        return False, f"Connection error: {str(e)}"


def get_ollama_models():
    """Get available Ollama models"""
    try:
        response = requests.get(f"{API_BASE_URL}/ollama/models", timeout=15)
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, response.json().get("detail", "Unknown error")
    except requests.RequestException as e:
        return False, f"Connection error: {str(e)}"


def pull_ollama_model(model_name):
    """Pull Ollama model"""
    try:
        response = requests.post(f"{API_BASE_URL}/ollama/pull", params={"model_name": model_name}, timeout=600)
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, response.json().get("detail", "Unknown error")
    except requests.RequestException as e:
        return False, f"Connection error: {str(e)}"


def format_file_size(size_bytes):
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024
        i += 1

    return f"{size_bytes:.1f} {size_names[i]}"


# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Main header
st.markdown('<div class="main-header"><h1>🧠 Simple RAG System</h1><p>Upload documents and ask questions</p></div>',
            unsafe_allow_html=True)

# Docker info
st.markdown(f"""
<div class="docker-info">
    <h4>🐳 Docker Environment</h4>
    <p><strong>API Endpoint:</strong> {API_BASE_URL}</p>
    <p><strong>Environment:</strong> {"Docker Container" if API_BASE_URL != "http://localhost:8000" else "Local Development"}</p>
</div>
""", unsafe_allow_html=True)

# Check API connection
api_connected, health_info = check_api_connection()

if not api_connected:
    st.error(f"❌ Cannot connect to the API server at {API_BASE_URL}")
    st.error(f"Error details: {health_info}")
    st.info("Make sure all Docker containers are running: `docker-compose ps`")
    st.stop()

# Sidebar
with st.sidebar:
    st.header("📊 System Status")
    st.success("✅ API Connected")

    # Container status
    st.info("🐳 Running in Docker")

    # Ollama Status
    if health_info:
        ollama_status = health_info.get("ollama_status", "unknown")
        if ollama_status == "running":
            st.markdown('<div class="model-status model-running">🤖 Ollama: Running</div>', unsafe_allow_html=True)
            st.write(f"**Current Model:** {health_info.get('ollama_model', 'Unknown')}")
        else:
            st.markdown('<div class="model-status model-not-running">🤖 Ollama: Not Running</div>',
                        unsafe_allow_html=True)
            st.info("Ollama is not running. The system will use basic responses without AI enhancement.")

    st.divider()

    # Ollama Management
    st.header("🤖 Ollama Management")

    # Docker command helper
    st.info("💡 To pull models via Docker:\n`docker exec rag-ollama ollama pull llama3.2`")

    # Get available models
    models_success, models_data = get_ollama_models()

    if models_success and models_data.get("available_models"):
        st.subheader("Available Models")
        for model in models_data["available_models"]:
            st.write(f"• {model['name']} ({format_file_size(model['size'])})")

    # Model pulling
    st.subheader("Pull New Model")
    model_to_pull = st.text_input("Model name (e.g., llama3.2:latest)", key="model_pull")

    if st.button("Pull Model", key="pull_model_btn"):
        if model_to_pull:
            with st.spinner(f"Pulling {model_to_pull}... This may take several minutes."):
                success, result = pull_ollama_model(model_to_pull)
                if success:
                    st.success(f"✅ Model {model_to_pull} pulled successfully!")
                    st.rerun()
                else:
                    st.error(f"❌ Failed to pull model: {result}")
        else:
            st.warning("Please enter a model name")

    st.divider()

    # File management in sidebar
    st.header("📁 Document Management")

    # File upload section
    st.subheader("Upload New Document")
    uploaded_file = st.file_uploader(
        "Choose a file",
        type=['txt', 'pdf', 'md', 'docx'],
        help="Supported formats: TXT, PDF, MD, DOCX"
    )

    if uploaded_file is not None:
        file_details = {
            "filename": uploaded_file.name,
            "size": uploaded_file.size,
            "type": uploaded_file.type
        }

        st.write("**File Details:**")
        st.json(file_details)

        if st.button("Upload Document", key="upload_btn"):
            with st.spinner("Uploading and processing document..."):
                success, result = upload_file_to_api(uploaded_file.read(), uploaded_file.name)

                if success:
                    st.success(f"✅ Document uploaded successfully!")
                    st.write(f"**File ID:** {result['file_id']}")
                    st.write(f"**Chunks created:** {result['chunk_count']}")
                    st.write(f"**File size:** {format_file_size(result['file_size'])}")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"❌ Upload failed: {result}")

    st.divider()

    # File list section
    st.subheader("📚 Uploaded Documents")

    if st.button("🔄 Refresh List", key="refresh_btn"):
        st.rerun()

    files_success, files_data = get_files_from_api()

    if files_success and files_data:
        for file_info in files_data:
            with st.expander(f"📄 {file_info['filename']}", expanded=False):
                st.write(f"**File ID:** {file_info['id']}")
                st.write(f"**Size:** {format_file_size(file_info['file_size'])}")
                st.write(f"**Upload Date:** {file_info['upload_date']}")
                st.write(f"**Chunks:** {file_info['chunk_count']}")

                if st.button(f"🗑️ Delete", key=f"delete_{file_info['id']}", type="secondary"):
                    if st.session_state.get(f"confirm_delete_{file_info['id']}", False):
                        with st.spinner("Deleting file..."):
                            success, result = delete_file_from_api(file_info['id'])
                            if success:
                                st.success("✅ File deleted successfully!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(f"❌ Delete failed: {result}")
                    else:
                        st.session_state[f"confirm_delete_{file_info['id']}"] = True
                        st.warning("⚠️ Click delete again to confirm")

    elif files_success:
        st.info("📭 No documents uploaded yet")
    else:
        st.error(f"❌ Error loading files: {files_data}")

# Main content area - Chat Interface
st.header("💬 Chat with Your Documents")

# Chat display area
chat_container = st.container()

with chat_container:
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if message["role"] == "assistant" and "sources" in message:
                if message["sources"]:
                    st.write("**Sources:**")
                    for source in message["sources"]:
                        st.markdown(f'<span class="source-tag">📄 {source}</span>', unsafe_allow_html=True)
                if "confidence" in message:
                    st.markdown(f'<div class="confidence-score">Confidence: {message["confidence"]:.2%}</div>',
                                unsafe_allow_html=True)

# Chat input - MUST be outside of containers/columns
if prompt := st.chat_input("Ask a question about your documents..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Display user message
    with st.chat_message("user"):
        st.write(prompt)

    # Generate and display assistant response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            success, response = ask_question_to_api(prompt)

            if success:
                st.write(response["answer"])

                # Add to chat history
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response["answer"],
                    "sources": response.get("sources", []),
                    "confidence": response.get("confidence", 0.0)
                })

                # Display sources and confidence
                if response.get("sources"):
                    st.write("**Sources:**")
                    for source in response["sources"]:
                        st.markdown(f'<span class="source-tag">📄 {source}</span>', unsafe_allow_html=True)

                if "confidence" in response:
                    st.markdown(f'<div class="confidence-score">Confidence: {response["confidence"]:.2%}</div>',
                                unsafe_allow_html=True)
            else:
                error_msg = f"❌ Error: {response}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})

# Clear chat button
if st.session_state.messages:
    st.divider()
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🗑️ Clear Chat History", key="clear_chat", type="secondary"):
            st.session_state.messages = []
            st.rerun()

# Footer
st.divider()
st.markdown("---")
st.markdown(
    f"""
    <div style="text-align: center; color: #666; font-size: 0.9rem;">
        <p>Simple RAG System • Running in Docker • API: {API_BASE_URL}</p>
        <p>💡 <strong>Tip:</strong> Upload documents using the sidebar, then ask questions about them!</p>
    </div>
    """,
    unsafe_allow_html=True
)