"""Data models for the WhatsApp prompt injection game."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class Message(BaseModel):
    """Represents a single message in the conversation."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime


class UserState(BaseModel):
    """Represents the state of a user in the game."""
    phone_number: str
    level: int = 1
    messages: List[Message] = []
    attempts: int = 0
    created_at: datetime
    last_active: datetime
    won: bool = False

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Phone(BaseModel):
    """Represents a phone in the catalog."""
    name: str
    price: int  # Price in ZAR
    description: str


class GameLevel(BaseModel):
    """Represents a level in the game."""
    level_number: int
    description: str
    bot_personality: str
    win_condition_keywords: List[str]
    defense_patterns: List[str]
