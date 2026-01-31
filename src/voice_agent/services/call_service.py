"""
Call Service

Handles:
- Call lifecycle management
- Real-time call state
- Recording and transcription
- Call analytics
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from ..integrations.twilio_client import TwilioClient
from ..integrations.ultravox_client import UltravoxClient, UltravoxSession
from ..integrations.openai_client import OpenAIVoiceClient
from ..models.schemas import (
    Call,
    CallCreate,
    CallUpdate,
    CallStatus,
    CallDirection,
)

logger = logging.getLogger(__name__)


class CallService:
    """
    Service for managing voice calls.

    Responsibilities:
    - Call creation and lifecycle
    - Session management
    - Recording handling
    - Transcript management
    - Analytics
    """

    def __init__(
        self,
        db_pool,
        twilio_client: Optional[TwilioClient] = None,
        ultravox_client: Optional[UltravoxClient] = None,
        openai_client: Optional[OpenAIVoiceClient] = None,
    ):
        self.db = db_pool
        self.twilio = twilio_client
        self.ultravox = ultravox_client
        self.openai = openai_client

        # Active call sessions
        self._active_sessions: dict[str, dict[str, Any]] = {}

    # =========================================================================
    # CALL LIFECYCLE
    # =========================================================================

    async def create_call(self, data: CallCreate) -> Call:
        """
        Create a new call record.

        Args:
            data: Call creation data

        Returns:
            Created call record
        """
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO voice_calls (
                    tenant_id, lead_id, twilio_call_sid, direction,
                    from_number, to_number, voice_config_id, started_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                RETURNING *
                """,
                data.tenant_id,
                data.lead_id,
                data.twilio_call_sid,
                data.direction.value,
                data.from_number,
                data.to_number,
                data.voice_config_id,
            )

            call = self._row_to_call(row)
            logger.info(f"Created call: {call.id} ({data.twilio_call_sid})")
            return call

    async def get_call(self, call_id: UUID) -> Optional[Call]:
        """Get a call by ID"""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM voice_calls WHERE id = $1",
                call_id,
            )
            return self._row_to_call(row) if row else None

    async def get_call_by_sid(self, twilio_call_sid: str) -> Optional[Call]:
        """Get a call by Twilio SID"""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM voice_calls WHERE twilio_call_sid = $1",
                twilio_call_sid,
            )
            return self._row_to_call(row) if row else None

    async def update_call(self, call_id: UUID, updates: CallUpdate) -> Optional[Call]:
        """Update a call record"""
        set_clauses = []
        params = []
        param_count = 1

        update_dict = updates.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            if value is not None:
                if isinstance(value, CallStatus):
                    value = value.value
                set_clauses.append(f"{field} = ${param_count}")
                params.append(value)
                param_count += 1

        if not set_clauses:
            return await self.get_call(call_id)

        params.append(call_id)

        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                UPDATE voice_calls
                SET {', '.join(set_clauses)}
                WHERE id = ${param_count}
                RETURNING *
                """,
                *params,
            )

            return self._row_to_call(row) if row else None

    async def end_call(
        self,
        call_id: UUID,
        outcome: Optional[str] = None,
        follow_up_required: bool = False,
    ) -> Optional[Call]:
        """End a call and finalize its record"""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE voice_calls
                SET
                    status = 'completed',
                    ended_at = NOW(),
                    duration_seconds = EXTRACT(EPOCH FROM (NOW() - answered_at))::INTEGER,
                    outcome = $1,
                    follow_up_required = $2
                WHERE id = $3
                RETURNING *
                """,
                outcome,
                follow_up_required,
                call_id,
            )

            if row:
                call = self._row_to_call(row)
                logger.info(
                    f"Call ended: {call_id}, duration={call.duration_seconds}s, "
                    f"outcome={outcome}"
                )

                # Clean up session
                self._cleanup_session(str(call_id))

                return call
            return None

    # =========================================================================
    # OUTBOUND CALLS
    # =========================================================================

    async def initiate_outbound_call(
        self,
        tenant_id: UUID,
        to_number: str,
        from_number: str,
        lead_id: Optional[UUID] = None,
        voice_config_id: Optional[UUID] = None,
    ) -> Call:
        """
        Initiate an outbound AI call.

        Args:
            tenant_id: Tenant ID
            to_number: Destination phone number
            from_number: Caller ID (Twilio number)
            lead_id: Optional lead ID
            voice_config_id: Voice configuration to use

        Returns:
            Created call record
        """
        if not self.twilio:
            raise ValueError("Twilio client not configured")

        # Initiate Twilio call
        result = await self.twilio.initiate_outbound_call(
            to_number=to_number,
            from_number=from_number,
            tenant_id=str(tenant_id),
            lead_id=str(lead_id) if lead_id else None,
            voice_config_id=str(voice_config_id) if voice_config_id else None,
        )

        # Create call record
        call = await self.create_call(
            CallCreate(
                tenant_id=tenant_id,
                lead_id=lead_id,
                twilio_call_sid=result["call_sid"],
                direction=CallDirection.OUTBOUND,
                from_number=from_number,
                to_number=to_number,
                voice_config_id=voice_config_id,
            )
        )

        return call

    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================

    async def start_session(
        self,
        call_id: UUID,
        twilio_call_sid: str,
        system_prompt: str,
        voice_config: dict[str, Any],
    ) -> UltravoxSession:
        """
        Start an Ultravox voice AI session for a call.

        Args:
            call_id: Call ID
            twilio_call_sid: Twilio call SID
            system_prompt: AI system prompt
            voice_config: Voice configuration

        Returns:
            Active Ultravox session
        """
        if not self.ultravox:
            raise ValueError("Ultravox client not configured")

        # Create Ultravox session
        session = await self.ultravox.create_session(
            system_prompt=system_prompt,
            session_id=str(call_id),
        )

        # Store session reference
        self._active_sessions[str(call_id)] = {
            "session": session,
            "twilio_call_sid": twilio_call_sid,
            "started_at": datetime.now(),
            "transcript": [],
        }

        # Update call status
        await self.update_call(
            call_id,
            CallUpdate(status=CallStatus.IN_PROGRESS),
        )

        logger.info(f"Started voice session for call {call_id}")
        return session

    def get_session(self, call_id: UUID) -> Optional[dict[str, Any]]:
        """Get active session for a call"""
        return self._active_sessions.get(str(call_id))

    def _cleanup_session(self, call_id: str):
        """Clean up session resources"""
        session_data = self._active_sessions.pop(call_id, None)
        if session_data and session_data.get("session"):
            asyncio.create_task(session_data["session"].disconnect())

    # =========================================================================
    # TRANSCRIPT MANAGEMENT
    # =========================================================================

    async def add_transcript_entry(
        self,
        call_id: UUID,
        role: str,
        text: str,
        confidence: Optional[float] = None,
        sentiment: Optional[float] = None,
    ):
        """
        Add a transcript entry to a call.

        Args:
            call_id: Call ID
            role: "user" or "assistant"
            text: Transcript text
            confidence: ASR confidence score
            sentiment: Sentiment score
        """
        entry = {
            "role": role,
            "text": text,
            "timestamp": datetime.now().isoformat(),
            "confidence": confidence,
            "sentiment": sentiment,
        }

        async with self.db.acquire() as conn:
            await conn.execute(
                """
                UPDATE voice_calls
                SET
                    transcript = transcript || $1::jsonb,
                    conversation_turns = conversation_turns + 1
                WHERE id = $2
                """,
                [entry],
                call_id,
            )

        # Update in-memory session
        session_data = self._active_sessions.get(str(call_id))
        if session_data:
            session_data["transcript"].append(entry)

    async def get_transcript(self, call_id: UUID) -> list[dict]:
        """Get full transcript for a call"""
        call = await self.get_call(call_id)
        return call.transcript if call else []

    async def get_transcript_text(self, call_id: UUID) -> str:
        """Get transcript as formatted text"""
        transcript = await self.get_transcript(call_id)
        lines = []
        for entry in transcript:
            role = "User" if entry["role"] == "user" else "AI"
            lines.append(f"{role}: {entry['text']}")
        return "\n".join(lines)

    # =========================================================================
    # CALL ANALYSIS
    # =========================================================================

    async def analyze_call(self, call_id: UUID) -> dict[str, Any]:
        """
        Analyze a completed call.

        Performs:
        - Sentiment analysis
        - Intent detection
        - Conversation summarization

        Args:
            call_id: Call ID

        Returns:
            Analysis results
        """
        if not self.openai:
            raise ValueError("OpenAI client not configured")

        transcript_text = await self.get_transcript_text(call_id)
        if not transcript_text:
            return {"error": "No transcript available"}

        # Parallel analysis
        results = await asyncio.gather(
            self.openai.analyze_sentiment(transcript_text),
            self.openai.summarize_conversation(transcript_text),
            return_exceptions=True,
        )

        sentiment_result = results[0] if not isinstance(results[0], Exception) else None
        summary_result = results[1] if not isinstance(results[1], Exception) else None

        # Update call with analysis
        updates = CallUpdate()
        if sentiment_result:
            updates.sentiment_score = sentiment_result.score
        if summary_result:
            updates.transcript_summary = summary_result.get("summary")

        await self.update_call(call_id, updates)

        return {
            "sentiment": sentiment_result.__dict__ if sentiment_result else None,
            "summary": summary_result,
        }

    # =========================================================================
    # ESCALATION
    # =========================================================================

    async def escalate_to_human(
        self,
        call_id: UUID,
        reason: str,
        transfer_to: Optional[str] = None,
    ) -> bool:
        """
        Escalate a call to a human agent.

        Args:
            call_id: Call ID
            reason: Escalation reason
            transfer_to: Optional specific number to transfer to

        Returns:
            True if escalation successful
        """
        call = await self.get_call(call_id)
        if not call:
            return False

        # Update call record
        await self.update_call(
            call_id,
            CallUpdate(
                escalated_to_human=True,
                escalation_reason=reason,
            ),
        )

        async with self.db.acquire() as conn:
            await conn.execute(
                """
                UPDATE voice_calls
                SET escalated_at = NOW()
                WHERE id = $1
                """,
                call_id,
            )

        # If transfer number provided, initiate transfer
        if transfer_to and self.twilio and call.twilio_call_sid:
            # Generate transfer TwiML and update call
            transfer_twiml = self.twilio.generate_transfer_twiml(
                transfer_to=transfer_to,
                whisper_message=f"Incoming transfer. Reason: {reason}",
            )
            # Note: Would need to update call with new TwiML via Twilio API

        logger.info(f"Escalated call {call_id} to human: {reason}")
        return True

    # =========================================================================
    # RECORDINGS
    # =========================================================================

    async def update_recording(
        self,
        call_id: UUID,
        recording_url: str,
        recording_sid: str,
        duration_seconds: int,
    ):
        """Update call with recording information"""
        async with self.db.acquire() as conn:
            await conn.execute(
                """
                UPDATE voice_calls
                SET
                    recording_url = $1,
                    recording_sid = $2,
                    recording_duration_seconds = $3
                WHERE id = $4
                """,
                recording_url,
                recording_sid,
                duration_seconds,
                call_id,
            )

        logger.info(f"Updated recording for call {call_id}")

    # =========================================================================
    # QUERIES
    # =========================================================================

    async def list_calls(
        self,
        tenant_id: UUID,
        lead_id: Optional[UUID] = None,
        status: Optional[CallStatus] = None,
        direction: Optional[CallDirection] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Call]:
        """List calls with filters"""
        conditions = ["tenant_id = $1"]
        params = [tenant_id]
        param_count = 2

        if lead_id:
            conditions.append(f"lead_id = ${param_count}")
            params.append(lead_id)
            param_count += 1

        if status:
            conditions.append(f"status = ${param_count}")
            params.append(status.value)
            param_count += 1

        if direction:
            conditions.append(f"direction = ${param_count}")
            params.append(direction.value)
            param_count += 1

        if start_date:
            conditions.append(f"started_at >= ${param_count}")
            params.append(start_date)
            param_count += 1

        if end_date:
            conditions.append(f"started_at <= ${param_count}")
            params.append(end_date)
            param_count += 1

        params.extend([limit, offset])

        async with self.db.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT * FROM voice_calls
                WHERE {' AND '.join(conditions)}
                ORDER BY started_at DESC
                LIMIT ${param_count} OFFSET ${param_count + 1}
                """,
                *params,
            )

            return [self._row_to_call(row) for row in rows]

    async def get_active_calls(self, tenant_id: Optional[UUID] = None) -> list[Call]:
        """Get all currently active calls"""
        async with self.db.acquire() as conn:
            if tenant_id:
                rows = await conn.fetch(
                    """
                    SELECT * FROM voice_calls
                    WHERE tenant_id = $1 AND status = 'in-progress'
                    ORDER BY started_at DESC
                    """,
                    tenant_id,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM voice_calls
                    WHERE status = 'in-progress'
                    ORDER BY started_at DESC
                    """,
                )

            return [self._row_to_call(row) for row in rows]

    async def get_call_stats(
        self,
        tenant_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Get call statistics for a period"""
        async with self.db.acquire() as conn:
            stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total_calls,
                    COUNT(*) FILTER (WHERE direction = 'inbound') as inbound_calls,
                    COUNT(*) FILTER (WHERE direction = 'outbound') as outbound_calls,
                    COUNT(*) FILTER (WHERE status = 'completed') as completed_calls,
                    COUNT(*) FILTER (WHERE escalated_to_human = true) as escalated_calls,
                    AVG(duration_seconds) FILTER (WHERE status = 'completed') as avg_duration,
                    AVG(conversation_turns) as avg_turns,
                    AVG(sentiment_score) as avg_sentiment,
                    SUM(total_cost_usd) as total_cost
                FROM voice_calls
                WHERE tenant_id = $1
                  AND started_at >= $2
                  AND started_at < $3
                """,
                tenant_id,
                start_date,
                end_date,
            )

            return dict(stats)

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _row_to_call(self, row: dict) -> Call:
        """Convert database row to Call model"""
        return Call(
            id=row["id"],
            tenant_id=row["tenant_id"],
            lead_id=row["lead_id"],
            twilio_call_sid=row["twilio_call_sid"],
            direction=CallDirection(row["direction"]),
            from_number=row["from_number"],
            to_number=row["to_number"],
            status=CallStatus(row["status"]),
            duration_seconds=row["duration_seconds"],
            started_at=row["started_at"],
            answered_at=row["answered_at"],
            ended_at=row["ended_at"],
            conversation_turns=row["conversation_turns"],
            ai_handled=row["ai_handled"],
            escalated_to_human=row["escalated_to_human"],
            escalation_reason=row["escalation_reason"],
            recording_url=row["recording_url"],
            transcript=row["transcript"] or [],
            transcript_summary=row["transcript_summary"],
            sentiment_score=float(row["sentiment_score"]) if row["sentiment_score"] else None,
            intent_detected=row["intent_detected"],
            outcome=row["outcome"],
            follow_up_required=row["follow_up_required"],
            total_cost_usd=float(row["total_cost_usd"]) if row["total_cost_usd"] else None,
            created_at=row["created_at"],
        )
