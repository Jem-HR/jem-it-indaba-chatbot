"""Kimi K2 model for guardian conversation (HackMerlin game mode)

Plain text conversation model without structured output.
"""

import logging
from langchain_groq import ChatGroq

logger = logging.getLogger(__name__)


def create_kimi_guardian_model() -> ChatGroq:
    """Create Kimi K2 model for guardian conversation (NO structured output)

    Used in HackMerlin mode for natural game guardian conversation.
    Guardian protects phones, player tries to hack them.

    Returns:
        ChatGroq model configured for conversational responses
    """
    try:
        model = ChatGroq(
            model="moonshotai/kimi-k2-instruct",
            temperature=0.5,  # Balanced for natural yet consistent responses
            max_tokens=512,   # Enough for guardian conversation
            # NO response_format - natural plain text conversation
        )

        logger.info("✅ Kimi K2 guardian model initialized (plain text conversation)")
        return model

    except Exception as e:
        logger.exception(f"❌ Failed to initialize Kimi K2 guardian model: {e}")
        raise
