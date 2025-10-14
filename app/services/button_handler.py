"""Button handler for processing interactive button responses."""

import logging
from typing import Optional

from app.postgres_store import PostgresStore
from app.whatsapp import WhatsAppClient
from app.config import config
from app import analytics
from app.services.message_formatter import MessageFormatter

logger = logging.getLogger(__name__)


class ButtonHandler:
    """Service for handling interactive button responses."""
    
    def __init__(self, game_store: PostgresStore, whatsapp_client: WhatsAppClient):
        """
        Initialize button handler.
        
        Args:
            game_store: Database store for game state
            whatsapp_client: WhatsApp API client
        """
        self.game_store = game_store
        self.whatsapp_client = whatsapp_client
    
    async def handle_button_click(self, phone_number: str, button_id: str, message_text: str) -> None:
        """
        Handle button click from user.
        
        Args:
            phone_number: User's phone number
            button_id: ID of clicked button
            message_text: Text of clicked button
        """
        try:
            self.game_store.add_message(phone_number, "user", f"[Button: {message_text}]")

            # Route to appropriate handler
            if button_id == "how_to_play":
                await self._handle_how_to_play(phone_number)
            elif button_id == "about_jem":
                await self._handle_about_jem(phone_number)
            elif button_id == "continue":
                await self._handle_continue(phone_number)
            elif button_id == "learn_defense":
                await self._handle_learn_defense(phone_number)
            elif button_id == "continue_game":
                # Just acknowledge, wait for actual message
                logger.info(f"▶️ User clicked continue game - waiting for their message")
            elif button_id == "main_menu":
                await self._handle_main_menu(phone_number)
            elif button_id == "reset_progress":
                await self._handle_reset_progress(phone_number)
            elif button_id.startswith("select_phone_"):
                await self._handle_phone_selection(phone_number, button_id)
            else:
                logger.warning(f"Unknown button ID: {button_id}")

        except Exception as e:
            logger.exception(f"Error handling button click: {e}")
            self.whatsapp_client.send_message(
                phone_number, 
                "Sorry, something went wrong! Please try again."
            )
    
    async def _handle_how_to_play(self, phone_number: str) -> None:
        """Handle how to play button."""
        response_text = MessageFormatter.format_how_to_play()
        self.game_store.add_message(phone_number, "assistant", response_text)
        self.whatsapp_client.send_message(phone_number, response_text)
        logger.info(f"ℹ️ Sent how to play to {phone_number[:5]}***")
    
    async def _handle_about_jem(self, phone_number: str) -> None:
        """Handle about Jem button."""
        response_text = MessageFormatter.format_about_jem()
        self.game_store.add_message(phone_number, "assistant", response_text)
        self.whatsapp_client.send_message(phone_number, response_text)
        logger.info(f"ℹ️ Sent about Jem to {phone_number[:5]}***")
    
    async def _handle_continue(self, phone_number: str) -> None:
        """Handle continue button."""
        user_state = self.game_store.get_user_state(phone_number)
        
        if user_state and user_state.level == 1:
            # Check if this is Level 1 start (no user messages yet)
            user_messages = [m for m in user_state.messages if m.role == "user" and not m.content.startswith("[Button:")]
            
            if len(user_messages) == 0:
                # First time at Level 1 - send intro
                from app.ai_game.hackmerlin_prompts import get_level_introduction
                from app.level_configs import LEVEL_CONFIGS

                intro_text = get_level_introduction(1, LEVEL_CONFIGS[1]["bot_name"])
                buttons = [
                    ("continue_game", "▶️ Start Hacking"),
                    ("learn_defense", "🛡️ Learn More")
                ]

                self.whatsapp_client.send_interactive_buttons(
                    phone_number,
                    intro_text,
                    buttons
                )
                logger.info(f"📱 Sent Level 1 intro to {phone_number[:5]}***")
                return
            else:
                logger.info(f"User has {len(user_messages)} user messages, not showing intro")
        else:
            logger.info(f"User state: {user_state.level if user_state else 'None'}")

        # Continue buttons just acknowledge - don't send to agent
        logger.info(f"▶️ User clicked continue - waiting for their actual message")
    
    async def _handle_learn_defense(self, phone_number: str) -> None:
        """Handle learn defense button."""
        from app.ai_game.hackmerlin_prompts import get_vulnerability_education
        
        user_state = self.game_store.get_user_state(phone_number)
        education_text = get_vulnerability_education(user_state.level)

        # Send with navigation buttons
        buttons = [
            ("continue_game", "▶️ Continue Playing"),
            ("main_menu", "🏠 Main Menu")
        ]

        self.whatsapp_client.send_interactive_buttons(
            phone_number,
            education_text,
            buttons
        )
        logger.info(f"🛡️ Sent vulnerability education for Level {user_state.level}")
    
    async def _handle_main_menu(self, phone_number: str) -> None:
        """Handle main menu button."""
        menu_text = """*🏠 MAIN MENU*

What would you like to do?"""

        buttons = [
            ("continue_game", "▶️ Continue Playing"),
            ("how_to_play", "ℹ️ How to Play"),
            ("reset_progress", "🔄 Reset My Progress"),
            ("about_jem", "ℹ️ About Jem")
        ]

        self.whatsapp_client.send_interactive_buttons(
            phone_number,
            menu_text,
            buttons
        )
        logger.info(f"🏠 Sent main menu")
    
    async def _handle_reset_progress(self, phone_number: str) -> None:
        """Handle reset progress button."""
        success = self.game_store.reset_user_progress(phone_number)

        if success:
            reset_msg = """🔄 *PROGRESS RESET*

Your game progress has been cleared!
You'll start fresh from Level 1.

Ready to try again? Click continue!"""

            buttons = [
                ("continue", "▶️ Start Fresh"),
                ("main_menu", "🏠 Main Menu")
            ]

            self.whatsapp_client.send_interactive_buttons(
                phone_number,
                reset_msg,
                buttons
            )
            logger.info(f"🔄 Reset progress for {phone_number[:5]}***")
        else:
            self.whatsapp_client.send_message(
                phone_number, 
                "Error resetting progress. Please try again."
            )
    
    async def _handle_phone_selection(self, phone_number: str, button_id: str) -> None:
        """Handle phone selection after winning."""
        from app.ai_game.hackmerlin_prompts import get_phone_selection_confirmation

        phone_choices = {
            "select_phone_huawei": "Huawei Nova Y73",
            "select_phone_samsung": "Samsung Galaxy A16",
            "select_phone_oppo": "Oppo A40"
        }

        phone_choice = phone_choices.get(button_id)

        if phone_choice:
            # Save phone preference
            self.game_store.set_phone_preference(phone_number, phone_choice)

            # Get user stats
            user_state = self.game_store.get_user_state(phone_number)
            if user_state:
                time_taken = (user_state.last_active - user_state.created_at).total_seconds() / 60

                confirmation = get_phone_selection_confirmation(
                    phone_choice,
                    time_taken,
                    user_state.attempts
                )

                self.whatsapp_client.send_message(phone_number, confirmation)
                logger.info(f"🏆 {phone_number[:5]}*** selected {phone_choice}")