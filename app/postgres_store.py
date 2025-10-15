"""Postgres storage for user state and winner management.

Replaces Redis with permanent Postgres storage for:
- User game state (level, attempts, won status)
- Session management (last_active, timeouts)
- Winners leaderboard
- Message history
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.pool import NullPool

from app.models import UserState, Message as MessageModel
from app.config import config

logger = logging.getLogger(__name__)

Base = declarative_base()


class User(Base):
    """User table for game state"""
    __tablename__ = 'game_users'

    phone_number = Column(String(20), primary_key=True)
    level = Column(Integer, default=1)
    won = Column(Boolean, default=False)
    attempts = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    last_active = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    session_started_at = Column(DateTime)
    session_warned = Column(Boolean, default=False)
    session_expired = Column(Boolean, default=False)

    # Relationships
    messages = relationship("Message", back_populates="user", cascade="all, delete-orphan")
    winner = relationship("Winner", back_populates="user", uselist=False)

    __table_args__ = (
        Index('idx_last_active', 'last_active'),
        Index('idx_won', 'won'),
        Index('idx_level', 'level'),
    )


class Message(Base):
    """Message table for conversation history"""
    __tablename__ = 'game_messages'

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone_number = Column(String(20), ForeignKey('game_users.phone_number', ondelete='CASCADE'))
    role = Column(String(10), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.now)
    level = Column(Integer)  # Which level this message was at

    # Relationships
    user = relationship("User", back_populates="messages")

    __table_args__ = (
        Index('idx_phone_timestamp', 'phone_number', 'timestamp'),
    )


class Winner(Base):
    """Winner table for leaderboard and prize draw"""
    __tablename__ = 'game_winners'

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone_number = Column(String(20), ForeignKey('game_users.phone_number', ondelete='CASCADE'), unique=True)
    completed_at = Column(DateTime, default=datetime.now)
    total_attempts = Column(Integer)
    time_taken_seconds = Column(Integer)
    rank = Column(Integer)  # Order of completion

    # Prize draw fields
    preferred_phone = Column(String(50))  # User's phone choice for draw
    draw_eligible = Column(Boolean, default=True)  # Eligible for prize draw

    # Relationships
    user = relationship("User", back_populates="winner")

    __table_args__ = (
        Index('idx_completed_at', 'completed_at'),
        Index('idx_rank', 'rank'),
    )


class MessageStatus(Base):
    """Message delivery status tracking for winner notifications"""
    __tablename__ = 'message_statuses'

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone_number = Column(String(20), nullable=False)
    message_type = Column(String(50))  # 'lucky_draw_winner', 'non_selected_winner'
    whatsapp_message_id = Column(String(255), unique=True)
    status = Column(String(20), default='sent')  # sent, delivered, read, failed
    sent_at = Column(DateTime, default=datetime.now)
    delivered_at = Column(DateTime)
    read_at = Column(DateTime)
    failed_reason = Column(Text)
    message_content = Column(Text)

    __table_args__ = (
        Index('idx_phone_msg_type', 'phone_number', 'message_type'),
        Index('idx_whatsapp_msg_id', 'whatsapp_message_id'),
        Index('idx_status', 'status'),
    )


class PostgresStore:
    """Postgres storage for game state management"""

    def __init__(self, db_uri: str = None):
        """Initialize Postgres connection

        Args:
            db_uri: Postgres connection string (defaults to config.POSTGRES_URI)
        """
        self.db_uri = db_uri or config.POSTGRES_URI

        # Create engine with proper connection pooling for concurrent players
        self.engine = create_engine(
            self.db_uri,
            pool_size=5,              # Keep 5 connections warm
            max_overflow=15,          # Allow 15 extra during burst (total 20 for 20 concurrent players)
            pool_pre_ping=True,       # Test connection health before using
            pool_recycle=3600,        # Recycle connections after 1 hour
            echo=False
        )

        # Create tables if they don't exist
        Base.metadata.create_all(self.engine)

        # Create session factory
        self.SessionLocal = sessionmaker(bind=self.engine)

        logger.info("✅ PostgresStore initialized with connection pool:")
        logger.info(f"   Pool size: 5, Max overflow: 15 (handles up to 20 concurrent)")
        logger.info(f"   Database: db-g1-small (1 vCPU, 1.7GB RAM)")

    def _get_session(self) -> Session:
        """Get database session"""
        return self.SessionLocal()

    def get_user_state(self, phone_number: str) -> Optional[UserState]:
        """Retrieve user state from Postgres"""
        session = self._get_session()
        try:
            user = session.query(User).filter(User.phone_number == phone_number).first()

            if not user:
                return None

            # Get user's messages
            messages = session.query(Message).filter(
                Message.phone_number == phone_number
            ).order_by(Message.timestamp).all()

            # Convert to Pydantic models
            message_models = [
                MessageModel(
                    role=msg.role,
                    content=msg.content,
                    timestamp=msg.timestamp
                )
                for msg in messages
            ]

            return UserState(
                phone_number=user.phone_number,
                level=user.level,
                messages=message_models,
                attempts=user.attempts,
                created_at=user.created_at,
                last_active=user.last_active,
                won=user.won,
                session_started_at=user.session_started_at,
                session_warned=user.session_warned,
                session_expired=user.session_expired
            )

        finally:
            session.close()

    def create_new_user(self, phone_number: str) -> UserState:
        """Create a new user in Postgres"""
        session = self._get_session()
        try:
            now = datetime.now()
            user = User(
                phone_number=phone_number,
                level=1,
                attempts=0,
                created_at=now,
                last_active=now,
                won=False,
                session_started_at=now,
                session_warned=False,
                session_expired=False
            )

            session.add(user)
            session.commit()

            logger.info(f"✨ Created new user: {phone_number[:5]}***")

            return UserState(
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

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create user: {e}")
            raise
        finally:
            session.close()

    def add_message(self, phone_number: str, role: str, content: str) -> bool:
        """Add a message to user's history"""
        session = self._get_session()
        try:
            # Get user
            user = session.query(User).filter(User.phone_number == phone_number).first()

            if not user:
                # Create user if doesn't exist
                session.close()
                self.create_new_user(phone_number)
                session = self._get_session()
                user = session.query(User).filter(User.phone_number == phone_number).first()

            # Add message
            now = datetime.now()
            message = Message(
                phone_number=phone_number,
                role=role,
                content=content,
                timestamp=now,
                level=user.level
            )

            session.add(message)

            # Update user's last_active and increment attempts if user message
            user.last_active = now
            if role == "user":
                user.attempts += 1
                user.session_warned = False  # Reset warning when user is active

            session.commit()
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to add message: {e}")
            return False
        finally:
            session.close()

    def update_level(self, phone_number: str, new_level: int) -> bool:
        """Update user's level"""
        session = self._get_session()
        try:
            user = session.query(User).filter(User.phone_number == phone_number).first()

            if not user:
                return False

            user.level = new_level
            user.last_active = datetime.now()

            session.commit()
            logger.info(f"📈 Updated {phone_number[:5]}*** to Level {new_level}")
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update level: {e}")
            return False
        finally:
            session.close()

    def mark_as_won(self, phone_number: str) -> bool:
        """Mark user as having won the game"""
        session = self._get_session()
        try:
            user = session.query(User).filter(User.phone_number == phone_number).first()

            if not user:
                return False

            user.won = True
            user.last_active = datetime.now()

            # Add to winners table
            existing_winner = session.query(Winner).filter(Winner.phone_number == phone_number).first()

            if not existing_winner:
                time_taken = (user.last_active - user.created_at).total_seconds()

                # Calculate rank (number of existing winners + 1)
                winner_count = session.query(Winner).count()

                winner = Winner(
                    phone_number=phone_number,
                    completed_at=user.last_active,
                    total_attempts=user.attempts,
                    time_taken_seconds=int(time_taken),
                    rank=winner_count + 1,
                    preferred_phone=None,  # Will be set when user selects phone
                    draw_eligible=True
                )

                session.add(winner)

            session.commit()
            logger.info(f"🎉 Marked {phone_number[:5]}*** as winner!")
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to mark as won: {e}")
            return False
        finally:
            session.close()

    def get_stats(self) -> dict:
        """Get overall game statistics"""
        session = self._get_session()
        try:
            total_users = session.query(User).count()
            winners_count = session.query(User).filter(User.won == True).count()

            # Level distribution
            level_dist = {}
            for i in range(1, 8):
                count = session.query(User).filter(User.level == i).count()
                level_dist[i] = count

            return {
                "total_users": total_users,
                "winners": winners_count,
                "level_distribution": level_dist
            }

        finally:
            session.close()

    def get_leaderboard(self) -> dict:
        """Get leaderboard with all users and winners"""
        session = self._get_session()
        try:
            # Get all users
            users = session.query(User).all()

            all_users = []
            winners = []

            for user in users:
                time_taken = None
                if user.created_at and user.last_active:
                    time_taken = (user.last_active - user.created_at).total_seconds()

                user_entry = {
                    "phone_masked": f"{user.phone_number[:5]}***{user.phone_number[-2:]}" if len(user.phone_number) > 7 else "***",
                    "level": user.level,
                    "won": user.won,
                    "attempts": user.attempts,
                    "last_active": user.last_active.isoformat() if user.last_active else None,
                    "started_at": user.created_at.isoformat() if user.created_at else None,
                    "time_taken_seconds": time_taken,
                    "time_taken_minutes": round(time_taken / 60, 1) if time_taken else None
                }

                all_users.append(user_entry)

                if user.won:
                    winners.append(user_entry)

            # Sort
            all_users.sort(key=lambda x: (-x.get("level", 0), x.get("last_active", "")))
            winners.sort(key=lambda x: x.get("last_active", ""))

            return {
                "all_users": all_users,
                "winners": winners
            }

        finally:
            session.close()

    def start_new_session(self, phone_number: str) -> bool:
        """Start a new session for user"""
        session = self._get_session()
        try:
            user = session.query(User).filter(User.phone_number == phone_number).first()

            if not user:
                return False

            now = datetime.now()
            user.session_started_at = now
            user.last_active = now
            user.session_warned = False
            user.session_expired = False

            session.commit()
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to start new session: {e}")
            return False
        finally:
            session.close()

    def mark_session_warned(self, phone_number: str) -> bool:
        """Mark that user has received 2-minute warning"""
        session = self._get_session()
        try:
            user = session.query(User).filter(User.phone_number == phone_number).first()

            if not user:
                return False

            user.session_warned = True
            session.commit()
            return True

        except Exception as e:
            session.rollback()
            return False
        finally:
            session.close()

    def get_inactive_users_for_warning(self, minutes: int) -> List[str]:
        """Get users inactive for specified minutes (for 2-minute warnings)"""
        session = self._get_session()
        try:
            threshold = datetime.now() - timedelta(minutes=minutes)
            timeout_threshold = datetime.now() - timedelta(minutes=config.SESSION_TIMEOUT_MINUTES)

            # Find users inactive between warning and timeout thresholds
            users = session.query(User).filter(
                User.last_active < threshold,
                User.last_active >= timeout_threshold,
                User.session_warned == False,
                User.won == False
            ).all()

            return [user.phone_number for user in users]

        finally:
            session.close()

    def set_phone_preference(self, phone_number: str, phone_choice: str) -> bool:
        """Save user's preferred phone for prize draw"""
        session = self._get_session()
        try:
            winner = session.query(Winner).filter(Winner.phone_number == phone_number).first()

            if winner:
                winner.preferred_phone = phone_choice
                session.commit()
                logger.info(f"💎 {phone_number[:5]}*** selected {phone_choice}")
                return True
            return False

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to set phone preference: {e}")
            return False
        finally:
            session.close()

    def reset_user_progress(self, phone_number: str) -> bool:
        """Reset user's progress to start fresh from Level 1

        Deletes all game data, messages, winner status for the user.
        Also clears LangGraph checkpointer for this user.

        Args:
            phone_number: User's phone number

        Returns:
            True if successful
        """
        session = self._get_session()
        try:
            # Delete from related tables (cascades should handle this, but being explicit)
            session.query(Message).filter(Message.phone_number == phone_number).delete()
            session.query(Winner).filter(Winner.phone_number == phone_number).delete()
            session.query(User).filter(User.phone_number == phone_number).delete()

            session.commit()

            # Also clear LangGraph checkpointer for this user
            try:
                from sqlalchemy import text
                thread_id = f"hackmerlin_{phone_number}"
                session.execute(text("DELETE FROM checkpoint_writes WHERE thread_id = :thread_id"), {"thread_id": thread_id})
                session.execute(text("DELETE FROM checkpoints WHERE thread_id = :thread_id"), {"thread_id": thread_id})
                session.commit()
            except Exception as e:
                logger.warning(f"Could not clear checkpointer: {e}")

            logger.info(f"🔄 Reset all progress for {phone_number[:5]}***")
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to reset progress: {e}")
            return False
        finally:
            session.close()

    def record_message_sent(self, phone_number: str, message_type: str, whatsapp_msg_id: str, content: str) -> bool:
        """Record that a message was sent to a winner"""
        session = self._get_session()
        try:
            msg_status = MessageStatus(
                phone_number=phone_number,
                message_type=message_type,
                whatsapp_message_id=whatsapp_msg_id,
                status='sent',
                message_content=content
            )
            session.add(msg_status)
            session.commit()
            logger.info(f"📝 Recorded message sent to {phone_number[:5]}***")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to record message: {e}")
            return False
        finally:
            session.close()

    def update_message_status(self, whatsapp_message_id: str, status: str, timestamp: datetime = None, error: str = None) -> bool:
        """Update message delivery status from WhatsApp webhook"""
        session = self._get_session()
        try:
            msg = session.query(MessageStatus).filter(
                MessageStatus.whatsapp_message_id == whatsapp_message_id
            ).first()

            if msg:
                msg.status = status

                if status == 'delivered' and timestamp:
                    msg.delivered_at = timestamp
                elif status == 'read' and timestamp:
                    msg.read_at = timestamp
                elif status == 'failed':
                    msg.failed_reason = error

                session.commit()
                logger.info(f"✅ Updated message {whatsapp_message_id[:10]}... to {status}")
                return True

            # Silently ignore non-tracked messages (regular game messages, not winner notifications)
            logger.debug(f"Message {whatsapp_message_id[:10]}... not tracked (regular game message)")
            return False

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update message status: {e}")
            return False
        finally:
            session.close()

    def get_message_delivery_stats(self) -> dict:
        """Get delivery statistics for winner notifications"""
        session = self._get_session()
        try:
            total = session.query(MessageStatus).count()
            by_status = {}

            for status in ['sent', 'delivered', 'read', 'failed']:
                count = session.query(MessageStatus).filter(MessageStatus.status == status).count()
                by_status[status] = count

            by_type = {}
            for msg_type in ['lucky_draw_winner', 'non_selected_winner']:
                count = session.query(MessageStatus).filter(MessageStatus.message_type == msg_type).count()
                by_type[msg_type] = count

            return {
                "total_messages": total,
                "by_status": by_status,
                "by_type": by_type
            }

        finally:
            session.close()

    def ping(self) -> bool:
        """Test database connection"""
        session = self._get_session()
        try:
            from sqlalchemy import text
            session.execute(text("SELECT 1"))
            session.commit()
            return True
        except Exception as e:
            logger.error(f"Ping failed: {e}")
            return False
        finally:
            session.close()
