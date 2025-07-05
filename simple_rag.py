import os
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
import tempfile
import shutil

# Document processing
import PyPDF2
import docx
from markdown import markdown
from bs4 import BeautifulSoup

# ML/NLP libraries
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
import re

# Updated import for huggingface_hub compatibility
try:
    from huggingface_hub import hf_hub_download

    HF_HUB_AVAILABLE = True
except ImportError:
    HF_HUB_AVAILABLE = False

# Try to import sentence transformers for better embeddings
try:
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')


class SimpleRAG:
    def __init__(self, data_dir: str = "data"):
        """Initialize the RAG system"""
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        # Initialize components
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words='english',
            ngram_range=(1, 2)
        )

        # Try to load a sentence transformer model if available
        self.sentence_model = None
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
                print("✅ Loaded SentenceTransformer model")
            except Exception as e:
                print(f"⚠️ Could not load SentenceTransformer: {e}")

        # Storage
        self.chunks = []
        self.embeddings = None
        self.file_metadata = {}

        # Load existing data
        self._load_data()

    def _load_data(self):
        """Load existing data from disk"""
        try:
            # Load chunks
            chunks_file = self.data_dir / "chunks.json"
            if chunks_file.exists():
                with open(chunks_file, 'r', encoding='utf-8') as f:
                    self.chunks = json.load(f)

            # Load file metadata
            metadata_file = self.data_dir / "metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    self.file_metadata = json.load(f)

            # Rebuild embeddings if we have chunks
            if self.chunks:
                self._rebuild_embeddings()

            print(f"✅ Loaded {len(self.chunks)} chunks from {len(self.file_metadata)} files")

        except Exception as e:
            print(f"⚠️ Error loading data: {e}")
            # Reset data if loading fails
            self.chunks = []
            self.embeddings = None
            self.file_metadata = {}

    def _save_data(self):
        """Save data to disk"""
        try:
            # Save chunks
            chunks_file = self.data_dir / "chunks.json"
            with open(chunks_file, 'w', encoding='utf-8') as f:
                json.dump(self.chunks, f, indent=2, ensure_ascii=False)

            # Save file metadata
            metadata_file = self.data_dir / "metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.file_metadata, f, indent=2, ensure_ascii=False)

            print("✅ Data saved successfully")

        except Exception as e:
            print(f"❌ Error saving data: {e}")

    def _extract_text_from_file(self, file_path: str) -> str:
        """Extract text from various file formats"""
        file_path = Path(file_path)
        extension = file_path.suffix.lower()

        try:
            if extension == '.txt':
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()

            elif extension == '.pdf':
                text = ""
                with open(file_path, 'rb') as f:
                    pdf_reader = PyPDF2.PdfReader(f)
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"
                return text

            elif extension == '.docx':
                doc = docx.Document(file_path)
                text = ""
                for paragraph in doc.paragraphs:
                    text += paragraph.text + "\n"
                return text

            elif extension == '.md':
                with open(file_path, 'r', encoding='utf-8') as f:
                    md_content = f.read()
                    html = markdown(md_content)
                    soup = BeautifulSoup(html, 'html.parser')
                    return soup.get_text()

            else:
                raise ValueError(f"Unsupported file format: {extension}")

        except Exception as e:
            raise Exception(f"Error extracting text from {file_path}: {str(e)}")

    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks"""
        # Clean text
        text = re.sub(r'\s+', ' ', text).strip()

        # Split into sentences
        sentences = sent_tokenize(text)

        chunks = []
        current_chunk = ""
        current_length = 0

        for sentence in sentences:
            sentence_length = len(sentence.split())

            # If adding this sentence would exceed chunk size
            if current_length + sentence_length > chunk_size and current_chunk:
                chunks.append(current_chunk.strip())

                # Create overlap
                overlap_text = " ".join(current_chunk.split()[-overlap:])
                current_chunk = overlap_text + " " + sentence
                current_length = len(current_chunk.split())
            else:
                current_chunk += " " + sentence
                current_length += sentence_length

        # Add the last chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def _create_embeddings(self, texts: List[str]) -> np.ndarray:
        """Create embeddings for texts"""
        if self.sentence_model:
            # Use sentence transformers if available
            try:
                embeddings = self.sentence_model.encode(texts)
                return embeddings
            except Exception as e:
                print(f"⚠️ Error with SentenceTransformer: {e}, falling back to TF-IDF")

        # Fallback to TF-IDF
        if len(texts) == 1:
            # For single text, we need to fit_transform on existing corpus
            all_texts = [chunk['text'] for chunk in self.chunks] + texts
            embeddings = self.vectorizer.fit_transform(all_texts)
            return embeddings[-1:].toarray()  # Return only the new embedding
        else:
            # For multiple texts
            embeddings = self.vectorizer.fit_transform(texts)
            return embeddings.toarray()

    def _rebuild_embeddings(self):
        """Rebuild embeddings for all chunks"""
        if not self.chunks:
            return

        texts = [chunk['text'] for chunk in self.chunks]

        try:
            if self.sentence_model:
                self.embeddings = self.sentence_model.encode(texts)
            else:
                self.embeddings = self.vectorizer.fit_transform(texts).toarray()

            print(f"✅ Rebuilt embeddings for {len(texts)} chunks")

        except Exception as e:
            print(f"❌ Error rebuilding embeddings: {e}")

    def upload_file(self, file_path: str, original_filename: str = None) -> Dict[str, Any]:
        """Upload and process a file"""
        try:
            # Extract text
            text = self._extract_text_from_file(file_path)

            if not text.strip():
                raise ValueError("No text content found in file")

            # Generate file ID
            file_id = str(uuid.uuid4())

            # Create chunks
            chunks = self._chunk_text(text)

            # Store file metadata
            filename = original_filename or Path(file_path).name
            file_size = Path(file_path).stat().st_size

            self.file_metadata[file_id] = {
                'id': file_id,
                'filename': filename,
                'file_size': file_size,
                'upload_date': datetime.now().isoformat(),
                'chunk_count': len(chunks)
            }

            # Add chunks to storage
            chunk_start_idx = len(self.chunks)
            for i, chunk_text in enumerate(chunks):
                chunk = {
                    'id': f"{file_id}_{i}",
                    'file_id': file_id,
                    'text': chunk_text,
                    'filename': filename,
                    'chunk_index': i
                }
                self.chunks.append(chunk)

            # Update embeddings
            self._rebuild_embeddings()

            # Save data
            self._save_data()

            return {
                'file_id': file_id,
                'filename': filename,
                'chunk_count': len(chunks),
                'file_size': file_size
            }

        except Exception as e:
            raise Exception(f"Error uploading file: {str(e)}")

    def get_files(self) -> List[Dict[str, Any]]:
        """Get list of uploaded files"""
        return list(self.file_metadata.values())

    def delete_file(self, file_id: str) -> bool:
        """Delete a file and its chunks"""
        try:
            if file_id not in self.file_metadata:
                return False

            # Remove chunks
            self.chunks = [chunk for chunk in self.chunks if chunk['file_id'] != file_id]

            # Remove file metadata
            del self.file_metadata[file_id]

            # Rebuild embeddings
            self._rebuild_embeddings()

            # Save data
            self._save_data()

            return True

        except Exception as e:
            print(f"❌ Error deleting file: {e}")
            return False

    def find_similar_chunks(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Find chunks similar to the query"""
        if not self.chunks or self.embeddings is None:
            return []

        try:
            # Create query embedding
            query_embedding = self._create_embeddings([query])

            # Calculate similarities
            if self.sentence_model:
                similarities = cosine_similarity(query_embedding, self.embeddings)[0]
            else:
                query_tfidf = self.vectorizer.transform([query])
                similarities = cosine_similarity(query_tfidf, self.embeddings)[0]

            # Get top results
            top_indices = np.argsort(similarities)[::-1][:max_results]

            results = []
            for idx in top_indices:
                if similarities[idx] > 0.1:  # Minimum similarity threshold
                    result = self.chunks[idx].copy()
                    result['similarity'] = float(similarities[idx])
                    results.append(result)

            return results

        except Exception as e:
            print(f"❌ Error finding similar chunks: {e}")
            return []

    def generate_answer(self, question: str, max_results: int = 5) -> Dict[str, Any]:
        """Generate an answer based on similar chunks"""
        try:
            # Find similar chunks
            similar_chunks = self.find_similar_chunks(question, max_results)

            if not similar_chunks:
                return {
                    'answer': "I don't have enough information to answer that question. Please upload relevant documents first.",
                    'sources': [],
                    'confidence': 0.0,
                    'context': ''
                }

            # Create context from similar chunks
            context_parts = []
            sources = set()

            for chunk in similar_chunks:
                context_parts.append(chunk['text'])
                sources.add(chunk['filename'])

            context = '\n\n'.join(context_parts)

            # Calculate confidence (average similarity)
            avg_similarity = np.mean([chunk['similarity'] for chunk in similar_chunks])
            confidence = float(avg_similarity)

            # Generate a basic answer (this can be enhanced with LLM)
            answer = self._generate_basic_answer(question, context, similar_chunks)

            return {
                'answer': answer,
                'sources': list(sources),
                'confidence': confidence,
                'context': context
            }

        except Exception as e:
            return {
                'answer': f"Error generating answer: {str(e)}",
                'sources': [],
                'confidence': 0.0,
                'context': ''
            }

    def _generate_basic_answer(self, question: str, context: str, chunks: List[Dict]) -> str:
        """Generate a basic answer without LLM"""
        # This is a simple extractive approach
        # In a real system, you'd use an LLM here

        if not chunks:
            return "No relevant information found."

        # Get the most relevant chunk
        best_chunk = chunks[0]

        # Try to find the most relevant sentences
        sentences = sent_tokenize(best_chunk['text'])

        # Simple keyword matching
        question_words = set(word_tokenize(question.lower()))
        question_words = question_words - set(stopwords.words('english'))

        scored_sentences = []
        for sentence in sentences:
            sentence_words = set(word_tokenize(sentence.lower()))
            overlap = len(question_words.intersection(sentence_words))
            if overlap > 0:
                scored_sentences.append((sentence, overlap))

        if scored_sentences:
            # Sort by overlap and take top sentences
            scored_sentences.sort(key=lambda x: x[1], reverse=True)
            top_sentences = [s[0] for s in scored_sentences[:3]]
            return ' '.join(top_sentences)
        else:
            # Return first few sentences of best chunk
            return ' '.join(sentences[:2])


# Example usage
if __name__ == "__main__":
    # Initialize RAG system
    rag = SimpleRAG()

    # Example file upload
    # result = rag.upload_file("path/to/your/document.pdf")
    # print(f"Uploaded file: {result}")

    # Example question
    # answer = rag.generate_answer("What is the main topic of the document?")
    # print(f"Answer: {answer}")

    print("RAG system initialized successfully!")