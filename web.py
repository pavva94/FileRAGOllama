import streamlit as st
import requests
import json
from datetime import datetime
import os
from pathlib import Path
import time

# Configuration - Updated for Azure deployment
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:3000")

# Page configuration
st.set_page_config(
    page_title="Azure RAG System",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS - Updated for Azure theme
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 2rem 0;
        background: linear-gradient(90deg, #0078d4 0%, #005a9f 100%);
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
        border-left: 4px solid #0078d4;
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

    .service-status {
        padding: 0.5rem;
        border-radius: 5px;
        text-align: center;
        font-weight: bold;
        margin: 0.5rem 0;
    }

    .service-running {
        background-color: #d4edda;
        color: #155724;
    }

    .service-not-running {
        background-color: #f8d7da;
        color: #721c24;
    }

    .service-unavailable {
        background-color: #fff3cd;
        color: #856404;
    }

    .azure-info {
        background-color: #e3f2fd;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 4px solid #0078d4;
    }

    .feature-card {
        background-color: #ffffff;
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    .metrics-container {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
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


def get_gemini_status():
    """Get Gemini status"""
    try:
        response = requests.get(f"{API_BASE_URL}/gemini/status", timeout=10)
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


def get_service_status_html(status, service_name):
    """Generate HTML for service status"""
    if status == "connected" or status == "available":
        return f'<div class="service-status service-running">✅ {service_name}: Running</div>'
    elif status == "unavailable":
        return f'<div class="service-status service-unavailable">⚠️ {service_name}: Unavailable</div>'
    else:
        return f'<div class="service-status service-not-running">❌ {service_name}: Not Running</div>'


# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Main header
st.markdown('''
<div class="main-header">
    <h1>☁️ Azure RAG System</h1>
    <p>Powered by Azure, PostgreSQL, and Google Gemini</p>
</div>
''', unsafe_allow_html=True)

# Azure deployment info
st.markdown(f"""
<div class="azure-info">
    <h4>☁️ Azure Deployment Information</h4>
    <p><strong>API Endpoint:</strong> {API_BASE_URL}</p>
    <p><strong>Environment:</strong> {"Azure Container Instance" if "azure" in API_BASE_URL.lower() else "Local Development"}</p>
    <p><strong>Storage:</strong> Azure Blob Storage</p>
    <p><strong>Database:</strong> PostgreSQL</p>
    <p><strong>AI Model:</strong> Google Gemini Pro</p>
</div>
""", unsafe_allow_html=True)

# Check API connection
api_connected, health_info = check_api_connection()

if not api_connected:
    st.error(f"❌ Cannot connect to the API server at {API_BASE_URL}")
    st.error(f"Error details: {health_info}")
    st.info("Please check your Azure Container Instance status and ensure all services are running.")
    st.stop()

# Sidebar
with st.sidebar:
    st.header("📊 System Status")

    # API Status
    st.success("✅ API Connected")

    # Service statuses
    if health_info:
        st.markdown("### Service Health")

        # Database
        db_status = health_info.get("database", "unknown")
        st.markdown(get_service_status_html(db_status, "PostgreSQL"), unsafe_allow_html=True)

        # Azure Storage
        azure_status = health_info.get("azure_storage", "unknown")
        st.markdown(get_service_status_html(azure_status, "Azure Storage"), unsafe_allow_html=True)

        # Embeddings
        embeddings_status = health_info.get("embeddings", "unknown")
        st.markdown(get_service_status_html(embeddings_status, "Embeddings"), unsafe_allow_html=True)

        # Gemini
        gemini_status = health_info.get("gemini", "unknown")
        st.markdown(get_service_status_html(gemini_status, "Google Gemini"), unsafe_allow_html=True)

    st.divider()

    # Gemini Status Details
    st.header("🤖 AI Model Status")

    gemini_success, gemini_data = get_gemini_status()
    if gemini_success:
        if gemini_data.get("available"):
            st.success(f"✅ Gemini Pro: Active")
            st.info("Advanced AI responses enabled")
        else:
            st.warning("⚠️ Gemini: Not Available")
            st.info("Using basic response generation")
    else:
        st.error("❌ Unable to check Gemini status")

    st.divider()

    # System Features
    st.header("🚀 Features")

    features = [
        ("📊", "PostgreSQL Database", "Persistent storage with full-text search"),
        ("☁️", "Azure Blob Storage", "Scalable document storage"),
        ("🧠", "Vector Embeddings", "Semantic similarity search"),
        ("🤖", "Google Gemini", "Advanced AI responses"),
        ("📱", "Responsive UI", "Modern web interface"),
        ("🔍", "Real-time Search", "Instant document querying")
    ]

    for icon, title, description in features:
        st.markdown(f"""
        <div class="feature-card">
            <div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
                <span style="font-size: 1.5rem; margin-right: 0.5rem;">{icon}</span>
                <strong>{title}</strong>
            </div>
            <p style="margin: 0; font-size: 0.9rem; color: #666;">{description}</p>
        </div>
        """, unsafe_allow_html=True)

# Main content area
col1, col2 = st.columns([2, 1])

with col1:
    st.header("💬 Chat with Your Documents")

    # Chat interface
    chat_container = st.container()

    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])
                if message["role"] == "assistant" and "sources" in message:
                    if message["sources"]:
                        st.write("**Sources:**")
                        for source in message["sources"]:
                            st.markdown(f'<span class="source-tag">📄 {source}</span>', unsafe_allow_html=True)
                    if "confidence" in message:
                        confidence_color = "#4caf50" if message["confidence"] > 0.7 else "#ff9800" if message[
                                                                                                          "confidence"] > 0.4 else "#f44336"
                        st.markdown(
                            f'<div class="confidence-score" style="color: {confidence_color};">Confidence: {message["confidence"]:.2%}</div>',
                            unsafe_allow_html=True)

    # Chat input
    if prompt := st.chat_input("Ask a question about your documents..."):
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            with st.spinner("🤖 Processing with Gemini..."):
                success, response = ask_question_to_api(prompt)

                if success:
                    st.write(response["answer"])
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response["answer"],
                        "sources": response["sources"],
                        "confidence": response["confidence"]
                    })

                    if response["sources"]:
                        st.write("**Sources:**")
                        for source in response["sources"]:
                            st.markdown(f'<span class="source-tag">📄 {source}</span>', unsafe_allow_html=True)

                    confidence_color = "#4caf50" if response["confidence"] > 0.7 else "#ff9800" if response[
                                                                                                       "confidence"] > 0.4 else "#f44336"
                    st.markdown(
                        f'<div class="confidence-score" style="color: {confidence_color};">Confidence: {response["confidence"]:.2%}</div>',
                        unsafe_allow_html=True)
                else:
                    error_msg = f"❌ Error: {response}"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})

    # Advanced search options
    with st.expander("🔧 Advanced Search Options"):
        max_results = st.slider("Maximum results to consider", 1, 10, 5)
        if st.button("🔄 Update Search Settings"):
            st.info(f"Search will now consider up to {max_results} document chunks")

