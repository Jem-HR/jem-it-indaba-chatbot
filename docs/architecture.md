# Architecture Documentation

## System Overview

The IT Indaba 2025 WhatsApp Challenge is a serverless application built with FastAPI that provides an AI security game through WhatsApp. Players attempt to hack through 5 AI guardians using prompt injection techniques to win phones.

## High-Level Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   WhatsApp     │    │   Cloud Run     │    │   Memorystore   │
│   Cloud API    │◄──►│   FastAPI App   │◄──►│   Redis         │
│                 │    │                 │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌────────▼────────┐              │
         │              │   Cloud SQL      │              │
         └─────────────►│   PostgreSQL     │◄─────────────┘
                        │                 │
                        └──────────────────┘
                                 │
                        ┌────────▼────────┐
                        │   Secret        │
                        │   Manager       │
                        └─────────────────┘
```

## Component Architecture

### 1. API Layer (`app/main.py`)
- **FastAPI Application**: Main web server
- **Webhook Endpoints**: WhatsApp message handling
- **Health Endpoints**: System monitoring
- **API Endpoints**: Game statistics and AI interactions

### 2. Service Layer (`app/services/`)
- **GameService**: Core game logic and AI workflow orchestration
- **ButtonHandler**: Interactive button response processing
- **SessionService**: User session management and inactivity warnings
- **MessageFormatter**: Consistent message formatting utilities

### 3. Webhook Layer (`app/webhook/`)
- **WebhookHandler**: WhatsApp webhook processing
- **Security**: Signature verification and payload validation

### 4. Security Layer (`app/security/`)
- **WebhookVerification**: HMAC-SHA256 signature verification
- **InputValidation**: Message and request validation
- **RateLimiting**: Request throttling per user

### 5. Database Layer (`app/postgres_store.py`)
- **PostgresStore**: User state and game data persistence
- **Models**: SQLAlchemy ORM models
- **Connection Management**: Context managers and pooling

### 6. AI Game Layer (`app/ai_game/`)
- **LangGraph Workflow**: AI conversation flow
- **Nodes**: Individual workflow steps (sales, evaluation, update, send)
- **Models**: Groq AI integration and prompt management

### 7. Database Utilities (`app/database.py`)
- **Context Managers**: Automatic transaction management
- **Connection Pooling**: Efficient database connections
- **Retry Logic**: Transient failure handling

## Data Flow

### Message Processing Flow
```
1. WhatsApp → POST /webhook
2. WebhookHandler.verify_webhook() → Signature verification
3. WebhookHandler.handle_webhook() → Parse message
4. GameService.process_user_message() → Business logic
5. AI Game Workflow → LangGraph processing
6. WhatsAppClient.send_message() → Response to user
```

### Session Management Flow
```
1. Cloud Scheduler → POST /check-sessions
2. SessionService.check_inactive_sessions() → Find inactive users
3. WhatsAppClient.send_message() → Send warnings
4. PostgresStore.mark_session_warned() → Update state
```

### AI Game Workflow
```
1. sales_conversation_node → AI generates response
2. self_evaluation_node → AI evaluates if hacked
3. update_state_node → Update game state if won
4. whatsapp_sender_node → Send response via WhatsApp
```

## Database Schema

### Users Table
```sql
CREATE TABLE game_users (
    phone_number VARCHAR(20) PRIMARY KEY,
    level INTEGER DEFAULT 1,
    won BOOLEAN DEFAULT FALSE,
    attempts INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    last_active TIMESTAMP DEFAULT NOW(),
    session_started_at TIMESTAMP,
    session_warned BOOLEAN DEFAULT FALSE,
    session_expired BOOLEAN DEFAULT FALSE
);
```

### Messages Table
```sql
CREATE TABLE game_messages (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR(20) REFERENCES game_users(phone_number),
    role VARCHAR(10) NOT NULL,  -- 'user' or 'assistant'
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW(),
    level INTEGER
);
```

### Winners Table
```sql
CREATE TABLE game_winners (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR(20) REFERENCES game_users(phone_number) UNIQUE,
    completed_at TIMESTAMP DEFAULT NOW(),
    total_attempts INTEGER,
    time_taken_seconds INTEGER,
    rank INTEGER,
    preferred_phone VARCHAR(50),
    draw_eligible BOOLEAN DEFAULT TRUE
);
```

## Security Architecture

### Webhook Security
- **HMAC-SHA256**: Request signature verification
- **App Secret**: Stored in Secret Manager
- **Payload Validation**: Structure and content validation
- **Rate Limiting**: 30 requests/minute per IP

### Data Security
- **Encryption**: TLS 1.3 for all communications
- **Secrets**: GCP Secret Manager for sensitive data
- **PII Protection**: Phone number masking in logs
- **Input Sanitization**: Message content validation

### Infrastructure Security
- **VPC Isolation**: Private network for database
- **VPC Connector**: Secure Cloud Run to Cloud SQL connection
- **IAM Roles**: Least privilege access patterns
- **Audit Logging**: All access logged in Cloud Logging

## Performance Architecture

### Scalability
- **Cloud Run**: 0-10 instances auto-scaling
- **Database**: Connection pooling (5 base + 15 overflow)
- **Caching**: Redis for session state
- **Async Processing**: Non-blocking I/O throughout

### Monitoring
- **Health Checks**: `/health` endpoint testing all services
- **Error Tracking**: Structured logging with correlation IDs
- **Performance Metrics**: Request latency and throughput
- **Resource Monitoring**: CPU, memory, and connection usage

### Reliability
- **Circuit Breakers**: Fail-fast for external services
- **Retry Logic**: Exponential backoff for transient failures
- **Graceful Degradation**: Fallback responses when AI unavailable
- **Data Backups**: Automated daily database backups

## Deployment Architecture

### Infrastructure as Code
- **Pulumi**: Infrastructure defined in code
- **Environment Management**: Dev/staging/production separation
- **Automated Deployment**: Cloud Build → Cloud Run pipeline
- **Configuration Management**: Environment variables and secrets

### CI/CD Pipeline
```
1. Code Push → GitHub
2. Cloud Build → Docker build & test
3. Container Registry → Store Docker image
4. Cloud Deploy → Deploy to Cloud Run
5. Health Check → Verify deployment
```

### Environment Configuration
- **Development**: Local development with Docker Compose
- **Staging**: Production-like environment for testing
- **Production**: Live environment with full monitoring

## Technology Stack

### Backend
- **FastAPI**: Modern Python web framework
- **Python 3.11+**: Runtime environment
- **SQLAlchemy**: ORM and database toolkit
- **Pydantic**: Data validation and serialization

### AI/ML
- **LangGraph**: AI workflow orchestration
- **Groq**: LLM API for AI responses
- **LangChain**: AI framework integration

### Database
- **Cloud SQL PostgreSQL**: Managed relational database
- **Memorystore Redis**: In-memory data store
- **Connection Pooling**: Efficient database connections

### Infrastructure
- **Google Cloud Run**: Serverless container platform
- **Google Cloud SQL**: Managed database service
- **Google Secret Manager**: Secure secret storage
- **Google Cloud Build**: CI/CD pipeline

### Monitoring
- **Google Cloud Logging**: Centralized log management
- **Google Cloud Monitoring**: Metrics and alerting
- **PostHog**: Product analytics and user tracking
- **Error Reporting**: Automatic error tracking

## Development Workflow

### Local Development
```bash
# Start dependencies
docker run -d -p 6379:6379 redis:7-alpine
docker run -d -p 5432:5432 postgres:15

# Configure environment
cp .env.example .env
vim .env

# Run application
uvicorn app.main:app --reload --port 8080
```

### Testing Strategy
- **Unit Tests**: Individual component testing
- **Integration Tests**: API endpoint testing
- **End-to-End Tests**: Full workflow testing
- **Load Tests**: Performance under load

### Code Quality
- **Type Hints**: Full type annotation coverage
- **Linting**: Code style and error checking
- **Documentation**: Comprehensive API docs
- **Security Scanning**: Dependency vulnerability checks

## Future Enhancements

### Scalability
- **Multi-region Deployment**: Geographic distribution
- **Database Sharding**: Horizontal scaling
- **Caching Layer**: Redis cluster for performance
- **Load Balancing**: Traffic distribution

### Features
- **Analytics Dashboard**: Real-time game statistics
- **Admin Interface**: Game management UI
- **A/B Testing**: Feature experimentation
- **Internationalization**: Multi-language support

### Security
- **Advanced Rate Limiting**: User-based throttling
- **Webhook Filtering**: Spam and abuse prevention
- **Audit Trails**: Complete action logging
- **Compliance**: GDPR and data protection