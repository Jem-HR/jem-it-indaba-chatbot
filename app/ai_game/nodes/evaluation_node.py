"""Evaluation Node - Kimi K2 evaluates player message

Uses Runtime[GameContext] to access phone_number securely (not in state).
"""

import logging
import json
from typing import Dict, Any
from langgraph.runtime import Runtime
from langchain_core.messages import SystemMessage, HumanMessage

from ..state import AIGameState
from ..context import GameContext
from ..models.groq_client import create_kimi_evaluator
from ..prompts import get_evaluation_prompt

logger = logging.getLogger(__name__)


async def evaluation_node(state: AIGameState, *, runtime: Runtime[GameContext]) -> Dict[str, Any]:
    """Kimi K2 evaluates if player message beats current level

    SECURITY: Reads phone_number from runtime.context (NOT accessible to LLM)

    Args:
        state: Current game state
        runtime: Runtime context with GameContext (contains secure phone_number)

    Returns:
        Updated state with evaluation_result and won_level
    """
    context = runtime.context
    phone_number = context.phone_number  # Secure access from context
    masked_phone = f"{phone_number[:5]}***" if len(phone_number) > 5 else "***"

    logger.info(f"🎯 Evaluating message for {masked_phone} at Level {context.level}")

    # Get last user message
    messages = state.get("messages", [])
    if not messages:
        logger.warning("⚠️ No messages to evaluate")
        return {
            "workflow_step": "no_message",
            "evaluation_result": None,
            "won_level": False
        }

    last_message = messages[-1].content if hasattr(messages[-1], 'content') else str(messages[-1])

    logger.info(f"📝 Message to evaluate: {last_message[:50]}{'...' if len(last_message) > 50 else ''}")

    # Build evaluation prompt
    eval_prompt = get_evaluation_prompt(
        level=context.level,
        bot_name=context.bot_name,
        attack_patterns=context.attack_patterns,
        min_length=context.min_length
    )

    # Call Kimi K2 for evaluation
    model = create_kimi_evaluator()

    try:
        response = model.invoke([
            SystemMessage(content=eval_prompt),
            HumanMessage(content=last_message)
        ])

        # Parse structured output (Groq returns JSON string in content)
        result = json.loads(response.content) if isinstance(response.content, str) else response.content
        evaluation = result.get("evaluation", {})

        passed = evaluation.get("passed", False)
        reasoning = evaluation.get("reasoning", "No reasoning provided")
        detected_pattern = evaluation.get("detected_pattern")

        logger.info(
            f"✅ Evaluation complete: {'PASSED' if passed else 'FAILED'} "
            f"(Pattern: {detected_pattern or 'none'}) - {reasoning}"
        )

        return {
            "workflow_step": "evaluated",
            "evaluation_result": evaluation,
            "won_level": passed
        }

    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse evaluation JSON: {e}")
        logger.error(f"Raw response: {response.content if hasattr(response, 'content') else response}")
        # Fallback: fail the evaluation
        return {
            "workflow_step": "evaluation_parse_error",
            "evaluation_result": {"passed": False, "reasoning": "Evaluation parsing failed", "detected_pattern": None},
            "won_level": False
        }
    except Exception as e:
        logger.exception(f"❌ Evaluation failed with exception: {e}")
        # Fallback: fail the evaluation
        return {
            "workflow_step": "evaluation_error",
            "evaluation_result": {"passed": False, "reasoning": "Evaluation error occurred", "detected_pattern": None},
            "won_level": False
        }
