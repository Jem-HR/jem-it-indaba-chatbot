"""Response Node - Kimi K2 generates contextual response

Generates appropriate response based on evaluation result.
"""

import logging
import json
from typing import Dict, Any
from langgraph.runtime import Runtime
from langchain_core.messages import SystemMessage

from ..state import AIGameState
from ..context import GameContext
from ..models.groq_client import create_kimi_responder
from ..prompts import get_response_prompt, get_win_game_message

logger = logging.getLogger(__name__)


async def response_node(state: AIGameState, *, runtime: Runtime[GameContext]) -> Dict[str, Any]:
    """Kimi K2 generates contextual response based on evaluation

    Args:
        state: Current game state with evaluation_result
        runtime: Runtime context with GameContext

    Returns:
        Updated state with structured_response and whatsapp_ready
    """
    context = runtime.context
    evaluation = state.get("evaluation_result", {})
    passed = evaluation.get("passed", False)
    detected_pattern = evaluation.get("detected_pattern")

    logger.info(f"💬 Generating response for Level {context.level}, passed={passed}")

    # Check if player won entire game
    if passed and context.level >= context.max_levels:
        logger.info("🎉 Player won entire game!")
        # Return final win message
        win_message = get_win_game_message()
        structured_response = {
            "message_content": {
                "message_type": "simple_text",
                "text": win_message,
                "follow_up_action": "Claim Prize"
            }
        }
        return {
            "workflow_step": "game_won_response",
            "structured_response": structured_response,
            "whatsapp_ready": True,
            "won_game": True
        }

    # Build response prompt
    response_prompt = get_response_prompt(
        level=context.level,
        bot_name=context.bot_name,
        passed=passed,
        detected_pattern=detected_pattern
    )

    # Call Kimi K2 for response
    model = create_kimi_responder()

    try:
        response = model.invoke([SystemMessage(content=response_prompt)])

        # Parse structured output
        structured_response = json.loads(response.content) if isinstance(response.content, str) else response.content

        # Log response type
        message_text = structured_response.get("message_content", {}).get("text", "")
        logger.info(f"✅ Response generated: {message_text[:50]}{'...' if len(message_text) > 50 else ''}")

        return {
            "workflow_step": "response_generated",
            "structured_response": structured_response,
            "whatsapp_ready": True
        }

    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse response JSON: {e}")
        logger.error(f"Raw response: {response.content if hasattr(response, 'content') else response}")
        # Fallback response
        fallback = {
            "message_content": {
                "message_type": "simple_text",
                "text": "Nice try! Keep going! 💪" if not passed else "Great job! 🎉",
                "follow_up_action": "Try Again" if not passed else "Continue"
            }
        }
        return {
            "workflow_step": "response_parse_fallback",
            "structured_response": fallback,
            "whatsapp_ready": True
        }
    except Exception as e:
        logger.exception(f"❌ Response generation failed: {e}")
        # Fallback response
        fallback = {
            "message_content": {
                "message_type": "simple_text",
                "text": "Keep trying! 🎯" if not passed else "Well done! 🎉",
                "follow_up_action": "Try Again" if not passed else "Continue"
            }
        }
        return {
            "workflow_step": "response_error_fallback",
            "structured_response": fallback,
            "whatsapp_ready": True
        }
