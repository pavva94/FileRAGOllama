# Deploy Containers from ACR and Get Frontend URL

This guide shows you how to deploy your backend and frontend containers from Azure Container Registry (ACR) and obtain a public URL for your frontend application.

## Prerequisites

- Containers already pushed to ACR
- Azure CLI installed and logged in
- Resource group created in Azure
- ACR admin credentials (if using username/password authentication)

## Get ACR Credentials

First, enable admin user and get credentials:

```bash
# Enable admin user
az acr update --name <your-acr-name> --admin-enabled true

# Get credentials
az acr credential show --name <your-acr-name>
```

Save the username and password for later use.

## Option 1: Azure Container Instances (ACI) - Quickest Setup

### Single Container Deployment

#### Deploy Backend Container
```bash
az container create \
  --resource-group <your-resource-group> \
  --name rag-backend \
  --image <your-acr-name>.azurecr.io/rag-backend:latest \
  --registry-login-server <your-acr-name>.azurecr.io \
  --registry-username <acr-username> \
  --registry-password <acr-password> \
  --dns-name-label rag-backend-unique \
  --ports 3000 \
  --environment-variables NODE_ENV=production \
  --os-type Linux  --cpu 1 --memory 1.5
```

#### Deploy Frontend Container
```bash
az container create \
  --resource-group <your-resource-group> \
  --name rag-frontend \
  --image <your-acr-name>.azurecr.io/rag-frontend:latest \
  --registry-login-server <your-acr-name>.azurecr.io \
  --registry-username <acr-username> \
  --registry-password <acr-password> \
  --dns-name-label rag-frontend-unique \
  --ports 80 \
  --os-type Linux  --cpu 1 --memory 1.5 \
  --environment-variables API_URL=http://rag-backend-unique.eastus.azurecontainer.io:3000
```

### Multi-Container Deployment (Recommended)

Create a file called `aci-deployment.yaml`:

```yaml
apiVersion: 2019-12-01
location: northeurope
name: rag-app-group
properties:
  containers:
  - name: rag-backend
    properties:
      image: <your-acr-name>.azurecr.io/rag-backend:latest
      resources:
        requests:
          cpu: 1
          memoryInGb: 1.5
      ports:
      - port: 3000
        protocol: TCP
      environmentVariables:
      - name: NODE_ENV
        value: production
      - name: PORT
        value: "3000"
  - name: rag-frontend
    properties:
      image: <your-acr-name>.azurecr.io/rag-frontend:latest
      resources:
        requests:
          cpu: 1
          memoryInGb: 1.5
      ports:
      - port: 80
        protocol: TCP
      environmentVariables:
      - name: API_URL
        value: http://localhost:3000
      - name: REACT_APP_API_URL
        value: http://localhost:3000
  osType: Linux
  ipAddress:
    type: Public
    ports:
    - protocol: TCP
      port: 80
    - protocol: TCP
      port: 3000
    dnsNameLabel: rag-app-unique
  imageRegistryCredentials:
  - server: <your-acr-name>.azurecr.io
    username: <acr-username>
    password: <acr-password>
tags: {}
type: Microsoft.ContainerInstance/containerGroups
```

Deploy the multi-container group:
```bash
az container create --resource-group <your-resource-group> --file aci-deployment.yaml
```

### Get Your Frontend URL (ACI)
```bash
# Get the frontend URL
az container show \
  --resource-group <your-resource-group> \
  --name rag-app-group \
  --query ipAddress.fqdn \
  --output tsv
```

Your frontend will be available at: `http://rag-app-unique.<region>.azurecontainer.io`

## Option 2: Azure App Service (Better for Production)

### Create App Service Plan
```bash
# Create App Service plan
az appservice plan create \
  --name rag-app-plan \
  --resource-group <your-resource-group> \
  --sku B1 \
  --is-linux
```

### Deploy Backend App Service
```bash
# Create backend web app
az webapp create \
  --resource-group <your-resource-group> \
  --plan rag-app-plan \
  --name rag-backend-app \
  --deployment-container-image-name <your-acr-name>.azurecr.io/rag-backend:latest

# Configure ACR credentials
az webapp config container set \
  --name rag-backend-app \
  --resource-group <your-resource-group> \
  --container-image-name <your-acr-name>.azurecr.io/rag-backend:latest \
  --container-registry-url https://<your-acr-name>.azurecr.io \
  --container-registry-user <acr-username> \
  --container-registry-password <acr-password>

# Set port configuration
az webapp config appsettings set \
  --resource-group <your-resource-group> \
  --name rag-backend-app \
  --settings WEBSITES_PORT=3000
```

### Deploy Frontend App Service
```bash
# Create frontend web app
az webapp create \
  --resource-group <your-resource-group> \
  --plan rag-app-plan \
  --name rag-frontend-app \
  --deployment-container-image-name <your-acr-name>.azurecr.io/rag-frontend:latest

# Configure ACR credentials
az webapp config container set \
  --name rag-frontend-app \
  --resource-group <your-resource-group> \
  --container-image-name <your-acr-name>.azurecr.io/rag-frontend:latest \
  --container-registry-url https://<your-acr-name>.azurecr.io \
  --container-registry-user <acr-username> \
  --container-registry-password <acr-password>

# Set environment variables for frontend
az webapp config appsettings set \
  --resource-group <your-resource-group> \
  --name rag-frontend-app \
  --settings API_URL=https://rag-backend-app.azurewebsites.net \
            REACT_APP_API_URL=https://rag-backend-app.azurewebsites.net
```

### Get Your Frontend URL (App Service)
Your frontend will be available at: `https://rag-frontend-app.azurewebsites.net`

