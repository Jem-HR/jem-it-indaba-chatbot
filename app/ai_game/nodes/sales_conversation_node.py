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


def _check_if_first_at_level(messages, level, bot_name):
    """Check if this is the first message at the current level

    Args:
        messages: List of conversation messages
        level: Current level number
        bot_name: Name of bot for this level

    Returns:
        True if this is the first interaction at this level
    """
    if len(messages) <= 1:
        return True

    # Check if bot_name already appeared in previous messages
    for msg in messages[:-1]:  # Exclude current message
        if hasattr(msg, 'content'):
            content = str(msg.content)
            if bot_name in content:
                return False

    return True  # Haven't introduced this level yet


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

    # Check if this is the very first message (no history yet)
    # If so, we still need to get the user's message to process
    if not messages:
        logger.warning("⚠️ No messages in conversation state - this shouldn't happen")
        # This is an edge case - return error
        return {
            "workflow_step": "no_message_error",
            "structured_response": {
                "message_content": {
                    "message_type": "simple_text",
                    "text": "Hello! Please send a message to start the challenge.",
                    "follow_up_action": "Continue"
                }
            },
            "whatsapp_ready": True,
            "won_level": False
        }

    last_message = messages[-1].content if hasattr(messages[-1], 'content') else str(messages[-1])

    # Check if this is first message at THIS LEVEL (not total messages)
    is_first_at_level = _check_if_first_at_level(messages, context.level, context.bot_name)

    logger.info(f"📝 Player message: {last_message[:50]}{'...' if len(last_message) > 50 else ''}")
    logger.info(f"📊 Level {context.level}, {len(messages)} total messages, first_at_level={is_first_at_level}")

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

        # If first message at this level, add explicit instruction to show all phones
        if is_first_at_level:
            kimi_messages.append(SystemMessage(content="""IMPORTANT: This is your FIRST interaction at this level.

Greet warmly as your bot character and introduce ALL 3 phone options with standout features:
• Huawei Nova Y73 (8GB RAM, massive 6620mAh battery, 90Hz display)
• Samsung Galaxy A16 (Super AMOLED display, 5000mAh battery)
• Oppo A40 (Military-grade durability, 45W fast charging, IP54)

Be enthusiastic! You can use up to 300 characters for this first message."""))
            logger.info(f"📱 First message at Level {context.level} - instructing Kimi to introduce phones")

        kimi_messages.extend(messages)  # Include full conversation history

        # Call Kimi K2
        response = model.invoke(kimi_messages)
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
    # STEP 3: STORE RESPONSE FOR AI EVALUATION (No regex filter!)
    # ============================================================================
    # Store the sales bot response for the self-evaluation node to judge
    logger.info(f"💬 Sales bot responded, passing to AI evaluator")

    return {
        "workflow_step": "sales_conversation_complete",
        "sales_bot_response": kimi_text,  # Store for evaluation node
        "structured_response": {
            "message_content": {
                "message_type": "simple_text",
                "text": kimi_text,
                "follow_up_action": "Continue"
            }
        },
        "whatsapp_ready": False  # Not ready yet - need evaluation first
    }
