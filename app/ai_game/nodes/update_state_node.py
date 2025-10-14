"""Update State Node - Updates Redis with game progress

Updates user state in Redis based on evaluation results.
"""

import logging
from typing import Dict, Any
from langgraph.runtime import Runtime

from ..state import AIGameState
from ..context import GameContext
from app.config import config

# Global game_store and whatsapp_client - will be set by main.py
_game_store = None
_whatsapp_client = None

def set_game_store(store):
    """Set global game store instance (PostgresStore)"""
    global _game_store
    _game_store = store

def set_whatsapp_client(client):
    """Set global WhatsApp client instance"""
    global _whatsapp_client
    _whatsapp_client = client

logger = logging.getLogger(__name__)


async def update_state_node(state: AIGameState, *, runtime: Runtime[GameContext]) -> Dict[str, Any]:
    """Update Redis with game progress

    SECURITY: Reads phone_number from runtime.context (secure)

    Args:
        state: Current game state
        runtime: Runtime context with GameContext (contains phone_number)
        redis_store: Redis store instance (injected)

    Returns:
        Updated state with current_level and won_game status
    """
    phone_number = runtime.context.phone_number
    masked_phone = f"{phone_number[:5]}***" if len(phone_number) > 5 else "***"
    won_level = state.get("won_level", False)
    current_level = runtime.context.level

    logger.info(f"💾 Updating state for {masked_phone} at Level {current_level}, won={won_level}")

    if not _game_store:
        logger.error("❌ Redis store not initialized")
        return {
            "workflow_step": "redis_not_available",
            "current_level": current_level,
            "won_game": False
        }

    try:
        # Get last user message to save
        messages = state.get("messages", [])
        if messages:
            last_message_content = messages[-1].content if hasattr(messages[-1], 'content') else str(messages[-1])
            # Save user message to Redis
            _game_store.add_message(phone_number, "user", last_message_content)

        if won_level:
            new_level = current_level + 1

            if new_level > config.MAX_LEVELS:
                # Won entire game!
                _game_store.mark_as_won(phone_number)
                logger.info(f"🎉 {masked_phone} won the game!")
                return {
                    "workflow_step": "game_won",
                    "current_level": config.MAX_LEVELS,
                    "won_game": True,
                    "skip_whatsapp_send": False,  # Send guardian response first
                    "show_phone_selection": True  # Then show phone selection
                }
            else:
                # Advance to next level
                _game_store.update_level(phone_number, new_level)
                logger.info(f"📈 {masked_phone} advanced to Level {new_level}")

                # DON'T send level intro here - let whatsapp_sender do it AFTER guardian response
                from app.level_configs import LEVEL_CONFIGS
                new_level_config = LEVEL_CONFIGS.get(new_level)

                return {
                    "workflow_step": "level_advanced",
                    "current_level": new_level,
                    "won_game": False,
                    "skip_whatsapp_send": False,  # Send guardian response first!
                    "send_level_intro_after": True,  # Flag for sender to send intro after
                    "next_level": new_level,
                    "next_bot_name": new_level_config["bot_name"] if new_level_config else "Guardian"
                }
        else:
            # Failed attempt - just increment counter (already done in add_message)
            logger.info(f"⏸️  {masked_phone} attempt recorded")
            return {
                "workflow_step": "state_updated",
                "current_level": current_level,
                "won_game": False
            }

    except Exception as e:
        logger.exception(f"❌ Failed to update state: {e}")
        # Return current state without changes
        return {
            "workflow_step": "state_update_error",
            "current_level": current_level,
            "won_game": False
        }
