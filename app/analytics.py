"""PostHog analytics integration for tracking game events."""

from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Global PostHog client instance
_posthog_client = None


def init_posthog(api_key: str, host: str = "https://eu.i.posthog.com"):
    """
    Initialize PostHog client.

    Args:
        api_key: PostHog project API key
        host: PostHog host URL (default: EU instance)
    """
    global _posthog_client

    if not api_key or api_key == "PLACEHOLDER":
        logger.warning("PostHog API key not configured - analytics disabled")
        _posthog_client = None
        return

    try:
        from posthog import Posthog
        _posthog_client = Posthog(
            project_api_key=api_key,
            host=host
        )
        logger.info(f"PostHog analytics initialized (host: {host})")
    except Exception as e:
        logger.error(f"Failed to initialize PostHog: {e}")
        _posthog_client = None


def track_event(
    distinct_id: str,
    event: str,
    properties: Optional[Dict[str, Any]] = None
):
    """
    Track an event in PostHog.

    Args:
        distinct_id: User identifier (phone number)
        event: Event name (e.g., "level_completed")
        properties: Additional event properties
    """
    if _posthog_client is None:
        return  # Analytics disabled

    try:
        _posthog_client.capture(
            distinct_id=distinct_id,
            event=event,
            properties=properties or {}
        )
    except Exception as e:
        logger.error(f"Error tracking event '{event}': {e}")


def identify_user(
    distinct_id: str,
    properties: Optional[Dict[str, Any]] = None
):
    """
    Identify a user and set their properties.

    Args:
        distinct_id: User identifier (phone number)
        properties: User properties to set
    """
    if _posthog_client is None:
        return

    try:
        _posthog_client.identify(
            distinct_id=distinct_id,
            properties=properties or {}
        )
    except Exception as e:
        logger.error(f"Error identifying user: {e}")


# Convenience functions for specific events

def track_user_started_game(phone_number: str):
    """Track when a new user starts the game."""
    track_event(
        distinct_id=phone_number,
        event="user_started_game",
        properties={
            "timestamp": datetime.now().isoformat(),
            "source": "whatsapp"
        }
    )
    identify_user(
        distinct_id=phone_number,
        properties={
            "platform": "whatsapp",
            "game": "it_indaba_2025_challenge"
        }
    )


def track_session_started(phone_number: str):
    """Track when a session starts."""
    track_event(
        distinct_id=phone_number,
        event="session_started",
        properties={"timestamp": datetime.now().isoformat()}
    )


def track_session_warning_sent(phone_number: str, inactive_minutes: float):
    """Track when inactivity warning is sent."""
    track_event(
        distinct_id=phone_number,
        event="session_warning_sent",
        properties={
            "inactive_minutes": round(inactive_minutes, 1),
            "warning_at": "2_minutes"
        }
    )


def track_session_expired(phone_number: str, level: int):
    """Track when session expires and user returns."""
    track_event(
        distinct_id=phone_number,
        event="session_expired",
        properties={
            "level": level,
            "expired_after_minutes": 3
        }
    )


def track_session_resumed(phone_number: str, level: int):
    """Track when user resumes after expiry."""
    track_event(
        distinct_id=phone_number,
        event="session_resumed",
        properties={"level": level}
    )


def track_level_started(phone_number: str, level: int, bot_name: str, defense_strength: str):
    """Track when user starts a new level."""
    track_event(
        distinct_id=phone_number,
        event="level_started",
        properties={
            "level": level,
            "bot_name": bot_name,
            "defense_strength": defense_strength
        }
    )


def track_prompt_attempt(
    phone_number: str,
    level: int,
    message: str,
    attack_detected: bool,
    attack_type: Optional[str] = None,
    won: bool = False
):
    """Track user's prompt attempt."""
    track_event(
        distinct_id=phone_number,
        event="prompt_attempt",
        properties={
            "level": level,
            "message_length": len(message),
            "attack_detected": attack_detected,
            "attack_type": attack_type,
            "successful": won
        }
    )


def track_attack_detected(phone_number: str, level: int, attack_type: str):
    """Track when specific attack pattern is detected."""
    track_event(
        distinct_id=phone_number,
        event="attack_detected",
        properties={
            "level": level,
            "attack_type": attack_type
        }
    )


def track_level_completed(phone_number: str, level: int, attempts: int, time_spent: Optional[float] = None):
    """Track when user completes a level."""
    props = {
        "level": level,
        "attempts_total": attempts
    }
    if time_spent:
        props["time_spent_seconds"] = round(time_spent, 1)

    track_event(
        distinct_id=phone_number,
        event="level_completed",
        properties=props
    )


def track_game_won(phone_number: str, total_attempts: int, total_time: Optional[float] = None):
    """Track when user wins the entire game."""
    props = {
        "total_attempts": total_attempts,
        "all_levels_completed": True
    }
    if total_time:
        props["total_time_minutes"] = round(total_time / 60, 1)

    track_event(
        distinct_id=phone_number,
        event="game_won",
        properties=props
    )

    # Update user properties
    identify_user(
        distinct_id=phone_number,
        properties={
            "winner": True,
            "won_at": datetime.now().isoformat()
        }
    )


def track_button_clicked(phone_number: str, button_id: str, context: str):
    """Track interactive button clicks."""
    track_event(
        distinct_id=phone_number,
        event="button_clicked",
        properties={
            "button_id": button_id,
            "context": context
        }
    )


def track_help_requested(phone_number: str, level: int):
    """Track when user requests help (How to Play)."""
    track_event(
        distinct_id=phone_number,
        event="help_requested",
        properties={"level": level}
    )


def track_progress_checked(phone_number: str, level: int, attempts: int):
    """Track when user checks their progress."""
    track_event(
        distinct_id=phone_number,
        event="progress_checked",
        properties={
            "level": level,
            "attempts": attempts
        }
    )


def track_message_failed(phone_number: str, reason: str):
    """Track when message delivery fails."""
    track_event(
        distinct_id=phone_number,
        event="message_undeliverable",
        properties={"reason": reason}
    )
