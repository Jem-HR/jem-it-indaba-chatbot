# Deployment Guide

## Overview

This guide covers deploying the IT Indaba 2025 WhatsApp Challenge to Google Cloud Platform using the provided infrastructure as code.

## Prerequisites

### Google Cloud Setup
```bash
# Install gcloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Authenticate
gcloud auth login
gcloud config set project jem-it-indaba-2025

# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable sqladmin.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable scheduler.googleapis.com
```

### Local Development Setup
```bash
# Clone repository
git clone <repository-url>
cd it-indada-2025

# Install dependencies
pip install -r requirements.txt

# Start local services
docker run -d -p 6379:6379 redis:7-alpine
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=password -e POSTGRES_DB=indaba_game postgres:15

# Configure environment
cp .env.example .env
# Edit .env with your credentials
```

## Configuration

### Environment Variables
Create `.env` file with:
```bash
# WhatsApp Configuration
WHATSAPP_API_TOKEN=your_whatsapp_api_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
WHATSAPP_VERIFY_TOKEN=challenge_token_2025
WHATSAPP_APP_SECRET=your_webhook_app_secret

# Database Configuration
POSTGRES_URI=postgresql://user:password@localhost:5432/indaba_game

# AI Configuration
GROQ_API_KEY=your_groq_api_key

# Analytics Configuration
POSTHOG_API_KEY=your_posthog_api_key
POSTHOG_HOST=https://eu.i.posthog.com

# Security Configuration
ENABLE_WEBHOOK_SIGNATURE_VERIFICATION=true
RATE_LIMIT_REQUESTS_PER_MINUTE=30
RATE_LIMIT_BURST_SIZE=10

# GCP Configuration
GCP_PROJECT_ID=jem-it-indaba-2025
```

### Secret Management
Store sensitive values in GCP Secret Manager:
```bash
# WhatsApp secrets
echo -n 'your_token' | gcloud secrets versions add whatsapp-api-token --data-file=-
echo -n 'your_phone_id' | gcloud secrets versions add whatsapp-phone-number-id --data-file=-
echo -n 'your_app_secret' | gcloud secrets versions add whatsapp-app-secret --data-file=-

# AI secrets
echo -n 'your_groq_key' | gcloud secrets versions add groq-api-key --data-file=-

# Analytics secrets
echo -n 'your_posthog_key' | gcloud secrets versions add posthog-api-key --data-file=-
```

## Deployment Methods

### 1. Quick Deploy (Recommended)
```bash
# Use the provided deployment script
./deploy.sh
```

This script:
- Builds Docker image
- Pushes to Container Registry
- Deploys to Cloud Run
- Configures secrets and environment variables

### 2. Manual Cloud Build
```bash
# Submit build
gcloud builds submit --config cloudbuild.yaml --project=jem-it-indaba-2025

# Deploy to Cloud Run
gcloud run deploy it-indaba-2025 \
  --image gcr.io/jem-it-indaba-2025/it-indaba-2025:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --max-instances 10 \
  --set-env-vars GCP_PROJECT_ID=jem-it-indaba-2025 \
  --set-secrets WHATSAPP_API_TOKEN=whatsapp-api-token:latest \
  --set-secrets WHATSAPP_PHONE_NUMBER_ID=whatsapp-phone-number-id:latest \
  --set-secrets WHATSAPP_APP_SECRET=whatsapp-app-secret:latest \
  --set-secrets GROQ_API_KEY=groq-api-key:latest \
  --set-secrets POSTHOG_API_KEY=posthog-api-key:latest
```

### 3. Pulumi Infrastructure
```bash
cd infra
pip install -r requirements.txt
pulumi up
```

## Infrastructure Deployment

### Database Setup
```bash
# Create Cloud SQL instance
gcloud sql instances create indaba-game-db \
  --database-version POSTGRES_15 \
  --tier db-g1-small \
  --region us-central1 \
  --storage-size 10GB \
  --storage-type SSD \
  --backup-start-time 02:00 \
  --retained-backups-count 7

# Create database
gcloud sql databases create indaba_game --instance indaba-game-db

# Create users
gcloud sql users create gameuser --instance indaba-game-db --password your_password
```

### Redis Setup
```bash
# Create Memorystore Redis instance
gcloud redis instances create indaba-game-redis \
  --region us-central1 \
  --tier basic \
  --size 1 \
  --memory-size 1GB \
  --redis-version redis_7_0
```

### VPC Connector Setup
```bash
# Create VPC connector for Cloud Run to access Cloud SQL
gcloud compute networks vpc-access connectors create indaba-connector \
  --region us-central1 \
  --range 10.8.0.0/28 \
  --subnet default \
  --min-throughput 200 \
  --max-throughput 400
```

### Cloud Scheduler Setup
```bash
# Create job for session checking
gcloud scheduler jobs create session-checker \
  --schedule "*/1 * * * *" \
  --time-zone "Africa/Johannesburg" \
  --http-endpoint https://your-app-url.run.app/check-sessions \
  --http-method POST \
  --oidc-service-account-email your-service-account@jem-it-indaba-2025.iam.gserviceaccount.com \
  --description "Check inactive user sessions"
```

## WhatsApp Configuration

