"""LangGraph State Schema for AI Game

Defines dynamic game state that changes during gameplay.
Phone number is in GameContext (static runtime context), NOT here.
"""

from typing import Optional, Dict, Any
from langgraph.graph import MessagesState


class AIGameState(MessagesState):
    """Dynamic game state for AI-powered prompt injection game

    SECURITY NOTE: phone_number is in GameContext (static runtime context).
    LLM never sees or modifies phone_number. Access via runtime.context.phone_number

    This state contains only dynamic data that changes during conversation.
    """

    # Current game status
    current_level: Optional[int]  # 1-5
    won_level: Optional[bool]  # Just won current level
    won_game: Optional[bool]  # Completed all 5 levels

    # Kimi's evaluation result
    evaluation_result: Optional[Dict[str, Any]]  # {passed: bool, reasoning: str, detected_pattern: str|null}

    # Sales bot response (for HackMerlin mode self-evaluation)
    sales_bot_response: Optional[str]  # The response to be evaluated

    # Structured output for WhatsApp (MessageResponse from Kimi)
    structured_response: Optional[Dict[str, Any]]  # Dict format for WhatsApp sender
    whatsapp_ready: Optional[bool]  # Ready to send via WhatsApp

    # Workflow tracking
    workflow_step: Optional[str]  # Current workflow position

    # Analytics
    conversation_id: Optional[str]  # For tracking conversation flow
