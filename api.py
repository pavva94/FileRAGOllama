from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import tempfile
import os
from pathlib import Path
import requests
import json

# Import our RAG system
from simple_rag import SimpleRAG

app = FastAPI(title="Simple RAG API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize RAG system
rag = SimpleRAG()


# Pydantic models
class QuestionRequest(BaseModel):
    question: str
    max_results: int = 5


class AnswerResponse(BaseModel):
    answer: str
    sources: List[str]
    confidence: float


class FileInfo(BaseModel):
    id: str
    filename: str
    file_size: int
    upload_date: str
    chunk_count: int


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    chunk_count: int
    file_size: int


# Ollama integration (optional)
OLLAMA_BASE_URL = "http://localhost:11434"


def check_ollama_status():
    """Check if Ollama is running"""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return response.status_code == 200
    except:
        return False


def get_ollama_models():
    """Get available Ollama models"""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
        if response.status_code == 200:
            data = response.json()
            models = data.get("models", [])
            return [{"name": model["name"], "size": model.get("size", 0)} for model in models]
        return []
    except:
        return []


def generate_with_ollama(prompt: str, model: str = "llama3.2:latest") -> str:
    """Generate response using Ollama"""
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False
            },
            timeout=60
        )

        if response.status_code == 200:
            return response.json()["response"]
        else:
            return None
    except:
        return None


@app.get("/health")
def health_check():
    """Health check endpoint"""
    ollama_status = "running" if check_ollama_status() else "not running"

    # Get current model (simplified)
    models = get_ollama_models()
    current_model = models[0]["name"] if models else "none"

    return {
        "status": "healthy",
        "ollama_status": ollama_status,
        "ollama_model": current_model,
        "rag_system": "running"
    }


@app.get("/ollama/models")
def get_models():
    """Get available Ollama models"""
    models = get_ollama_models()
    current_model = models[0]["name"] if models else ""

    return {
        "available_models": models,
        "current_model": current_model
    }


@app.post("/ollama/pull")
def pull_model(model_name: str):
    """Pull a model from Ollama"""
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/pull",
            json={"name": model_name},
            timeout=300
        )

        if response.status_code == 200:
            return {"success": True, "message": f"Model {model_name} pulled successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to pull model")
    except requests.RequestException:
        raise HTTPException(status_code=500, detail="Failed to connect to Ollama")


@app.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """Upload a file to the RAG system"""

    # Check file type
    allowed_extensions = ['.txt', '.pdf', '.md', '.docx']
    file_extension = Path(file.filename).suffix.lower()

    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
        )

    # Save uploaded file temporarily
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name

        # Process file with RAG system
        result = rag.upload_file(tmp_file_path, file.filename)

        # Clean up temp file
        os.unlink(tmp_file_path)

        return UploadResponse(**result)

    except Exception as e:
        # Clean up temp file if it exists
        if 'tmp_file_path' in locals():
            try:
                os.unlink(tmp_file_path)
            except:
                pass

        raise HTTPException(status_code=500, detail=str(e))


@app.get("/files", response_model=List[FileInfo])
def get_files():
    """Get list of uploaded files"""
    try:
        files = rag.get_files()
        return [FileInfo(**file) for file in files]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/files/{file_id}")
def delete_file(file_id: str):
    """Delete a file"""
    try:
        success = rag.delete_file(file_id)
        if success:
            return {"message": "File deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ask", response_model=AnswerResponse)
def ask_question(request: QuestionRequest):
    """Ask a question to the RAG system"""
    try:
        # Get similar chunks and basic answer
        result = rag.generate_answer(request.question, request.max_results)

        # Try to enhance with Ollama if available
        if check_ollama_status():
            # Create a better prompt with context
            prompt = f"""Based on the following context, please answer the question.

Context:
{result['context']}

Question: {request.question}

Please provide a clear, concise answer based on the context provided. If the context doesn't contain enough information to answer the question, please say so.

Answer:"""

            ollama_response = generate_with_ollama(prompt)
            if ollama_response:
                result['answer'] = ollama_response

        return AnswerResponse(
            answer=result['answer'],
            sources=result['sources'],
            confidence=result['confidence']
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def root():
    """Root endpoint"""
    return {"message": "Simple RAG API is running!"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)