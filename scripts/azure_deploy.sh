#!/bin/bash

# Azure RAG System Deployment Script
# This script helps deploy the RAG system to Azure Container Instances

set -e

# Configuration
RESOURCE_GROUP="rag-system-rg"
LOCATION="eastus"
CONTAINER_GROUP_NAME="rag-system"
STORAGE_ACCOUNT_NAME="ragstorage$(date +%s)"
DATABASE_SERVER_NAME="rag-postgres-$(date +%s)"
REGISTRY_NAME="ragregistry$(date +%s)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Azure RAG System Deployment ===${NC}"

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo -e "${RED}Azure CLI is not installed. Please install it first.${NC}"
    exit 1
fi

# Check if logged in to Azure
if ! az account show &> /dev/null; then
    echo -e "${YELLOW}Please login to Azure first${NC}"
    az login
fi

# Get current subscription
SUBSCRIPTION_ID=$(az account show --query id --output tsv)
echo -e "${GREEN}Using subscription: $SUBSCRIPTION_ID${NC}"

# Register required resource providers
echo -e "${YELLOW}Registering required resource providers...${NC}"
az provider register --namespace Microsoft.ContainerRegistry
az provider register --namespace Microsoft.Storage
az provider register --namespace Microsoft.ContainerInstance
az provider register --namespace Microsoft.DBforPostgreSQL

# Wait for registration to complete (this can take a few minutes)
echo -e "${YELLOW}Waiting for resource provider registration to complete...${NC}"
while true; do
    ACR_STATUS=$(az provider show --namespace Microsoft.ContainerRegistry --query registrationState --output tsv)
    STORAGE_STATUS=$(az provider show --namespace Microsoft.Storage --query registrationState --output tsv)
    CONTAINER_STATUS=$(az provider show --namespace Microsoft.ContainerInstance --query registrationState --output tsv)
    POSTGRES_STATUS=$(az provider show --namespace Microsoft.DBforPostgreSQL --query registrationState --output tsv)

    if [[ "$ACR_STATUS" == "Registered" && "$STORAGE_STATUS" == "Registered" && "$CONTAINER_STATUS" == "Registered" && "$POSTGRES_STATUS" == "Registered" ]]; then
        echo -e "${GREEN}All resource providers registered successfully${NC}"
        break
    fi

    echo -e "${YELLOW}Waiting for registration... (ACR: $ACR_STATUS, Storage: $STORAGE_STATUS, Containers: $CONTAINER_STATUS, PostgreSQL: $POSTGRES_STATUS)${NC}"
    sleep 10
done

# Create resource group
echo -e "${YELLOW}Creating resource group...${NC}"
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create Azure Container Registry
echo -e "${YELLOW}Creating Azure Container Registry...${NC}"
az acr create --resource-group $RESOURCE_GROUP --name $REGISTRY_NAME --sku Basic --admin-enabled true

# Get ACR login server
ACR_LOGIN_SERVER=$(az acr show --name $REGISTRY_NAME --query loginServer --output tsv)
ACR_USERNAME=$(az acr credential show --name $REGISTRY_NAME --query username --output tsv)
ACR_PASSWORD=$(az acr credential show --name $REGISTRY_NAME --query passwords[0].value --output tsv)

# Create Azure Database for PostgreSQL
echo -e "${YELLOW}Creating PostgreSQL database...${NC}"
az postgres server create \
    --resource-group $RESOURCE_GROUP \
    --name $DATABASE_SERVER_NAME \
    --location $LOCATION \
    --admin-user rag_admin \
    --admin-password "RagSystem2024!" \
    --sku-name B_Gen5_1 \
    --version 11

# Configure PostgreSQL firewall
echo -e "${YELLOW}Configuring PostgreSQL firewall...${NC}"
az postgres server firewall-rule create \
    --resource-group $RESOURCE_GROUP \
    --server $DATABASE_SERVER_NAME \
    --name "AllowAllAzureIPs" \
    --start-ip-address 0.0.0.0 \
    --end-ip-address 0.0.0.0

# Create PostgreSQL database
az postgres db create \
    --resource-group $RESOURCE_GROUP \
    --server-name $DATABASE_SERVER_NAME \
    --name rag_db

# Create Azure Storage Account
echo -e "${YELLOW}Creating Azure Storage Account...${NC}"
az storage account create \
    --name $STORAGE_ACCOUNT_NAME \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION \
    --sku Standard_LRS

