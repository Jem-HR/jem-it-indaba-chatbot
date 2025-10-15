"""FastAPI application for WhatsApp prompt injection game."""

from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from datetime import datetime
from typing import Optional
import logging

from app.config import config
from app.whatsapp import create_whatsapp_client, WhatsAppClient
from app.postgres_store import PostgresStore
from app import analytics

# Configure logging FIRST (before any logging calls)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AI Game imports (LangGraph + Kimi K2)
AI_GAME_AVAILABLE = False
try:
    from langchain_core.messages import HumanMessage
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg_pool import AsyncConnectionPool
    from psycopg.rows import dict_row
    from app.ai_game.workflow_hackmerlin import create_hackmerlin_agent
    from app.ai_game.context import load_game_context
    AI_GAME_AVAILABLE = True
    logger.info("✅ AI Game imports successful")
except ImportError as e:
    logger.warning(f"⚠️ AI Game not available (missing dependencies): {e}")

# Initialize FastAPI app
app = FastAPI(
    title="IT Indaba 2025 WhatsApp Challenge",
    description="WhatsApp-based prompt injection game",
    version="1.0.0"
)

# Initialize clients
whatsapp_client: WhatsAppClient = create_whatsapp_client()

# Initialize Postgres store (will be fully set up in startup event)
game_store = None
try:
    game_store = PostgresStore()  # Postgres storage for all game state
    logger.info("✅ PostgresStore pre-initialized")
except Exception as e:
    logger.error(f"⚠️ PostgresStore initialization deferred: {e}")
    # Will be retried in startup event

# Initialize AI Game components (Postgres checkpointer for LangGraph)
# Following Puffin pattern: AsyncConnectionPool → AsyncPostgresSaver
ai_game_agent = None
postgres_checkpointer = None
postgres_pool = None

async def init_postgres_checkpointer():
    """Initialize Postgres checkpointer following Puffin pattern"""
    global postgres_checkpointer, postgres_pool

    if not AI_GAME_AVAILABLE:
        return

    if not config.POSTGRES_URI or config.POSTGRES_URI == "postgresql://localhost:5432/indaba_game":
        logger.info("ℹ️ Postgres not configured - AI game endpoint will be disabled")
        return

    try:
        logger.info(f"🔌 Creating Postgres connection pool: {config.POSTGRES_URI[:40]}...")

        # Create connection pool (Puffin pattern)
        postgres_pool = AsyncConnectionPool(
            conninfo=config.POSTGRES_URI,
            min_size=1,
            max_size=5,
            max_idle=300.0,  # 5 minutes
            max_lifetime=1800.0,  # 30 minutes
            timeout=30.0,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
                "row_factory": dict_row,
            },
            check=AsyncConnectionPool.check_connection
        )
        await postgres_pool.wait()

        # Create checkpointer from pool
        postgres_checkpointer = AsyncPostgresSaver(postgres_pool)

        # Setup tables
        await postgres_checkpointer.setup()

        logger.info("✅ Postgres checkpointer initialized for AI game")

    except Exception as e:
        logger.warning(f"⚠️ Postgres checkpointer not available (AI game disabled): {e}")


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
    postgres_healthy = False
    try:
        # Test Postgres connection
        if game_store:
            postgres_healthy = game_store.ping()
        else:
            logger.warning("game_store not initialized")
    except Exception as e:
        logger.error(f"Postgres health check failed: {e}")

    return {
        "status": "healthy" if postgres_healthy else "degraded",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "postgres": "up" if postgres_healthy else "down",
            "whatsapp": "configured" if config.WHATSAPP_API_TOKEN else "not configured",
            "game_store_initialized": game_store is not None
        }
    }


@app.get("/stats")
async def get_stats():
    """Get game statistics."""
    try:
        stats = game_store.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving statistics")


