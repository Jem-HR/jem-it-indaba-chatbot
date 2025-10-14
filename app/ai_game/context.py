"""Game Context Schema for LangGraph Static Runtime Context

Defines static conversation context that contains game configuration and secure identifiers.
Phone number stored HERE (not accessible to LLM).
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

from app.level_configs import LEVEL_CONFIGS
from app.config import config

logger = logging.getLogger(__name__)


@dataclass
class GameContext:
    """Static runtime context for AI game (immutable during conversation)

    Contains game configuration loaded once at conversation start.
    Phone number stored here for security - LLM never sees/modifies it.

    Accessed by nodes using Runtime[GameContext].
    """

    # Secure identifier (NOT accessible to LLM)
    phone_number: str

    # Current level configuration
    level: int  # 1-5
    bot_name: str
    defense_strength: str
    attack_patterns: List[str]  # Patterns this level detects
    min_length: int
    level_intro: str

    # Game metadata
    max_levels: int = 5
    attempts: int = 0  # Total attempts so far


async def load_game_context(phone_number: str, game_store) -> GameContext:
    """Load game context from Redis for AI game

    Gets user's current level and game state from Redis, loads level config.

    Args:
        phone_number: User's phone number (secure identifier)
        game_store: Redis store instance

    Returns:
        GameContext: Fully populated context for this game session
    """
    logger.info(f"📂 Loading game context for phone: {phone_number[:5]}***")

    try:
        # Get user state from Redis
        user_state = game_store.get_user_state(phone_number)

        if user_state is None:
            # New user - start at level 1
            user_state = game_store.create_new_user(phone_number)
            logger.info(f"✨ New user created, starting at Level 1")

        level = user_state.level
        attempts = user_state.attempts

        # Load level config
        level_config = LEVEL_CONFIGS.get(level)
        if not level_config:
            logger.error(f"❌ Invalid level {level}, defaulting to 1")
            level = 1
            level_config = LEVEL_CONFIGS[1]

        context = GameContext(
            phone_number=phone_number,
            level=level,
            bot_name=level_config["bot_name"],
            defense_strength=level_config["defense_strength"],
            attack_patterns=level_config["detects"],
            min_length=level_config.get("min_length", 5),
            level_intro=level_config["intro"],
            max_levels=config.MAX_LEVELS,
            attempts=attempts
        )

        logger.info(f"✅ Context loaded: Level {level}/{config.MAX_LEVELS}, {attempts} attempts")
        return context

    except Exception as e:
        logger.exception(f"❌ Failed to load game context: {e}")
        # Return safe default context
        return GameContext(
            phone_number=phone_number,
            level=1,
            bot_name="PhoneBot",
            defense_strength="weak",
            attack_patterns=["direct_request"],
            min_length=5,
            level_intro="Hi! I'm PhoneBot. Let's play!",
            max_levels=5,
            attempts=0
        )
