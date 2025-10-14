"""Database utilities and context managers for improved connection management."""

import logging
from contextlib import contextmanager
from typing import Generator, Optional, Any, Callable
from functools import wraps
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.config import config

logger = logging.getLogger(__name__)


@contextmanager
def get_db_session(session_factory: Callable[[], Session]) -> Generator[Session, None, None]:
    """
    Context manager for database sessions with automatic commit/rollback.
    
    Args:
        session_factory: Function that creates a new database session
        
    Yields:
        Session: Database session with automatic transaction management
        
    Example:
        with get_db_session(store.SessionLocal) as session:
            user = session.query(User).filter_by(id=user_id).first()
            user.name = "New Name"
            # Automatic commit on success, rollback on exception
    """
    session = session_factory()
    try:
        yield session
        session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Database error, transaction rolled back: {e}")
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Unexpected error, transaction rolled back: {e}")
        raise
    finally:
        session.close()


def transactional(session_factory: Callable[[], Session]):
    """
    Decorator for making functions transactional.
    
    Args:
        session_factory: Function that creates a new database session
        
    Example:
        @transactional(store.SessionLocal)
        def update_user_name(user_id: int, new_name: str):
            session = get_db_session_from_context()
            user = session.query(User).filter_by(id=user_id).first()
            user.name = new_name
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with get_db_session(session_factory) as session:
                # Store session in function context for access by decorated function
                kwargs['_session'] = session
                return func(*args, **kwargs)
        return wrapper
    return decorator


def with_session(session_factory: Callable[[], Session]):
    """
    Decorator that provides a database session to the function.
    
    Args:
        session_factory: Function that creates a new database session
        
    Example:
        @with_session(store.SessionLocal)
        def get_user_by_id(user_id: int, _session: Session = None):
            return _session.query(User).filter_by(id=user_id).first()
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with get_db_session(session_factory) as session:
                kwargs['_session'] = session
                return func(*args, **kwargs)
        return wrapper
    return decorator


class DatabaseManager:
    """
    High-level database manager with connection pooling and retry logic.
    
    Provides a clean interface for database operations with built-in
    error handling, connection pooling, and retry logic for transient failures.
    """
    
    def __init__(self, session_factory: Callable[[], Session], max_retries: int = 3):
        """
        Initialize database manager.
        
        Args:
            session_factory: Function that creates a new database session
            max_retries: Maximum number of retry attempts for transient failures
        """
        self.session_factory = session_factory
        self.max_retries = max_retries
        
    def execute_with_retry(
        self, 
        operation: Callable[[Session], Any], 
        *args, 
        **kwargs
    ) -> Any:
        """
        Execute a database operation with retry logic for transient failures.
        
        Args:
            operation: Function that takes a session and returns a result
            *args: Additional arguments to pass to operation
            **kwargs: Additional keyword arguments to pass to operation
            
        Returns:
            Result of the operation
            
        Raises:
            SQLAlchemyError: If all retry attempts fail
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                with get_db_session(self.session_factory) as session:
                    return operation(session, *args, **kwargs)
            except SQLAlchemyError as e:
                last_exception = e
                if attempt < self.max_retries:
                    logger.warning(f"Database operation failed (attempt {attempt + 1}/{self.max_retries + 1}), retrying: {e}")
                    continue
                else:
                    logger.error(f"Database operation failed after {self.max_retries + 1} attempts: {e}")
                    raise
            except Exception as e:
                # Non-database exceptions are not retried
                logger.error(f"Non-retryable error in database operation: {e}")
                raise
        
        # This should never be reached, but just in case
        if last_exception:
            raise last_exception
    
    def health_check(self) -> bool:
        """
        Perform a health check on the database connection.
        
        Returns:
            True if database is healthy, False otherwise
        """
        try:
            with get_db_session(self.session_factory) as session:
                session.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


# Global database manager instance (will be initialized in main.py)
db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """
    Get the global database manager instance.
    
    Returns:
        DatabaseManager: Global database manager
        
    Raises:
        RuntimeError: If database manager is not initialized
    """
    if db_manager is None:
        raise RuntimeError("Database manager not initialized. Call init_db_manager() first.")
    return db_manager


def init_db_manager(session_factory: Callable[[], Session]) -> DatabaseManager:
    """
    Initialize the global database manager.
    
    Args:
        session_factory: Function that creates a new database session
        
    Returns:
        DatabaseManager: Initialized database manager
    """
    global db_manager
    db_manager = DatabaseManager(session_factory)
    logger.info("Database manager initialized")
    return db_manager