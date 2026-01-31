"""
Database Service
Provides persistent storage for call records
Supports SQLite for local development and Turso for production
"""

import json
import sqlite3
from typing import Optional, List, Dict, Any
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger
from app.models.call import CallRecord, CallStatus, CallTranscript, CallSummary

logger = get_logger(__name__)


class DatabaseService:
    """
    Database service for persistent call storage
    Uses SQLite for simplicity - can be extended to use Turso, PostgreSQL, etc.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or "calling_agent.db"
        self._init_database()

    def _init_database(self):
        """Initialize database schema"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Create calls table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS calls (
                    call_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    phone_number TEXT NOT NULL,
                    from_number TEXT NOT NULL,
                    ultravox_call_id TEXT,
                    twilio_call_sid TEXT,
                    system_prompt TEXT,
                    greeting_message TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    ended_at TEXT,
                    duration_seconds INTEGER,
                    metadata TEXT
                )
            """)

            # Create transcripts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transcripts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    call_id TEXT NOT NULL,
                    speaker TEXT NOT NULL,
                    text TEXT NOT NULL,
                    confidence REAL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (call_id) REFERENCES calls(call_id)
                )
            """)

            # Create summaries table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS summaries (
                    call_id TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    key_points TEXT,
                    action_items TEXT,
                    sentiment TEXT,
                    generated_at TEXT NOT NULL,
                    FOREIGN KEY (call_id) REFERENCES calls(call_id)
                )
            """)

            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_calls_tenant ON calls(tenant_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_calls_status ON calls(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_calls_created ON calls(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_transcripts_call ON transcripts(call_id)")

            conn.commit()
            logger.info("Database initialized")

    @contextmanager
    def _get_connection(self):
        """Get database connection context manager"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def save_call(self, call: CallRecord, tenant_id: str = "default") -> bool:
        """Save or update a call record"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT OR REPLACE INTO calls (
                        call_id, tenant_id, status, direction, phone_number, from_number,
                        ultravox_call_id, twilio_call_sid, system_prompt, greeting_message,
                        error_message, created_at, started_at, ended_at, duration_seconds, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    call.call_id,
                    tenant_id,
                    call.status.value if isinstance(call.status, CallStatus) else call.status,
                    call.direction.value if hasattr(call.direction, 'value') else call.direction,
                    call.phone_number,
                    call.from_number,
                    call.ultravox_call_id,
                    call.twilio_call_sid,
                    call.system_prompt,
                    call.greeting_message,
                    call.error_message,
                    call.created_at.isoformat() if call.created_at else datetime.utcnow().isoformat(),
                    call.started_at.isoformat() if call.started_at else None,
                    call.ended_at.isoformat() if call.ended_at else None,
                    call.duration_seconds,
                    json.dumps(call.metadata)
                ))

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Failed to save call: {e}")
            return False

    def get_call(self, call_id: str) -> Optional[CallRecord]:
        """Get a call record by ID"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT * FROM calls WHERE call_id = ?", (call_id,))
                row = cursor.fetchone()

                if not row:
                    return None

                # Get transcripts
                cursor.execute(
                    "SELECT * FROM transcripts WHERE call_id = ? ORDER BY timestamp",
                    (call_id,)
                )
                transcript_rows = cursor.fetchall()

                # Get summary
                cursor.execute("SELECT * FROM summaries WHERE call_id = ?", (call_id,))
                summary_row = cursor.fetchone()

                return self._row_to_call_record(row, transcript_rows, summary_row)

        except Exception as e:
            logger.error(f"Failed to get call: {e}")
            return None

    def get_calls(
        self,
        tenant_id: Optional[str] = None,
        status: Optional[CallStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[CallRecord]:
        """Get call records with optional filters"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                query = "SELECT * FROM calls WHERE 1=1"
                params = []

                if tenant_id:
                    query += " AND tenant_id = ?"
                    params.append(tenant_id)

                if status:
                    query += " AND status = ?"
                    params.append(status.value if isinstance(status, CallStatus) else status)

                query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                cursor.execute(query, params)
                rows = cursor.fetchall()

                calls = []
                for row in rows:
                    # Get transcripts for this call
                    cursor.execute(
                        "SELECT * FROM transcripts WHERE call_id = ? ORDER BY timestamp",
                        (row['call_id'],)
                    )
                    transcript_rows = cursor.fetchall()

                    # Get summary
                    cursor.execute(
                        "SELECT * FROM summaries WHERE call_id = ?",
                        (row['call_id'],)
                    )
                    summary_row = cursor.fetchone()

                    call = self._row_to_call_record(row, transcript_rows, summary_row)
                    if call:
                        calls.append(call)

                return calls

        except Exception as e:
            logger.error(f"Failed to get calls: {e}")
            return []

    def save_transcript(self, call_id: str, transcript: CallTranscript) -> bool:
        """Save a transcript entry"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO transcripts (call_id, speaker, text, confidence, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    call_id,
                    transcript.speaker,
                    transcript.text,
                    transcript.confidence,
                    transcript.timestamp.isoformat()
                ))

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Failed to save transcript: {e}")
            return False

    def save_summary(self, call_id: str, summary: CallSummary) -> bool:
        """Save a call summary"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT OR REPLACE INTO summaries (
                        call_id, summary, key_points, action_items, sentiment, generated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    call_id,
                    summary.summary,
                    json.dumps(summary.key_points),
                    json.dumps(summary.action_items),
                    summary.sentiment,
                    summary.generated_at.isoformat()
                ))

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Failed to save summary: {e}")
            return False

    def get_call_stats(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get call statistics"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                where_clause = "WHERE tenant_id = ?" if tenant_id else ""
                params = [tenant_id] if tenant_id else []

                # Total calls
                cursor.execute(f"SELECT COUNT(*) FROM calls {where_clause}", params)
                total = cursor.fetchone()[0]

                # Completed calls
                completed_where = f"{where_clause} {'AND' if where_clause else 'WHERE'} status = 'completed'"
                cursor.execute(f"SELECT COUNT(*) FROM calls {completed_where}", params)
                completed = cursor.fetchone()[0]

                # Failed calls
                failed_where = f"{where_clause} {'AND' if where_clause else 'WHERE'} status = 'failed'"
                cursor.execute(f"SELECT COUNT(*) FROM calls {failed_where}", params)
                failed = cursor.fetchone()[0]

                # Average duration
                duration_where = f"{where_clause} {'AND' if where_clause else 'WHERE'} duration_seconds IS NOT NULL"
                cursor.execute(
                    f"SELECT AVG(duration_seconds) FROM calls {duration_where}",
                    params
                )
                avg_duration = cursor.fetchone()[0] or 0

                # Total duration
                cursor.execute(
                    f"SELECT SUM(duration_seconds) FROM calls {duration_where}",
                    params
                )
                total_duration = cursor.fetchone()[0] or 0

                return {
                    "total_calls": total,
                    "completed_calls": completed,
                    "failed_calls": failed,
                    "average_duration_seconds": round(avg_duration, 2),
                    "total_duration_seconds": total_duration
                }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}

    def _row_to_call_record(
        self,
        row,
        transcript_rows=None,
        summary_row=None
    ) -> Optional[CallRecord]:
        """Convert database row to CallRecord"""
        try:
            # Parse transcripts
            transcripts = []
            if transcript_rows:
                for t_row in transcript_rows:
                    transcripts.append(CallTranscript(
                        speaker=t_row['speaker'],
                        text=t_row['text'],
                        confidence=t_row['confidence'],
                        timestamp=datetime.fromisoformat(t_row['timestamp'])
                    ))

            # Parse summary
            summary = None
            if summary_row:
                summary = CallSummary(
                    call_id=summary_row['call_id'],
                    summary=summary_row['summary'],
                    key_points=json.loads(summary_row['key_points'] or '[]'),
                    action_items=json.loads(summary_row['action_items'] or '[]'),
                    sentiment=summary_row['sentiment'],
                    generated_at=datetime.fromisoformat(summary_row['generated_at'])
                )

            return CallRecord(
                call_id=row['call_id'],
                status=CallStatus(row['status']),
                direction=row['direction'],
                phone_number=row['phone_number'],
                from_number=row['from_number'],
                ultravox_call_id=row['ultravox_call_id'],
                twilio_call_sid=row['twilio_call_sid'],
                system_prompt=row['system_prompt'],
                greeting_message=row['greeting_message'],
                error_message=row['error_message'],
                created_at=datetime.fromisoformat(row['created_at']),
                started_at=datetime.fromisoformat(row['started_at']) if row['started_at'] else None,
                ended_at=datetime.fromisoformat(row['ended_at']) if row['ended_at'] else None,
                duration_seconds=row['duration_seconds'],
                metadata=json.loads(row['metadata'] or '{}'),
                transcript=transcripts,
                summary=summary
            )

        except Exception as e:
            logger.error(f"Failed to parse call record: {e}")
            return None


# Singleton instance
_db_service: Optional[DatabaseService] = None


def get_database_service() -> DatabaseService:
    """Get database service singleton"""
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService()
    return _db_service
