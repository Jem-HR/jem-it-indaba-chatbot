"""Session service for managing user sessions and inactivity warnings."""

import logging
from typing import List

from app.postgres_store import PostgresStore
from app.whatsapp import WhatsAppClient
from app.config import config
from app import analytics

logger = logging.getLogger(__name__)


class SessionService:
    """Service for managing user sessions and inactivity warnings."""
    
    def __init__(self, game_store: PostgresStore, whatsapp_client: WhatsAppClient):
        """
        Initialize session service.
        
        Args:
            game_store: Database store for game state
            whatsapp_client: WhatsApp API client
        """
        self.game_store = game_store
        self.whatsapp_client = whatsapp_client
    
    async def check_inactive_sessions(self) -> dict:
        """
        Check for inactive users and send warnings.
        
        Returns:
            Dictionary with check results
        """
        try:
            logger.info("Checking for inactive sessions...")

            # Find users inactive for warning threshold
            users_to_warn = self.game_store.get_inactive_users_for_warning(config.SESSION_WARNING_MINUTES)
            logger.info(f"Users needing warning: {len(users_to_warn)}")

            warnings_sent = 0
            for phone_number in users_to_warn:
                if await self._send_warning(phone_number):
                    warnings_sent += 1

            logger.info(f"Session check complete. Warnings sent: {warnings_sent}/{len(users_to_warn)}")

            return {
                "status": "ok",
                "users_checked": len(users_to_warn),
                "warnings_sent": warnings_sent
            }
        except Exception as e:
            logger.error(f"Error in check_inactive_sessions: {e}", exc_info=True)
            raise
    
    async def _send_warning(self, phone_number: str) -> bool:
        """
        Send inactivity warning to user.
        
        Args:
            phone_number: User's phone number
            
        Returns:
            True if warning sent successfully
        """
        try:
            warning_msg = """⏰ *Hey there!* Still working on the challenge?

Your session will expire in *1 minute* if you don't respond!

Don't worry - you can always start again from where you left off. But let's keep the momentum going! 💪

Send any message to keep your session active! 🎮"""
            
            success = self.whatsapp_client.send_message(phone_number, warning_msg)

            if success:
                self.game_store.mark_session_warned(phone_number)
                logger.info(f"✅ Sent inactivity warning to {phone_number}")
                
                # Track session warning sent
                analytics.track_session_warning_sent(phone_number, config.SESSION_WARNING_MINUTES)
                return True
            else:
                logger.error(f"❌ Failed to send warning to {phone_number}")
                return False

        except Exception as e:
            logger.error(f"❌ Error sending warning to {phone_number}: {e}")
            return False