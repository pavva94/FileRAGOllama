# 🤖 RAG Assistant

A full-stack Retrieval-Augmented Generation (RAG) application that allows users to upload documents, ask questions, and receive AI-powered answers based on the content of their documents.

## ✨ Features

- **📁 Document Upload**: Support for TXT, PDF, MD, and DOCX files
- **🔍 Smart Search**: Vector similarity search using PostgreSQL with pgvector
- **🤖 AI-Powered Answers**: Local LLM integration with Ollama (llama3.2:latest)
- **🎯 Model Selection**: Choose from available Ollama models
- **💬 Chat Interface**: Interactive question-answering with chat history
- **📊 File Management**: View, manage, and delete uploaded documents
- **🌐 Web Interface**: Beautiful Streamlit frontend
- **⚡ Fast API**: RESTful backend with automatic documentation

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Streamlit     │    │    FastAPI      │    │   PostgreSQL    │
│   Frontend      │────│    Backend      │────│   + pgvector    │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                │
                       ┌─────────────────┐
                       │     Ollama      │
                       │   llama3.2      │
                       │                 │
                       └─────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- PostgreSQL 12+
- Ollama

### 1. Clone the Repository

```bash
git clone <repository-url>
cd rag-assistant
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up PostgreSQL

```sql
-- Create database
CREATE DATABASE rag_db;

-- Install pgvector extension
\c rag_db
CREATE EXTENSION vector;
```

### 5. Install and Configure Ollama

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama service
ollama serve

# Pull llama3.2:latest model
ollama pull llama3.2:latest
```

### 6. Configure Environment Variables

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql://username:password@localhost/rag_db
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:latest
UPLOAD_DIR=./uploads
API_BASE_URL=http://localhost:8000
```

### 7. Run the Application

**Start the Backend:**
```bash
python app.py
```

**Start the Frontend (in another terminal):**
```bash
streamlit run streamlit_app.py
```

### 8. Access the Application

- **Frontend**: http://localhost:8501
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## 📦 Installation

### Option 1: From Requirements File

```bash
pip install -r requirements.txt
```

### Option 2: Manual Installation

```bash
pip install fastapi uvicorn asyncpg sentence-transformers langchain httpx aiofiles python-multipart streamlit requests
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:password@localhost/rag_db` |
| `OLLAMA_URL` | Ollama API endpoint | `http://localhost:11434` |
| `OLLAMA_MODEL` | Model to use for generation | `llama3.2:latest` |
| `UPLOAD_DIR` | Directory for uploaded files | `./uploads` |
| `API_BASE_URL` | FastAPI backend URL | `http://localhost:8000` |

### Database Setup

The application automatically creates the required tables on startup:
- `files`: Stores file metadata
- `embeddings`: Stores text chunks and their vector embeddings

## 🎯 Usage

### 1. Upload Documents

- Navigate to the web interface
- Use the file upload section to upload documents
- Supported formats: TXT, PDF, MD, DOCX
- Files are automatically processed and chunked

### 2. Select Model

- Choose from available Ollama models in the dropdown
- Default model is llama3.2:latest
- Pull new models using the interface if needed

### 3. Ask Questions

- Type your question in the text area
- Click "Ask Question" to get AI-powered answers
- View sources and chat history

### 4. Manage Files

- View uploaded files with metadata
- Delete files when no longer needed
- Monitor system status in the sidebar

## 🌐 API Endpoints

### File Operations
- `POST /upload` - Upload and process a file
- `GET /files` - List all uploaded files
- `DELETE /files/{file_id}` - Delete a file

### Question Answering
- `POST /ask` - Ask a question and get an answer

### Model Management
- `GET /ollama/models` - List available models
- `POST /ollama/pull` - Pull a new model

### System
- `GET /health` - Check system health
- `GET /files/{file_id}/chunks` - View file chunks

## 🧪 Testing

### Test the API

```bash
# Upload a file
curl -X POST "http://localhost:8000/upload" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@example.txt"

# Ask a question
curl -X POST "http://localhost:8000/ask" \
     -H "Content-Type: application/json" \
     -d '{"question": "What is the main topic?"}'
```

### Test the Frontend

1. Open http://localhost:8501
2. Upload a test document
3. Ask a question about the document
4. Verify the answer and sources

## 🔧 Troubleshooting

### Common Issues

**1. Database Connection Error**
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Verify connection string
psql "postgresql://username:password@localhost/rag_db"
```

**2. Ollama Not Available**
```bash
# Check Ollama service
ollama serve

# Verify model is available
ollama list
```

**3. File Upload Issues**
```bash
# Check upload directory permissions
mkdir -p uploads
chmod 755 uploads
```

**4. Vector Extension Missing**
```sql
-- Install pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
```

### Performance Optimization

**1. Database Indexing**
```sql
-- Create index for better search performance
CREATE INDEX IF NOT EXISTS embeddings_embedding_idx 
ON embeddings USING ivfflat (embedding vector_cosine_ops);
```

**2. Chunking Strategy**
- Adjust chunk size (default: 1000 characters)
- Modify overlap (default: 200 characters)
- Optimize for your document types

## 📊 System Requirements

### Minimum Requirements
- **CPU**: 4 cores
- **RAM**: 8GB
- **Storage**: 10GB free space
- **Network**: Internet connection for model downloads

### Recommended Requirements
- **CPU**: 8 cores
- **RAM**: 16GB
- **Storage**: 50GB free space
- **GPU**: Optional (for faster inference)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 🙏 Acknowledgments

- **FastAPI**: For the excellent web framework
- **Streamlit**: For the beautiful frontend framework
- **Ollama**: For local LLM integration
- **pgvector**: For PostgreSQL vector operations
- **Sentence Transformers**: For text embeddings
- **LangChain**: For document processing utilities



