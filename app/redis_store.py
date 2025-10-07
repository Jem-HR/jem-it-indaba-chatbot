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
            won=False
        )
        self.save_user_state(user_state)
        return user_state

    def add_message(self, phone_number: str, role: str, content: str) -> bool:
        """Add a message to user's history."""
        user_state = self.get_user_state(phone_number)
        if not user_state:
            user_state = self.create_new_user(phone_number)

        message = Message(
            role=role,
            content=content,
            timestamp=datetime.now()
        )
        user_state.messages.append(message)
        user_state.last_active = datetime.now()
        user_state.attempts += 1 if role == "user" else 0

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
