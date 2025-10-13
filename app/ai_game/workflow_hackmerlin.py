"""LangGraph Workflow for HackMerlin-Style Game

E-commerce sales bot that players try to hack for free phones.
Follows HackMerlin.io dual-filter pattern.
"""

import logging
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from .state import AIGameState
from .context import GameContext
from .nodes.sales_conversation_node import sales_conversation_node
from .nodes.update_state_node import update_state_node
from .nodes.sender_node import whatsapp_sender_node

logger = logging.getLogger(__name__)


def create_hackmerlin_workflow() -> StateGraph:
    """Create HackMerlin-style workflow for phone sales bot game

    Flow:
    START → sales_conversation → update_state → whatsapp_sender → END

    1. sales_conversation: Kimi plays e-commerce bot, dual filtering
    2. update_state: Updates Redis if player hacked successfully
    3. whatsapp_sender: Sends response via WhatsApp

    Returns:
        StateGraph configured for HackMerlin mode
    """
    logger.info("🏗️ Creating HackMerlin workflow (sales bot game)")

    # Create StateGraph with GameContext for static runtime context
    workflow = StateGraph(AIGameState, context_schema=GameContext)

    # ============================================================================
    # Add Nodes
    # ============================================================================

    workflow.add_node("sales_conversation", sales_conversation_node)  # Kimi sales bot with dual filtering
    workflow.add_node("update_state", update_state_node)             # Reuse existing (updates Redis)
    workflow.add_node("whatsapp_sender", whatsapp_sender_node)       # Reuse existing (sends WhatsApp)

    # ============================================================================
    # Define Workflow Edges
    # ============================================================================

    # Entry point: Start with sales conversation
    workflow.set_entry_point("sales_conversation")

    # Linear flow through all nodes
    workflow.add_edge("sales_conversation", "update_state")
    workflow.add_edge("update_state", "whatsapp_sender")

    # Terminal: WhatsApp sender → END
    workflow.add_edge("whatsapp_sender", END)

    logger.info("✅ HackMerlin workflow created: sales_conversation → update_state → send → END")
    return workflow


async def create_hackmerlin_agent(checkpointer: AsyncPostgresSaver):
    """Create compiled HackMerlin agent with Postgres checkpointer

    Args:
        checkpointer: AsyncPostgresSaver instance for conversation persistence

    Returns:
        Compiled LangGraph agent for HackMerlin mode
    """
    logger.info("🚀 Creating HackMerlin agent (sales bot game)")

    # Create workflow
    workflow = create_hackmerlin_workflow()

    # Compile with Postgres checkpointer
    agent = workflow.compile(checkpointer=checkpointer)

    logger.info("✅ HackMerlin agent compiled with Postgres checkpointer")
    return agent
