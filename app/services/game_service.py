"""Game service for handling game logic and AI interactions."""

import logging
from datetime import datetime
from typing import Optional

from app.postgres_store import PostgresStore
from app.whatsapp import WhatsAppClient
from app.config import config
from app import analytics

logger = logging.getLogger(__name__)


class GameService:
    """Service for handling game logic and AI interactions."""
    
    def __init__(self, game_store: PostgresStore, whatsapp_client: WhatsAppClient):
        """
        Initialize game service.
        
        Args:
            game_store: Database store for game state
            whatsapp_client: WhatsApp API client
        """
        self.game_store = game_store
        self.whatsapp_client = whatsapp_client
    
    async def process_user_message(self, phone_number: str, message_text: str) -> None:
        """
        Process user message through AI game workflow.
        
        Args:
            phone_number: User's phone number
            message_text: User's message content
        """
        try:
            # Check if user is new
            user_state = self.game_store.get_user_state(phone_number)
            is_new_user = user_state is None

            if is_new_user:
                await self._handle_new_user(phone_number)
                return

            # Check session expiry
            if self._is_session_expired(user_state):
                await self._handle_session_expired(phone_number, user_state)
                return

            # Process through AI game
            await self._process_ai_game(phone_number, message_text)

        except Exception as e:
            logger.exception(f"Error processing user message: {e}")
            self.whatsapp_client.send_message(
                phone_number, 
                "Sorry, something went wrong! Please try again."
            )
    
    async def _handle_new_user(self, phone_number: str) -> None:
        """Handle new user registration and welcome message."""
        from app.ai_game.hackmerlin_prompts import get_hackmerlin_welcome_message
        
        user_state = self.game_store.create_new_user(phone_number)
        response_text = get_hackmerlin_welcome_message()
        buttons = [
            ("continue", "▶️ Start Challenge"),
            ("how_to_play", "ℹ️ How to Play"),
            ("about_jem", "ℹ️ About Jem")
        ]

        analytics.track_user_started_game(phone_number)
        self.game_store.add_message(phone_number, "assistant", response_text)

        self.whatsapp_client.send_interactive_buttons(
            phone_number,
            response_text,
            buttons,
            header_image_url=config.OPENING_HEADER_URL
        )
        logger.info(f"🎮 Sent welcome message to {phone_number[:5]}***")
    
    async def _handle_session_expired(self, phone_number: str, user_state) -> None:
        """Handle session expiry with welcome back message."""
        from app.ai_game.hackmerlin_prompts import get_hackmerlin_session_expired_message
        
        self.game_store.start_new_session(phone_number)
        response_text = get_hackmerlin_session_expired_message(user_state.level)
        buttons = [
            ("continue", "▶️ Continue"),
            ("how_to_play", "ℹ️ How to Play"),
            ("about_jem", "ℹ️ About Jem")
        ]

        analytics.track_session_expired(phone_number, user_state.level)
        analytics.track_session_resumed(phone_number, user_state.level)

        self.game_store.add_message(phone_number, "user", "Session expired - user returned")
        self.game_store.add_message(phone_number, "assistant", response_text)

        self.whatsapp_client.send_interactive_buttons(
            phone_number,
            response_text,
            buttons,
            header_image_url=config.OPENING_HEADER_URL
        )
        logger.info(f"🔄 Sent session expired message to {phone_number[:5]}***")
    
    async def _process_ai_game(self, phone_number: str, message_text: str) -> None:
        """Process message through AI game workflow."""
        # Check if AI game is available
        try:
            from app.ai_game.context import load_game_context
            from app.ai_game.workflow_hackmerlin import create_hackmerlin_agent
            from langchain_core.messages import HumanMessage
            
            # Import global checkpointer from main module
            import sys
            main_module = sys.modules.get('app.main')
            if not main_module or not main_module.postgres_checkpointer:
                logger.error("AI game not available - checkpointer not initialized")
                self.whatsapp_client.send_message(
                    phone_number, 
                    "Game temporarily unavailable. Please try again later!"
                )
                return

            context = await load_game_context(phone_number, self.game_store)
            agent = await create_hackmerlin_agent(main_module.postgres_checkpointer)

            agent_config = {
                "configurable": {
                    "thread_id": f"hackmerlin_{phone_number}",
                }
            }

            # Invoke workflow - whatsapp_sender_node will send the message
            await agent.ainvoke(
                {"messages": [HumanMessage(content=message_text)]},
                config=agent_config,
                context=context
            )

            logger.info(f"✅ HackMerlin workflow completed for {phone_number[:5]}***")

        except ImportError as e:
            logger.error(f"AI game dependencies not available: {e}")
            self.whatsapp_client.send_message(
                phone_number, 
                "Game temporarily unavailable. Please try again later!"
            )
        except Exception as e:
            logger.exception(f"❌ HackMerlin workflow error for {phone_number}: {e}")
            self.whatsapp_client.send_message(
                phone_number, 
                "Sorry, something went wrong! Please try again."
            )
    
    def _is_session_expired(self, user_state) -> bool:
        """Check if user session has expired."""
        now = datetime.now()
        time_since_last_active = (now - user_state.last_active).total_seconds() / 60
        return time_since_last_active >= config.SESSION_TIMEOUT_MINUTES