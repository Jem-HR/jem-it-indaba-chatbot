"""LangGraph AI-Powered Prompt Injection Game

Architecture following jem_mobile/whatsapp_chatbot pattern:
- StateGraph with context_schema for static runtime context
- Postgres checkpointer for conversation state
- Kimi K2 via Groq for intelligent evaluation and responses
- Structured output with JSON schema validation
- Secure phone number injection via Runtime[GameContext]
"""

from .workflow import create_ai_game_agent
from .state import AIGameState
from .context import GameContext

__all__ = [
    "create_ai_game_agent",
    "AIGameState",
    "GameContext"
]
