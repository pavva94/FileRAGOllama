from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import asyncpg
import os
import uuid
from datetime import datetime
import json
import hashlib
from sentence_transformers import SentenceTransformer
import numpy as np
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import TextLoader
import tempfile
import aiofiles
import httpx
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/rag_db")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Initialize FastAPI app
app = FastAPI(title="RAG API", description="FastAPI app for RAG with PostgreSQL embeddings")

# Initialize HTTP client for Ollama
ollama_client = httpx.AsyncClient(timeout=300.0)  # 5 minute timeout for LLM responses

# Initialize sentence transformer for embeddings
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')


# Pydantic models
class QuestionRequest(BaseModel):
    question: str
    max_results: Optional[int] = 5


class QuestionResponse(BaseModel):
    answer: str
    sources: List[str]


class FileInfo(BaseModel):
    id: str
    filename: str
    upload_date: datetime
    file_size: int
    chunk_count: int


# Database connection pool
db_pool = None


async def init_db_pool():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL)
    await create_tables()


async def get_db():
    async with db_pool.acquire() as conn:
        yield conn


async def create_tables():
    async with db_pool.acquire() as conn:
        # Create extension for vector operations
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

        # Create files table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id VARCHAR PRIMARY KEY,
                filename VARCHAR NOT NULL,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_size INTEGER NOT NULL,
                file_path VARCHAR NOT NULL,
                chunk_count INTEGER DEFAULT 0
            )
        """)

        # Create embeddings table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                id SERIAL PRIMARY KEY,
                file_id VARCHAR REFERENCES files(id) ON DELETE CASCADE,
                chunk_text TEXT NOT NULL,
                embedding vector(384),
                chunk_index INTEGER NOT NULL
            )
        """)

        # Create index for similarity search
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS embeddings_embedding_idx 
            ON embeddings USING ivfflat (embedding vector_cosine_ops)
        """)


def create_embedding(text: str) -> List[float]:
    """Create embedding for text using sentence transformer"""
    embedding = embedding_model.encode(text)
    return embedding.tolist()


async def save_file_chunks(file_id: str, file_path: str, conn):
    """Process file and save chunks with embeddings"""
    try:
        # Load and split document
        loader = TextLoader(file_path)
        documents = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )

        chunks = text_splitter.split_documents(documents)

        # Process each chunk
        for i, chunk in enumerate(chunks):
            chunk_text = chunk.page_content
            embedding = create_embedding(chunk_text)

            await conn.execute("""
                INSERT INTO embeddings (file_id, chunk_text, embedding, chunk_index)
                VALUES ($1, $2, $3, $4)
            """, file_id, chunk_text, embedding, i)

        # Update chunk count in files table
        await conn.execute("""
            UPDATE files SET chunk_count = $1 WHERE id = $2
        """, len(chunks), file_id)

        return len(chunks)

    except Exception as e:
        logger.error(f"Error processing file {file_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


async def generate_answer_with_ollama(question: str, context: str) -> str:
    """Generate answer using Ollama with llama3.2:latest"""
    try:
        system_prompt = """You are a helpful assistant that answers questions based on the provided context. 
Use only the information from the context to answer questions. 
If the context doesn't contain enough information to answer the question, say so clearly.
Be concise and accurate in your responses."""

        user_prompt = f"""Context:
{context}

Question: {question}

