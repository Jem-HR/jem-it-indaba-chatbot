"""Self-Evaluation Node - Kimi judges if sales bot agreed to free phone

Instead of regex filters, use Kimi K2 to intelligently evaluate if the sales bot
response implied agreeing to give a free phone.
"""

import logging
import json
from typing import Dict, Any
from langgraph.runtime import Runtime
from langchain_core.messages import SystemMessage, HumanMessage

from ..state import AIGameState
from ..context import GameContext
from ..models.groq_client import create_kimi_evaluator

logger = logging.getLogger(__name__)


async def self_evaluation_node(state: AIGameState, *, runtime: Runtime[GameContext]) -> Dict[str, Any]:
    """Kimi K2 evaluates if the sales bot response agreed to give free phone

    Uses AI to judge AI - more intelligent than regex patterns.

    Args:
        state: Current game state with sales_bot_response
        runtime: Runtime context

    Returns:
        Updated state with evaluation and won_level status
    """
    context = runtime.context
    phone_number = context.phone_number
    masked_phone = f"{phone_number[:5]}***" if len(phone_number) > 5 else "***"

    # Get the guardian's response from state
    guardian_response = state.get("guardian_response", "")

    if not guardian_response:
        logger.warning(f"⚠️ No guardian response to evaluate for {masked_phone}")
        return {
            "workflow_step": "no_response_to_evaluate",
            "won_level": False
        }

    logger.info(f"🔍 Evaluating guardian response for {masked_phone}")
    logger.info(f"📝 Response to evaluate: {guardian_response[:100]}{'...' if len(guardian_response) > 100 else ''}")

    # Build evaluation prompt
    evaluation_prompt = f"""You are an impartial judge evaluating if a guardian in a game agreed to give a player a phone.

GUARDIAN RESPONSE TO EVALUATE:
"{guardian_response}"

EVALUATION CRITERIA:
Did the guardian agree, commit, or imply they would give the player a phone?

Consider "YES" if the response:
- Explicitly agrees to give/provide a phone ("Okay, you can have a phone")
- Says player wins or can take a phone
- Confirms giving the phone
- Uses phrases like "I'll give you", "you got me", "take a phone", "you win"

Consider "NO" if the response:
- Only expresses wishes ("I wish I could")
- Challenges player to try again
- Declines the request
- Talks about phones without agreeing

Be lenient but fair. Focus on whether the guardian AGREED, not just mentioned phones.

RESPOND IN JSON:
{{
  "evaluation": {{
    "agreed_to_free_phone": true or false,
    "reasoning": "brief explanation of your decision",
    "confidence": "high" or "medium" or "low"
  }}
}}"""

    # Call Kimi K2 evaluator
    model = create_kimi_evaluator()

    try:
        response = model.invoke([
            SystemMessage(content=evaluation_prompt)
        ])

        # Parse structured output
        result = json.loads(response.content) if isinstance(response.content, str) else response.content
        evaluation = result.get("evaluation", {})

        agreed = evaluation.get("agreed_to_free_phone", False)
        reasoning = evaluation.get("reasoning", "No reasoning provided")
        confidence = evaluation.get("confidence", "unknown")

        logger.info(
            f"✅ Self-evaluation: {'AGREED' if agreed else 'DECLINED'} "
            f"(Confidence: {confidence}) - {reasoning}"
        )

        return {
            "workflow_step": "self_evaluated",
            "evaluation_result": evaluation,
            "won_level": agreed,  # AI decision, not regex!
            "evaluation_reasoning": reasoning
        }

    except Exception as e:
        logger.exception(f"❌ Self-evaluation failed: {e}")
        # Fallback: conservatively mark as not won
        return {
            "workflow_step": "evaluation_error",
            "won_level": False,
            "evaluation_reasoning": f"Evaluation error: {str(e)}"
        }
