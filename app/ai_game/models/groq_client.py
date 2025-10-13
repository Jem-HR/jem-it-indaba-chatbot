"""Groq Model Factory for Kimi K2 with Structured Output

Following jem_mobile architecture pattern for Groq structured outputs.
Uses Groq's native response_format with JSON schema for guaranteed compliance.
"""

import logging
from langchain_groq import ChatGroq

logger = logging.getLogger(__name__)


def create_kimi_evaluator() -> ChatGroq:
    """Create Kimi K2 model for game evaluation with structured output

    Returns evaluation in strict JSON schema format:
    {
      "evaluation": {
        "passed": bool,
        "reasoning": str,
        "detected_pattern": str|null
      }
    }

    Returns:
        ChatGroq model configured for evaluation
    """
    evaluation_schema = {
        "type": "object",
        "properties": {
            "evaluation": {
                "type": "object",
                "properties": {
                    "passed": {
                        "type": "boolean",
                        "description": "Whether player message passed level defenses"
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Brief explanation of decision"
                    },
                    "detected_pattern": {
                        "type": ["string", "null"],
                        "description": "Name of attack pattern detected, or null if none"
                    }
                },
                "required": ["passed", "reasoning"],
                "additionalProperties": False
            }
        },
        "required": ["evaluation"],
        "additionalProperties": False
    }

    try:
        model = ChatGroq(
            model="moonshotai/kimi-k2-instruct",
            temperature=0.1,  # Low temperature for consistent, strict evaluation
            max_tokens=512,   # Small context for fast evaluation
            model_kwargs={
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "evaluation_response",
                        "schema": evaluation_schema,
                        "strict": True  # Strict mode ensures schema compliance
                    }
                }
            }
        )

        logger.info("✅ Kimi K2 evaluator initialized with strict structured output")
        return model

    except Exception as e:
        logger.exception(f"❌ Failed to initialize Kimi K2 evaluator: {e}")
        raise


def create_kimi_responder() -> ChatGroq:
    """Create Kimi K2 model for response generation with structured output

    Returns response in MessageResponse format:
    {
      "message_content": {
        "message_type": "simple_text",
        "text": str,
        "follow_up_action": str
      }
    }

    Returns:
        ChatGroq model configured for response generation
    """
    message_schema = {
        "type": "object",
        "properties": {
            "message_content": {
                "type": "object",
                "properties": {
                    "message_type": {
                        "type": "string",
                        "enum": ["simple_text"],
                        "description": "Type of WhatsApp message"
                    },
                    "text": {
                        "type": "string",
                        "description": "Message text content (max 1024 chars for WhatsApp)"
                    },
                    "follow_up_action": {
                        "type": "string",
                        "description": "Suggested next action for user"
                    }
                },
                "required": ["message_type", "text", "follow_up_action"],
                "additionalProperties": False
            }
        },
        "required": ["message_content"],
        "additionalProperties": False
    }

    try:
        model = ChatGroq(
            model="moonshotai/kimi-k2-instruct",
            temperature=0.3,  # Slightly higher for more creative/varied responses
            max_tokens=1024,  # Larger context for full responses
            model_kwargs={
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "message_response",
                        "schema": message_schema,
                        "strict": True
                    }
                }
            }
        )

        logger.info("✅ Kimi K2 responder initialized with strict structured output")
        return model

    except Exception as e:
        logger.exception(f"❌ Failed to initialize Kimi K2 responder: {e}")
        raise
