"""
Call Repository Implementation

This module provides a concrete implementation of the CallRepositoryInterface
that works with any DatabaseAdapter (Turso, PostgreSQL, etc.)
"""

import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.db.base import DatabaseAdapter, CallRepositoryInterface
from app.db.models import CallRecordDB, CallTranscriptDB, CallSummaryDB
from app.core.config import settings

logger = logging.getLogger(__name__)

# Singleton instance
_repository_instance: Optional["CallRepository"] = None


class CallRepository(CallRepositoryInterface):
    """
    Repository for managing call data.

    This class implements all call-related database operations
    using the provided database adapter.
    """

    def __init__(self, adapter: DatabaseAdapter):
        """
        Initialize the repository with a database adapter.

        Args:
            adapter: A DatabaseAdapter implementation (Turso, PostgreSQL, etc.)
        """
        self.adapter = adapter

    async def initialize(self) -> bool:
        """
        Initialize the repository (connect and setup schema).

        Returns:
            True if initialization successful, False otherwise.
        """
        connected = await self.adapter.connect()
        if not connected:
            return False

        schema_ok = await self.adapter.initialize_schema()
        return schema_ok

    async def close(self) -> None:
        """Close the database connection."""
        await self.adapter.disconnect()

    # ==================== Call Records ====================

    async def create_call(self, call: CallRecordDB) -> CallRecordDB:
        """Create a new call record."""
        query = """
            INSERT INTO call_records (
                call_id, status, direction, phone_number, from_number,
                ultravox_call_id, twilio_call_sid, system_prompt, greeting_message,
                metadata, error_message, duration_seconds, created_at, started_at, ended_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        params = (
            call.call_id,
            call.status,
            call.direction,
            call.phone_number,
            call.from_number,
            call.ultravox_call_id,
            call.twilio_call_sid,
            call.system_prompt,
            call.greeting_message,
            json.dumps(call.metadata, default=str),
            call.error_message,
            call.duration_seconds,
            call.created_at.isoformat() if call.created_at else datetime.utcnow().isoformat(),
            call.started_at.isoformat() if call.started_at else None,
            call.ended_at.isoformat() if call.ended_at else None,
        )

        await self.adapter.execute(query, params)
        logger.info(f"Created call record: {call.call_id}")
        return call

    async def get_call(self, call_id: str) -> Optional[CallRecordDB]:
        """Get a call record by call_id."""
        query = "SELECT * FROM call_records WHERE call_id = ?"
        row = await self.adapter.fetch_one(query, (call_id,))

        if not row:
            return None

        return self._row_to_call_record(row)

    async def update_call(self, call_id: str, updates: Dict[str, Any]) -> Optional[CallRecordDB]:
        """Update a call record."""
        if not updates:
            return await self.get_call(call_id)

        # Build dynamic UPDATE query
        set_clauses = []
        params = []

        for key, value in updates.items():
            if key == "metadata":
                value = json.dumps(value, default=str)
            elif key in ("created_at", "started_at", "ended_at") and isinstance(value, datetime):
                value = value.isoformat()
            set_clauses.append(f"{key} = ?")
            params.append(value)

        params.append(call_id)
        query = f"UPDATE call_records SET {', '.join(set_clauses)} WHERE call_id = ?"

        await self.adapter.execute(query, tuple(params))
        logger.info(f"Updated call record: {call_id}")
        return await self.get_call(call_id)

    async def delete_call(self, call_id: str) -> bool:
        """Delete a call record and all related data."""
        try:
            # Delete related data first (transcripts, summaries)
            await self.adapter.execute(
                "DELETE FROM call_transcripts WHERE call_id = ?", (call_id,)
            )
            await self.adapter.execute(
                "DELETE FROM call_summaries WHERE call_id = ?", (call_id,)
            )
            await self.adapter.execute(
                "DELETE FROM call_records WHERE call_id = ?", (call_id,)
            )
            logger.info(f"Deleted call record and related data: {call_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete call {call_id}: {e}")
            return False

    async def list_calls(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        direction: Optional[str] = None,
    ) -> List[CallRecordDB]:
        """List call records with optional filtering."""
        query = "SELECT * FROM call_records"
        params = []
        conditions = []

        if status:
            conditions.append("status = ?")
            params.append(status)

        if direction:
            conditions.append("direction = ?")
            params.append(direction)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = await self.adapter.fetch_all(query, tuple(params))
        return [self._row_to_call_record(row) for row in rows]

    async def get_active_calls(self) -> List[CallRecordDB]:
        """Get all currently active calls."""
        query = """
            SELECT * FROM call_records
            WHERE status IN ('pending', 'initiating', 'ringing', 'in_progress')
            ORDER BY created_at DESC
        """
        rows = await self.adapter.fetch_all(query)
        return [self._row_to_call_record(row) for row in rows]

    # ==================== Transcripts ====================

    async def add_transcript_entry(self, transcript: CallTranscriptDB) -> CallTranscriptDB:
        """Add a transcript entry to a call."""
        query = """
            INSERT INTO call_transcripts (call_id, timestamp, speaker, text, confidence)
            VALUES (?, ?, ?, ?, ?)
        """

        params = (
            transcript.call_id,
            transcript.timestamp.isoformat() if transcript.timestamp else datetime.utcnow().isoformat(),
            transcript.speaker,
            transcript.text,
            transcript.confidence,
        )

        await self.adapter.execute(query, params)
        logger.debug(f"Added transcript entry for call: {transcript.call_id}")
        return transcript

    async def get_transcripts(self, call_id: str) -> List[CallTranscriptDB]:
        """Get all transcript entries for a call."""
        query = """
            SELECT * FROM call_transcripts
            WHERE call_id = ?
            ORDER BY timestamp ASC
        """
        rows = await self.adapter.fetch_all(query, (call_id,))

        return [
            CallTranscriptDB(
                id=row.get("id"),
                call_id=row["call_id"],
                timestamp=self._parse_datetime(row.get("timestamp")),
                speaker=row["speaker"],
                text=row["text"],
                confidence=row.get("confidence"),
            )
            for row in rows
        ]

    # ==================== Summaries ====================

    async def save_summary(self, summary: CallSummaryDB) -> CallSummaryDB:
        """Save or update a call summary."""
        # Check if summary exists
        existing = await self.get_summary(summary.call_id)

        if existing:
            # Update existing summary
            query = """
                UPDATE call_summaries
                SET summary = ?, key_points = ?, sentiment = ?, action_items = ?
                WHERE call_id = ?
            """
            params = (
                summary.summary,
                json.dumps(summary.key_points),
                summary.sentiment,
                json.dumps(summary.action_items),
                summary.call_id,
            )
        else:
            # Insert new summary
            query = """
                INSERT INTO call_summaries (call_id, summary, key_points, sentiment, action_items, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            params = (
                summary.call_id,
                summary.summary,
                json.dumps(summary.key_points),
                summary.sentiment,
                json.dumps(summary.action_items),
                summary.created_at.isoformat() if summary.created_at else datetime.utcnow().isoformat(),
            )

        await self.adapter.execute(query, params)
        logger.info(f"Saved summary for call: {summary.call_id}")
        return summary

    async def get_summary(self, call_id: str) -> Optional[CallSummaryDB]:
        """Get the summary for a call."""
        query = "SELECT * FROM call_summaries WHERE call_id = ?"
        row = await self.adapter.fetch_one(query, (call_id,))

        if not row:
            return None

        return CallSummaryDB(
            id=row.get("id"),
            call_id=row["call_id"],
            summary=row["summary"],
            key_points=self._parse_json_list(row.get("key_points")),
            sentiment=row.get("sentiment"),
            action_items=self._parse_json_list(row.get("action_items")),
            created_at=self._parse_datetime(row.get("created_at")),
        )

    # ==================== Analytics ====================

    async def get_call_statistics(self) -> Dict[str, Any]:
        """Get aggregated call statistics."""
        stats_query = """
            SELECT
                COUNT(*) as total_calls,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_calls,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_calls,
                SUM(CASE WHEN status IN ('pending', 'initiating', 'ringing', 'in_progress') THEN 1 ELSE 0 END) as active_calls,
                SUM(COALESCE(duration_seconds, 0)) as total_duration,
                AVG(CASE WHEN status = 'completed' AND duration_seconds > 0 THEN duration_seconds END) as avg_duration
            FROM call_records
        """

        row = await self.adapter.fetch_one(stats_query)

        if not row:
            return {
                "total_calls": 0,
                "completed_calls": 0,
                "failed_calls": 0,
                "active_calls": 0,
                "total_duration_seconds": 0,
                "average_duration_seconds": 0,
                "success_rate": 0,
            }

        total = row.get("total_calls", 0) or 0
        completed = row.get("completed_calls", 0) or 0

        return {
            "total_calls": total,
            "completed_calls": completed,
            "failed_calls": row.get("failed_calls", 0) or 0,
            "active_calls": row.get("active_calls", 0) or 0,
            "total_duration_seconds": row.get("total_duration", 0) or 0,
            "average_duration_seconds": round(row.get("avg_duration", 0) or 0, 1),
            "success_rate": round((completed / total * 100) if total > 0 else 0, 1),
        }

    async def get_sentiment_distribution(self) -> Dict[str, int]:
        """Get distribution of sentiment across calls."""
        query = """
            SELECT sentiment, COUNT(*) as count
            FROM call_summaries
            WHERE sentiment IS NOT NULL
            GROUP BY sentiment
        """

        rows = await self.adapter.fetch_all(query)

        distribution = {"positive": 0, "neutral": 0, "negative": 0}
        for row in rows:
            sentiment = (row.get("sentiment") or "").lower()
            if sentiment in distribution:
                distribution[sentiment] = row.get("count", 0) or 0

        return distribution

    async def get_recent_action_items(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent action items from call summaries."""
        query = """
            SELECT s.call_id, s.action_items, s.created_at, c.phone_number
            FROM call_summaries s
            JOIN call_records c ON s.call_id = c.call_id
            WHERE s.action_items IS NOT NULL AND s.action_items != '[]'
            ORDER BY s.created_at DESC
            LIMIT ?
        """

        rows = await self.adapter.fetch_all(query, (limit,))

        action_items = []
        for row in rows:
            items = self._parse_json_list(row.get("action_items"))
            for item in items:
                action_items.append({
                    "item": item,
                    "call_id": row["call_id"],
                    "phone_number": row.get("phone_number"),
                    "created_at": row.get("created_at"),
                })

        return action_items[:limit]

    # ==================== Helper Methods ====================

    def _row_to_call_record(self, row: Dict[str, Any]) -> CallRecordDB:
        """Convert a database row to CallRecordDB."""
        return CallRecordDB(
            id=row.get("id"),
            call_id=row["call_id"],
            status=row["status"],
            direction=row["direction"],
            phone_number=row["phone_number"],
            from_number=row["from_number"],
            ultravox_call_id=row.get("ultravox_call_id"),
            twilio_call_sid=row.get("twilio_call_sid"),
            system_prompt=row.get("system_prompt"),
            greeting_message=row.get("greeting_message"),
            metadata=self._parse_json_dict(row.get("metadata")),
            error_message=row.get("error_message"),
            duration_seconds=row.get("duration_seconds"),
            created_at=self._parse_datetime(row.get("created_at")),
            started_at=self._parse_datetime(row.get("started_at")),
            ended_at=self._parse_datetime(row.get("ended_at")),
        )

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        """Parse datetime from string or return as-is if already datetime."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    def _parse_json_list(self, value: Any) -> List[str]:
        """Parse JSON list from string or return as-is if already list."""
        if value is None:
            return []
        if isinstance(value, list):
            return value
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def _parse_json_dict(self, value: Any) -> Dict[str, Any]:
        """Parse JSON dict from string or return as-is if already dict."""
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}


class DatabaseRepository:
    """
    Main database repository factory.

    This class provides a unified interface to get the appropriate
    repository based on configuration.
    """

    @staticmethod
    def create_repository(db_type: str = "turso") -> CallRepository:
        """
        Create a repository with the specified database type.

        Args:
            db_type: Database type ("turso" or "postgres")

        Returns:
            CallRepository instance with the appropriate adapter.
        """
        if db_type == "postgres":
            from app.db.adapters.postgres import PostgresAdapter
            adapter = PostgresAdapter()
        else:
            # Default to Turso
            from app.db.adapters.turso import TursoAdapter
            adapter = TursoAdapter()

        return CallRepository(adapter)


def get_repository() -> CallRepository:
    """
    Get or create the singleton repository instance.

    The database type is determined by configuration:
    - Uses DATABASE_TYPE setting (default: "turso")
    - Falls back to checking which credentials are available

    Returns:
        CallRepository singleton instance.
    """
    global _repository_instance

    if _repository_instance is None:
        # Use configured database type
        db_type = settings.database_type.lower()

        # Validate that credentials exist for the selected database
        if db_type == "postgres" and not settings.postgres_url:
            logger.warning("PostgreSQL selected but POSTGRES_URL not set, falling back to Turso")
            db_type = "turso"
        elif db_type == "turso" and not settings.turso_db_url:
            logger.warning("Turso selected but TURSO_DB_URL not set")

        _repository_instance = DatabaseRepository.create_repository(db_type)
        logger.info(f"Created {db_type} repository instance")

    return _repository_instance


async def initialize_database() -> bool:
    """
    Initialize the database (connect and create schema).

    Call this at application startup.

    Returns:
        True if initialization successful, False otherwise.
    """
    repo = get_repository()
    return await repo.initialize()


async def close_database() -> None:
    """
    Close the database connection.

    Call this at application shutdown.
    """
    global _repository_instance
    if _repository_instance:
        await _repository_instance.close()
        _repository_instance = None
        logger.info("Database connection closed")
