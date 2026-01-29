# Web Hosting Setup Guide

Complete guide for deploying the QMS Trading Bot to cloud platforms (AWS, GCP, Azure).

## Overview

The bot can be deployed to various cloud platforms using container-based deployments with external schedulers. This guide covers setup for AWS, GCP, and Azure.

## Prerequisites

- Cloud platform account (AWS, GCP, or Azure)
- Docker installed locally (for building images)
- Broker account (Alpaca, Robinhood, or Webull)
- Leaderboard API access

## General Setup Steps

1. **Build Docker image**
2. **Push to container registry**
3. **Deploy to container service**
4. **Configure external scheduler**
5. **Set environment variables**

## AWS Deployment

### Step 1: Build and Push to ECR

1. **Create ECR repository:**
   ```bash
   aws ecr create-repository --repository-name qms-trading-bot
   ```

2. **Authenticate Docker:**
   ```bash
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
   ```

3. **Build and tag image:**
   ```bash
   docker build -t qms-trading-bot .
   docker tag qms-trading-bot:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/qms-trading-bot:latest
   ```

4. **Push to ECR:**
   ```bash
   docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/qms-trading-bot:latest
   ```

### Step 2: Deploy to ECS/Fargate

1. **Create ECS cluster** (via console or CLI)
2. **Create task definition** with your Docker image
3. **Create service** or run as scheduled task
4. **Configure environment variables** (see Configuration section below)

### Step 3: Set Up EventBridge Scheduler

1. **Create EventBridge rule:**
   - Name: `qms-trading-bot-rebalance`
   - Schedule: `cron(0 0 ? * MON *)` (Mondays at midnight)
   - Target: ECS Task or API Gateway endpoint

2. **Configure target:**
   - If using API Gateway: POST to `http://your-container:8080/rebalance`
   - Add header: `Authorization: Bearer <WEBHOOK_SECRET>` (if configured)

### Complete Environment Variables Reference

Set environment variables in ECS task definition or use AWS Systems Manager Parameter Store / Secrets Manager.

#### Required Variables

**Leaderboard API:**
```bash
LEADERBOARD_API_URL=your-leaderboard-api-url
LEADERBOARD_API_TOKEN=your-leaderboard-api-token  # Store in Secrets Manager
```

**Broker Type:**
```bash
BROKER_TYPE=alpaca  # Options: alpaca, robinhood, webull
```

**Scheduler (Required for cloud deployments):**
```bash
SCHEDULER_MODE=external
WEBHOOK_PORT=8080
WEBHOOK_SECRET=your-secret-token  # Strongly recommended - Store in Secrets Manager
```

#### Broker-Specific Variables

**Alpaca (required if BROKER_TYPE=alpaca):**
```bash
ALPACA_API_KEY=your-api-key  # Store in Secrets Manager
ALPACA_API_SECRET=your-api-secret  # Store in Secrets Manager
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # or https://api.alpaca.markets for live
```

**Robinhood (required if BROKER_TYPE=robinhood):**
```bash
ROBINHOOD_USERNAME=your-email@example.com  # Store in Secrets Manager
ROBINHOOD_PASSWORD=your-password  # Store in Secrets Manager
ROBINHOOD_MFA_CODE=optional-mfa-code  # Optional: If 2FA is enabled - Store in Secrets Manager
```

**Webull (required if BROKER_TYPE=webull):**
```bash
WEBULL_APP_KEY=your-app-key  # Store in Secrets Manager
WEBULL_APP_SECRET=your-app-secret  # Store in Secrets Manager
WEBULL_ACCOUNT_ID=optional-account-id  # Optional: Will use first account if not provided
WEBULL_REGION=US  # Optional: US, HK, or JP (default: US)
```

#### Trading Configuration

```bash
INITIAL_CAPITAL=10000.0  # Initial capital amount for portfolio allocation (in USD)
```

#### Email Configuration

**Basic Email Settings:**
```bash
EMAIL_ENABLED=true
EMAIL_RECIPIENT=your-email@example.com
EMAIL_PROVIDER=ses  # Options: smtp, sendgrid, ses (ses recommended for AWS)
```

**SMTP Configuration (if EMAIL_PROVIDER=smtp):**
```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com  # Store in Secrets Manager
SMTP_PASSWORD=your-app-password  # Store in Secrets Manager
SMTP_FROM_EMAIL=your-email@gmail.com
```

