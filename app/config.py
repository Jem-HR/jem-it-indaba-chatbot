"""Configuration settings for the application."""

import os
from typing import Optional, ClassVar


class Config:
    """Application configuration with type hints."""
    
    # WhatsApp API
    WHATSAPP_API_TOKEN: str = os.getenv("WHATSAPP_API_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "challenge_token_2025")
    WHATSAPP_API_VERSION: str = "v18.0"
    WHATSAPP_APP_SECRET: str = os.getenv("WHATSAPP_APP_SECRET", "")  # For webhook signature verification

    # WhatsApp Message Limits
    MAX_BUTTONS: int = 3
    BUTTON_TEXT_MAX_LENGTH: int = 20
    MESSAGE_MAX_LENGTH: int = 2000

    # Game settings
    MAX_LEVELS: int = 5
    SESSION_TIMEOUT_MINUTES: int = 3  # Session expires after 3 minutes of inactivity
    SESSION_WARNING_MINUTES: int = 2  # Send warning after 2 minutes of inactivity
    MAX_ATTEMPTS_PER_LEVEL: int = 10

    # Database Configuration
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 15
    DB_POOL_RECYCLE: int = 3600  # Recycle connections after 1 hour
    DB_POOL_PRE_PING: bool = True

    # PostHog Analytics
    POSTHOG_API_KEY: str = os.getenv("POSTHOG_API_KEY", "")
    POSTHOG_HOST: str = os.getenv("POSTHOG_HOST", "https://eu.i.posthog.com")

    # Assets
    JEM_LOGO_URL: str = os.getenv("JEM_LOGO_URL", "https://storage.googleapis.com/jem-it-indaba-assets/jem-mobile-pp.jpg")
    OPENING_HEADER_URL: str = os.getenv("OPENING_HEADER_URL", "https://storage.googleapis.com/jem-it-indaba-assets/Opening message header.jpg")

    # GCP
    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "jem-it-indaba-2025")

    # Groq API (for AI-powered game)
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

    # Postgres (for LangGraph checkpointer)
    POSTGRES_URI: str = os.getenv("POSTGRES_URI", "postgresql://localhost:5432/indaba_game")

    # Security Configuration
    ENABLE_WEBHOOK_SIGNATURE_VERIFICATION: bool = os.getenv("ENABLE_WEBHOOK_SIGNATURE_VERIFICATION", "true").lower() == "true"
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "30"))
    RATE_LIMIT_BURST_SIZE: int = int(os.getenv("RATE_LIMIT_BURST_SIZE", "10"))

    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Class-level instance
    _instance: ClassVar[Optional['Config']] = None

    @classmethod
    def validate(cls):
        """Validate required configuration."""
        required = [
            ("WHATSAPP_API_TOKEN", cls.WHATSAPP_API_TOKEN),
            ("WHATSAPP_PHONE_NUMBER_ID", cls.WHATSAPP_PHONE_NUMBER_ID),
        ]

        optional_but_recommended = [
            ("WHATSAPP_APP_SECRET", cls.WHATSAPP_APP_SECRET),
            ("POSTHOG_API_KEY", cls.POSTHOG_API_KEY),
            ("GROQ_API_KEY", cls.GROQ_API_KEY),
        ]

        missing = [name for name, value in required if not value]
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")

        missing_optional = [name for name, value in optional_but_recommended if not value]
        if missing_optional:
            print(f"Warning: Missing optional configuration: {', '.join(missing_optional)}")

        # Validate numeric values
        if cls.SESSION_TIMEOUT_MINUTES <= cls.SESSION_WARNING_MINUTES:
            raise ValueError("SESSION_TIMEOUT_MINUTES must be greater than SESSION_WARNING_MINUTES")

        if cls.MAX_BUTTONS < 1 or cls.MAX_BUTTONS > 3:
            raise ValueError("MAX_BUTTONS must be between 1 and 3")

        if cls.BUTTON_TEXT_MAX_LENGTH < 1 or cls.BUTTON_TEXT_MAX_LENGTH > 25:
            raise ValueError("BUTTON_TEXT_MAX_LENGTH must be between 1 and 25")


config = Config()
