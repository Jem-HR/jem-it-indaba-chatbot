"""Webhook handlers for WhatsApp messages and verification."""

import logging
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException, Query
from fastapi.responses import PlainTextResponse, JSONResponse

from app.config import config
from app.whatsapp import WhatsAppClient
from app.postgres_store import PostgresStore
from app import analytics
from app.security.webhook_verification import verify_webhook_signature, validate_webhook_payload

logger = logging.getLogger(__name__)


class WebhookHandler:
    """Handles WhatsApp webhook verification and message processing."""
    
    def __init__(self, game_store: PostgresStore, whatsapp_client: WhatsAppClient):
        """
        Initialize webhook handler.
        
        Args:
            game_store: Database store for game state
            whatsapp_client: WhatsApp API client
        """
        self.game_store = game_store
        self.whatsapp_client = whatsapp_client
    
    async def verify_webhook(
        self,
        hub_mode: str = Query(alias="hub.mode"),
        hub_challenge: str = Query(alias="hub.challenge"),
        hub_verify_token: str = Query(alias="hub.verify_token")
    ) -> PlainTextResponse:
        """
        Verify webhook endpoint for WhatsApp.
        
        Args:
            hub_mode: Webhook mode from WhatsApp
            hub_challenge: Challenge token from WhatsApp
            hub_verify_token: Verification token from WhatsApp
            
        Returns:
            PlainTextResponse with challenge token if valid
            
        Raises:
            HTTPException: If verification fails
        """
        logger.info(f"Webhook verification request: mode={hub_mode}, token={hub_verify_token}")

        if hub_mode == "subscribe" and hub_verify_token == config.WHATSAPP_VERIFY_TOKEN:
            logger.info("Webhook verified successfully")
            return PlainTextResponse(content=hub_challenge)
        else:
            logger.warning("Webhook verification failed")
            raise HTTPException(status_code=403, detail="Verification failed")
    
    async def handle_webhook(self, request: Request) -> JSONResponse:
        """
        Handle incoming webhook messages from WhatsApp.
        
        Args:
            request: FastAPI request object
            
        Returns:
            JSONResponse with status
        """
        try:
            # Get raw body for signature verification
            body = await request.body()
            payload = await request.json()

            # Log incoming webhook
            logger.info(f"Received webhook: {payload}")

            # Verify signature if enabled
            signature = request.headers.get("X-Hub-Signature-256", "")
            if not verify_webhook_signature(body, signature, config.WHATSAPP_APP_SECRET):
                logger.warning("Invalid webhook signature")
                raise HTTPException(status_code=403, detail="Invalid signature")
            
            # Validate payload structure
            if not validate_webhook_payload(payload):
                logger.warning("Invalid webhook payload structure")
                raise HTTPException(status_code=400, detail="Invalid payload")

            # Parse message
            message_data = WhatsAppClient.parse_webhook_message(payload)

            if message_data:
                # Process the message
                await self._process_message(
                    from_number=message_data["from"],
                    message_text=message_data["text"],
                    message_id=message_data["message_id"],
                    button_id=message_data.get("button_id")
                )

            # Always return 200 OK to WhatsApp
            return JSONResponse(content={"status": "ok"}, status_code=200)

        except Exception as e:
            logger.error(f"Error processing webhook: {e}", exc_info=True)
            # Still return 200 to avoid WhatsApp retries
            return JSONResponse(content={"status": "error"}, status_code=200)
    
    async def _process_message(
        self, 
        from_number: str, 
        message_text: str, 
        message_id: str, 
        button_id: Optional[str] = None
    ) -> None:
        """
        Process incoming WhatsApp message.
        
        Args:
            from_number: Sender's phone number
            message_text: Message content
            message_id: WhatsApp message ID
            button_id: Optional button ID if button click
        """
        try:
            logger.info(f"Processing WhatsApp message from {from_number}: {message_text} (button: {button_id})")

            # Mark message as read
            self.whatsapp_client.mark_message_read(message_id)

            # Import here to avoid circular imports
            from app.services.game_service import GameService
            from app.services.button_handler import ButtonHandler
            
            game_service = GameService(self.game_store, self.whatsapp_client)
            button_handler = ButtonHandler(self.game_store, self.whatsapp_client)

            # Handle button clicks
            if button_id:
                await button_handler.handle_button_click(from_number, button_id, message_text)
                return

            # Handle regular messages
            await game_service.process_user_message(from_number, message_text)

        except Exception as e:
            logger.exception(f"❌ Error processing webhook message: {e}")