**SendGrid Configuration (if EMAIL_PROVIDER=sendgrid):**
```bash
SENDGRID_API_KEY=your-sendgrid-api-key  # Store in Secrets Manager
SENDGRID_FROM_EMAIL=your-verified-email@example.com
```

**AWS SES Configuration (if EMAIL_PROVIDER=ses - recommended for AWS):**
```bash
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key  # Store in Secrets Manager
AWS_SECRET_ACCESS_KEY=your-secret-key  # Store in Secrets Manager
SES_FROM_EMAIL=your-verified-email@example.com
```

#### Persistence Configuration (Optional)

```bash
PERSISTENCE_ENABLED=true  # Optional: Auto-enabled if Firebase credentials are configured
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_CREDENTIALS_JSON='{"type":"service_account","project_id":"...","private_key":"..."}'  # Full JSON content - Store in Secrets Manager
```

#### Multiple Portfolio Configuration (Optional)

**Default Behavior:**
If no portfolio configuration is provided, the bot **defaults to trading SP400** (S&P 400 MidCap) with the `INITIAL_CAPITAL` amount.

**Method 1: Environment Variables:**
```bash
TRADE_INDICES=SP400,SP500,SP600  # If not set, defaults to SP400
INITIAL_CAPITAL_SP400=50000
INITIAL_CAPITAL_SP500=100000
INITIAL_CAPITAL_SP600=30000
```

**Method 2: JSON Configuration:**
```bash
PORTFOLIO_CONFIG='[{"portfolio_name":"SP400","index_id":"13","initial_capital":50000,"enabled":true}]'
```

**Note:** To explicitly configure a single SP400 portfolio, you can either:
- Leave `TRADE_INDICES` unset (defaults to SP400)
- Set `TRADE_INDICES=SP400`

#### Security Configuration

```bash
MASK_FINANCIAL_AMOUNTS=true  # Optional: Mask financial amounts in logs (default: true)
```

**Security Best Practices:**
- Use AWS Secrets Manager for sensitive credentials (API keys, passwords, tokens)
- Use IAM roles for ECS tasks (avoid hardcoding credentials)
- Enable VPC endpoints for private networking
- Use security groups to restrict access
- Never commit secrets to version control

## GCP Deployment

### Step 1: Build and Push to GCR/Artifact Registry

1. **Authenticate Docker:**
   ```bash
   gcloud auth configure-docker
   ```

2. **Build and tag image:**
   ```bash
   docker build -t qms-trading-bot .
   docker tag qms-trading-bot:latest gcr.io/<project-id>/qms-trading-bot:latest
   # Or for Artifact Registry:
   # docker tag qms-trading-bot:latest <region>-docker.pkg.dev/<project-id>/<repo>/qms-trading-bot:latest
   ```

3. **Push to registry:**
   ```bash
   docker push gcr.io/<project-id>/qms-trading-bot:latest
   ```

### Step 2: Deploy to Cloud Run

1. **Deploy service:**
   ```bash
   gcloud run deploy qms-trading-bot \
     --image gcr.io/<project-id>/qms-trading-bot:latest \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --set-env-vars="SCHEDULER_MODE=external,WEBHOOK_PORT=8080"
   ```

2. **Note the service URL** (e.g., `https://qms-trading-bot-xxx.run.app`)

### Step 3: Set Up Cloud Scheduler

1. **Create Cloud Scheduler job:**
   ```bash
   gcloud scheduler jobs create http qms-trading-bot-rebalance \
     --schedule="0 0 * * 1" \
     --uri="https://qms-trading-bot-xxx.run.app/rebalance" \
     --http-method=POST \
     --headers="Authorization=Bearer YOUR_WEBHOOK_SECRET" \
     --time-zone="America/New_York"
   ```

### Configuration

Set environment variables in Cloud Run or use Secret Manager for sensitive values.