# Get storage connection string
STORAGE_CONNECTION_STRING=$(az storage account show-connection-string \
    --name $STORAGE_ACCOUNT_NAME \
    --resource-group $RESOURCE_GROUP \
    --query connectionString --output tsv)

# Create storage container
az storage container create \
    --name "rag-documents" \
    --connection-string "$STORAGE_CONNECTION_STRING"

# Build and push Docker images
echo -e "${YELLOW}Building and pushing Docker images...${NC}"

# Login to ACR
az acr login --name $REGISTRY_NAME

# Build and push backend image
docker build -t $ACR_LOGIN_SERVER/rag-backend:latest -f Dockerfile.backend .
docker push $ACR_LOGIN_SERVER/rag-backend:latest

# Build and push frontend image
docker build -t $ACR_LOGIN_SERVER/rag-frontend:latest -f Dockerfile.frontend .
docker push $ACR_LOGIN_SERVER/rag-frontend:latest

# Create container group
echo -e "${YELLOW}Creating container group...${NC}"

# Construct database URL
DATABASE_URL="postgresql://rag_admin:RagSystem2024!@$DATABASE_SERVER_NAME.postgres.database.azure.com:5432/rag_db"

# Create container instances
az container create \
    --resource-group $RESOURCE_GROUP \
    --name $CONTAINER_GROUP_NAME \
    --image $ACR_LOGIN_SERVER/rag-backend:latest \
    --cpu 2 \
    --memory 4 \
    --registry-login-server $ACR_LOGIN_SERVER \
    --registry-username $ACR_USERNAME \
    --registry-password $ACR_PASSWORD \
    --environment-variables \
        DATABASE_URL="$DATABASE_URL" \
        AZURE_STORAGE_CONNECTION_STRING="$STORAGE_CONNECTION_STRING" \
        AZURE_STORAGE_CONTAINER_NAME="rag-documents" \
        GOOGLE_API_KEY="$GOOGLE_API_KEY" \
    --ports 3000 \
    --dns-name-label "rag-backend-$(date +%s)" \
    --restart-policy Always

# Wait for backend to be ready
echo -e "${YELLOW}Waiting for backend to be ready...${NC}"
sleep 60

# Get backend URL
BACKEND_URL=$(az container show --resource-group $RESOURCE_GROUP --name $CONTAINER_GROUP_NAME --query ipAddress.fqdn --output tsv)
BACKEND_URL="http://$BACKEND_URL:3000"

# Create frontend container
az container create \
    --resource-group $RESOURCE_GROUP \
    --name "$CONTAINER_GROUP_NAME-frontend" \
    --image $ACR_LOGIN_SERVER/rag-frontend:latest \
    --cpu 1 \
    --memory 2 \
    --registry-login-server $ACR_LOGIN_SERVER \
    --registry-username $ACR_USERNAME \
    --registry-password $ACR_PASSWORD \
    --environment-variables \
        API_BASE_URL="$BACKEND_URL" \
    --ports 8501 \
    --dns-name-label "rag-frontend-$(date +%s)" \
    --restart-policy Always

# Get frontend URL
FRONTEND_URL=$(az container show --resource-group $RESOURCE_GROUP --name "$CONTAINER_GROUP_NAME-frontend" --query ipAddress.fqdn --output tsv)
FRONTEND_URL="http://$FRONTEND_URL:8501"

echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo -e "${GREEN}Backend URL: $BACKEND_URL${NC}"
echo -e "${GREEN}Frontend URL: $FRONTEND_URL${NC}"
echo -e "${GREEN}Database: $DATABASE_SERVER_NAME.postgres.database.azure.com${NC}"
echo -e "${GREEN}Storage Account: $STORAGE_ACCOUNT_NAME${NC}"
echo -e "${GREEN}Container Registry: $REGISTRY_NAME${NC}"

echo -e "${YELLOW}=== Important Notes ===${NC}"
echo -e "${YELLOW}1. Make sure to set your GOOGLE_API_KEY environment variable before running this script${NC}"
echo -e "${YELLOW}2. The PostgreSQL password is: RagSystem2024!${NC}"
echo -e "${YELLOW}3. Save the connection details for future reference${NC}"
echo -e "${YELLOW}4. Monitor your Azure costs as this setup includes paid services${NC}"

echo -e "${GREEN}=== Cleanup Command ===${NC}"
echo -e "${GREEN}To delete all resources: az group delete --name $RESOURCE_GROUP --yes --no-wait${NC}"