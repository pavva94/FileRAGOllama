#!/bin/bash
# setup.sh - Initial setup script

echo "🐳 Setting up RAG System Docker Environment..."

# Create necessary directories
mkdir -p uploads data ollama

# Set permissions
chmod 755 uploads data ollama

# Build and start services
echo "📦 Building Docker images..."
docker-compose build

echo "🚀 Starting services..."
docker-compose up -d

echo "⏳ Waiting for services to be ready..."
sleep 30

# Check if services are running
echo "🔍 Checking service status..."
docker-compose ps

echo "✅ Setup complete!"
echo ""
echo "🌐 Access points:"
echo "   - Frontend (Streamlit): http://localhost:8501"
echo "   - Backend API: http://localhost:8000"
echo "   - Ollama API: http://localhost:11434"
echo ""
echo "📋 Useful commands:"
echo "   - View logs: docker-compose logs -f"
echo "   - Stop services: docker-compose down"
echo "   - Pull Ollama model: docker exec rag-ollama ollama pull llama3.2"
sleep 30




