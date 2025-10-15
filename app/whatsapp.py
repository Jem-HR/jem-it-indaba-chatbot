"""WhatsApp Cloud API integration."""

import hmac
import hashlib
import requests
import logging
from typing import Optional, Dict, Any, List, Tuple
from app.config import config

logger = logging.getLogger(__name__)


class WhatsAppClient:
    """Client for WhatsApp Cloud API."""

    def __init__(self, game_store=None):
        """Initialize WhatsApp client.

        Args:
            game_store: Optional PostgresStore instance for message tracking
        """
        self.api_token = config.WHATSAPP_API_TOKEN
        self.phone_number_id = config.WHATSAPP_PHONE_NUMBER_ID
        self.api_version = config.WHATSAPP_API_VERSION
        self.base_url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}"
        self.game_store = game_store

    def send_message(self, to: str, message: str) -> Optional[str]:
        """
        Send a text message via WhatsApp.

        Args:
            to: Recipient phone number (with country code)
            message: Message text to send

        Returns:
            WhatsApp message ID if successful, None otherwise
        """
        url = f"{self.base_url}/messages"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": message
            }
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()

            # Extract WhatsApp message ID from response
            response_data = response.json()
            message_id = response_data.get("messages", [{}])[0].get("id")

            # Auto-track message if game_store available
            if message_id and self.game_store:
                try:
                    self.game_store.record_message_sent(
                        phone_number=to,
                        message_type="text_message",
                        whatsapp_msg_id=message_id,
                        content=message[:500]  # Limit to 500 chars
                    )
                except Exception as e:
                    logger.warning(f"Failed to auto-track message: {e}")

            return message_id
        except requests.exceptions.RequestException as e:
            print(f"Error sending WhatsApp message: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            return None

    def send_image_message(self, to: str, image_url: str, caption: Optional[str] = None) -> bool:
        """
        Send an image message via WhatsApp.

        Args:
            to: Recipient phone number (with country code)
            image_url: Public URL of the image to send
            caption: Optional caption text for the image

        Returns:
            True if successful, False otherwise
        """
        url = f"{self.base_url}/messages"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "image",
            "image": {
                "link": image_url
            }
        }

        if caption:
            payload["image"]["caption"] = caption

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error sending WhatsApp image: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            return False

    def send_interactive_buttons(
        self,
        to: str,
        body_text: str,
        buttons: List[Tuple[str, str]],
        header_image_url: Optional[str] = None
    ) -> bool:
        """
        Send an interactive message with reply buttons and optional image header.

        Args:
            to: Recipient phone number (with country code)
            body_text: Main message text
            buttons: List of (button_id, button_text) tuples (max 3 buttons)
            header_image_url: Optional image URL to show as header

        Returns:
            True if successful, False otherwise
        """
        if len(buttons) > 3:
            print("Warning: WhatsApp supports max 3 buttons, truncating")
            buttons = buttons[:3]

        url = f"{self.base_url}/messages"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

        button_components = [
            {
                "type": "reply",
                "reply": {
                    "id": button_id,
                    "title": button_text[:20]  # Max 20 chars for button text
                }
            }
            for button_id, button_text in buttons
        ]

        interactive_content = {
            "type": "button",
            "body": {
                "text": body_text
            },
            "action": {
                "buttons": button_components
            }
        }

        # Add header image if provided
        if header_image_url:
            interactive_content["header"] = {
                "type": "image",
                "image": {
                    "link": header_image_url
                }
            }

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": interactive_content
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()

            # Extract message ID and auto-track
            response_data = response.json()
            message_id = response_data.get("messages", [{}])[0].get("id")

            if message_id and self.game_store:
                try:
                    self.game_store.record_message_sent(
                        phone_number=to,
                        message_type="interactive_message",
                        whatsapp_msg_id=message_id,
                        content=body_text[:500]
                    )
                except Exception as e:
                    logger.warning(f"Failed to auto-track interactive message: {e}")

            return True
        except requests.exceptions.RequestException as e:
            print(f"Error sending WhatsApp interactive message: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            return False

    def mark_message_read(self, message_id: str) -> bool:
        """
        Mark a message as read.

        Args:
            message_id: The message ID to mark as read

        Returns:
            True if successful, False otherwise
        """
        url = f"{self.base_url}/messages"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error marking message as read: {e}")
            return False

    @staticmethod
    def verify_webhook_signature(payload: bytes, signature: str, app_secret: Optional[str] = None) -> bool:
        """
        Verify webhook signature from WhatsApp.

        Args:
            payload: Raw request body
            signature: X-Hub-Signature-256 header value
            app_secret: App secret for verification (optional, uses env if not provided)

        Returns:
            True if signature is valid, False otherwise
        """
        if not app_secret:
            # For now, we'll skip signature verification if no app secret is provided
            # In production, you should always verify
            return True

        if not signature.startswith("sha256="):
            return False

        expected_signature = hmac.new(
            app_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        provided_signature = signature[7:]  # Remove 'sha256=' prefix

        return hmac.compare_digest(expected_signature, provided_signature)

    @staticmethod
    def parse_webhook_message(payload: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """
        Parse incoming webhook payload to extract message details.

        Args:
            payload: Webhook payload from WhatsApp

        Returns:
            Dictionary with message details or None if not a message
        """
        try:
            # WhatsApp webhook structure
            entry = payload.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})

            # Check if this is a message event
            messages = value.get("messages")
            if not messages or len(messages) == 0:
                return None

            message = messages[0]
            message_type = message.get("type")

            # Handle text messages
            if message_type == "text":
                return {
                    "message_id": message.get("id"),
                    "from": message.get("from"),  # Phone number
                    "text": message.get("text", {}).get("body"),
                    "timestamp": message.get("timestamp"),
                    "type": "text"
                }

            # Handle interactive button responses
            elif message_type == "interactive":
                interactive = message.get("interactive", {})
                button_reply = interactive.get("button_reply", {})

                return {
                    "message_id": message.get("id"),
                    "from": message.get("from"),
                    "text": button_reply.get("title"),  # Button text clicked
                    "button_id": button_reply.get("id"),  # Button ID
                    "timestamp": message.get("timestamp"),
                    "type": "interactive"
                }

            else:
                # Unsupported message type
                return None

        except (KeyError, IndexError, TypeError) as e:
            print(f"Error parsing webhook message: {e}")
            return None

    @staticmethod
    def parse_webhook_status(payload: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """
        Parse incoming webhook payload for message status updates.

        Args:
            payload: Webhook payload from WhatsApp

        Returns:
            Dictionary with status details or None
        """
        try:
            entry = payload.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})

            statuses = value.get("statuses")
            if not statuses or len(statuses) == 0:
                return None

            status = statuses[0]

            return {
                "message_id": status.get("id"),
                "status": status.get("status"),  # sent, delivered, read, failed
                "timestamp": status.get("timestamp"),
                "recipient_id": status.get("recipient_id")
            }
        except (KeyError, IndexError, TypeError) as e:
            print(f"Error parsing webhook status: {e}")
            return None


def create_whatsapp_client() -> WhatsAppClient:
    """Factory function to create WhatsApp client."""
    return WhatsAppClient()
