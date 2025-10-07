#!/bin/bash

# Deployment script for IT Indaba 2025 WhatsApp Challenge
# Uses Cloud Build for building and deploying to GCP

set -e

PROJECT_ID="${GCP_PROJECT_ID:-jem-it-indaba-2025}"
REGION="${GCP_REGION:-us-central1}"

echo "🚀 Deploying IT Indaba 2025 WhatsApp Challenge"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI is not installed"
    echo "Please install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
    echo "❌ Error: Not authenticated with gcloud"
    echo "Run: gcloud auth login"
    exit 1
fi

# Set project
echo "📝 Setting GCP project..."
gcloud config set project "$PROJECT_ID"

# Submit build
echo "🔨 Building and deploying with Cloud Build..."
gcloud builds submit \
    --config cloudbuild.yaml \
    --project="$PROJECT_ID" \
    --substitutions=_REGION="$REGION"

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 Next steps:"
echo "1. Update WhatsApp secrets:"
echo "   echo -n 'YOUR_TOKEN' | gcloud secrets versions add whatsapp-api-token --data-file=- --project=$PROJECT_ID"
echo "   echo -n 'YOUR_PHONE_ID' | gcloud secrets versions add whatsapp-phone-number-id --data-file=- --project=$PROJECT_ID"
echo ""
echo "2. Get your webhook URL:"
echo "   gcloud run services describe it-indaba-chatbot --region=$REGION --format='value(status.url)'"
echo ""
echo "3. Configure WhatsApp webhook in Meta Developer Console"
echo ""