### 1. Create WhatsApp Business Account
1. Go to [Meta for Developers](https://developers.facebook.com/)
2. Create WhatsApp Business Account
3. Get Phone Number ID and API Token

### 2. Configure Webhook
1. In WhatsApp Business settings, add webhook URL:
   ```
   https://your-app-url.run.app/webhook
   ```
2. Set verify token to: `challenge_token_2025`
3. Subscribe to `messages` and `message_statuses` events

### 3. Test Integration
```bash
# Test webhook verification
curl "https://your-app-url.run.app/webhook?hub.mode=subscribe&hub.challenge=test&hub.verify_token=challenge_token_2025"

# Test health endpoint
curl https://your-app-url.run.app/health
```

## Monitoring and Logging

### Health Checks
```bash
# Application health
curl https://your-app-url.run.app/health

# Database connectivity
curl https://your-app-url.run.app/health | jq '.services.postgres'
```

### Log Viewing
```bash
# View application logs
gcloud logs read "resource.type=cloud_run_revision" \
  --limit 50 \
  --format "table(timestamp,textPayload)"

# View error logs
gcloud logs read "resource.type=cloud_run_revision AND severity>=ERROR" \
  --limit 20 \
  --format "table(timestamp,textPayload)"
```

### Monitoring Setup
```bash
# Create alerting policies
gcloud monitoring policies create \
  --notification-channels projects/jem-it-indaba-2025/notificationChannels/123456789 \
  --condition-display-name "High Error Rate" \
  --condition-filter 'metric.type="run.googleapis.com/container/error_count"' \
  --condition-threshold-value 10 \
  --condition-threshold-comparison COMPARISON_GT \
  --condition-aggregations alignmentPeriod="60s",perSeriesAligner=ALIGN_RATE
```

## Scaling Configuration

### Cloud Run Scaling
```bash
# Update scaling settings
gcloud run services update it-indaba-2025 \
  --region us-central1 \
  --min-instances 0 \
  --max-instances 10 \
  --cpu-throttling
```

### Database Scaling
```bash
# Upgrade database tier if needed
gcloud sql instances patch indaba-game-db \
  --tier db-g1-medium \
  --memory-size 4GB
```

## Security Configuration

### SSL/TLS
- All endpoints use HTTPS automatically
- WhatsApp requires TLS for webhooks
- Database connections use SSL

### IAM Roles
```bash
# Create service account for Cloud Run
gcloud iam service-accounts create indaba-run-sa \
  --display-name "IT Indaba Run Service Account"

# Grant necessary roles
gcloud projects add-iam-policy-binding jem-it-indaba-2025 \
  --member="serviceAccount:indaba-run-sa@jem-it-indaba-2025.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"

gcloud projects add-iam-policy-binding jem-it-indaba-2025 \
  --member="serviceAccount:indaba-run-sa@jem-it-indaba-2025.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### Firewall Rules
```bash
# Cloud SQL requires authorized networks
gcloud sql instances patch indaba-game-db \
  --authorized-networks 0.0.0.0/0  # For testing only
```

## Troubleshooting

### Common Issues

#### 1. Webhook Verification Fails
```bash
# Check verify token
echo $WHATSAPP_VERIFY_TOKEN

# Check webhook URL
curl -v "https://your-app-url.run.app/webhook?hub.mode=subscribe&hub.challenge=test&hub.verify_token=challenge_token_2025"
```

#### 2. Database Connection Issues
```bash
# Test database connectivity
gcloud sql connect indaba-game-db --user=gameuser

# Check connection string
echo $POSTGRES_URI
```

#### 3. WhatsApp API Issues
```bash
# Test WhatsApp API directly
curl -X POST "https://graph.facebook.com/v18.0/YOUR_PHONE_ID/messages" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "messaging_product": "whatsapp",
    "to": "YOUR_PHONE_NUMBER",
    "type": "text",
    "text": {"body": "Test message"}
  }'
```

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run locally with debug
uvicorn app.main:app --reload --log-level debug --port 8080
```

## Performance Optimization

### Database Optimization
```sql
-- Add indexes for better performance
CREATE INDEX CONCURRENTLY idx_users_last_active ON game_users(last_active);
CREATE INDEX CONCURRENTLY idx_messages_phone_timestamp ON game_messages(phone_number, timestamp);
CREATE INDEX CONCURRENTLY idx_winners_completed_at ON game_winners(completed_at);
```

### Caching Strategy
- Redis for session state
- Application-level caching for static data
- CDN for static assets

### Load Testing
```bash
# Install artillery
npm install -g artillery

# Run load test
artillery run load-test-config.yml
```

## Backup and Recovery

### Database Backups
```bash
# List backups
gcloud sql backups list --instance indaba-game-db

# Create manual backup
gcloud sql backups create --instance indaba-game-db backup-$(date +%Y%m%d-%H%M%S)

# Restore from backup
gcloud sql backups restore BACKUP_ID --restore-instance indaba-game-db-restore
```

### Disaster Recovery
1. **Data Recovery**: Restore from automated backups
2. **Infrastructure Recovery**: Use Pulumi to recreate resources
3. **Configuration Recovery**: Secrets stored in Secret Manager

## Maintenance

### Regular Tasks
- Monitor error rates and performance
- Update dependencies and security patches
- Review and rotate secrets
- Clean up old logs and backups

### Update Process
```bash
# 1. Update code
git pull origin main

# 2. Update dependencies
pip install -r requirements.txt

# 3. Run tests
python -m pytest

# 4. Deploy
./deploy.sh

# 5. Verify deployment
curl https://your-app-url.run.app/health
```

## Support

### Getting Help
- Check Cloud Logging for error messages
- Review this documentation
- Monitor WhatsApp Business dashboard
- Check GCP project status

### Emergency Contacts
- GCP Support: https://cloud.google.com/support
- WhatsApp Business Support: https://developers.facebook.com/support/
- Internal team: [contact information]