## Option 3: Azure Kubernetes Service (AKS) - For Advanced Users

### Create AKS Cluster
```bash
# Create AKS cluster
az aks create \
  --resource-group <your-resource-group> \
  --name rag-aks-cluster \
  --node-count 2 \
  --generate-ssh-keys \
  --attach-acr <your-acr-name>

# Get credentials
az aks get-credentials --resource-group <your-resource-group> --name rag-aks-cluster
```

### Create Kubernetes Deployment Files

Create `k8s-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rag-backend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: rag-backend
  template:
    metadata:
      labels:
        app: rag-backend
    spec:
      containers:
      - name: rag-backend
        image: <your-acr-name>.azurecr.io/rag-backend:latest
        ports:
        - containerPort: 3000
        env:
        - name: NODE_ENV
          value: production
---
apiVersion: v1
kind: Service
metadata:
  name: rag-backend-service
spec:
  selector:
    app: rag-backend
  ports:
  - port: 3000
    targetPort: 3000
  type: ClusterIP
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rag-frontend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: rag-frontend
  template:
    metadata:
      labels:
        app: rag-frontend
    spec:
      containers:
      - name: rag-frontend
        image: <your-acr-name>.azurecr.io/rag-frontend:latest
        ports:
        - containerPort: 80
        env:
        - name: API_URL
          value: http://rag-backend-service:3000
---
apiVersion: v1
kind: Service
metadata:
  name: rag-frontend-service
spec:
  selector:
    app: rag-frontend
  ports:
  - port: 80
    targetPort: 80
  type: LoadBalancer
```

### Deploy to AKS
```bash
# Deploy applications
kubectl apply -f k8s-deployment.yaml

# Get external IP
kubectl get service rag-frontend-service
```

## Monitoring and Troubleshooting

### Check Container Status

#### Azure Container Instances
```bash
# Check container status
az container show --resource-group <your-resource-group> --name rag-frontend

# View logs
az container logs --resource-group <your-resource-group> --name rag-frontend

# Follow logs in real-time
az container attach --resource-group <your-resource-group> --name rag-frontend
```

#### Azure App Service
```bash
# Check app status
az webapp show --name rag-frontend-app --resource-group <your-resource-group>

# View logs
az webapp log tail --name rag-frontend-app --resource-group <your-resource-group>

# Download logs
az webapp log download --name rag-frontend-app --resource-group <your-resource-group>
```

### Common Issues and Solutions

#### 1. Container Won't Start
```bash
# Check container logs
az container logs --resource-group <your-resource-group> --name <container-name>

# For App Service
az webapp log tail --name <app-name> --resource-group <your-resource-group>
```

#### 2. Frontend Can't Connect to Backend
- Check environment variables are correctly set
- Verify backend URL is accessible
- Check CORS settings in backend if needed

#### 3. ACR Authentication Issues
```bash
# Verify ACR credentials
az acr credential show --name <your-acr-name>

# Test login
az acr login --name <your-acr-name>
```

## Quick Commands Reference

### Get URLs
```bash
# For Container Instances
az container show --resource-group <your-resource-group> --name <container-name> --query ipAddress.fqdn -o tsv

# For App Service
echo "https://<app-name>.azurewebsites.net"

# For AKS
kubectl get service rag-frontend-service
```

### Update Containers
```bash
# Update Container Instance
az container restart --resource-group <your-resource-group> --name <container-name>

# Update App Service
az webapp restart --name <app-name> --resource-group <your-resource-group>
```

### Scale Applications
```bash
# Scale App Service
az appservice plan update --name rag-app-plan --resource-group <your-resource-group> --sku P1V2

# Scale AKS
kubectl scale deployment rag-frontend --replicas=3
```

## Cost Optimization

### Container Instances
- Use smaller CPU/memory allocations
- Consider stopping containers when not needed
- Use consumption-based pricing

### App Service
- Use appropriate SKU (B1 for development, P1V2+ for production)
- Enable auto-scaling based on metrics
- Use staging slots for blue-green deployments

### AKS
- Use node auto-scaling
- Implement horizontal pod autoscaling
- Use spot instances for non-critical workloads

## Security Best Practices

1. **Use Managed Identity** instead of username/password when possible
2. **Enable HTTPS** for production deployments
3. **Configure proper CORS** settings
4. **Use Azure Key Vault** for secrets
5. **Enable container scanning** in ACR
6. **Configure network restrictions** if needed

## Environment Variables Template

Replace these placeholders with your actual values:

```bash
# Required variables
export RESOURCE_GROUP="your-resource-group"
export ACR_NAME="your-acr-name"
export ACR_USERNAME="your-acr-username"
export ACR_PASSWORD="your-acr-password"
export LOCATION="northeurope"  # or your preferred region

# Optional customization
export BACKEND_APP_NAME="rag-backend-app"
export FRONTEND_APP_NAME="rag-frontend-app"
export DNS_LABEL="rag-app-unique"
```

## Next Steps

After deployment, consider:
1. **Custom Domain**: Configure custom domains for production
2. **SSL Certificate**: Set up HTTPS with Let's Encrypt or Azure certificates
3. **CDN**: Add Azure CDN for better performance
4. **Monitoring**: Set up Application Insights for monitoring
5. **CI/CD**: Implement GitHub Actions or Azure DevOps pipelines
6. **Backup**: Configure backup strategies for data persistence

Choose the deployment option that best fits your needs:
- **Container Instances**: Quick testing and development
- **App Service**: Production web applications with easy scaling
- **AKS**: Complex applications requiring orchestration and advanced scaling