@app.get("/leaderboard")
async def get_leaderboard():
    """Get leaderboard showing all users and their progress.

    Returns:
    - All users sorted by level (highest first)
    - Winners sorted by completion time
    - First 5 winners eligible for prizes
    """
    try:
        leaderboard_data = game_store.get_leaderboard()
        all_users = leaderboard_data["all_users"]
        winners = leaderboard_data["winners"]

        return {
            "total_users": len(all_users),
            "total_winners": len(winners),
            "first_5_prize_eligible": winners[:5] if len(winners) >= 5 else winners,
            "all_winners": winners,
            "all_users_by_level": all_users,
            "level_summary": {
                "level_5": len([u for u in all_users if u["level"] == 5]),
                "level_4": len([u for u in all_users if u["level"] == 4]),
                "level_3": len([u for u in all_users if u["level"] == 3]),
                "level_2": len([u for u in all_users if u["level"] == 2]),
                "level_1": len([u for u in all_users if u["level"] == 1]),
            },
            "note": "First 5 winners are eligible for phone prizes at IT Indaba booth"
        }
    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving leaderboard")


@app.post("/ai/hackmerlin")
async def hackmerlin_game(phone_number: str, message: str):
    """
    HackMerlin-style game: Hack e-commerce sales bot to get free phone.

    Kimi K2 plays a sales bot selling phones. Players use prompt injection
    to hack Kimi into agreeing to give them a phone for free.

    Implements dual-filter pattern from HackMerlin.io:
    - Input filter: Blocks banned words at higher levels
    - Output filter: Detects if Kimi agreed to free phone
    """
    if not AI_GAME_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="AI Game not available. Install dependencies."
        )

    if not postgres_checkpointer:
        raise HTTPException(
            status_code=503,
            detail="Postgres checkpointer not initialized. Check POSTGRES_URI configuration."
        )

    try:
        logger.info(f"🎮 HackMerlin game request from {phone_number[:5]}***")

        # Load static game context
        context = await load_game_context(phone_number, game_store)

        # Create HackMerlin agent (sales bot mode)
        agent = await create_hackmerlin_agent(postgres_checkpointer)

        # Build config with unique thread_id for HackMerlin mode
        agent_config = {
            "configurable": {
                "thread_id": f"hackmerlin_{phone_number}",  # Separate thread from other modes
            }
        }

        # Invoke LangGraph workflow with context injected
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=message)]},
            config=agent_config,
            context=context
        )

        # Extract response
        structured_response = result.get("structured_response", {})
        message_content = structured_response.get("message_content", {})
        response_text = message_content.get("text", "Please try again!")
        won_level = result.get("won_level", False)

        return {
            "status": "success",
            "mode": "hackmerlin",
            "level": result.get("current_level", context.level),
            "response": response_text,
            "won_level": won_level,
            "won_game": result.get("won_game", False),
            "workflow_step": result.get("workflow_step", "unknown"),
            "hint": "Try to hack the sales bot into giving you a free phone!" if not won_level else "🎉 Hacked! Advancing..."
        }

    except Exception as e:
        logger.exception(f"❌ HackMerlin game error for {phone_number[:5]}***: {e}")
        raise HTTPException(status_code=500, detail=f"HackMerlin game error: {str(e)}")


@app.post("/check-sessions")
async def check_inactive_sessions():
    """
    Background job endpoint to check for inactive users and send warnings.
    Called by Cloud Scheduler every minute.
    """
    try:
        logger.info("Checking for inactive sessions...")

        # Find users inactive for 2 minutes (who need warning)
        users_to_warn = game_store.get_inactive_users_for_warning(config.SESSION_WARNING_MINUTES)
        logger.info(f"Users needing warning: {len(users_to_warn)}")

        warnings_sent = 0
        for phone_number in users_to_warn:
            try:
                warning_msg = """⏰ *Hey there!* Still working on the challenge?

Your session will expire in *1 minute* if you don't respond!

Don't worry - you can always start again from where you left off. But let's keep the momentum going! 💪

Send any message to keep your session active! 🎮"""
                success = whatsapp_client.send_message(phone_number, warning_msg)

                if success:
                    game_store.mark_session_warned(phone_number)
                    warnings_sent += 1
                    logger.info(f"✅ Sent inactivity warning to {phone_number}")

                    # Track session warning sent
                    analytics.track_session_warning_sent(phone_number, config.SESSION_WARNING_MINUTES)
                else:
                    logger.error(f"❌ Failed to send warning to {phone_number}")
            except Exception as e:
                logger.error(f"❌ Error sending warning to {phone_number}: {e}")

        logger.info(f"Session check complete. Warnings sent: {warnings_sent}/{len(users_to_warn)}")

        return {
            "status": "ok",
            "users_checked": len(users_to_warn),
            "warnings_sent": warnings_sent
        }
    except Exception as e:
        logger.error(f"Error in check_inactive_sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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
                message_id=message_data["message_id"],
                button_id=message_data.get("button_id")
            )

        # Always return 200 OK to WhatsApp
        return JSONResponse(content={"status": "ok"}, status_code=200)

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        # Still return 200 to avoid WhatsApp retries
        return JSONResponse(content={"status": "error"}, status_code=200)


