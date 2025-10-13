"""Redis storage for user state management."""

import json
from datetime import datetime
from typing import Optional
import redis
from app.models import UserState, Message
from app.config import config


class RedisStore:
    """Redis client for managing user states."""

    def __init__(self):
        """Initialize Redis connection."""
        self.client = redis.Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            password=config.REDIS_PASSWORD,
            db=config.REDIS_DB,
            decode_responses=True,
        )

    def _get_user_key(self, phone_number: str) -> str:
        """Generate Redis key for user."""
        return f"user:{phone_number}"

    def get_user_state(self, phone_number: str) -> Optional[UserState]:
        """Retrieve user state from Redis."""
        key = self._get_user_key(phone_number)
        data = self.client.get(key)

        if not data:
            return None

        try:
            user_dict = json.loads(data)
            # Parse datetime fields
            user_dict["created_at"] = datetime.fromisoformat(user_dict["created_at"])
            user_dict["last_active"] = datetime.fromisoformat(user_dict["last_active"])
            user_dict["session_started_at"] = datetime.fromisoformat(user_dict["session_started_at"]) if user_dict.get("session_started_at") else None
            # Parse messages
            user_dict["messages"] = [
                Message(
                    role=msg["role"],
                    content=msg["content"],
                    timestamp=datetime.fromisoformat(msg["timestamp"])
                )
                for msg in user_dict.get("messages", [])
            ]
            return UserState(**user_dict)
        except Exception as e:
            print(f"Error parsing user state: {e}")
            return None

    def save_user_state(self, user_state: UserState) -> bool:
        """Save user state to Redis."""
        key = self._get_user_key(user_state.phone_number)

        try:
            # Convert to dict and handle datetime serialization
            user_dict = user_state.dict()
            user_dict["created_at"] = user_state.created_at.isoformat()
            user_dict["last_active"] = user_state.last_active.isoformat()
            user_dict["session_started_at"] = user_state.session_started_at.isoformat() if user_state.session_started_at else None
            user_dict["messages"] = [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat()
                }
                for msg in user_state.messages
            ]

            data = json.dumps(user_dict)
            self.client.set(key, data)
            # Set expiration (24 hours * 7 days = 1 week)
            self.client.expire(key, 60 * 60 * 24 * 7)
            return True
        except Exception as e:
            print(f"Error saving user state: {e}")
            return False

    def create_new_user(self, phone_number: str) -> UserState:
        """Create a new user state."""
        now = datetime.now()
        user_state = UserState(
            phone_number=phone_number,
            level=1,
            messages=[],
            attempts=0,
            created_at=now,
            last_active=now,
            won=False,
            session_started_at=now,
            session_warned=False,
            session_expired=False
        )
        self.save_user_state(user_state)
        return user_state

    def add_message(self, phone_number: str, role: str, content: str) -> bool:
        """Add a message to user's history."""
        user_state = self.get_user_state(phone_number)
        if not user_state:
            user_state = self.create_new_user(phone_number)

        now = datetime.now()
        message = Message(
            role=role,
            content=content,
            timestamp=now
        )
        user_state.messages.append(message)
        user_state.last_active = now
        user_state.attempts += 1 if role == "user" else 0

        # Initialize session fields if missing (for existing users)
        if user_state.session_started_at is None:
            user_state.session_started_at = now

        # Reset session warning flag when user sends a message
        if role == "user":
            user_state.session_warned = False

        return self.save_user_state(user_state)

    def update_level(self, phone_number: str, new_level: int) -> bool:
        """Update user's level."""
        user_state = self.get_user_state(phone_number)
        if not user_state:
            return False

        user_state.level = new_level
        user_state.last_active = datetime.now()
        return self.save_user_state(user_state)

    def mark_as_won(self, phone_number: str) -> bool:
        """Mark user as having won the game."""
        user_state = self.get_user_state(phone_number)
        if not user_state:
            return False

        user_state.won = True
        user_state.last_active = datetime.now()
        return self.save_user_state(user_state)

    def get_stats(self) -> dict:
        """Get overall statistics."""
        # Get all user keys
        keys = self.client.keys("user:*")
        total_users = len(keys)

        winners = 0
        level_distribution = {i: 0 for i in range(1, 8)}

        for key in keys:
            data = self.client.get(key)
            if data:
                try:
                    user_dict = json.loads(data)
                    if user_dict.get("won"):
                        winners += 1
                    level = user_dict.get("level", 1)
                    if 1 <= level <= 7:
                        level_distribution[level] += 1
                except Exception:
                    pass

        return {
            "total_users": total_users,
            "winners": winners,
            "level_distribution": level_distribution
        }

    def get_leaderboard(self) -> dict:
        """Get leaderboard showing all users and their progress.

        Returns all users sorted by level (highest first), then by completion time.
        """
        keys = self.client.keys("user:*")
        all_users = []
        winners = []

        for key in keys:
            data = self.client.get(key)
            if data:
                try:
                    user_dict = json.loads(data)
                    phone = user_dict.get("phone_number", "")
                    level = user_dict.get("level", 1)
                    won = user_dict.get("won", False)
                    created_at = datetime.fromisoformat(user_dict["created_at"]) if user_dict.get("created_at") else None
                    last_active = datetime.fromisoformat(user_dict["last_active"]) if user_dict.get("last_active") else None

                    # Calculate time taken
                    time_taken_seconds = None
                    if created_at and last_active:
                        time_taken_seconds = (last_active - created_at).total_seconds()

                    user_entry = {
                        "phone_masked": f"{phone[:5]}***{phone[-2:]}" if len(phone) > 7 else "***",
                        "level": level,
                        "won": won,
                        "attempts": user_dict.get("attempts", 0),
                        "last_active": user_dict.get("last_active"),
                        "started_at": user_dict.get("created_at"),
                        "time_taken_seconds": time_taken_seconds,
                        "time_taken_minutes": round(time_taken_seconds / 60, 1) if time_taken_seconds else None
                    }

                    all_users.append(user_entry)

                    if won:
                        winners.append(user_entry)

                except Exception as e:
                    print(f"Error processing user: {e}")
                    pass

        # Sort all users by level (descending), then by last_active
        all_users.sort(key=lambda x: (-x.get("level", 0), x.get("last_active", "")))

        # Sort winners by completion time (earliest first)
        winners.sort(key=lambda x: x.get("last_active", ""))

        return {
            "all_users": all_users,
            "winners": winners
        }

    def start_new_session(self, phone_number: str) -> bool:
        """Start a new session for user."""
        user_state = self.get_user_state(phone_number)
        if not user_state:
            return False

        now = datetime.now()
        user_state.session_started_at = now
        user_state.last_active = now
        user_state.session_warned = False
        user_state.session_expired = False
        return self.save_user_state(user_state)

    def mark_session_warned(self, phone_number: str) -> bool:
        """Mark that user has received 2-minute inactivity warning."""
        user_state = self.get_user_state(phone_number)
        if not user_state:
            return False

        user_state.session_warned = True
        return self.save_user_state(user_state)

    def mark_session_expired(self, phone_number: str) -> bool:
        """Mark user's session as expired."""
        user_state = self.get_user_state(phone_number)
        if not user_state:
            return False

        user_state.session_expired = True
        return self.save_user_state(user_state)

    def get_inactive_users_for_warning(self, minutes: int) -> list:
        """
        Get users who have been inactive for specified minutes.
        Used for sending 2-minute warnings.

        Returns list of phone numbers.
        """
        from app.config import config

        keys = self.client.keys("user:*")
        inactive_users = []
        now = datetime.now()

        print(f"DEBUG: Checking {len(keys)} users for {minutes}-minute inactivity")

        for key in keys:
            data = self.client.get(key)
            if data:
                try:
                    user_dict = json.loads(data)
                    phone = user_dict.get("phone_number", "unknown")

                    # Skip if already won
                    if user_dict.get("won"):
                        print(f"DEBUG: {phone} - skipped (won)")
                        continue

                    # Skip if already warned in this session
                    if user_dict.get("session_warned"):
                        print(f"DEBUG: {phone} - skipped (already warned)")
                        continue

                    # Skip if session already expired
                    if user_dict.get("session_expired"):
                        print(f"DEBUG: {phone} - skipped (session expired)")
                        continue

                    # Check last activity
                    last_active_str = user_dict.get("last_active")
                    if last_active_str:
                        last_active = datetime.fromisoformat(last_active_str)
                        inactive_duration = (now - last_active).total_seconds() / 60

                        print(f"DEBUG: {phone} - inactive for {inactive_duration:.1f} minutes")

                        # Check if inactive >= 2 minutes and < 3 minutes (full 1-minute window)
                        # This catches users between warning time and expiry time
                        if minutes <= inactive_duration < config.SESSION_TIMEOUT_MINUTES:
                            phone_number = user_dict.get("phone_number")
                            if phone_number:
                                print(f"DEBUG: {phone} - WILL WARN (inactive {inactive_duration:.1f} min)")
                                inactive_users.append(phone_number)
                        else:
                            print(f"DEBUG: {phone} - outside warning window ({minutes}-{config.SESSION_TIMEOUT_MINUTES} min)")
                except Exception as e:
                    print(f"Error checking user inactivity: {e}")
                    pass

        print(f"DEBUG: Found {len(inactive_users)} users needing warnings")
        return inactive_users
