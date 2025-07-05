# Azure RAG System Deployment Guide

This guide explains how to deploy the RAG system to Azure with PostgreSQL and Google Gemini integration.

## 🏗️ Architecture Overview

The system consists of:
* **Frontend**: Streamlit app running in Azure Container Instance
* **Backend**: FastAPI server running in Azure Container Instance
* **Database**: Azure Database for PostgreSQL
* **Storage**: Azure Blob Storage for document files
* **AI**: Google Gemini Pro for advanced responses
* **Embeddings**: Sentence Transformers for vector similarity

## 📋 Prerequisites

1. **Azure CLI** installed and configured
2. **Docker** installed locally
3. **Google API Key** for Gemini Pro
4. **Azure Subscription** with appropriate permissions

## 🚀 Quick Deployment

### Option 1: Automated Script (Recommended)

```bash
# Set your Google API key
export GOOGLE_API_KEY="your_google_api_key_here"

# Run the deployment script
chmod +x deploy-azure.sh
./deploy-azure.sh
```

### Option 2: Manual Deployment

#### Step 1: Create Azure Resources

```bash
# Create resource group
az group create --name rag-system-rg --location eastus

# Create PostgreSQL database
az postgres server create \
    --resource-group rag-system-rg \
    --name rag-postgres-server \
    --location eastus \
    --admin-user rag_admin \
    --admin-password "YourSecurePassword123!" \
    --sku-name B_Gen5_1

# Create database
az postgres db create \
    --resource-group rag-system-rg \
    --server-name rag-postgres-server \
    --name rag_db

# Create storage account
az storage account create \
    --name ragstorage123 \
    --resource-group rag-system-rg \
    --location eastus \
    --sku Standard_LRS

# Create container registry
az acr create \
    --resource-group rag-system-rg \
    --name ragregistry123 \
    --sku Basic \
    --admin-enabled true
```

#### Step 2: Build and Push Images

```bash
# Get registry login server
ACR_LOGIN_SERVER=$(az acr show --name ragregistry123 --resource-group rag-system-rg --query loginServer --output tsv)

# Login to registry
az acr login --name ragregistry123

# Build and push backend image
docker build -t $ACR_LOGIN_SERVER/rag-backend:latest ./backend
docker push $ACR_LOGIN_SERVER/rag-backend:latest

# Build and push frontend image
docker build -t $ACR_LOGIN_SERVER/rag-frontend:latest ./frontend
docker push $ACR_LOGIN_SERVER/rag-frontend:latest
```

#### Step 3: Configure Database and Storage

```bash
# Configure PostgreSQL firewall
az postgres server firewall-rule create \
    --resource-group rag-system-rg \
    --server-name rag-postgres-server \
    --name AllowAzureServices \
    --start-ip-address 0.0.0.0 \
    --end-ip-address 0.0.0.0

# Get storage account connection string
STORAGE_CONNECTION_STRING=$(az storage account show-connection-string \
    --name ragstorage123 \
    --resource-group rag-system-rg \
    --query connectionString --output tsv)

# Create blob container
az storage container create \
    --name documents \
    --connection-string "$STORAGE_CONNECTION_STRING" \
    --public-access off
```

#### Step 4: Deploy Container Instances

```bash
# Get registry credentials
ACR_USERNAME=$(az acr credential show --name ragregistry123 --query username --output tsv)
ACR_PASSWORD=$(az acr credential show --name ragregistry123 --query passwords[0].value --output tsv)

# Deploy backend container
az container create \
    --resource-group rag-system-rg \
    --name rag-backend \
    --image $ACR_LOGIN_SERVER/rag-backend:latest \
    --registry-username $ACR_USERNAME \
    --registry-password $ACR_PASSWORD \
    --cpu 2 \
    --memory 4 \
    --ports 8000 \
    --dns-name-label rag-backend-api \
    --environment-variables \
        DATABASE_URL="postgresql://rag_admin:YourSecurePassword123!@rag-postgres-server.postgres.database.azure.com:5432/rag_db" \
        GOOGLE_API_KEY="$GOOGLE_API_KEY" \
        AZURE_STORAGE_CONNECTION_STRING="$STORAGE_CONNECTION_STRING" \
        AZURE_STORAGE_CONTAINER_NAME="documents"

# Deploy frontend container
az container create \
    --resource-group rag-system-rg \
    --name rag-frontend \
    --image $ACR_LOGIN_SERVER/rag-frontend:latest \
    --registry-username $ACR_USERNAME \
    --registry-password $ACR_PASSWORD \
    --cpu 1 \
    --memory 2 \
    --ports 8501 \
    --dns-name-label rag-frontend-app \
    --environment-variables \
        BACKEND_URL="http://rag-backend-api.eastus.azurecontainer.io:8000"
```

## 📁 Configuration Files

### Environment Variables Template

Create a `.env` file:

```env
# Database Configuration
DATABASE_URL=postgresql://rag_admin:YourSecurePassword123!@rag-postgres-server.postgres.database.azure.com:5432/rag_db

# Google API Configuration
GOOGLE_API_KEY=your_google_api_key_here

# Azure Storage Configuration
AZURE_STORAGE_CONNECTION_STRING=your_storage_connection_string
AZURE_STORAGE_CONTAINER_NAME=documents

# Application Configuration
BACKEND_URL=http://rag-backend-api.eastus.azurecontainer.io:8000
FRONTEND_URL=http://rag-frontend-app.eastus.azurecontainer.io:8501
```

