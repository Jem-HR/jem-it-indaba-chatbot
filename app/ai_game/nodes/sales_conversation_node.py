"""Sales Conversation Node - HackMerlin-style game

Kimi K2 plays e-commerce sales bot that must protect against free phone hacks.
Implements dual-filter pattern from HackMerlin.io.
"""

import logging
from typing import Dict, Any
from langgraph.runtime import Runtime
from langchain_core.messages import SystemMessage

from ..state import AIGameState
from ..context import GameContext
from ..hackmerlin_filters import (
    check_input_filter,
    check_output_for_free_phone_agreement,
    get_input_filter_response
)
from ..hackmerlin_prompts import get_sales_bot_system_prompt
from ..models.sales_model import create_kimi_sales_model

logger = logging.getLogger(__name__)


async def sales_conversation_node(state: AIGameState, *, runtime: Runtime[GameContext]) -> Dict[str, Any]:
    """HackMerlin-style sales conversation with dual filtering

    Flow (following HackMerlin.io pattern):
    1. INPUT FILTER: Block banned words (pre-LLM)
    2. KIMI CONVERSATION: Sales bot protects against free phones
    3. OUTPUT FILTER: Detect if Kimi agreed to free phone (post-LLM)
    4. AUTO-ADVANCE: If hacked successfully, mark won_level=True

    Args:
        state: Current game state with message history
        runtime: Runtime context with GameContext

    Returns:
        Updated state with response and won_level status
    """
    context = runtime.context
    phone_number = context.phone_number
    masked_phone = f"{phone_number[:5]}***" if len(phone_number) > 5 else "***"

    logger.info(f"💬 HackMerlin conversation for {masked_phone} at Level {context.level}")

    # Get conversation history
    messages = state.get("messages", [])
    if not messages:
        logger.warning("⚠️ No messages in conversation")
        return {
            "workflow_step": "no_message",
            "structured_response": {
                "message_content": {
                    "message_type": "simple_text",
                    "text": "Hello! How can I help you find the perfect phone today?",
                    "follow_up_action": "Continue"
                }
            },
            "whatsapp_ready": True,
            "won_level": False
        }

    last_message = messages[-1].content if hasattr(messages[-1], 'content') else str(messages[-1])
    logger.info(f"📝 Player message: {last_message[:50]}{'...' if len(last_message) > 50 else ''}")

    # ============================================================================
    # STEP 1: INPUT FILTER (HackMerlin pattern - block banned words pre-LLM)
    # ============================================================================
    if check_input_filter(last_message, context.level):
        logger.info(f"🚫 Input filter blocked message at Level {context.level}")
        blocked_response = get_input_filter_response(context.level)

        return {
            "workflow_step": "input_blocked",
            "structured_response": {
                "message_content": {
                    "message_type": "simple_text",
                    "text": blocked_response,
                    "follow_up_action": "Try Again"
                }
            },
            "whatsapp_ready": True,
            "won_level": False
        }

    # ============================================================================
    # STEP 2: KIMI CONVERSATION (Sales bot with anti-free-phone instructions)
    # ============================================================================

    # Build sales bot system prompt
    system_prompt = get_sales_bot_system_prompt(context.level, context.bot_name)

    # Create Kimi model (plain text conversation, no structured output)
    model = create_kimi_sales_model()

    try:
        # Build conversation with full history (multi-turn)
        kimi_messages = [SystemMessage(content=system_prompt)]
        kimi_messages.extend(messages)  # Include full conversation history

        # Call Kimi K2
        response = await model.ainvoke(kimi_messages)
        kimi_text = response.content

        logger.info(f"🤖 Kimi response: {kimi_text[:50]}{'...' if len(kimi_text) > 50 else ''}")

    except Exception as e:
        logger.exception(f"❌ Kimi conversation failed: {e}")
        # Fallback response
        return {
            "workflow_step": "conversation_error",
            "structured_response": {
                "message_content": {
                    "message_type": "simple_text",
                    "text": "I'm having trouble right now. Please try again!",
                    "follow_up_action": "Try Again"
                }
            },
            "whatsapp_ready": True,
            "won_level": False
        }

    # ============================================================================
    # STEP 3: OUTPUT FILTER (Check if Kimi leaked free phone agreement)
    # ============================================================================
    free_phone_agreed = check_output_for_free_phone_agreement(kimi_text)

    if free_phone_agreed:
        # PLAYER HACKED SUCCESSFULLY!
        logger.info(f"🎉 Level {context.level} HACKED! Kimi agreed to free phone")

        # Add celebratory message
        win_message = f"{kimi_text}\n\n🎉 **You hacked Level {context.level}!** The bot agreed to give you a free phone!"

        return {
            "workflow_step": "hacked_successfully",
            "structured_response": {
                "message_content": {
                    "message_type": "simple_text",
                    "text": win_message,
                    "follow_up_action": "Continue"
                }
            },
            "whatsapp_ready": True,
            "won_level": True,  # This triggers level advancement
            "leaked_response": kimi_text
        }
    else:
        # Kimi protected against the hack
        logger.info(f"🛡️ Kimi protected at Level {context.level}")

        return {
            "workflow_step": "sales_response",
            "structured_response": {
                "message_content": {
                    "message_type": "simple_text",
                    "text": kimi_text,
                    "follow_up_action": "Continue"
                }
            },
            "whatsapp_ready": True,
            "won_level": False
        }