with col2:
    st.header("📁 Document Management")

    # File upload section
    st.subheader("📤 Upload New Document")
    uploaded_file = st.file_uploader(
        "Choose a file",
        type=['txt', 'pdf', 'md', 'docx'],
        help="Supported formats: TXT, PDF, MD, DOCX\nFiles will be stored in Azure Blob Storage"
    )

    if uploaded_file is not None:
        file_details = {
            "filename": uploaded_file.name,
            "size": format_file_size(uploaded_file.size),
            "type": uploaded_file.type
        }

        st.markdown("**File Details:**")
        st.json(file_details)

        if st.button("📤 Upload to Azure", key="upload_btn"):
            with st.spinner("Uploading to Azure and processing..."):
                success, result = upload_file_to_api(uploaded_file.read(), uploaded_file.name)

                if success:
                    st.success(f"✅ Document uploaded successfully!")
                    st.markdown(f"""
                    <div class="metrics-container">
                        <p><strong>File ID:</strong> {result['file_id']}</p>
                        <p><strong>Chunks created:</strong> {result['chunk_count']}</p>
                        <p><strong>File size:</strong> {format_file_size(result['file_size'])}</p>
                        <p><strong>Storage:</strong> Azure Blob Storage</p>
                    </div>
                    """, unsafe_allow_html=True)
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"❌ Upload failed: {result}")

    st.divider()

    # File list section
    st.subheader("📚 Document Library")

    col_refresh, col_stats = st.columns(2)
    with col_refresh:
        if st.button("🔄 Refresh", key="refresh_btn"):
            st.rerun()

    files_success, files_data = get_files_from_api()

    if files_success and files_data:
        with col_stats:
            st.metric("Total Documents", len(files_data))

        # Document statistics
        total_size = sum(file_info['file_size'] for file_info in files_data)
        total_chunks = sum(file_info['chunk_count'] for file_info in files_data)

        st.markdown(f"""
        <div class="metrics-container">
            <div style="display: flex; justify-content: space-between;">
                <div>
                    <h4>📊 Library Stats</h4>
                    <p><strong>Total Size:</strong> {format_file_size(total_size)}</p>
                    <p><strong>Total Chunks:</strong> {total_chunks}</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # File list with improved UI
        for file_info in files_data:
            upload_date = datetime.fromisoformat(file_info['upload_date'].replace('Z', '+00:00'))

            with st.expander(f"📄 {file_info['filename']}", expanded=False):
                col_info, col_actions = st.columns([2, 1])

                with col_info:
                    st.markdown(f"""
                    **File Details:**
                    - **ID:** `{file_info['id'][:8]}...`
                    - **Size:** {format_file_size(file_info['file_size'])}
                    - **Uploaded:** {upload_date.strftime('%Y-%m-%d %H:%M')}
                    - **Chunks:** {file_info['chunk_count']}
                    - **Storage:** Azure Blob
                    """)

                with col_actions:
                    if st.button(f"🗑️ Delete", key=f"delete_{file_info['id']}", type="secondary"):
                        if st.session_state.get(f"confirm_delete_{file_info['id']}", False):
                            with st.spinner("Deleting from Azure..."):
                                success, result = delete_file_from_api(file_info['id'])
                                if success:
                                    st.success("✅ File deleted successfully!")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(f"❌ Delete failed: {result}")
                        else:
                            st.session_state[f"confirm_delete_{file_info['id']}"] = True
                            st.warning("⚠️ Click again to confirm")

    elif files_success:
        st.info("📭 No documents uploaded yet")
        st.markdown("""
        <div class="azure-info">
            <h4>🚀 Get Started</h4>
            <p>Upload your first document to begin using the RAG system!</p>
            <ul>
                <li>Support for TXT, PDF, MD, and DOCX files</li>
                <li>Automatic text extraction and chunking</li>
                <li>Secure storage in Azure Blob Storage</li>
                <li>Vector embeddings for semantic search</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.error(f"❌ Error loading files: {files_data}")

# Footer
st.divider()
st.markdown("---")

# System information and metrics
col_footer1, col_footer2, col_footer3 = st.columns(3)

with col_footer1:
    st.markdown("### 🏗️ Architecture")
    st.markdown("""
    - **Frontend:** Streamlit
    - **Backend:** FastAPI
    - **Database:** PostgreSQL
    - **Storage:** Azure Blob
    - **AI:** Google Gemini Pro
    """)

with col_footer2:
    st.markdown("### 🔧 Capabilities")
    st.markdown("""
    - **Document Processing:** Multi-format support
    - **Semantic Search:** Vector embeddings
    - **AI Responses:** Advanced language model
    - **Scalable Storage:** Cloud-native design
    """)

with col_footer3:
    st.markdown("### 📊 Performance")
    if health_info:
        st.markdown(f"""
        - **Database:** {health_info.get('database', 'Unknown').title()}
        - **Storage:** {health_info.get('azure_storage', 'Unknown').title()}
        - **AI Model:** {health_info.get('gemini', 'Unknown').title()}
        - **Embeddings:** {health_info.get('embeddings', 'Unknown').title()}
        """)

st.markdown(
    f"""
    <div style="text-align: center; color: #666; font-size: 0.9rem; margin-top: 2rem;">
        <p>Azure RAG System • Powered by Microsoft Azure & Google Gemini • API: {API_BASE_URL}</p>
        <p>Secure • Scalable • Intelligent</p>
    </div>
    """,
    unsafe_allow_html=True
)

# Clear chat button
if st.session_state.messages:
    st.divider()
    col_clear1, col_clear2, col_clear3 = st.columns([1, 1, 1])
    with col_clear2:
        if st.button("🗑️ Clear Chat History", key="clear_chat", type="secondary", use_container_width=True):
            st.session_state.messages = []
            st.rerun()