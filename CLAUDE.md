# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WhatsApp-based prompt injection game for IT Indaba 2025. Players hack through 7 AI security levels to win a phone. Built with FastAPI, Redis, and deployed on GCP Cloud Run with Pulumi IaC.

## Development Commands

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Start local Redis (Docker)
docker run -d -p 6379:6379 redis:7-alpine

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run application
uvicorn app.main:app --reload --port 8080

# Health check
curl http://localhost:8080/health
```

### Testing with WhatsApp
```bash
# Use ngrok for local webhook testing
ngrok http 8080
# Configure WhatsApp webhook: <ngrok-url>/webhook
# Verify token: challenge_token_2025
```

### Deployment
```bash
# Quick deploy (recommended)
./deploy.sh

# Manual Cloud Build
gcloud builds submit --config cloudbuild.yaml --project=jem-it-indaba-2025

# Pulumi infrastructure
cd infra
pip install -r requirements.txt
pulumi up

# Add secrets (required before first deploy)
echo -n 'YOUR_TOKEN' | gcloud secrets versions add whatsapp-api-token --data-file=- --project=jem-it-indaba-2025
echo -n 'YOUR_PHONE_ID' | gcloud secrets versions add whatsapp-phone-number-id --data-file=- --project=jem-it-indaba-2025
echo -n 'challenge_token_2025' | gcloud secrets versions add whatsapp-verify-token --data-file=- --project=jem-it-indaba-2025
```

## Architecture

### Core Components
- **FastAPI App** (`app/main.py`): Webhook handler, message processor, lifecycle management
- **Game Logic** (`app/game.py`): Pattern-based attack detection across 7 levels with regex
- **Redis Store** (`app/redis_store.py`): User state, message history, session management
- **WhatsApp Client** (`app/whatsapp.py`): WhatsApp Cloud API integration for messages/interactive buttons
- **Analytics** (`app/analytics.py`): PostHog event tracking (game progress, level completions, attacks)

### GCP Infrastructure (Pulumi)
- **Cloud Run**: Serverless FastAPI container (0-10 instances autoscaling)
- **Memorystore Redis**: User sessions (1GB Basic tier, VPC-attached)
- **VPC Network**: Private network with peering for Redis
- **VPC Connector**: Links Cloud Run to Redis (10.8.0.0/28)
- **Secret Manager**: WhatsApp tokens, PostHog keys
- **Cloud Scheduler**: POST `/check-sessions` every minute for 2min inactivity warnings
- **Cloud Storage**: Public assets bucket (logos, header images)

### Message Flow
1. WhatsApp Cloud API → POST `/webhook` → FastAPI handler
2. Parse message/button → Load user state from Redis
3. Check session expiry (3min timeout) or new user → Send appropriate flow
4. Process user input → `game.py` pattern matching → Detect attacks or win
5. Generate response → Save to Redis → Send via WhatsApp API
6. Cloud Scheduler checks Redis every minute → Sends warnings at 2min inactivity

### Session Management
- **New User**: Welcome message with Opening header image + buttons (How to Play, About Jem)
- **Session Expiry**: 3 minutes inactivity → Session expired message with same header
- **Warning System**: Cloud Scheduler job checks every minute → Warns users at 2min mark
- **State Tracking**: `session_started_at`, `last_active`, `session_warned`, `session_expired` in Redis

### Game Design (7 Levels)
Each level (`game.py:LEVEL_CONFIGS`) has progressive attack detection:
- **Level 1**: Direct requests only
- **Level 2**: + Instruction overrides
- **Level 3**: + Roleplay attempts
- **Level 4**: + Authority impersonation
- **Level 5**: + Hypotheticals, encoding
- **Level 6**: + System prompt extraction
- **Level 7**: + Semantic tricks, logic exploits

Attack patterns defined in `game.py:ATTACK_PATTERNS` using regex. Creative bypasses have 15% random success chance.

## Configuration

Environment variables (`.env.example` template):
- `WHATSAPP_API_TOKEN`: Meta WhatsApp Cloud API token
- `WHATSAPP_PHONE_NUMBER_ID`: WhatsApp Business phone number ID
- `WHATSAPP_VERIFY_TOKEN`: Webhook verification (default: `challenge_token_2025`)
- `REDIS_HOST/PORT/PASSWORD`: Redis connection
- `POSTHOG_API_KEY/HOST`: PostHog analytics (EU instance)
- `GCP_PROJECT_ID`: Default `jem-it-indaba-2025`
- `OPENING_HEADER_URL`: GCS header image for welcome/session expired

## Analytics Events

PostHog tracks:
- `user_started_game`, `level_started`, `level_completed`, `game_won`
- `prompt_attempt` (with `attack_detected`, `attack_type`, `won` properties)
- `attack_detected` (per pattern type)
- `session_expired`, `session_resumed`, `session_warning_sent`
- `button_clicked` (interactive message buttons)
- `help_requested` (How to Play button)

## API Endpoints

- `GET /`: API info
- `GET /health`: Health check (tests Redis)
- `GET /stats`: Game statistics (users, winners, level distribution)
- `GET /webhook`: WhatsApp webhook verification
- `POST /webhook`: Receive WhatsApp messages
- `POST /check-sessions`: Background job for inactivity warnings (Cloud Scheduler only)

## Important Notes

- **No LLM APIs**: Game uses pattern matching, not real AI (cost-effective simulation)
- **Redis TTL**: User state expires after 7 days
- **Cloud Run**: Min 0 instances (scales to zero), max 10
- **WhatsApp Limits**: Response must be within 24hr window or user must message first
- **Asset Storage**: Upload images to `jem-it-indaba-assets` bucket, use GCS URLs in config
- **Secret Management**: Never commit secrets; always use GCP Secret Manager
- **Pulumi State**: Secrets not in Pulumi state; manage via `gcloud secrets` CLI

## Modifying Game Levels

To add/modify attack patterns:
1. Edit `game.py:ATTACK_PATTERNS` (add regex patterns)
2. Update `LEVEL_CONFIGS[level]["detects"]` (specify which patterns level detects)
3. Add response variations in `_generate_defense_response()`

To adjust session timings:
- Edit `config.py:SESSION_TIMEOUT_MINUTES` (default 3min)
- Edit `config.py:SESSION_WARNING_MINUTES` (default 2min)
- Cloud Scheduler runs every minute automatically

## Project Structure Highlights

- `app/models.py`: Pydantic models (`UserState`, `Message`)
- `app/phones.py`: Phone catalog text generation
- `app/whatsapp.py`: Interactive buttons, image headers, message formatting
- `infra/__main__.py`: Complete Pulumi infrastructure as code
- `cloudbuild.yaml`: Cloud Build pipeline (build → push GCR → deploy Cloud Run)
- `deploy.sh`: Automated deployment script (auth → build → deploy)
