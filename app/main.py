"""FastAPI application for WhatsApp prompt injection game."""

from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from datetime import datetime
from typing import Optional
import logging

from app.config import config
from app.whatsapp import create_whatsapp_client, WhatsAppClient
from app.redis_store import RedisStore
from app.game import PromptInjectionGame
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
    from app.ai_game.workflow import create_ai_game_agent
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
redis_store = RedisStore()

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


@app.get("/leaderboard")
async def get_leaderboard():
    """Get leaderboard showing all users and their progress.

    Returns:
    - All users sorted by level (highest first)
    - Winners sorted by completion time
    - First 5 winners eligible for prizes
    """
    try:
        leaderboard_data = redis_store.get_leaderboard()
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


@app.post("/test/message")
async def test_message(phone_number: str, message: str):
    """
    Test endpoint to simulate message processing without WhatsApp.
    Directly tests game logic and level progression.
    """
    try:
        # Get or create user state
        user_state = redis_store.get_user_state(phone_number)
        is_new_user = user_state is None

        if is_new_user:
            user_state = redis_store.create_new_user(phone_number)
            response_text = PromptInjectionGame.get_welcome_message()
            redis_store.add_message(phone_number, "assistant", response_text)
            return {
                "status": "new_user",
                "level": 1,
                "response": response_text,
                "won_level": False,
                "won_game": False
            }

        # Add user message to history
        redis_store.add_message(phone_number, "user", message)

        # Check if user already won
        if user_state.won:
            return {
                "status": "already_won",
                "level": user_state.level,
                "response": "🎉 You've already won! Your code is: *INDABA2025*",
                "won_level": False,
                "won_game": True
            }

        # Check if this is first message in current level
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
            user_message=message,
            level=user_state.level,
            is_first_message=is_first_message_in_level,
            phone_number=phone_number
        )

        now = datetime.now()
        current_level = user_state.level
        won_game = False

        if won_level:
            new_level = current_level + 1

            if new_level > config.MAX_LEVELS:
                # User won the entire game!
                redis_store.mark_as_won(phone_number)
                response_text = PromptInjectionGame.get_final_win_message()
                won_game = True
            else:
                # Move to next level
                redis_store.update_level(phone_number, new_level)
                response_text += "\n\n" + PromptInjectionGame.get_level_message(new_level)

        # Save assistant response
        redis_store.add_message(phone_number, "assistant", response_text)

        return {
            "status": "processed",
            "level": user_state.level if not won_level else (user_state.level + 1 if user_state.level < config.MAX_LEVELS else user_state.level),
            "response": response_text,
            "won_level": won_level,
            "won_game": won_game,
            "attempts": user_state.attempts + 1
        }

    except Exception as e:
        logger.error(f"Error in test_message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ai/message")