async def process_message(from_number: str, message_text: str, message_id: str, button_id: Optional[str] = None):
    """
    Process incoming WhatsApp message using HackMerlin AI game.

    Args:
        from_number: Sender's phone number
        message_text: Text content of the message
        message_id: WhatsApp message ID
        button_id: Optional button ID if this is a button click
    """
    try:
        logger.info(f"Processing WhatsApp message from {from_number}: {message_text} (button: {button_id})")

        # Mark message as read
        whatsapp_client.mark_message_read(message_id)

        # Check if AI game is available
        if not AI_GAME_AVAILABLE or not postgres_checkpointer:
            logger.error("AI game not available, falling back to simple response")
            whatsapp_client.send_message(from_number, "Game temporarily unavailable. Please try again later!")
            return

        # Check if user is new (for welcome message)
        user_state = game_store.get_user_state(from_number)
        is_new_user = user_state is None

        if is_new_user:
            # New user - send welcome message with header image + buttons
            from app.ai_game.hackmerlin_prompts import get_hackmerlin_welcome_message
            user_state = game_store.create_new_user(from_number)
            response_text = get_hackmerlin_welcome_message()
            buttons = [
                ("continue", "▶️ Start Challenge"),
                ("how_to_play", "ℹ️ How to Play"),
                ("about_jem", "ℹ️ About Jem")
            ]

            analytics.track_user_started_game(from_number)
            game_store.add_message(from_number, "assistant", response_text)

            # Send with Opening message header image + buttons
            whatsapp_client.send_interactive_buttons(
                from_number,
                response_text,
                buttons,
                header_image_url=config.OPENING_HEADER_URL
            )
            logger.info(f"🎮 Sent welcome message to {from_number[:5]}***")
            return

        # Check session expiry (3 minutes of inactivity)
        now = datetime.now()
        time_since_last_active = (now - user_state.last_active).total_seconds() / 60

        if time_since_last_active >= config.SESSION_TIMEOUT_MINUTES:
            # Session expired - send Opening header + text + buttons
            from app.ai_game.hackmerlin_prompts import get_hackmerlin_session_expired_message
            game_store.start_new_session(from_number)
            response_text = get_hackmerlin_session_expired_message(user_state.level)
            buttons = [
                ("continue", "▶️ Continue"),
                ("how_to_play", "ℹ️ How to Play"),
                ("about_jem", "ℹ️ About Jem")
            ]

            analytics.track_session_expired(from_number, user_state.level)
            analytics.track_session_resumed(from_number, user_state.level)

            game_store.add_message(from_number, "user", message_text)
            game_store.add_message(from_number, "assistant", response_text)

            whatsapp_client.send_interactive_buttons(
                from_number,
                response_text,
                buttons,
                header_image_url=config.OPENING_HEADER_URL
            )
            logger.info(f"🔄 Sent session expired message to {from_number[:5]}***")
            return

        # Handle button clicks
        if button_id:
            game_store.add_message(from_number, "user", f"[Button: {message_text}]")

            if button_id == "how_to_play":
                from app.ai_game.hackmerlin_prompts import get_hackmerlin_how_to_play
                response_text = get_hackmerlin_how_to_play()

                # Add navigation buttons
                buttons = [
                    ("continue_game", "▶️ Continue Playing"),
                    ("main_menu", "🏠 Main Menu")
                ]

                game_store.add_message(from_number, "assistant", response_text)
                whatsapp_client.send_interactive_buttons(
                    from_number,
                    response_text,
                    buttons
                )
                logger.info(f"ℹ️ Sent how to play to {from_number[:5]}***")
                return

            elif button_id == "about_jem":
                response_text = """*📲 About Jem*

Jem is the HR and employee benefits platform built for deskless teams.

*Learn more:* https://www.jemhr.com/

Ready to continue? 🚀"""

                # Add navigation buttons
                buttons = [
                    ("continue_game", "▶️ Continue Playing"),
                    ("main_menu", "🏠 Main Menu")
                ]

                game_store.add_message(from_number, "assistant", response_text)
                whatsapp_client.send_interactive_buttons(
                    from_number,
                    response_text,
                    buttons
                )
                logger.info(f"ℹ️ Sent about Jem to {from_number[:5]}***")
                return

            elif button_id == "continue":
                # Continue button - always show current level intro
                from app.ai_game.hackmerlin_prompts import get_level_introduction
                from app.level_configs import LEVEL_CONFIGS

                user_state = game_store.get_user_state(from_number)

                if user_state:
                    level_config = LEVEL_CONFIGS.get(user_state.level)
                    if level_config:
                        intro_text = get_level_introduction(user_state.level, level_config["bot_name"])

                        # Only educational button
                        buttons = [
                            ("learn_defense", "🛡️ Learn More")
                        ]

                        whatsapp_client.send_interactive_buttons(
                            from_number,
                            intro_text,
                            buttons
                        )
                        logger.info(f"📱 Sent Level {user_state.level} intro after Continue button")
                        return

                # Fallback if no user state
                whatsapp_client.send_message(from_number, "Welcome! Starting game...")
                return

            elif button_id == "learn_defense":
                # Educational content about current level's vulnerability
                from app.ai_game.hackmerlin_prompts import get_vulnerability_education
                user_state = game_store.get_user_state(from_number)
                education_text = get_vulnerability_education(user_state.level)

                # Send with navigation buttons
                buttons = [
                    ("continue_game", "▶️ Continue Playing"),
                    ("main_menu", "🏠 Main Menu")
                ]

                whatsapp_client.send_interactive_buttons(
                    from_number,
                    education_text,
                    buttons
                )
                logger.info(f"🛡️ Sent vulnerability education for Level {user_state.level}")
                return

            elif button_id == "continue_game":
                # Show current level intro (from educational content or other info screens)
                from app.ai_game.hackmerlin_prompts import get_level_introduction
                from app.level_configs import LEVEL_CONFIGS

                user_state = game_store.get_user_state(from_number)

                if user_state:
                    level_config = LEVEL_CONFIGS.get(user_state.level)
                    if level_config:
                        intro_text = get_level_introduction(user_state.level, level_config["bot_name"])

                        # Only Learn More button (no confusing action buttons)
                        buttons = [
                            ("learn_defense", "🛡️ Learn More")
                        ]

                        whatsapp_client.send_interactive_buttons(
                            from_number,
                            intro_text,
                            buttons
                        )
                        logger.info(f"📱 Sent Level {user_state.level} intro from Continue Playing")
                        return

                # Fallback
                whatsapp_client.send_message(from_number, "💬 Type your message to hack the guardian...")
                return

            elif button_id == "main_menu":
                # Show main menu
                menu_text = """*🏠 MAIN MENU*

What would you like to do?"""

                buttons = [
                    ("continue_game", "▶️ Continue Playing"),
                    ("how_to_play", "ℹ️ How to Play"),
                    ("reset_progress", "🔄 Reset My Progress"),
                    ("about_jem", "ℹ️ About Jem")
                ]

                whatsapp_client.send_interactive_buttons(
                    from_number,
                    menu_text,
                    buttons
                )
                logger.info(f"🏠 Sent main menu")
                return

            elif button_id == "reset_progress":
                # Reset user's progress to start fresh
                success = game_store.reset_user_progress(from_number)

                if success:
                    reset_msg = """🔄 *PROGRESS RESET*

Your game progress has been cleared!
You'll start fresh from Level 1.

Ready to try again? Click continue!"""

                    buttons = [
                        ("continue", "▶️ Start Fresh"),
                        ("main_menu", "🏠 Main Menu")
                    ]

                    whatsapp_client.send_interactive_buttons(
                        from_number,
                        reset_msg,
                        buttons
                    )
                    logger.info(f"🔄 Reset progress for {from_number[:5]}***")
                else:
                    whatsapp_client.send_message(from_number, "Error resetting progress. Please try again.")

                return

            elif button_id.startswith("select_phone_"):
                # Phone selection after winning all 5 levels
                from app.ai_game.hackmerlin_prompts import get_phone_selection_confirmation

                phone_choices = {
                    "select_phone_huawei": "Huawei Nova Y73",
                    "select_phone_samsung": "Samsung Galaxy A16",
                    "select_phone_oppo": "Oppo A40"
                }

                phone_choice = phone_choices.get(button_id)

                if phone_choice:
                    # Save phone preference
                    game_store.set_phone_preference(from_number, phone_choice)

                    # Get user stats
                    user_state = game_store.get_user_state(from_number)
                    if user_state:
                        time_taken = (user_state.last_active - user_state.created_at).total_seconds() / 60

                        confirmation = get_phone_selection_confirmation(
                            phone_choice,
                            time_taken,
                            user_state.attempts
                        )

                        whatsapp_client.send_message(from_number, confirmation)
                        logger.info(f"🏆 {from_number[:5]}*** selected {phone_choice}")

                return

        # Invoke HackMerlin LangGraph agent (handles everything including WhatsApp sending)
        try:
            context = await load_game_context(from_number, game_store)
            agent = await create_hackmerlin_agent(postgres_checkpointer)

            agent_config = {
                "configurable": {
                    "thread_id": f"hackmerlin_{from_number}",
                }
            }

            # Invoke workflow - whatsapp_sender_node will send the message
            await agent.ainvoke(
                {"messages": [HumanMessage(content=message_text)]},
                config=agent_config,
                context=context
            )

            logger.info(f"✅ HackMerlin workflow completed for {from_number[:5]}***")

        except Exception as e:
            logger.exception(f"❌ HackMerlin workflow error for {from_number}: {e}")
            whatsapp_client.send_message(from_number, "Sorry, something went wrong! Please try again.")

    except Exception as e:
        logger.exception(f"❌ Error processing webhook message: {e}")


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

    # Test Postgres connection
    try:
        game_store.ping()
        logger.info("Postgres connection successful")
    except Exception as e:
        logger.error(f"Postgres connection failed: {e}")

    # Initialize PostHog analytics
    try:
        analytics.init_posthog(
            api_key=config.POSTHOG_API_KEY,
            host=config.POSTHOG_HOST
        )
    except Exception as e:
        logger.error(f"PostHog initialization failed: {e}")

    # Initialize Postgres checkpointer for AI game (async)
    await init_postgres_checkpointer()

    # Initialize AI game global dependencies
    if AI_GAME_AVAILABLE and postgres_checkpointer:
        from app.ai_game.nodes.update_state_node import set_game_store, set_whatsapp_client as set_update_whatsapp
        from app.ai_game.nodes.sender_node import set_whatsapp_client
        set_game_store(game_store)  # Use Postgres store
        set_whatsapp_client(whatsapp_client)
        set_update_whatsapp(whatsapp_client)  # Also set for update_state_node
        logger.info("✅ AI game global dependencies initialized")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info("Shutting down IT Indaba 2025 WhatsApp Challenge API")

    # Close Postgres pool if initialized
    global postgres_pool
    if postgres_pool:
        try:
            await postgres_pool.close()
            logger.info("✅ Postgres pool closed")
        except Exception as e:
            logger.error(f"Error closing Postgres pool: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