**All variables are the same as AWS (see [Complete Environment Variables Reference](#complete-environment-variables-reference) above).**

**GCP-Specific Notes:**
- Use Secret Manager for sensitive credentials (API keys, passwords, tokens)
- Use service accounts with minimal permissions
- Environment variables can be set via Cloud Run console or `gcloud` CLI

**Security Best Practices:**
- Use Secret Manager for sensitive credentials
- Use service accounts with minimal permissions
- Enable VPC connector for private networking (if needed)
- Use Cloud Armor for DDoS protection

## Azure Deployment

### Step 1: Build and Push to ACR

1. **Create ACR:**
   ```bash
   az acr create --resource-group <resource-group> --name <registry-name> --sku Basic
   ```

2. **Login to ACR:**
   ```bash
   az acr login --name <registry-name>
   ```

3. **Build and push:**
   ```bash
   az acr build --registry <registry-name> --image qms-trading-bot:latest .
   ```

### Step 2: Deploy to Container Instances

1. **Create container instance:**
   ```bash
   az container create \
     --resource-group <resource-group> \
     --name qms-trading-bot \
     --image <registry-name>.azurecr.io/qms-trading-bot:latest \
     --registry-login-server <registry-name>.azurecr.io \
     --environment-variables SCHEDULER_MODE=external WEBHOOK_PORT=8080
   ```

2. **Get container IP:**
   ```bash
   az container show --resource-group <resource-group> --name qms-trading-bot --query ipAddress.ip
   ```

### Step 3: Set Up Logic Apps Scheduler

1. **Create Logic App** in Azure Portal
2. **Add Recurrence trigger:** Weekly on Monday
3. **Add HTTP action:**
   - Method: POST
   - URI: `http://<container-ip>:8080/rebalance`
   - Headers: `Authorization: Bearer <WEBHOOK_SECRET>`

### Configuration

Set environment variables in Container Instances or use Key Vault for sensitive values.

**All variables are the same as AWS (see [Complete Environment Variables Reference](#complete-environment-variables-reference) above).**

**Azure-Specific Notes:**
- Use Key Vault for sensitive credentials (API keys, passwords, tokens)
- Use managed identities for authentication
- Environment variables can be set via Azure Portal or Azure CLI

**Security Best Practices:**
- Use Key Vault for sensitive credentials
- Use managed identities for authentication
- Enable network security groups
- Use private endpoints for private networking

## Common Configuration

All platforms use the same environment variables. See [Complete Environment Variables Reference](#complete-environment-variables-reference) above for the full list.

### Platform-Specific Secret Management

**AWS:**
- Use AWS Secrets Manager or Systems Manager Parameter Store
- Reference secrets in ECS task definitions
- Use IAM roles for ECS tasks

**GCP:**
- Use Secret Manager
- Reference secrets in Cloud Run environment variables
- Use service accounts with minimal permissions

**Azure:**
- Use Key Vault
- Reference secrets in Container Instances environment variables
- Use managed identities for authentication

## Testing

After deployment, test the webhook endpoint:

```bash
curl -X POST http://your-service-url/rebalance \
  -H "Authorization: Bearer YOUR_WEBHOOK_SECRET"
```

Or test health check:
```bash
curl http://your-service-url/health
```

## Troubleshooting

### Container Not Starting
- Check container logs: `docker logs <container-id>` or platform-specific log viewer
- Verify environment variables are set correctly
- Check resource limits (CPU/memory)

### Scheduler Not Triggering
- Verify scheduler configuration (cron expression, timezone)
- Check scheduler logs for errors
- Verify webhook endpoint is accessible
- Test webhook manually with curl

### Authentication Issues
- Verify `WEBHOOK_SECRET` matches in scheduler and application
- Check authorization headers are set correctly
- Review security group/firewall rules

### Broker Connection Issues
- Verify API keys are correct
- Check network connectivity from container
- Review broker account status
- Ensure paper trading is enabled for testing

## Cost Optimization

- **AWS:** Use Fargate Spot for non-critical workloads
- **GCP:** Use Cloud Run (pay per request) for cost efficiency
- **Azure:** Use Container Instances with auto-shutdown
- **All:** Consider using smaller instance sizes for scheduled tasks

## Next Steps

- 📖 See [Local Setup](LOCAL_SETUP.md) for local development
- 📖 See [GitHub Actions Setup](GITHUB_ACTIONS_DEPLOYMENT.md) for free scheduled runs
- 📖 See [Persistence Scenarios](PERSISTENCE_SCENARIOS.md) for detailed persistence examples
