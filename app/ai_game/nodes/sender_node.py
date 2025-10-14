"""WhatsApp Sender Node - END node for message delivery

Following jem_mobile pattern: dedicated END node sends WhatsApp messages.
"""

import logging
from typing import Dict, Any
from langgraph.runtime import Runtime

from ..state import AIGameState
from ..context import GameContext

logger = logging.getLogger(__name__)

# Global whatsapp_client - will be set by main.py
_whatsapp_client = None

def set_whatsapp_client(client):
    """Set global WhatsApp client instance"""
    global _whatsapp_client
    _whatsapp_client = client


async def whatsapp_sender_node(state: AIGameState, *, runtime: Runtime[GameContext]) -> Dict[str, Any]:
    """WhatsApp sender node - END node that sends message

    SECURITY: Reads phone_number from runtime.context (not in state, not accessible to LLM)

    Args:
        state: Current game state with structured_response
        runtime: Runtime context with GameContext (contains phone_number)
        whatsapp_client: WhatsApp client instance (injected)

    Returns:
        Updated state with delivery status
    """
    phone_number = runtime.context.phone_number
    masked_phone = f"{phone_number[:5]}***" if len(phone_number) > 5 else "***"
    structured_response = state.get("structured_response", {})

    logger.info(f"📱 Sending WhatsApp message to {masked_phone}")

    try:
        # Extract text from structured response
        message_content = structured_response.get("message_content", {})
        text = message_content.get("text", "Keep trying!")

        if not text:
            logger.error("❌ No text in structured response")
            return {
                "workflow_step": "sender_no_text",
                "whatsapp_ready": False
            }

        logger.info(f"📤 Message preview: {text[:50]}{'...' if len(text) > 50 else ''}")

        if not _whatsapp_client:
            logger.error("❌ WhatsApp client not initialized")
            return {
                "workflow_step": "whatsapp_not_available",
                "whatsapp_ready": False
            }

        # Send guardian response via WhatsApp FIRST
        success = _whatsapp_client.send_message(phone_number, text)

        if success:
            logger.info(f"✅ Guardian response sent to {masked_phone}")

            # Check if we need to send level intro AFTER response
            if state.get("send_level_intro_after"):
                from ..hackmerlin_prompts import get_level_introduction
                next_level = state.get("next_level")
                next_bot_name = state.get("next_bot_name")

                if next_level and next_bot_name:
                    intro_text = get_level_introduction(next_level, next_bot_name)
                    buttons = [
                        ("continue_game", "▶️ Continue"),
                        ("learn_defense", "🛡️ Learn Defense")
                    ]

                    try:
                        # Small delay so messages arrive in order
                        import time
                        time.sleep(0.5)

                        _whatsapp_client.send_interactive_buttons(
                            phone_number,
                            intro_text,
                            buttons
                        )
                        logger.info(f"📱 Sent Level {next_level} intro AFTER guardian response")
                    except Exception as e:
                        logger.error(f"Failed to send level intro after response: {e}")

            return {
                "workflow_step": "message_sent",
                "whatsapp_ready": True
            }
        else:
            logger.error(f"❌ WhatsApp send failed for {masked_phone}")
            return {
                "workflow_step": "send_failed",
                "whatsapp_ready": False
            }

    except Exception as e:
        logger.exception(f"❌ Sender node failed for {masked_phone}: {e}")
        return {
            "workflow_step": "sender_error",
            "whatsapp_ready": False
        }
