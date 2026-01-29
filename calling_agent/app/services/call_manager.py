"""
Call Manager Service
Orchestrates Ultravox and Twilio services to manage calls
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


class CallManager:
    """
    Manages the lifecycle of calls including initiation, monitoring,
    and transcription/summary generation
    """

    def __init__(self):
        self.ultravox = UltravoxService()
        self.twilio = TwilioService()
        self.openai = OpenAIService()

        # In-memory call storage (use database in production)
        self.active_calls: Dict[str, CallRecord] = {}
        self.call_history: List[CallRecord] = []

        # File-based persistence for demo
        self.records_file = Path(settings.call_records_file_path)
        self._load_call_records()

    def _load_call_records(self):
        """Load call records from file"""
        if self.records_file.exists():
            try:
                with open(self.records_file, "r") as f:
                    data = json.load(f)
                    for record_data in data.get("history", []):
                        record = CallRecord(**record_data)
                        self.call_history.append(record)
                logger.info(f"Loaded {len(self.call_history)} call records")
            except Exception as e:
                logger.warning(f"Failed to load call records: {e}")

    def _save_call_records(self):
        """Save call records to file"""
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
                self._move_to_history(call_id)
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

            # Step 2: Initiate Twilio call with Ultravox connection
            # Create TwiML endpoint URL that will connect to Ultravox
            twiml_url = f"{settings.api_base_url}/api/v1/webhooks/twilio/connect/{call_id}"

            twilio_result = await self.twilio.initiate_call(
                to_number=request.phone_number,
                twiml_url=twiml_url,
                status_callback_url=f"{settings.api_base_url}/api/v1/webhooks/twilio/status/{call_id}"
            )

            if not twilio_result.get("success"):
                call_record.status = CallStatus.FAILED
                call_record.error_message = twilio_result.get("error", "Failed to initiate call")
                # Try to clean up Ultravox session
                await self.ultravox.end_call(ultravox_call_id)
                self._move_to_history(call_id)
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

            # Store the join URL for later use
            call_record.metadata["ultravox_join_url"] = join_url

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
            self._move_to_history(call_id)
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
        """
        Handle an inbound call

        Args:
            twilio_call_sid: Twilio call SID
            from_number: Caller's phone number
            to_number: Called number
            system_prompt: Optional custom system prompt
            greeting_message: Optional greeting message

        Returns:
            TwiML and call info
        """
        call_id = str(uuid.uuid4())
        logger.info(f"Handling inbound call {call_id} from {from_number}")

        # Create call record
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

        try:
            # Create Ultravox session
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

            # Generate TwiML to connect to Ultravox
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
        """
        Get the current status of a call

        Args:
            call_id: Call identifier

        Returns:
            Call record if found
        """
        # Check active calls first
        if call_id in self.active_calls:
            return self.active_calls[call_id]

        # Check history
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
        """
        Update the status of a call

        Args:
            call_id: Call identifier
            status: New status
            error_message: Optional error message
        """
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

            # Move to history
            self._move_to_history(call_id)

            # Generate summary if call completed
            if status == CallStatus.COMPLETED and call_record.transcript:
                asyncio.create_task(self._generate_summary(call_record))

        logger.info(f"Call {call_id} status updated to {status}")

    async def end_call(self, call_id: str) -> Dict[str, Any]:
        """
        End an active call

        Args:
            call_id: Call identifier

        Returns:
            Result of the operation
        """
        if call_id not in self.active_calls:
            return {
                "success": False,
                "error": "Call not found"
            }

        call_record = self.active_calls[call_id]

        # End Twilio call
        if call_record.twilio_call_sid:
            await self.twilio.end_call(call_record.twilio_call_sid)

        # End Ultravox session
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
        """
        Add a transcript entry to a call

        Args:
            call_id: Call identifier
            speaker: Speaker identifier
            text: Transcribed text
            confidence: Transcription confidence
        """
        if call_id not in self.active_calls:
            return

        entry = CallTranscript(
            speaker=speaker,
            text=text,
            confidence=confidence
        )

        self.active_calls[call_id].transcript.append(entry)

    def get_twiml_for_call(self, call_id: str) -> Optional[str]:
        """
        Get TwiML for connecting a call to Ultravox

        Args:
            call_id: Call identifier

        Returns:
            TwiML string or None
        """
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
        """
        Get call history

        Args:
            limit: Maximum number of records
            status_filter: Optional status filter

        Returns:
            List of call records
        """
        records = self.call_history.copy()

        if status_filter:
            records = [r for r in records if r.status == status_filter]

        return records[-limit:]

    def _move_to_history(self, call_id: str):
        """Move a call from active to history"""
        if call_id in self.active_calls:
            record = self.active_calls.pop(call_id)
            self.call_history.append(record)
            self._save_call_records()

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
                # Parse the summary response
                import json
                try:
                    summary_data = json.loads(result.get("content", "{}"))
                    call_record.summary = CallSummary(
                        call_id=call_record.call_id,
                        summary=summary_data.get("summary", ""),
                        key_points=summary_data.get("key_points", []),
                        sentiment=summary_data.get("sentiment"),
                        action_items=summary_data.get("action_items", [])
                    )
                    self._save_call_records()
                except json.JSONDecodeError:
                    call_record.summary = CallSummary(
                        call_id=call_record.call_id,
                        summary=result.get("content", ""),
                        key_points=[],
                        action_items=[]
                    )

        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")


# Singleton instance
_call_manager: Optional[CallManager] = None


def get_call_manager() -> CallManager:
    """Get the CallManager singleton instance"""
    global _call_manager
    if _call_manager is None:
        _call_manager = CallManager()
    return _call_manager
