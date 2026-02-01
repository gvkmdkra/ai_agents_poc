"""
Call Manager Service
Orchestrates Ultravox and Twilio services to manage calls
Now with database support (Turso/PostgreSQL)
"""

import uuid
import json
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger
from app.models.call import (
    CallStatus,
    CallDirection,
    CallRequest,
    CallResponse,
    CallRecord,
    CallTranscript,
    CallSummary
)
from app.services.voice.ultravox_service import UltravoxService
from app.services.telephony.twilio_service import TwilioService
from app.services.llm.openai_service import OpenAIService

logger = get_logger(__name__)

# Try to import database module
try:
    from app.db.repository import get_repository, CallRepository
    from app.db.models import CallRecordDB, CallTranscriptDB, CallSummaryDB
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    logger.warning("Database module not available, using file-based storage")


class CallManager:
    """
    Manages the lifecycle of calls including initiation, monitoring,
    and transcription/summary generation.

    Supports both database storage (Turso/PostgreSQL) and file-based storage.
    """

    def __init__(self, use_database: bool = True):
        """
        Initialize CallManager.

        Args:
            use_database: Whether to use database storage (default: True)
                         Falls back to file storage if database unavailable
        """
        self.ultravox = UltravoxService()
        self.twilio = TwilioService()
        self.openai = OpenAIService()

        # In-memory cache for active calls
        self.active_calls: Dict[str, CallRecord] = {}
        self.call_history: List[CallRecord] = []

        # Database repository
        self._db_repo: Optional[CallRepository] = None
        self._db_initialized = False
        self._use_database = use_database and DB_AVAILABLE and settings.turso_db_url

        # File-based persistence fallback
        self.records_file = Path(settings.call_records_file_path)

        # Load existing records
        if not self._use_database:
            self._load_call_records_from_file()

    async def initialize_database(self) -> bool:
        """
        Initialize database connection.
        Call this at application startup.

        Returns:
            True if database initialized successfully
        """
        if not self._use_database:
            logger.info("Database not configured, using file-based storage")
            return False

        try:
            self._db_repo = get_repository()
            self._db_initialized = await self._db_repo.initialize()

            if self._db_initialized:
                logger.info("Database initialized successfully")
                # Load active calls from database
                await self._load_active_calls_from_db()
            else:
                logger.warning("Database initialization failed, falling back to file storage")
                self._use_database = False
                self._load_call_records_from_file()

            return self._db_initialized
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            self._use_database = False
            self._load_call_records_from_file()
            return False

    async def close_database(self) -> None:
        """Close database connection."""
        if self._db_repo:
            await self._db_repo.close()
            self._db_repo = None
            self._db_initialized = False

    async def _load_active_calls_from_db(self):
        """Load active calls from database into memory."""
        if not self._db_repo:
            return
        try:
            active = await self._db_repo.get_active_calls()
            for db_record in active:
                call_record = self._db_to_model(db_record)
                self.active_calls[call_record.call_id] = call_record
            logger.info(f"Loaded {len(self.active_calls)} active calls from database")
        except Exception as e:
            logger.error(f"Failed to load active calls from database: {e}")

    def _load_call_records_from_file(self):
        """Load call records from file (fallback)"""
        if self.records_file.exists():
            try:
                with open(self.records_file, "r") as f:
                    data = json.load(f)
                    for record_data in data.get("history", []):
                        record = CallRecord(**record_data)
                        self.call_history.append(record)
                logger.info(f"Loaded {len(self.call_history)} call records from file")
            except Exception as e:
                logger.warning(f"Failed to load call records: {e}")

    def _save_call_records_to_file(self):
        """Save call records to file (fallback)"""
        try:
            data = {
                "history": [
                    record.model_dump(mode="json")
                    for record in self.call_history[-100:]  # Keep last 100
                ]
            }
            with open(self.records_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Failed to save call records: {e}")

    def _model_to_db(self, record: CallRecord) -> CallRecordDB:
        """Convert CallRecord model to database model."""
        return CallRecordDB(
            call_id=record.call_id,
            status=record.status.value if isinstance(record.status, CallStatus) else record.status,
            direction=record.direction.value if isinstance(record.direction, CallDirection) else record.direction,
            phone_number=record.phone_number,
            from_number=record.from_number,
            ultravox_call_id=record.ultravox_call_id,
            twilio_call_sid=record.twilio_call_sid,
            system_prompt=record.system_prompt,
            greeting_message=record.greeting_message,
            metadata=record.metadata or {},
            error_message=record.error_message,
            duration_seconds=record.duration_seconds,
            created_at=record.created_at,
            started_at=record.started_at,
            ended_at=record.ended_at,
        )

    def _db_to_model(self, db_record: CallRecordDB) -> CallRecord:
        """Convert database model to CallRecord model."""
        return CallRecord(
            call_id=db_record.call_id,
            status=CallStatus(db_record.status) if db_record.status else CallStatus.PENDING,
            direction=CallDirection(db_record.direction) if db_record.direction else CallDirection.OUTBOUND,
            phone_number=db_record.phone_number,
            from_number=db_record.from_number,
            ultravox_call_id=db_record.ultravox_call_id,
            twilio_call_sid=db_record.twilio_call_sid,
            system_prompt=db_record.system_prompt,
            greeting_message=db_record.greeting_message,
            metadata=db_record.metadata or {},
            error_message=db_record.error_message,
            duration_seconds=db_record.duration_seconds,
            created_at=db_record.created_at,
            started_at=db_record.started_at,
            ended_at=db_record.ended_at,
        )

    async def _save_call_to_db(self, call_record: CallRecord):
        """Save call record to database."""
        if not self._db_repo or not self._db_initialized:
            return
        try:
            db_record = self._model_to_db(call_record)
            existing = await self._db_repo.get_call(call_record.call_id)
            if existing:
                await self._db_repo.update_call(call_record.call_id, db_record.model_dump(exclude={'id'}))
            else:
                await self._db_repo.create_call(db_record)
        except Exception as e:
            logger.error(f"Failed to save call to database: {e}")

    async def initiate_call(self, request: CallRequest) -> CallResponse:
        """
        Initiate an outbound call

        Args:
            request: Call request parameters

        Returns:
            Call response with status
        """
        call_id = str(uuid.uuid4())
        logger.info(f"Initiating call {call_id} to {request.phone_number}")

        # Create call record
        call_record = CallRecord(
            call_id=call_id,
            status=CallStatus.PENDING,
            direction=CallDirection.OUTBOUND,
            phone_number=request.phone_number,
            from_number=settings.twilio_phone_number,
            system_prompt=request.system_prompt,
            greeting_message=request.greeting_message,
            metadata=request.metadata or {}
        )

        self.active_calls[call_id] = call_record
        await self._save_call_to_db(call_record)

        try:
            # Step 1: Create Ultravox session
            system_prompt = request.system_prompt or self.ultravox.get_default_system_prompt()
            greeting = request.greeting_message or "Hello! How can I help you today?"

            ultravox_result = await self.ultravox.create_call_session(
                system_prompt=system_prompt,
                greeting_message=greeting,
                voice_id=request.voice_id,
                metadata={"call_id": call_id, **request.metadata}
            )

            if not ultravox_result.get("success"):
                call_record.status = CallStatus.FAILED
                call_record.error_message = ultravox_result.get("error", "Failed to create voice session")
                await self._move_to_history(call_id)
                return CallResponse(
                    call_id=call_id,
                    status=CallStatus.FAILED,
                    phone_number=request.phone_number,
                    message=call_record.error_message
                )

            ultravox_call_id = ultravox_result.get("call_id")
            join_url = ultravox_result.get("join_url")

            call_record.ultravox_call_id = ultravox_call_id
            call_record.status = CallStatus.INITIATING
            await self._save_call_to_db(call_record)

            # Step 2: Initiate Twilio call with Ultravox connection
            twiml_url = f"{settings.api_base_url}/api/v1/webhooks/twilio/connect/{call_id}"

            twilio_result = await self.twilio.initiate_call(
                to_number=request.phone_number,
                twiml_url=twiml_url,
                status_callback_url=f"{settings.api_base_url}/api/v1/webhooks/twilio/status/{call_id}"
            )

            if not twilio_result.get("success"):
                call_record.status = CallStatus.FAILED
                call_record.error_message = twilio_result.get("error", "Failed to initiate call")
                await self.ultravox.end_call(ultravox_call_id)
                await self._move_to_history(call_id)
                return CallResponse(
                    call_id=call_id,
                    status=CallStatus.FAILED,
                    phone_number=request.phone_number,
                    ultravox_call_id=ultravox_call_id,
                    message=call_record.error_message
                )

            twilio_call_sid = twilio_result.get("call_sid")
            call_record.twilio_call_sid = twilio_call_sid
            call_record.status = CallStatus.RINGING
            call_record.metadata["ultravox_join_url"] = join_url
            await self._save_call_to_db(call_record)

            logger.info(f"Call {call_id} initiated successfully")
            return CallResponse(
                call_id=call_id,
                status=CallStatus.RINGING,
                phone_number=request.phone_number,
                ultravox_call_id=ultravox_call_id,
                twilio_call_sid=twilio_call_sid,
                message="Call initiated successfully"
            )

        except Exception as e:
            logger.error(f"Error initiating call: {str(e)}")
            call_record.status = CallStatus.FAILED
            call_record.error_message = str(e)
            await self._move_to_history(call_id)
            return CallResponse(
                call_id=call_id,
                status=CallStatus.FAILED,
                phone_number=request.phone_number,
                message=f"Error: {str(e)}"
            )

    async def handle_inbound_call(
        self,
        twilio_call_sid: str,
        from_number: str,
        to_number: str,
        system_prompt: Optional[str] = None,
        greeting_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handle an inbound call"""
        call_id = str(uuid.uuid4())
        logger.info(f"Handling inbound call {call_id} from {from_number}")

        call_record = CallRecord(
            call_id=call_id,
            status=CallStatus.IN_PROGRESS,
            direction=CallDirection.INBOUND,
            phone_number=from_number,
            from_number=to_number,
            twilio_call_sid=twilio_call_sid,
            started_at=datetime.utcnow()
        )

        self.active_calls[call_id] = call_record
        await self._save_call_to_db(call_record)

        try:
            prompt = system_prompt or self.ultravox.get_default_system_prompt()
            greeting = greeting_message or "Hello! Thank you for calling. How can I help you today?"

            ultravox_result = await self.ultravox.create_call_session(
                system_prompt=prompt,
                greeting_message=greeting,
                metadata={"call_id": call_id, "inbound": True}
            )

            if not ultravox_result.get("success"):
                logger.error(f"Failed to create Ultravox session: {ultravox_result}")
                return {
                    "success": False,
                    "twiml": self.twilio.generate_hangup_twiml(
                        "We're sorry, but we cannot take your call right now. Please try again later."
                    )
                }

            join_url = ultravox_result.get("join_url")
            call_record.ultravox_call_id = ultravox_result.get("call_id")
            call_record.metadata["ultravox_join_url"] = join_url
            await self._save_call_to_db(call_record)

            twiml = self.twilio.generate_connect_twiml(join_url)

            return {
                "success": True,
                "call_id": call_id,
                "twiml": twiml
            }

        except Exception as e:
            logger.error(f"Error handling inbound call: {str(e)}")
            return {
                "success": False,
                "twiml": self.twilio.generate_hangup_twiml(
                    "We're experiencing technical difficulties. Please try again later."
                )
            }

    async def get_call_status(self, call_id: str) -> Optional[CallRecord]:
        """Get the current status of a call"""
        # Check active calls first
        if call_id in self.active_calls:
            return self.active_calls[call_id]

        # Check database
        if self._db_repo and self._db_initialized:
            try:
                db_record = await self._db_repo.get_call(call_id)
                if db_record:
                    return self._db_to_model(db_record)
            except Exception as e:
                logger.error(f"Failed to get call from database: {e}")

        # Check in-memory history (fallback)
        for record in self.call_history:
            if record.call_id == call_id:
                return record

        return None

    async def update_call_status(
        self,
        call_id: str,
        status: CallStatus,
        error_message: Optional[str] = None
    ):
        """Update the status of a call"""
        if call_id not in self.active_calls:
            logger.warning(f"Call {call_id} not found in active calls")
            return

        call_record = self.active_calls[call_id]
        call_record.status = status

        if error_message:
            call_record.error_message = error_message

        if status == CallStatus.IN_PROGRESS and not call_record.started_at:
            call_record.started_at = datetime.utcnow()

        if status in [CallStatus.COMPLETED, CallStatus.FAILED, CallStatus.NO_ANSWER, CallStatus.BUSY]:
            call_record.ended_at = datetime.utcnow()
            if call_record.started_at:
                duration = (call_record.ended_at - call_record.started_at).total_seconds()
                call_record.duration_seconds = int(duration)

            await self._move_to_history(call_id)

            if status == CallStatus.COMPLETED and call_record.transcript:
                asyncio.create_task(self._generate_summary(call_record))
        else:
            await self._save_call_to_db(call_record)

        logger.info(f"Call {call_id} status updated to {status}")

    async def end_call(self, call_id: str) -> Dict[str, Any]:
        """End an active call"""
        if call_id not in self.active_calls:
            return {
                "success": False,
                "error": "Call not found"
            }

        call_record = self.active_calls[call_id]

        if call_record.twilio_call_sid:
            await self.twilio.end_call(call_record.twilio_call_sid)

        if call_record.ultravox_call_id:
            await self.ultravox.end_call(call_record.ultravox_call_id)

        await self.update_call_status(call_id, CallStatus.COMPLETED)

        return {
            "success": True,
            "message": "Call ended"
        }

    async def add_transcript_entry(
        self,
        call_id: str,
        speaker: str,
        text: str,
        confidence: Optional[float] = None
    ):
        """Add a transcript entry to a call"""
        if call_id not in self.active_calls:
            return

        entry = CallTranscript(
            speaker=speaker,
            text=text,
            confidence=confidence
        )

        self.active_calls[call_id].transcript.append(entry)

        # Save to database
        if self._db_repo and self._db_initialized:
            try:
                db_entry = CallTranscriptDB(
                    call_id=call_id,
                    speaker=speaker,
                    text=text,
                    confidence=confidence
                )
                await self._db_repo.add_transcript_entry(db_entry)
            except Exception as e:
                logger.error(f"Failed to save transcript to database: {e}")

    def get_twiml_for_call(self, call_id: str) -> Optional[str]:
        """Get TwiML for connecting a call to Ultravox"""
        if call_id not in self.active_calls:
            return None

        call_record = self.active_calls[call_id]
        join_url = call_record.metadata.get("ultravox_join_url")

        if not join_url:
            return None

        return self.twilio.generate_connect_twiml(join_url)

    async def get_call_history(
        self,
        limit: int = 50,
        status_filter: Optional[CallStatus] = None
    ) -> List[CallRecord]:
        """Get call history"""
        # Use database if available
        if self._db_repo and self._db_initialized:
            try:
                status_str = status_filter.value if status_filter else None
                db_records = await self._db_repo.list_calls(limit=limit, status=status_str)
                return [self._db_to_model(r) for r in db_records]
            except Exception as e:
                logger.error(f"Failed to get call history from database: {e}")

        # Fallback to in-memory history
        records = self.call_history.copy()
        if status_filter:
            records = [r for r in records if r.status == status_filter]
        return records[-limit:]

    async def _move_to_history(self, call_id: str):
        """Move a call from active to history"""
        if call_id in self.active_calls:
            record = self.active_calls.pop(call_id)
            self.call_history.append(record)

            # Save to database
            await self._save_call_to_db(record)

            # Also save to file as backup
            self._save_call_records_to_file()

    async def _generate_summary(self, call_record: CallRecord):
        """Generate and store call summary"""
        try:
            transcript_data = [
                {"speaker": t.speaker, "text": t.text}
                for t in call_record.transcript
            ]

            result = await self.openai.generate_call_summary(
                transcript=transcript_data,
                call_metadata=call_record.metadata
            )

            if result.get("success"):
                try:
                    summary_data = json.loads(result.get("content", "{}"))
                    call_record.summary = CallSummary(
                        call_id=call_record.call_id,
                        summary=summary_data.get("summary", ""),
                        key_points=summary_data.get("key_points", []),
                        sentiment=summary_data.get("sentiment"),
                        action_items=summary_data.get("action_items", [])
                    )

                    # Save summary to database
                    if self._db_repo and self._db_initialized:
                        db_summary = CallSummaryDB(
                            call_id=call_record.call_id,
                            summary=call_record.summary.summary,
                            key_points=call_record.summary.key_points,
                            sentiment=call_record.summary.sentiment,
                            action_items=call_record.summary.action_items
                        )
                        await self._db_repo.save_summary(db_summary)

                    self._save_call_records_to_file()
                except json.JSONDecodeError:
                    call_record.summary = CallSummary(
                        call_id=call_record.call_id,
                        summary=result.get("content", ""),
                        key_points=[],
                        action_items=[]
                    )

        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")

    # ==================== Analytics Methods ====================

    async def get_statistics(self) -> Dict[str, Any]:
        """Get call statistics"""
        if self._db_repo and self._db_initialized:
            try:
                return await self._db_repo.get_call_statistics()
            except Exception as e:
                logger.error(f"Failed to get statistics from database: {e}")

        # Fallback calculation
        total = len(self.call_history)
        completed = sum(1 for c in self.call_history if c.status == CallStatus.COMPLETED)
        failed = sum(1 for c in self.call_history if c.status == CallStatus.FAILED)
        total_duration = sum(c.duration_seconds or 0 for c in self.call_history)

        return {
            "total_calls": total,
            "completed_calls": completed,
            "failed_calls": failed,
            "active_calls": len(self.active_calls),
            "total_duration_seconds": total_duration,
            "average_duration_seconds": total_duration / completed if completed > 0 else 0,
            "success_rate": (completed / total * 100) if total > 0 else 0,
        }

    async def get_sentiment_distribution(self) -> Dict[str, int]:
        """Get sentiment distribution"""
        if self._db_repo and self._db_initialized:
            try:
                return await self._db_repo.get_sentiment_distribution()
            except Exception as e:
                logger.error(f"Failed to get sentiment from database: {e}")

        # Fallback calculation
        distribution = {"positive": 0, "neutral": 0, "negative": 0}
        for call in self.call_history:
            if call.summary and call.summary.sentiment:
                sentiment = call.summary.sentiment.lower()
                if sentiment in distribution:
                    distribution[sentiment] += 1
        return distribution


# Singleton instance
_call_manager: Optional[CallManager] = None


def get_call_manager() -> CallManager:
    """Get the CallManager singleton instance"""
    global _call_manager
    if _call_manager is None:
        _call_manager = CallManager()
    return _call_manager


async def initialize_call_manager() -> CallManager:
    """Initialize CallManager with database connection"""
    manager = get_call_manager()
    await manager.initialize_database()
    return manager
