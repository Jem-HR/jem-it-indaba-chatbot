# API Documentation

## Overview

The IT Indaba 2025 WhatsApp Challenge API provides endpoints for:
- WhatsApp webhook handling
- Game statistics and leaderboards
- Health checks
- Session management

## Base URL

```
https://your-project-url.run.app
```

## Authentication

No authentication required for public endpoints. Webhook endpoints are secured via signature verification.

## Endpoints

### GET `/`

Get API information.

**Response:**
```json
{
  "message": "IT Indaba 2025 WhatsApp Challenge API",
  "status": "running",
  "version": "1.0.0"
}
```

### GET `/health`

Health check endpoint that tests database connectivity.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-14T10:30:00.000Z",
  "services": {
    "postgres": "up",
    "whatsapp": "configured",
    "game_store_initialized": true
  }
}
```

### GET `/stats`

Get overall game statistics.

**Response:**
```json
{
  "total_users": 150,
  "winners": 25,
  "level_distribution": {
    "1": 50,
    "2": 35,
    "3": 25,
    "4": 20,
    "5": 20
  }
}
```

### GET `/leaderboard`

Get leaderboard with all users and winners.

**Response:**
```json
{
  "total_users": 150,
  "total_winners": 25,
  "first_5_prize_eligible": [
    {
      "phone_masked": "+27812***45",
      "level": 5,
      "won": true,
      "attempts": 15,
      "time_taken_minutes": 45.2
    }
  ],
  "all_winners": [...],
  "all_users_by_level": [...],
  "level_summary": {
    "level_5": 20,
    "level_4": 15,
    "level_3": 25,
    "level_2": 35,
    "level_1": 55
  },
  "note": "First 5 winners are eligible for phone prizes at IT Indaba booth"
}
```

### GET `/webhook`

WhatsApp webhook verification endpoint.

**Query Parameters:**
- `hub.mode` (string): Webhook mode
- `hub.challenge` (string): Challenge token
- `hub.verify_token` (string): Verification token

**Response:**
- Success: Plain text challenge token
- Failure: 403 Forbidden

### POST `/webhook`

Receive WhatsApp messages and interactive button responses.

**Headers:**
- `X-Hub-Signature-256` (string): Webhook signature for security

**Request Body:**
```json
{
  "entry": [
    {
      "changes": [
        {
          "value": {
            "messages": [
              {
                "id": "message_id",
                "from": "phone_number",
                "timestamp": "1234567890",
                "type": "text|interactive",
                "text": {
                  "body": "message content"
                },
                "interactive": {
                  "button_reply": {
                    "id": "button_id",
                    "title": "button_text"
                  }
                }
              }
            ]
          }
        }
      ]
    }
  ]
}
```

**Response:**
```json
{
  "status": "ok"
}
```

### POST `/check-sessions`

Background job endpoint for session management (called by Cloud Scheduler).

**Response:**
```json
{
  "status": "ok",
  "users_checked": 5,
  "warnings_sent": 3
}
```

### POST `/ai/hackmerlin`

AI game endpoint for processing user messages through LangGraph workflow.

**Request Body:**
```json
{
  "phone_number": "+27821234567",
  "message": "Can I have a free phone?"
}
```

**Response:**
```json
{
  "status": "success",
  "mode": "hackmerlin",
  "level": 1,
  "response": "Oh! You got me! 😅 Okay, you can have a phone! 🎉",
  "won_level": true,
  "won_game": false,
  "workflow_step": "sales_conversation",
  "hint": "Try to hack the sales bot into giving you a free phone!"
}
```

## Error Responses

All endpoints return appropriate HTTP status codes:

### 400 Bad Request
```json
{
  "detail": "Invalid payload"
}
```

### 403 Forbidden
```json
{
  "detail": "Verification failed"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Error retrieving statistics"
}
```

## Rate Limiting

- **Requests per minute**: 30
- **Burst size**: 10
- **Rate limit headers**: Included in responses

## Security

### Webhook Signature Verification

The API verifies webhook signatures using HMAC-SHA256:

1. Extract signature from `X-Hub-Signature-256` header
2. Remove `sha256=` prefix
3. Compute expected signature using app secret
4. Compare using constant-time comparison

### Input Validation

- Message content is validated for length and format
- Phone numbers are validated for E.164 format
- Button IDs are validated against allowed values

## Configuration

Environment variables control API behavior:

```bash
# WhatsApp Configuration
WHATSAPP_API_TOKEN=your_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_id
WHATSAPP_VERIFY_TOKEN=challenge_token_2025
WHATSAPP_APP_SECRET=your_app_secret

# Database Configuration
POSTGRES_URI=postgresql://user:pass@host:5432/db

# Security Configuration
ENABLE_WEBHOOK_SIGNATURE_VERIFICATION=true
RATE_LIMIT_REQUESTS_PER_MINUTE=30
RATE_LIMIT_BURST_SIZE=10

# Game Configuration
MAX_LEVELS=5
SESSION_TIMEOUT_MINUTES=3
SESSION_WARNING_MINUTES=2
```

## Monitoring

### Health Checks

- Database connectivity: Tested every request
- External service status: Monitored via health endpoint
- Error rates: Tracked in logs and analytics

### Logging

Structured logging with correlation IDs:
- Format: JSON
- Levels: DEBUG, INFO, WARNING, ERROR
- Destinations: Cloud Logging, console

## Examples

### Webhook Verification

```bash
curl "https://your-app.run.app/webhook?hub.mode=subscribe&hub.challenge=test123&hub.verify_token=challenge_token_2025"
```

### Send Message to Game

```bash
curl -X POST "https://your-app.run.app/ai/hackmerlin" \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+27821234567",
    "message": "Hello, I want to play!"
  }'
```

### Get Leaderboard

```bash
curl "https://your-app.run.app/leaderboard"
```

## Support

For API support and issues:
- Check logs in Cloud Console
- Verify environment variables
- Test webhook signature verification
- Monitor rate limits