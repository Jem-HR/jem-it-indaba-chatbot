"""Webhook signature verification for WhatsApp security."""

import hmac
import hashlib
import logging
from typing import Optional

from app.config import config

logger = logging.getLogger(__name__)


def verify_webhook_signature(payload: bytes, signature: str, app_secret: Optional[str] = None) -> bool:
    """
    Verify webhook signature from WhatsApp.
    
    Args:
        payload: Raw request body
        signature: X-Hub-Signature-256 header value
        app_secret: App secret for verification (optional, uses config if not provided)
        
    Returns:
        True if signature is valid, False otherwise
    """
    if not config.ENABLE_WEBHOOK_SIGNATURE_VERIFICATION:
        logger.warning("Webhook signature verification is disabled")
        return True
    
    if not app_secret:
        app_secret = config.WHATSAPP_APP_SECRET
        
    if not app_secret:
        logger.error("WhatsApp app secret not configured for signature verification")
        return False

    if not signature.startswith("sha256="):
        logger.warning("Invalid signature format - missing sha256= prefix")
        return False

    try:
        expected_signature = hmac.new(
            app_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        provided_signature = signature[7:]  # Remove 'sha256=' prefix

        # Use constant-time comparison to prevent timing attacks
        is_valid = hmac.compare_digest(expected_signature, provided_signature)
        
        if not is_valid:
            logger.warning("Webhook signature verification failed")
            
        return is_valid

    except Exception as e:
        logger.error(f"Error verifying webhook signature: {e}")
        return False


def validate_webhook_payload(payload: dict) -> bool:
    """
    Validate webhook payload structure.
    
    Args:
        payload: Webhook payload from WhatsApp
        
    Returns:
        True if payload structure is valid, False otherwise
    """
    try:
        # Check basic structure
        if not isinstance(payload, dict):
            return False
            
        entry = payload.get("entry", [])
        if not isinstance(entry, list) or len(entry) == 0:
            return False
            
        changes = entry[0].get("changes", [])
        if not isinstance(changes, list) or len(changes) == 0:
            return False
            
        value = changes[0].get("value", {})
        if not isinstance(value, dict):
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"Error validating webhook payload: {e}")
        return False