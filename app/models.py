"""Data models for the WhatsApp prompt injection game."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Message(BaseModel):
    """Represents a single message in the conversation."""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(..., description="Message timestamp")


class UserState(BaseModel):
    """Represents the state of a user in the game."""
    phone_number: str = Field(..., description="User's phone number")
    level: int = Field(default=1, description="Current game level")
    messages: List[Message] = Field(default_factory=list, description="Message history")
    attempts: int = Field(default=0, description="Total attempts made")
    created_at: datetime = Field(..., description="Account creation timestamp")
    last_active: datetime = Field(..., description="Last activity timestamp")
    won: bool = Field(default=False, description="Whether user has won the game")

    # Session management
    session_started_at: Optional[datetime] = Field(default=None, description="Current session start time")
    session_warned: bool = Field(default=False, description="Whether 2-minute warning has been sent")
    session_expired: bool = Field(default=False, description="Whether current session has expired")

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