async def ai_game_message(phone_number: str, message: str):
    """
    AI-powered game endpoint using LangGraph + Kimi K2.
    Uses Kimi K2 for intelligent evaluation and response generation.

    Separate from pattern-matching version for comparison.
    """
    if not AI_GAME_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="AI Game not available. Install dependencies: pip install langgraph groq langchain-groq langgraph-checkpoint-postgres"
        )

    if not postgres_checkpointer:
        raise HTTPException(
            status_code=503,
            detail="Postgres checkpointer not initialized. Check POSTGRES_URI configuration."
        )

    try:
        logger.info(f"🤖 AI game request from {phone_number[:5]}***")

        # Load static game context (includes phone_number securely in Runtime context)
        context = await load_game_context(phone_number, redis_store)

        # Create/get AI game agent
        agent = await create_ai_game_agent(postgres_checkpointer)

        # Build config with thread_id for conversation persistence
        agent_config = {
            "configurable": {
                "thread_id": phone_number,  # Per-user conversation thread
            }
        }

        # Invoke LangGraph workflow with context injected
        # Context (with phone_number) accessible via Runtime[GameContext] in nodes
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=message)]},
            config=agent_config,
            context=context  # Inject GameContext here (phone_number secured)
        )

        # Extract response from result
        structured_response = result.get("structured_response", {})
        message_content = structured_response.get("message_content", {})
        response_text = message_content.get("text", "Keep trying!")

        return {
            "status": "success",
            "level": result.get("current_level", context.level),
            "won_level": result.get("won_level", False),
            "won_game": result.get("won_game", False),
            "response": response_text,
            "workflow_step": result.get("workflow_step", "unknown")
        }

    except Exception as e:
        logger.exception(f"❌ AI game error for {phone_number[:5]}***: {e}")
        raise HTTPException(status_code=500, detail=f"AI game error: {str(e)}")


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
        context = await load_game_context(phone_number, redis_store)

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

        # Get all user keys for debugging
        all_keys = redis_store.client.keys("user:*")
        logger.info(f"Total users in Redis: {len(all_keys)}")

        # Find users inactive for 2 minutes (who need warning)
        users_to_warn = redis_store.get_inactive_users_for_warning(config.SESSION_WARNING_MINUTES)
        logger.info(f"Users needing warning: {len(users_to_warn)}")

        warnings_sent = 0
        for phone_number in users_to_warn:
            try:
                warning_msg = PromptInjectionGame.get_session_warning_message()
                success = whatsapp_client.send_message(phone_number, warning_msg)

                if success:
                    redis_store.mark_session_warned(phone_number)
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
            "total_users": len(all_keys),
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
        user_state = redis_store.get_user_state(from_number)
        is_new_user = user_state is None

        if is_new_user:
            # New user - send welcome message with header image + buttons
            from app.ai_game.hackmerlin_prompts import get_hackmerlin_welcome_message
            user_state = redis_store.create_new_user(from_number)
            response_text = get_hackmerlin_welcome_message()
            buttons = [
                ("continue", "▶️ Start Challenge"),
                ("how_to_play", "ℹ️ How to Play"),
                ("about_jem", "ℹ️ About Jem")
            ]

            analytics.track_user_started_game(from_number)
            redis_store.add_message(from_number, "assistant", response_text)

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
            redis_store.start_new_session(from_number)
            response_text = get_hackmerlin_session_expired_message(user_state.level)
            buttons = [
                ("continue", "▶️ Continue"),
                ("how_to_play", "ℹ️ How to Play"),
                ("about_jem", "ℹ️ About Jem")
            ]

            analytics.track_session_expired(from_number, user_state.level)
            analytics.track_session_resumed(from_number, user_state.level)

            redis_store.add_message(from_number, "user", message_text)
            redis_store.add_message(from_number, "assistant", response_text)

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
            redis_store.add_message(from_number, "user", f"[Button: {message_text}]")

            if button_id == "how_to_play":
                from app.ai_game.hackmerlin_prompts import get_hackmerlin_how_to_play
                response_text = get_hackmerlin_how_to_play()
                redis_store.add_message(from_number, "assistant", response_text)
                whatsapp_client.send_message(from_number, response_text)
                logger.info(f"ℹ️ Sent how to play to {from_number[:5]}***")
                return

            elif button_id == "about_jem":
                response_text = PromptInjectionGame.get_about_jem_message()
                redis_store.add_message(from_number, "assistant", response_text)
                whatsapp_client.send_message(from_number, response_text)
                logger.info(f"ℹ️ Sent about Jem to {from_number[:5]}***")
                return

            elif button_id == "continue":
                # Continue button - proceed to game
                logger.info(f"▶️ User clicked continue, proceeding to HackMerlin game")
                # Fall through to invoke agent below

            elif button_id == "learn_defense":
                # Educational content about current level's vulnerability
                from app.ai_game.hackmerlin_prompts import get_vulnerability_education
                user_state = redis_store.get_user_state(from_number)
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
                # User wants to continue playing - proceed to agent
                logger.info(f"▶️ User continuing game from educational content")
                # Fall through to invoke agent below

            elif button_id == "main_menu":
                # Show main menu
                menu_text = """*🏠 MAIN MENU*

What would you like to do?"""

                buttons = [
                    ("continue_game", "▶️ Continue Playing"),
                    ("how_to_play", "ℹ️ How to Play"),
                    ("about_jem", "ℹ️ About Jem")
                ]

                whatsapp_client.send_interactive_buttons(
                    from_number,
                    menu_text,
                    buttons
                )
                logger.info(f"🏠 Sent main menu")
                return

        # Invoke HackMerlin LangGraph agent (handles everything including WhatsApp sending)
        try:
            context = await load_game_context(from_number, redis_store)
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


