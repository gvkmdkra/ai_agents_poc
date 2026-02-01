"""
Database Adapter Base Classes

This module defines the abstract interfaces that all database adapters
must implement. This enables easy switching between different databases.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from app.db.models import CallRecordDB, CallTranscriptDB, CallSummaryDB


class DatabaseAdapter(ABC):
    """
    Abstract base class for database adapters.

    All database implementations (Turso, PostgreSQL, SQLite, etc.)
    must implement this interface.
    """

    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to the database.
        Returns True if successful, False otherwise.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the database connection."""
        pass

    @abstractmethod
    async def initialize_schema(self) -> bool:
        """
        Create necessary tables if they don't exist.
        Returns True if successful, False otherwise.
        """
        pass

    @abstractmethod
    async def execute(self, query: str, params: tuple = ()) -> Any:
        """Execute a raw SQL query."""
        pass

    @abstractmethod
    async def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Execute query and return single row as dict."""
        pass

    @abstractmethod
    async def fetch_all(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute query and return all rows as list of dicts."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if database connection is active."""
        pass


class CallRepositoryInterface(ABC):
    """
    Abstract interface for call data operations.

    This defines all the operations needed for managing call records,
    transcripts, and summaries. Any database adapter can implement this.
    """

    # ==================== Call Records ====================

    @abstractmethod
    async def create_call(self, call: CallRecordDB) -> CallRecordDB:
        """Create a new call record."""
        pass

    @abstractmethod
    async def get_call(self, call_id: str) -> Optional[CallRecordDB]:
        """Get a call record by call_id."""
        pass

    @abstractmethod
    async def update_call(self, call_id: str, updates: Dict[str, Any]) -> Optional[CallRecordDB]:
        """Update a call record."""
        pass

    @abstractmethod
    async def delete_call(self, call_id: str) -> bool:
        """Delete a call record and all related data."""
        pass

    @abstractmethod
    async def list_calls(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        direction: Optional[str] = None,
    ) -> List[CallRecordDB]:
        """List call records with optional filtering."""
        pass

    @abstractmethod
    async def get_active_calls(self) -> List[CallRecordDB]:
        """Get all currently active calls."""
        pass

    # ==================== Transcripts ====================

    @abstractmethod
    async def add_transcript_entry(self, transcript: CallTranscriptDB) -> CallTranscriptDB:
        """Add a transcript entry to a call."""
        pass

    @abstractmethod
    async def get_transcripts(self, call_id: str) -> List[CallTranscriptDB]:
        """Get all transcript entries for a call."""
        pass

    # ==================== Summaries ====================

    @abstractmethod
    async def save_summary(self, summary: CallSummaryDB) -> CallSummaryDB:
        """Save or update a call summary."""
        pass

    @abstractmethod
    async def get_summary(self, call_id: str) -> Optional[CallSummaryDB]:
        """Get the summary for a call."""
        pass

    # ==================== Analytics ====================

    @abstractmethod
    async def get_call_statistics(self) -> Dict[str, Any]:
        """Get aggregated call statistics."""
        pass

    @abstractmethod
    async def get_sentiment_distribution(self) -> Dict[str, int]:
        """Get distribution of sentiment across calls."""
        pass

    @abstractmethod
    async def get_recent_action_items(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent action items from call summaries."""
        pass
