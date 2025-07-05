# RAG System Docker Setup

This guide will help you containerize and run your RAG (Retrieval-Augmented Generation) system using Docker.

## 📋 Prerequisites

- Docker (version 20.10 or higher)
- Docker Compose (version 2.0 or higher)
- At least 4GB of RAM available for Docker
- 10GB of free disk space (for Ollama models)

## 🏗️ Project Structure

```
rag-system/
├── docker-compose.yml          # Multi-service orchestration
├── Dockerfile.backend          # FastAPI backend container
├── Dockerfile.frontend         # Streamlit frontend container
├── requirements.txt            # Backend Python dependencies
├── requirements-frontend.txt   # Frontend Python dependencies
├── .dockerignore              # Files to exclude from Docker builds
├── main.py                    # FastAPI application (your existing file)
├── simple_rag.py              # RAG system implementation (your existing file)
├── streamlit_app.py           # Updated Streamlit app for Docker
├── scripts/
│   ├── setup.sh               # Initial setup script
│   ├── start.sh               # Start services
│   ├── stop.sh                # Stop services
│   ├── logs.sh                # View logs
│   ├── reset.sh               # Reset everything
│   └── pull-model.sh          # Pull Ollama models
├── uploads/                   # Uploaded files (created automatically)
├── data/                      # RAG system data (created automatically)
└── ollama/                    # Ollama models and config (created automatically)
```

## 🚀 Quick Start

### 1. Create the Project Structure

Create all the necessary files in your project directory:

```bash
# Create directories
mkdir -p rag-system/scripts
cd rag-system

# Create the files using the provided artifacts
# (Copy the content from the artifacts above)
```

### 2. Set Up Files

Create the following files with the content from the artifacts:

- `docker-compose.yml` - Main orchestration file
- `Dockerfile.backend` - Backend container definition
- `Dockerfile.frontend` - Frontend container definition
- `requirements.txt` - Backend dependencies
- `requirements-frontend.txt` - Frontend dependencies
- `.dockerignore` - Files to exclude from builds
- `streamlit_app.py` - Updated Streamlit app (replace your existing one)

### 3. Create Setup Scripts

Make the scripts executable:

```bash
# Create all scripts from the artifacts
chmod +x scripts/*.sh
```

### 4. Initial Setup

Run the setup script:

```bash
./scripts/setup.sh
```

This will:
- Create necessary directories
- Build Docker images
- Start all services
- Display access information

## 🐳 Services Overview

The Docker setup includes three main services:

### 1. Backend (FastAPI)
- **Port:** 8000
- **Container:** `rag-backend`
- **Purpose:** API endpoints for file upload, RAG processing, and chat

### 2. Frontend (Streamlit)
- **Port:** 8501
- **Container:** `rag-frontend`
- **Purpose:** Web interface for interacting with the RAG system

### 3. Ollama (LLM Service)
- **Port:** 11434
- **Container:** `rag-ollama`
- **Purpose:** Local LLM inference for enhanced responses

## 📖 Usage

### Starting the System

```bash
# Start all services
./scripts/start.sh

# Or manually with docker-compose
docker-compose up -d
```

### Accessing the Application

- **Frontend:** http://localhost:8501
- **Backend API:** http://localhost:8000
- **API Documentation:** http://localhost:8000/docs
- **Ollama API:** http://localhost:11434

### Pulling Ollama Models

```bash
# Using the script
./scripts/pull-model.sh llama3.2

# Or manually
docker exec rag-ollama ollama pull llama3.2:latest
```

### Viewing Logs

```bash
# All services
./scripts/logs.sh

# Specific service
./scripts/logs.sh backend
./scripts/logs.sh frontend
./scripts/logs.sh ollama
```

### Stopping the System

```bash
# Stop all services
./scripts/stop.sh

# Or manually
docker-compose down
```

## 🔧 Configuration

### Environment Variables

You can customize the setup by modifying environment variables in `docker-compose.yml`:

```yaml
environment:
  - PYTHONPATH=/app
  - OLLAMA_BASE_URL=http://ollama:11434
  - API_BASE_URL=http://backend:8000
```

### Volume Mounts

The setup uses the following volumes for data persistence:

- `./uploads:/app/uploads` - Uploaded files
- `./data:/app/data` - RAG system data and vector stores
- `./ollama:/root/.ollama` - Ollama models and configuration

### GPU Support (Optional)

To enable GPU support for Ollama, uncomment the GPU section in `docker-compose.yml`:

```yaml
ollama:
  # ... other config
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

## 🛠️ Development

### Building Images

```bash
# Build all images
docker-compose build

# Build specific service
docker-compose build backend
docker-compose build frontend
```

### Debugging

```bash
# Enter container shell
docker exec -it rag-backend bash
docker exec -it rag-frontend bash
docker exec -it rag-ollama bash

# View container logs
docker logs rag-backend
docker logs rag-frontend
docker logs rag-ollama
```

## 📊 Monitoring

### Health Checks

The setup includes health checks for all services:

```bash
# Check service status
docker-compose ps

# Check specific service health
docker inspect rag-backend | jq '.[0].State.Health'
```

### Resource Usage

```bash
# Monitor resource usage
docker stats

# View system usage
docker system df
```

## 🔄 Maintenance

### Updating the System

```bash
# Stop services
./scripts/stop.sh

# Rebuild images
docker-compose build

# Start services
./scripts/start.sh
```

### Backup Data

```bash
# Backup uploads and data
tar -czf rag-backup-$(date +%Y%m%d).tar.gz uploads/ data/ ollama/
```

### Reset System

```bash
# WARNING: This will delete all data!
./scripts/reset.sh
```

## 🐛 Troubleshooting

### Common Issues

1. **Port Already in Use**
   ```bash
   # Check what's using the port
   sudo netstat -tulpn | grep :8000
   # Kill the process or change ports in docker-compose.yml
   ```

2. **Out of Memory**
   ```bash
   # Increase Docker memory limit
   # Or use smaller Ollama models
   ```

3. **Ollama Model Not Loading**
   ```bash
   # Check if model is pulled
   docker exec rag-ollama ollama list
   
   # Pull model manually
   docker exec rag-ollama ollama pull llama3.2:latest
   ```

4. **API Connection Issues**
   ```bash
   # Check if backend is running
   curl http://localhost:8000/health
   
   # Check Docker network
   docker network ls
   docker network inspect rag-system_rag-network
   ```

### Log Analysis

```bash
# Check specific service logs
docker-compose logs backend | grep ERROR
docker-compose logs frontend | grep ERROR
docker-compose logs ollama | grep ERROR
```

## 📝 Notes

- The first startup may take longer as Docker images are built
- Ollama models are large (2-7GB each) and take time to download
- The system persists data in local directories, so your uploads and models are preserved between restarts
- For production use, consider using proper secrets management and SSL certificates

## 🤝 Contributing

To contribute to this Docker setup:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with `docker-compose up`
5. Submit a pull request

## 📄 License

This Docker setup is provided as-is for educational and development purposes.