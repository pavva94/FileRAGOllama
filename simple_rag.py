import sqlite3
import os
import json
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import hashlib
import pickle
from pathlib import Path

# For text processing
import re
from dataclasses import dataclass
import numpy as np
from sentence_transformers import SentenceTransformer

# Document processing
import PyPDF2
from docx import Document as DocxDocument
import markdown


@dataclass
class DocumentChunk:
    id: str
    file_id: str
    content: str
    embedding: np.ndarray
    metadata: Dict
    chunk_index: int


class SimpleRAG:
    def __init__(self, data_dir: str = "rag_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        # Initialize directories
        self.files_dir = self.data_dir / "files"
        self.embeddings_dir = self.data_dir / "embeddings"
        self.files_dir.mkdir(exist_ok=True)
        self.embeddings_dir.mkdir(exist_ok=True)

        # Initialize SQLite database
        self.db_path = self.data_dir / "rag.db"
        self.init_database()

        # Initialize embedding model
        print("Loading embedding model...")
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.embedding_dim = 384  # Dimension for all-MiniLM-L6-v2

        print("RAG system initialized!")

    def init_database(self):
        """Initialize SQLite database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Files table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                upload_date TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                chunk_count INTEGER DEFAULT 0
            )
        """)

        # Chunks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                embedding_path TEXT NOT NULL,
                metadata TEXT,
                FOREIGN KEY (file_id) REFERENCES files (id)
            )
        """)

        conn.commit()
        conn.close()

    def extract_text_from_file(self, file_path: Path) -> str:
        """Extract text from various file formats"""
        file_extension = file_path.suffix.lower()

        if file_extension == '.txt':
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()

        elif file_extension == '.pdf':
            text = ""
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            return text

        elif file_extension == '.docx':
            doc = DocxDocument(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text

        elif file_extension == '.md':
            with open(file_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
            # Convert markdown to plain text (basic conversion)
            html = markdown.markdown(md_content)
            text = re.sub(r'<[^>]+>', '', html)
            return text

        else:
            raise ValueError(f"Unsupported file format: {file_extension}")

    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks"""
        words = text.split()
        chunks = []

        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk.strip())

        return chunks

    def upload_file(self, file_path: str, filename: str = None) -> Dict:
        """Upload and process a file"""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if filename is None:
            filename = file_path.name

        # Generate file ID
        file_id = str(uuid.uuid4())

        # Calculate file hash
        with open(file_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()

        # Check if file already exists
        if self.file_exists(file_hash):
            raise ValueError("File already exists in the system")

        # Copy file to storage
        stored_file_path = self.files_dir / f"{file_id}_{filename}"
        with open(file_path, 'rb') as src, open(stored_file_path, 'wb') as dst:
            dst.write(src.read())

        # Extract text
        try:
            text = self.extract_text_from_file(file_path)
        except Exception as e:
            # Clean up if text extraction fails
            stored_file_path.unlink()
            raise e

        # Create chunks
        chunks = self.chunk_text(text)

        # Generate embeddings and store chunks
        chunk_objects = []
        for i, chunk_text in enumerate(chunks):
            chunk_id = str(uuid.uuid4())

            # Generate embedding
            embedding = self.embedding_model.encode(chunk_text)

            # Save embedding
            embedding_path = self.embeddings_dir / f"{chunk_id}.pkl"
            with open(embedding_path, 'wb') as f:
                pickle.dump(embedding, f)

            # Create chunk object
            chunk_obj = DocumentChunk(
                id=chunk_id,
                file_id=file_id,
                content=chunk_text,
                embedding=embedding,
                metadata={"filename": filename, "chunk_index": i},
                chunk_index=i
            )
            chunk_objects.append(chunk_obj)

        # Store in database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Insert file record
        cursor.execute("""
            INSERT INTO files (id, filename, file_path, file_size, upload_date, content_hash, chunk_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            file_id, filename, str(stored_file_path), file_path.stat().st_size,
            datetime.now().isoformat(), file_hash, len(chunks)
        ))

        # Insert chunk records
        for chunk in chunk_objects:
            cursor.execute("""
                INSERT INTO chunks (id, file_id, chunk_index, content, embedding_path, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                chunk.id, chunk.file_id, chunk.chunk_index, chunk.content,
                str(self.embeddings_dir / f"{chunk.id}.pkl"), json.dumps(chunk.metadata)
            ))

        conn.commit()
        conn.close()

        return {
            "file_id": file_id,
            "filename": filename,
            "chunk_count": len(chunks),
            "file_size": file_path.stat().st_size
        }

    def file_exists(self, content_hash: str) -> bool:
        """Check if file with given hash already exists"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM files WHERE content_hash = ?", (content_hash,))
        result = cursor.fetchone()

        conn.close()
        return result is not None

    def get_files(self) -> List[Dict]:
        """Get list of all uploaded files"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, filename, file_size, upload_date, chunk_count
            FROM files
            ORDER BY upload_date DESC
        """)

        files = []
        for row in cursor.fetchall():
            files.append({
                "id": row[0],
                "filename": row[1],
                "file_size": row[2],
                "upload_date": row[3],
                "chunk_count": row[4]
            })

        conn.close()
        return files

    def delete_file(self, file_id: str) -> bool:
        """Delete a file and all its chunks"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get file info
        cursor.execute("SELECT file_path FROM files WHERE id = ?", (file_id,))
        file_info = cursor.fetchone()

        if not file_info:
            conn.close()
            return False

        # Get chunk embedding paths
        cursor.execute("SELECT embedding_path FROM chunks WHERE file_id = ?", (file_id,))
        embedding_paths = [row[0] for row in cursor.fetchall()]

        # Delete from database
        cursor.execute("DELETE FROM chunks WHERE file_id = ?", (file_id,))
        cursor.execute("DELETE FROM files WHERE id = ?", (file_id,))

        conn.commit()
        conn.close()

        # Delete files
        try:
            # Delete stored file
            file_path = Path(file_info[0])
            if file_path.exists():
                file_path.unlink()

            # Delete embeddings
            for embedding_path in embedding_paths:
                embedding_file = Path(embedding_path)
                if embedding_file.exists():
                    embedding_file.unlink()
        except Exception as e:
            print(f"Error deleting files: {e}")
            return False

        return True

    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    def search_similar_chunks(self, query: str, max_results: int = 5) -> List[Tuple[str, float, Dict]]:
        """Search for chunks similar to the query"""
        # Generate query embedding
        query_embedding = self.embedding_model.encode(query)

        # Get all chunks
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT c.id, c.content, c.embedding_path, c.metadata, f.filename
            FROM chunks c
            JOIN files f ON c.file_id = f.id
        """)

        chunks = cursor.fetchall()
        conn.close()

        # Calculate similarities
        similarities = []
        for chunk in chunks:
            chunk_id, content, embedding_path, metadata_json, filename = chunk

            # Load embedding
            try:
                with open(embedding_path, 'rb') as f:
                    chunk_embedding = pickle.load(f)

                # Calculate similarity
                similarity = self.cosine_similarity(query_embedding, chunk_embedding)

                metadata = json.loads(metadata_json)
                metadata['filename'] = filename

                similarities.append((content, similarity, metadata))
            except Exception as e:
                print(f"Error loading embedding for chunk {chunk_id}: {e}")
                continue

        # Sort by similarity and return top results
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:max_results]

    def generate_answer(self, query: str, max_results: int = 5) -> Dict:
        """Generate answer using retrieved chunks"""
        # Get similar chunks
        similar_chunks = self.search_similar_chunks(query, max_results)

        if not similar_chunks:
            return {
                "answer": "I couldn't find any relevant information to answer your question.",
                "sources": [],
                "confidence": 0.0
            }

        # Simple answer generation (you can integrate with Ollama here)
        context = "\n\n".join([chunk[0] for chunk in similar_chunks])

        # For now, return the most relevant chunk as the answer
        # You can replace this with actual LLM generation
        best_chunk = similar_chunks[0]

        answer = f"Based on the documents, here's what I found:\n\n{best_chunk[0]}"

        sources = list(set([chunk[2]['filename'] for chunk in similar_chunks]))
        confidence = best_chunk[1]

        return {
            "answer": answer,
            "sources": sources,
            "confidence": confidence,
            "context": context  # You can use this for LLM prompting
        }


# Example usage and testing
if __name__ == "__main__":
    # Initialize RAG system
    rag = SimpleRAG()

    # Example: Upload a file
    try:
        # Create a sample text file for testing
        sample_text = """
        Artificial Intelligence (AI) is a broad field of computer science focused on creating systems
        that can perform tasks that typically require human intelligence. This includes learning,
        reasoning, perception, and language understanding.

        Machine Learning is a subset of AI that focuses on algorithms that can learn from data
        without being explicitly programmed. Deep Learning is a subset of Machine Learning
        that uses neural networks with multiple layers.

        Natural Language Processing (NLP) is another important area of AI that deals with
        the interaction between computers and human language. It includes tasks like text
        classification, sentiment analysis, and question answering.
        """

        # Save sample file
        sample_file_path = "sample_ai_doc.txt"
        with open(sample_file_path, 'w') as f:
            f.write(sample_text)

        # Upload file
        result = rag.upload_file(sample_file_path)
        print(f"File uploaded: {result}")

        # Search for similar content
        query = "What is machine learning?"
        answer = rag.generate_answer(query)
        print(f"\nQuery: {query}")
        print(f"Answer: {answer['answer']}")
        print(f"Sources: {answer['sources']}")
        print(f"Confidence: {answer['confidence']:.3f}")

        # List files
        files = rag.get_files()
        print(f"\nUploaded files: {files}")

        # Clean up
        os.remove(sample_file_path)

    except Exception as e:
        print(f"Error: {e}")