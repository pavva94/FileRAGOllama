# GitHub Secrets Setup for Azure Container Registry

This guide will help you set up the required secrets for the GitHub Actions workflow to push Docker images to Azure Container Registry (ACR).

## Prerequisites

- Azure CLI installed (`az --version` to check)
- Access to Azure subscription
- GitHub repository with admin access

## Step 1: Get Azure Container Registry Credentials

### Option A: Using Azure CLI
```bash
# Login to Azure
az login

# Get ACR credentials
az acr credential show --name YOUR_ACR_NAME
```

### Option B: Using Azure Portal
1. Go to [portal.azure.com](https://portal.azure.com)
2. Navigate to **Container registries** → **Your ACR**
3. Go to **Access keys**
4. Enable **Admin user** if not already enabled
5. Copy the **Username** and **Password**

## Step 2: Create Azure Service Principal (Optional - for deployment)

Only needed if you want to deploy to Azure Container Instances.

```bash
# Get your subscription ID
az account show --query id --output tsv

# Create service principal (replace YOUR_SUBSCRIPTION_ID)
az ad sp create-for-rbac --name "github-actions-sp" \
  --role contributor \
  --scopes /subscriptions/YOUR_SUBSCRIPTION_ID \
  --sdk-auth
```

Copy the entire JSON output - you'll need it for `AZURE_CREDENTIALS`.

## Step 3: Add Secrets to GitHub

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret** for each secret:

### Required Secrets

| Secret Name | Value | Description |
|-------------|--------|-------------|
| `ACR_USERNAME` | Your ACR username | From Step 1 |
| `ACR_PASSWORD` | Your ACR password | From Step 1 |

### Optional Secrets (for deployment)

| Secret Name | Value | Description |
|-------------|--------|-------------|
| `AZURE_CREDENTIALS` | Full JSON from Step 2 | Service principal credentials |
| `AZURE_RESOURCE_GROUP` | Your resource group name | Where to deploy containers |

## Step 4: Update Workflow Variables

In your workflow file (`.github/workflows/acr-deploy.yml`), update these variables:

```yaml
env:
  REGISTRY: your-acr-name.azurecr.io  # Replace with your ACR URL
  IMAGE_NAME: your-app-name           # Replace with your app name
```

## Step 5: Test the Setup

1. Push code to your main branch
2. Check the **Actions** tab in your GitHub repository
3. Verify the workflow runs successfully
4. Check your ACR for the pushed image

## Troubleshooting

**ACR Login Failed:**
- Verify ACR credentials are correct
- Ensure admin user is enabled in ACR

**Azure Login Failed:**
- Check `AZURE_CREDENTIALS` JSON format
- Verify service principal has correct permissions

**Deployment Failed:**
- Ensure resource group exists
- Check service principal permissions on resource group

## Security Best Practices

- ✅ Use least privilege principle for service principal
- ✅ Rotate secrets regularly
- ✅ Monitor Azure activity logs
- ✅ Use specific resource group scopes, not subscription-wide

## Next Steps

After setup, your workflow will automatically:
1. Build Docker images on code push
2. Push to Azure Container Registry
3. Deploy to Azure Container Instances (if configured)
4. Scan for vulnerabilities
5. Generate build attestations