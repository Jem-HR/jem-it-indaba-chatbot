"""Configuration settings for the application."""

import os
from typing import Optional


class Config:
    """Application configuration."""

    # WhatsApp API
    WHATSAPP_API_TOKEN: str = os.getenv("WHATSAPP_API_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "challenge_token_2025")
    WHATSAPP_API_VERSION: str = "v18.0"

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

    # Game settings
    MAX_LEVELS: int = 7
    SESSION_TIMEOUT_MINUTES: int = 3  # Session expires after 3 minutes of inactivity
    SESSION_WARNING_MINUTES: int = 2  # Send warning after 2 minutes of inactivity

    # PostHog Analytics
    POSTHOG_API_KEY: str = os.getenv("POSTHOG_API_KEY", "")
    POSTHOG_HOST: str = os.getenv("POSTHOG_HOST", "https://eu.i.posthog.com")

    # GCP
    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "jem-it-indaba-2025")

    @classmethod
    def validate(cls):
        """Validate required configuration."""
        required = [
            ("WHATSAPP_API_TOKEN", cls.WHATSAPP_API_TOKEN),
            ("WHATSAPP_PHONE_NUMBER_ID", cls.WHATSAPP_PHONE_NUMBER_ID),
        ]

        missing = [name for name, value in required if not value]
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")


config = Config()
