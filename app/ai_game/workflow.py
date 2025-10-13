"""LangGraph Workflow for AI-Powered Game

Following jem_mobile architecture:
- StateGraph with context_schema for static runtime context
- Postgres checkpointer for conversation state
- Nodes connected in linear flow to END
"""

import logging
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver

from .state import AIGameState
from .context import GameContext
from .nodes import (
    evaluation_node,
    response_node,
    update_state_node,
    whatsapp_sender_node
)

logger = logging.getLogger(__name__)


def create_ai_game_workflow() -> StateGraph:
    """Create LangGraph workflow for AI game

    Flow:
    START → evaluate_message → generate_response → update_state → whatsapp_sender → END

    Returns:
        StateGraph configured with all nodes and edges
    """
    logger.info("🏗️ Creating AI game workflow")

    # Create StateGraph with AIGameState and GameContext for static runtime context
    # Following jem_mobile pattern: context_schema injects GameContext via Runtime
    workflow = StateGraph(AIGameState, context_schema=GameContext)

    # ============================================================================
    # Add Nodes
    # ============================================================================

    workflow.add_node("evaluate_message", evaluation_node)      # Kimi evaluates player message
    workflow.add_node("generate_response", response_node)       # Kimi generates response
    workflow.add_node("update_state", update_state_node)        # Update Redis state
    workflow.add_node("whatsapp_sender", whatsapp_sender_node)  # Send via WhatsApp (END node)

    # ============================================================================
    # Define Workflow Edges - Linear Flow
    # ============================================================================

    # Entry point: Start with evaluation
    workflow.set_entry_point("evaluate_message")

    # Linear flow through all nodes
    workflow.add_edge("evaluate_message", "generate_response")
    workflow.add_edge("generate_response", "update_state")
    workflow.add_edge("update_state", "whatsapp_sender")

    # Terminal: WhatsApp sender → END (conversation turn completes)
    workflow.add_edge("whatsapp_sender", END)

    logger.info("✅ AI game workflow created: evaluate → respond → update → send → END")
    return workflow


async def create_ai_game_agent(checkpointer: PostgresSaver):
    """Create compiled LangGraph agent with Postgres checkpointer

    Args:
        checkpointer: PostgresSaver instance for conversation state persistence

    Returns:
        Compiled LangGraph agent ready for invocation
    """
    logger.info("🚀 Creating AI game agent")

    # Create workflow
    workflow = create_ai_game_workflow()

    # Compile with Postgres checkpointer
    agent = workflow.compile(checkpointer=checkpointer)

    logger.info("✅ AI game agent compiled with Postgres checkpointer")
    return agent