Please provide a clear and accurate answer based on the context above."""

        payload = {
            "model": OLLAMA_MODEL,
            "prompt": f"System: {system_prompt}\n\nUser: {user_prompt}",
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
                "max_tokens": 500
            }
        }

        response = await ollama_client.post(
            f"{OLLAMA_URL}/api/generate",
            json=payload
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"Ollama API error: {response.status_code} - {response.text}"
            )

        result = response.json()
        return result.get("response", "I couldn't generate an answer.")

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Request to Ollama timed out. Please try again."
        )
    except Exception as e:
        logger.error(f"Error calling Ollama API: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating answer: {str(e)}"
        )
    """Perform similarity search on embeddings"""
    query_embedding = create_embedding(query)

    results = await conn.fetch("""
        SELECT 
            e.chunk_text,
            f.filename,
            e.embedding <=> $1 as distance
        FROM embeddings e
        JOIN files f ON e.file_id = f.id
        ORDER BY e.embedding <=> $1
        LIMIT $2
    """, query_embedding, max_results)

    return [
        {
            "text": row["chunk_text"],
            "filename": row["filename"],
            "distance": row["distance"]
        }
        for row in results
    ]


# Startup event
@app.on_event("startup")
async def startup():
    await init_db_pool()
    os.makedirs(UPLOAD_DIR, exist_ok=True)


# Shutdown event
@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()
    await ollama_client.aclose()


@app.post("/upload", response_model=dict)
async def upload_file(
        file: UploadFile = File(...),
        conn=Depends(get_db)
):
    """Upload a file and process it for RAG"""
    try:
        # Validate file size
        if file.size > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File too large")

        # Generate unique file ID
        file_id = str(uuid.uuid4())

        # Create file path
        file_extension = os.path.splitext(file.filename)[1]
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}{file_extension}")

        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)

        # Save file info to database
        await conn.execute("""
            INSERT INTO files (id, filename, file_size, file_path)
            VALUES ($1, $2, $3, $4)
        """, file_id, file.filename, file.size, file_path)

        # Process file and create embeddings
        chunk_count = await save_file_chunks(file_id, file_path, conn)

        return {
            "message": "File uploaded successfully",
            "file_id": file_id,
            "filename": file.filename,
            "chunk_count": chunk_count
        }

    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/files", response_model=List[FileInfo])
async def list_files(conn=Depends(get_db)):
    """List all uploaded files"""
    try:
        files = await conn.fetch("""
            SELECT id, filename, upload_date, file_size, chunk_count
            FROM files
            ORDER BY upload_date DESC
        """)

        return [
            FileInfo(
                id=row["id"],
                filename=row["filename"],
                upload_date=row["upload_date"],
                file_size=row["file_size"],
                chunk_count=row["chunk_count"]
            )
            for row in files
        ]

    except Exception as e:
        logger.error(f"Error listing files: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/files/{file_id}")
async def delete_file(file_id: str, conn=Depends(get_db)):
    """Delete a file and its embeddings"""
    try:
        # Get file info
        file_info = await conn.fetchrow("""
            SELECT file_path FROM files WHERE id = $1
        """, file_id)

        if not file_info:
            raise HTTPException(status_code=404, detail="File not found")

        # Delete file from filesystem
        file_path = file_info["file_path"]
        if os.path.exists(file_path):
            os.remove(file_path)

        # Delete from database (cascades to embeddings)
        await conn.execute("DELETE FROM files WHERE id = $1", file_id)

        return {"message": "File deleted successfully"}

    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ask", response_model=QuestionResponse)
async def ask_question(
        request: QuestionRequest,
        conn=Depends(get_db)
):
    """Ask a question and get an answer based on uploaded documents"""
    try:
        # Perform similarity search
        relevant_chunks = await similarity_search(
            request.question,
            request.max_results,
            conn
        )

        if not relevant_chunks:
            return QuestionResponse(
                answer="I couldn't find relevant information to answer your question.",
                sources=[]
            )

        # Prepare context from relevant chunks
        context = "\n\n".join([chunk["text"] for chunk in relevant_chunks])
        sources = list(set([chunk["filename"] for chunk in relevant_chunks]))

        # Generate answer using Ollama
        answer = await generate_answer_with_ollama(request.question, context)

        return QuestionResponse(
            answer=answer,
            sources=sources
        )

    except Exception as e:
        logger.error(f"Error answering question: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    # Check Ollama health
    ollama_healthy, ollama_message = await check_ollama_health()

    return {
        "status": "healthy" if ollama_healthy else "degraded",
        "message": "RAG API is running",
        "ollama_status": ollama_message,
        "ollama_model": OLLAMA_MODEL
    }


# Additional utility endpoints
@app.get("/files/{file_id}/chunks")
async def get_file_chunks(file_id: str, conn=Depends(get_db)):
    """Get all chunks for a specific file"""
    try:
        chunks = await conn.fetch("""
            SELECT chunk_text, chunk_index
            FROM embeddings
            WHERE file_id = $1
            ORDER BY chunk_index
        """, file_id)

        if not chunks:
            raise HTTPException(status_code=404, detail="File not found or no chunks available")

        return {
            "file_id": file_id,
            "chunks": [
                {
                    "index": chunk["chunk_index"],
                    "text": chunk["chunk_text"]
                }
                for chunk in chunks
            ]
        }

    except Exception as e:
        logger.error(f"Error getting file chunks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)