async def process_message_old_pattern_matching(from_number: str, message_text: str, message_id: str, button_id: Optional[str] = None):
    """
    OLD PATTERN-MATCHING VERSION - Kept for reference
    Process incoming WhatsApp message and generate response.

    Args:
        from_number: Sender's phone number
        message_text: Text content of the message
        message_id: WhatsApp message ID
        button_id: Optional button ID if this is a button click
    """
    try:
        logger.info(f"Processing message from {from_number}: {message_text} (button: {button_id})")

        # Mark message as read
        whatsapp_client.mark_message_read(message_id)

        # Get or create user state
        user_state = redis_store.get_user_state(from_number)
        is_new_user = user_state is None

        if is_new_user:
            # New user - send welcome message with header image + buttons in ONE message
            user_state = redis_store.create_new_user(from_number)
            response_text = PromptInjectionGame.get_welcome_message()
            buttons = PromptInjectionGame.get_session_expired_buttons()  # Same buttons for consistency

            # Track new user
            analytics.track_user_started_game(from_number)

            # Save welcome message to history
            redis_store.add_message(from_number, "assistant", response_text)

            # Send with Opening message header image + buttons in single message
            whatsapp_client.send_interactive_buttons(
                from_number,
                response_text,
                buttons,
                header_image_url=config.OPENING_HEADER_URL
            )
            return

        # Check session expiry (3 minutes of inactivity)
        now = datetime.now()
        time_since_last_active = (now - user_state.last_active).total_seconds() / 60

        if time_since_last_active >= config.SESSION_TIMEOUT_MINUTES:
            # Session expired - send Opening header + text + buttons in ONE message
            redis_store.start_new_session(from_number)
            response_text = PromptInjectionGame.get_session_expired_message(user_state.level)
            buttons = PromptInjectionGame.get_session_expired_buttons()

            # Track session expiry and resumption
            analytics.track_session_expired(from_number, user_state.level)
            analytics.track_session_resumed(from_number, user_state.level)

            redis_store.add_message(from_number, "user", message_text)
            redis_store.add_message(from_number, "assistant", f"[Opening Header + Interactive Message] {response_text}")

            # Send Opening message header + text + buttons in SINGLE message
            whatsapp_client.send_interactive_buttons(
                from_number,
                response_text,
                buttons,
                header_image_url=config.OPENING_HEADER_URL
            )
            return

        # Handle button clicks
        if button_id:
            redis_store.add_message(from_number, "user", f"[Button: {message_text}]")
            analytics.track_button_clicked(from_number, button_id, "session_expired" if time_since_last_active >= config.SESSION_TIMEOUT_MINUTES else "in_session")

            if button_id == "how_to_play":
                analytics.track_help_requested(from_number, user_state.level)
                response_text = PromptInjectionGame.get_how_to_play_message()
                redis_store.add_message(from_number, "assistant", response_text)
                whatsapp_client.send_message(from_number, response_text)
                return

            elif button_id == "about_jem":
                response_text = PromptInjectionGame.get_about_jem_message()
                redis_store.add_message(from_number, "assistant", response_text)
                whatsapp_client.send_message(from_number, response_text)
                return

            elif button_id == "continue":
                # Continue button - proceed with game
                # Just add the button click to history and continue below
                pass

        # Add user message to history (if not already added by button handler)
        if not button_id or button_id == "continue":
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
            is_first_message=is_first_message_in_level,
            phone_number=from_number
        )

        if won_level:
            # User beat this level!
            current_level = user_state.level
            new_level = current_level + 1

            # Track level completion
            time_on_level = (now - user_state.session_started_at).total_seconds() if user_state.session_started_at else None
            analytics.track_level_completed(from_number, current_level, user_state.attempts, time_on_level)

            if new_level > config.MAX_LEVELS:
                # User won the entire game!
                redis_store.mark_as_won(from_number)
                response_text = PromptInjectionGame.get_final_win_message()

                # Track game won
                total_time = (now - user_state.created_at).total_seconds() if user_state.created_at else None
                analytics.track_game_won(from_number, user_state.attempts, total_time)
            else:
                # Move to next level
                redis_store.update_level(from_number, new_level)
                # Append next level intro
                response_text += "\n\n" + PromptInjectionGame.get_level_message(new_level)

                # Track new level started
                next_level_config = PromptInjectionGame.LEVEL_CONFIGS[new_level]
                analytics.track_level_started(
                    from_number,
                    new_level,
                    next_level_config["bot_name"],
                    next_level_config["defense_strength"]
                )

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
        from app.ai_game.nodes.update_state_node import set_redis_store, set_whatsapp_client as set_update_whatsapp
        from app.ai_game.nodes.sender_node import set_whatsapp_client
        set_redis_store(redis_store)
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
