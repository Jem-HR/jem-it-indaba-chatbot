"""LangGraph AI-Powered Prompt Injection Game - HackMerlin Mode Only

Architecture following jem_mobile/whatsapp_chatbot pattern:
- StateGraph with context_schema for static runtime context
- Postgres checkpointer for conversation state
- Kimi K2 via Groq for guardian characters
- AI self-evaluation for win detection
- Secure phone number injection via Runtime[GameContext]
"""

from .workflow_hackmerlin import create_hackmerlin_agent
from .state import AIGameState
from .context import GameContext

__all__ = [
    "create_hackmerlin_agent",
    "AIGameState",
    "GameContext"
]
