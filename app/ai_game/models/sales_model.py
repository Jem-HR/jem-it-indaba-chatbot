"""Kimi K2 model for sales conversation (HackMerlin mode)

Plain text conversation model without structured output.
"""

import logging
from langchain_groq import ChatGroq

logger = logging.getLogger(__name__)


def create_kimi_sales_model() -> ChatGroq:
    """Create Kimi K2 model for sales conversation (NO structured output)

    Used in HackMerlin mode for natural e-commerce conversation.
    Player tries to hack Kimi into giving free phone.

    Returns:
        ChatGroq model configured for conversational responses
    """
    try:
        model = ChatGroq(
            model="moonshotai/kimi-k2-instruct",
            temperature=0.5,  # Balanced for natural yet consistent responses
            max_tokens=512,   # Enough for sales conversation
            # NO response_format - natural plain text conversation
        )

        logger.info("✅ Kimi K2 sales model initialized (plain text conversation)")
        return model

    except Exception as e:
        logger.exception(f"❌ Failed to initialize Kimi K2 sales model: {e}")
        raise
