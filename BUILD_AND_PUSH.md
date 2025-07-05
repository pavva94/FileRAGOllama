# Azure Container Registry (ACR) - Backend and Frontend Container Guide

This guide walks you through creating, building, and pushing both backend and frontend containers to Azure Container Registry manually.

## Prerequisites

Before starting, ensure you have:
- Docker installed locally
- Azure CLI installed and logged in
- ACR registry created and accessible
- Access permissions to push to the ACR registry

## Backend Container Setup

### 1. Create Backend Dockerfile

Create a `Dockerfile` in your backend directory:

```dockerfile
# Example for Node.js backend
FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./
RUN npm ci --only=production

# Copy source code
COPY . .

EXPOSE 3000

CMD ["npm", "start"]
```

**Alternative for other technologies:**

```dockerfile
# Python/Flask example
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "app.py"]
```

```dockerfile
# .NET Core example
FROM mcr.microsoft.com/dotnet/aspnet:6.0 AS base
WORKDIR /app
EXPOSE 80

FROM mcr.microsoft.com/dotnet/sdk:6.0 AS build
WORKDIR /src
COPY ["MyApp.csproj", "."]
RUN dotnet restore "MyApp.csproj"
COPY . .
RUN dotnet build "MyApp.csproj" -c Release -o /app/build

FROM build AS publish
RUN dotnet publish "MyApp.csproj" -c Release -o /app/publish

FROM base AS final
WORKDIR /app
COPY --from=publish /app/publish .
ENTRYPOINT ["dotnet", "MyApp.dll"]
```

### 2. Build Backend Image

```bash
# Navigate to backend directory
cd /path/to/backend

# Build the image
docker build -t myapp-backend:latest .

# Tag for ACR
docker tag myapp-backend:latest <your-acr-name>.azurecr.io/myapp-backend:latest
```

## Frontend Container Setup

### 1. Create Frontend Dockerfile

Create a `Dockerfile` in your frontend directory:

```dockerfile
# Multi-stage build for React/Vue/Angular
FROM node:18-alpine as build

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### 2. Create nginx.conf

Create an `nginx.conf` file for your frontend:

```nginx
events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    server {
        listen 80;
        server_name localhost;
        root /usr/share/nginx/html;
        index index.html;

        # Handle client-side routing
        location / {
            try_files $uri $uri/ /index.html;
        }

        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }
}
```

### 3. Build Frontend Image

```bash
# Navigate to frontend directory
cd /path/to/frontend

# Build the image
docker build -t myapp-frontend:latest .

# Tag for ACR
docker tag myapp-frontend:latest <your-acr-name>.azurecr.io/myapp-frontend:latest
```

## Push to Azure Container Registry

### 1. Login to ACR

```bash
# Login to Azure CLI
az login

# Login to ACR
az acr login --name <your-acr-name>
```

**Alternative login methods:**

```bash
# Using admin credentials
docker login <your-acr-name>.azurecr.io -u <admin-username> -p <admin-password>

# Using service principal
az login --service-principal -u <app-id> -p <password> --tenant <tenant-id>
```

### 2. Push Both Images

```bash
# Push backend
docker push <your-acr-name>.azurecr.io/myapp-backend:latest

# Push frontend
docker push <your-acr-name>.azurecr.io/myapp-frontend:latest
```

### 3. Push with Version Tags

```bash
# Tag with version
docker tag myapp-backend:latest <your-acr-name>.azurecr.io/myapp-backend:v1.0.0
docker tag myapp-frontend:latest <your-acr-name>.azurecr.io/myapp-frontend:v1.0.0

# Push versioned tags
docker push <your-acr-name>.azurecr.io/myapp-backend:v1.0.0
docker push <your-acr-name>.azurecr.io/myapp-frontend:v1.0.0
```

## Verify Images in ACR

```bash
# List repositories
az acr repository list --name <your-acr-name> --output table

# List tags for specific repository
az acr repository show-tags --name <your-acr-name> --repository myapp-backend --output table
az acr repository show-tags --name <your-acr-name> --repository myapp-frontend --output table

