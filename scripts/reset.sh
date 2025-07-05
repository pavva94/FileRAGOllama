#!/bin/bash
echo "⚠️  This will remove all containers, volumes, and data!"
read -p "Are you sure? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🗑️  Removing containers and volumes..."
    docker-compose down -v
    docker system prune -f
    rm -rf uploads/* data/* ollama/*
    echo "✅ Reset complete!"
else
    echo "❌ Reset cancelled."
fi