### Docker Compose for Local Testing

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:13
    environment:
      POSTGRES_DB: rag_db
      POSTGRES_USER: rag_admin
      POSTGRES_PASSWORD: YourSecurePassword123!
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://rag_admin:YourSecurePassword123!@postgres:5432/rag_db
      GOOGLE_API_KEY: ${GOOGLE_API_KEY}
    depends_on:
      - postgres

  frontend:
    build: ./frontend
    ports:
      - "8501:8501"
    environment:
      BACKEND_URL: http://backend:8000
    depends_on:
      - backend

volumes:
  postgres_data:
```

## 🔧 Troubleshooting

### Common Issues

1. **Database Connection Errors**
   ```bash
   # Check firewall rules
   az postgres server firewall-rule list --resource-group rag-system-rg --server-name rag-postgres-server
   
   # Test connection
   psql "postgresql://rag_admin:YourSecurePassword123!@rag-postgres-server.postgres.database.azure.com:5432/rag_db"
   ```

2. **Container Instance Issues**
   ```bash
   # Check container logs
   az container logs --resource-group rag-system-rg --name rag-backend
   az container logs --resource-group rag-system-rg --name rag-frontend
   
   # Check container status
   az container show --resource-group rag-system-rg --name rag-backend --query instanceView.state
   ```

3. **Storage Access Issues**
   ```bash
   # Test storage connection
   az storage blob list --container-name documents --connection-string "$STORAGE_CONNECTION_STRING"
   ```

### Performance Optimization

1. **Scale Container Instances**
   ```bash
   # Update container resources
   az container update \
       --resource-group rag-system-rg \
       --name rag-backend \
       --cpu 4 \
       --memory 8
   ```

2. **Database Performance**
   ```bash
   # Upgrade PostgreSQL tier
   az postgres server update \
       --resource-group rag-system-rg \
       --name rag-postgres-server \
       --sku-name GP_Gen5_2
   ```

## 🔐 Security Considerations

### Network Security

```bash
# Create virtual network
az network vnet create \
    --resource-group rag-system-rg \
    --name rag-vnet \
    --address-prefix 10.0.0.0/16 \
    --subnet-name rag-subnet \
    --subnet-prefix 10.0.1.0/24

# Create network security group
az network nsg create \
    --resource-group rag-system-rg \
    --name rag-nsg

# Add security rules
az network nsg rule create \
    --resource-group rag-system-rg \
    --nsg-name rag-nsg \
    --name AllowHTTP \
    --priority 1000 \
    --protocol Tcp \
    --destination-port-range 80 \
    --access Allow
```

### Key Vault Integration

```bash
# Create Key Vault
az keyvault create \
    --resource-group rag-system-rg \
    --name rag-keyvault-123 \
    --location eastus

# Store secrets
az keyvault secret set \
    --vault-name rag-keyvault-123 \
    --name database-password \
    --value "YourSecurePassword123!"

az keyvault secret set \
    --vault-name rag-keyvault-123 \
    --name google-api-key \
    --value "$GOOGLE_API_KEY"
```

## 📊 Monitoring and Logging

### Application Insights

```bash
# Create Application Insights
az monitor app-insights component create \
    --resource-group rag-system-rg \
    --app rag-app-insights \
    --location eastus \
    --application-type web

# Get instrumentation key
INSTRUMENTATION_KEY=$(az monitor app-insights component show \
    --resource-group rag-system-rg \
    --app rag-app-insights \
    --query instrumentationKey --output tsv)
```

### Log Analytics

```bash
# Create Log Analytics workspace
az monitor log-analytics workspace create \
    --resource-group rag-system-rg \
    --workspace-name rag-logs \
    --location eastus
```

## 🧹 Cleanup

To remove all resources:

```bash
# Delete entire resource group
az group delete --name rag-system-rg --yes --no-wait

# Or delete individual resources
az container delete --resource-group rag-system-rg --name rag-backend --yes
az container delete --resource-group rag-system-rg --name rag-frontend --yes
az postgres server delete --resource-group rag-system-rg --name rag-postgres-server --yes
az storage account delete --resource-group rag-system-rg --name ragstorage123 --yes
az acr delete --resource-group rag-system-rg --name ragregistry123 --yes
```

## 📝 Next Steps

1. **Set up CI/CD Pipeline** using Azure DevOps or GitHub Actions
2. **Implement Auto-scaling** with Azure Container Apps
3. **Add Custom Domain** and SSL certificate
4. **Set up Backup Strategy** for database and storage
5. **Implement Health Checks** and alerting
6. **Add Load Balancing** for high availability

## 🔗 Useful Links

- [Azure Container Instances Documentation](https://docs.microsoft.com/azure/container-instances/)
- [Azure Database for PostgreSQL Documentation](https://docs.microsoft.com/azure/postgresql/)
- [Azure Blob Storage Documentation](https://docs.microsoft.com/azure/storage/blobs/)
- [Google Gemini API Documentation](https://ai.google.dev/docs)

---

**Note**: Replace placeholder values (like `ragstorage123`, `ragregistry123`) with your actual resource names. Ensure all passwords and API keys are stored securely.