# Show repository details
az acr repository show --name <your-acr-name> --repository myapp-backend
```

## Alternative: Using Docker Compose

If you have both services, create a `docker-compose.yml` in your project root:

```yaml
version: '3.8'
services:
  backend:
    build: 
      context: ./backend
      dockerfile: Dockerfile
    image: <your-acr-name>.azurecr.io/myapp-backend:latest
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
    
  frontend:
    build: 
      context: ./frontend
      dockerfile: Dockerfile
    image: <your-acr-name>.azurecr.io/myapp-frontend:latest
    ports:
      - "80:80"
    depends_on:
      - backend
```

### Build and Push with Docker Compose

```bash
# Build both images
docker-compose build

# Push both images
docker-compose push

# Or build and push in one command
docker-compose build && docker-compose push
```

## Best Practices

### 1. Use .dockerignore Files

Create `.dockerignore` in both frontend and backend directories:

```
# Backend .dockerignore
node_modules
npm-debug.log
.git
.gitignore
README.md
.env
.nyc_output
coverage
.nyc_output
.vscode
```

```
# Frontend .dockerignore
node_modules
.git
.gitignore
npm-debug.log
README.md
.env
.nyc_output
coverage
.vscode
dist
build
```

### 2. Multi-stage Builds

Use multi-stage builds to reduce image size:

```dockerfile
# Optimized Node.js backend
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production && npm cache clean --force

FROM node:18-alpine AS runtime
WORKDIR /app
COPY --from=builder /app/node_modules ./node_modules
COPY . .
EXPOSE 3000
CMD ["npm", "start"]
```

### 3. Version Management

```bash
# Use semantic versioning
VERSION=1.0.0
docker build -t myapp-backend:$VERSION .
docker tag myapp-backend:$VERSION <your-acr-name>.azurecr.io/myapp-backend:$VERSION
docker tag myapp-backend:$VERSION <your-acr-name>.azurecr.io/myapp-backend:latest
```

## Troubleshooting

### Common Issues

1. **Permission Denied**
   ```bash
   # Check ACR permissions
   az acr show --name <your-acr-name> --query loginServer
   az role assignment list --assignee <your-user-id> --scope /subscriptions/<subscription-id>/resourceGroups/<rg-name>/providers/Microsoft.ContainerRegistry/registries/<acr-name>
   ```

2. **Build Context Too Large**
   ```bash
   # Check .dockerignore file
   # Use --no-cache flag if needed
   docker build --no-cache -t myapp-backend:latest .
   ```

3. **Push Fails**
   ```bash
   # Re-authenticate
   az acr login --name <your-acr-name>
   
   # Check network connectivity
   docker push <your-acr-name>.azurecr.io/myapp-backend:latest --debug
   ```

### Cleanup Commands

```bash
# Remove local images
docker rmi myapp-backend:latest
docker rmi myapp-frontend:latest

# Remove from ACR
az acr repository delete --name <your-acr-name> --repository myapp-backend --yes
az acr repository delete --name <your-acr-name> --repository myapp-frontend --yes
```

## Environment Variables

Replace the following placeholders with your actual values:
- `<your-acr-name>`: Your Azure Container Registry name
- `<admin-username>`: ACR admin username (if using admin credentials)
- `<admin-password>`: ACR admin password (if using admin credentials)
- `<app-id>`: Service principal application ID
- `<password>`: Service principal password
- `<tenant-id>`: Azure tenant ID
- `<subscription-id>`: Azure subscription ID
- `<rg-name>`: Resource group name

## Next Steps

After pushing to ACR, you can:
1. Deploy to Azure Container Instances (ACI)
2. Deploy to Azure Kubernetes Service (AKS)
3. Use with Azure App Service
4. Set up CI/CD pipelines with Azure DevOps or GitHub Actions

For production deployments, consider implementing:
- Health checks in your containers
- Proper logging and monitoring
- Security scanning
  - Automated vulnerability assessments