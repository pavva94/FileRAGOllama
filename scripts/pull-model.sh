#!/bin/bash
MODEL=${1:-llama3.2}
echo "📥 Pulling Ollama model: $MODEL"
docker exec rag-ollama ollama pull $MODEL
echo "✅ Model $MODEL pulled successfully!"