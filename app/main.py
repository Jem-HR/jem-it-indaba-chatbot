"""FastAPI application for WhatsApp prompt injection game."""

from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from datetime import datetime
import logging

from app.config import config
from app.whatsapp import create_whatsapp_client, WhatsAppClient
from app.redis_store import RedisStore
from app.game import PromptInjectionGame

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="IT Indaba 2025 WhatsApp Challenge",
    description="WhatsApp-based prompt injection game",
    version="1.0.0"
)

# Initialize clients
whatsapp_client: WhatsAppClient = create_whatsapp_client()
redis_store = RedisStore()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "IT Indaba 2025 WhatsApp Challenge API",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Test Redis connection
        redis_store.client.ping()
        redis_healthy = True
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        redis_healthy = False

    return {
        "status": "healthy" if redis_healthy else "degraded",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "redis": "up" if redis_healthy else "down",
            "whatsapp": "configured" if config.WHATSAPP_API_TOKEN else "not configured"
        }
    }


@app.get("/stats")
async def get_stats():
    """Get game statistics."""
    try:
        stats = redis_store.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving statistics")


@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_challenge: str = Query(alias="hub.challenge"),
    hub_verify_token: str = Query(alias="hub.verify_token")
):
    """
    Webhook verification endpoint for WhatsApp.
    WhatsApp will call this to verify the webhook URL.
    """
    logger.info(f"Webhook verification request: mode={hub_mode}, token={hub_verify_token}")

    # Verify the token matches
    if hub_mode == "subscribe" and hub_verify_token == config.WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook verified successfully")
        return PlainTextResponse(content=hub_challenge)
    else:
        logger.warning("Webhook verification failed")
        raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook")
async def webhook(request: Request):
    """
    Webhook endpoint to receive WhatsApp messages.
    """
    try:
        # Get raw body for signature verification
        body = await request.body()
        payload = await request.json()

        # Log incoming webhook
        logger.info(f"Received webhook: {payload}")

        # Verify signature (optional but recommended)
        signature = request.headers.get("X-Hub-Signature-256", "")
        # if not WhatsAppClient.verify_webhook_signature(body, signature):
        #     logger.warning("Invalid webhook signature")
        #     raise HTTPException(status_code=403, detail="Invalid signature")

        # Parse message
        message_data = WhatsAppClient.parse_webhook_message(payload)

        if message_data:
            # Process the message
            await process_message(
                from_number=message_data["from"],
                message_text=message_data["text"],
                message_id=message_data["message_id"]
            )

        # Always return 200 OK to WhatsApp
        return JSONResponse(content={"status": "ok"}, status_code=200)

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        # Still return 200 to avoid WhatsApp retries
        return JSONResponse(content={"status": "error"}, status_code=200)


async def process_message(from_number: str, message_text: str, message_id: str):
    """
    Process incoming WhatsApp message and generate response.

    Args:
        from_number: Sender's phone number
        message_text: Text content of the message
        message_id: WhatsApp message ID
    """
    try:
        logger.info(f"Processing message from {from_number}: {message_text}")

        # Mark message as read
        whatsapp_client.mark_message_read(message_id)

        # Get or create user state
        user_state = redis_store.get_user_state(from_number)
        is_new_user = user_state is None

        if is_new_user:
            # New user - send welcome message
            user_state = redis_store.create_new_user(from_number)
            response_text = PromptInjectionGame.get_welcome_message()

            # Save welcome message to history
            redis_store.add_message(from_number, "assistant", response_text)

            # Send response
            whatsapp_client.send_message(from_number, response_text)
            return

        # Add user message to history
        redis_store.add_message(from_number, "user", message_text)

        # Check if user already won
        if user_state.won:
            response_text = "🎉 You've already won! Your code is: *INDABA2025*\n\nVisit the IT Indaba booth to claim your prize! 🎁"
            redis_store.add_message(from_number, "assistant", response_text)
            whatsapp_client.send_message(from_number, response_text)
            return

        # Check if this is first message in current level
        # Count messages at current level
        level_messages = [
            msg for msg in user_state.messages
            if msg.role == "assistant" and (
                f"LEVEL {user_state.level}" in msg.content.upper() or
                "Hi! I'm" in msg.content or
                "Hello! I'm" in msg.content or
                "Greetings! I'm" in msg.content or
                "Welcome! I'm" in msg.content or
                "Hey! I'm" in msg.content
            )
        ]
        is_first_message_in_level = len(level_messages) == 0

        # Generate response based on game logic
        response_text, won_level = PromptInjectionGame.generate_response(
            user_message=message_text,
            level=user_state.level,
            is_first_message=is_first_message_in_level
        )

        if won_level:
            # User beat this level!
            new_level = user_state.level + 1

            if new_level > config.MAX_LEVELS:
                # User won the entire game!
                redis_store.mark_as_won(from_number)
                response_text = PromptInjectionGame.get_final_win_message()
            else:
                # Move to next level
                redis_store.update_level(from_number, new_level)
                # Append next level intro
                response_text += "\n\n" + PromptInjectionGame.get_level_message(new_level)

        # Save assistant response
        redis_store.add_message(from_number, "assistant", response_text)

        # Send response
        success = whatsapp_client.send_message(from_number, response_text)

        if success:
            logger.info(f"Response sent successfully to {from_number}")
        else:
            logger.error(f"Failed to send response to {from_number}")

    except Exception as e:
        logger.error(f"Error in process_message: {e}", exc_info=True)
        # Try to send error message to user
        try:
            error_msg = "Sorry, something went wrong! 😅 Please try again."
            whatsapp_client.send_message(from_number, error_msg)
        except Exception:
            pass


@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info("Starting IT Indaba 2025 WhatsApp Challenge API")
    logger.info(f"Environment: {config.GCP_PROJECT_ID}")

    # Validate configuration
    try:
        config.validate()
        logger.info("Configuration validated successfully")
    except ValueError as e:
        logger.error(f"Configuration validation failed: {e}")

    # Test Redis connection
    try:
        redis_store.client.ping()
        logger.info("Redis connection successful")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info("Shutting down IT Indaba 2025 WhatsApp Challenge API")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
