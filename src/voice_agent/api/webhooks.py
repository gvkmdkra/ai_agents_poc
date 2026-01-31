"""
Twilio Webhook Handlers

Handles:
- Incoming voice calls
- Call status updates
- Recording callbacks
- WhatsApp/SMS incoming messages
"""

import logging
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Form, Header, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse

from ..models.schemas import (
    CallDirection,
    CallStatus,
    LeadSource,
    NotificationChannel,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["Webhooks"])


# =========================================================================
# VOICE WEBHOOKS
# =========================================================================


@router.post("/voice/answer", response_class=PlainTextResponse)
async def voice_answer(
    request: Request,
    CallSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(...),
    CallStatus: str = Form(...),
    Direction: Optional[str] = Form(None),
    tenant_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    voice_config_id: Optional[str] = None,
):
    """
    Handle incoming voice call - Twilio webhook.

    This is the entry point for all incoming calls. It:
    1. Looks up the tenant by the called number (To)
    2. Gets or creates a lead from the caller (From)
    3. Creates a call record
    4. Returns TwiML to connect to Media Stream for Ultravox
    """
    # Get services from app state
    tenant_service = request.app.state.tenant_service
    lead_service = request.app.state.lead_service
    call_service = request.app.state.call_service
    twilio_client = request.app.state.twilio_client

    try:
        # 1. Look up tenant by called number
        if tenant_id:
            tenant = await tenant_service.get_tenant(UUID(tenant_id))
        else:
            tenant = await tenant_service.get_tenant_by_phone(To)

        if not tenant:
            logger.warning(f"No tenant found for number: {To}")
            return twilio_client.generate_fallback_twiml(
                "Sorry, this number is not currently configured. Please try again later."
            )

        # 2. Check business hours
        is_open = await tenant_service.is_within_business_hours(tenant.id)
        if not is_open:
            # Get after-hours configuration
            # For now, return voicemail
            voice_config = await tenant_service.get_default_voice_config(tenant.id)
            return twilio_client.generate_voicemail_twiml(
                greeting=f"Thank you for calling {tenant.name}. We are currently closed. Please leave a message after the beep.",
                recording_callback_url=f"{request.base_url}webhook/voice/recording",
            )

        # 3. Get or create lead
        lead, is_new = await lead_service.get_or_create_lead(
            tenant_id=tenant.id,
            phone=From,
            source=LeadSource.INBOUND_CALL,
            source_phone_number=To,
        )

        logger.info(f"Call from {From} to {To}: lead={lead.id}, new={is_new}")

        # 4. Get voice configuration
        if voice_config_id:
            voice_config = await tenant_service.get_voice_config(UUID(voice_config_id))
        else:
            voice_config = await tenant_service.get_default_voice_config(tenant.id)

        if not voice_config:
            return twilio_client.generate_fallback_twiml(
                "Sorry, we are experiencing technical difficulties. Please try again later."
            )

        # 5. Create call record
        from ..models.schemas import CallCreate

        call = await call_service.create_call(
            CallCreate(
                tenant_id=tenant.id,
                lead_id=lead.id,
                twilio_call_sid=CallSid,
                direction=CallDirection.INBOUND,
                from_number=From,
                to_number=To,
                voice_config_id=voice_config.id,
            )
        )

        # 6. Generate TwiML to connect to Media Stream
        twiml = twilio_client.generate_answer_twiml(
            tenant_id=str(tenant.id),
            voice_config_id=str(voice_config.id),
            call_sid=CallSid,
        )

        return Response(content=twiml, media_type="application/xml")

    except Exception as e:
        logger.error(f"Error handling voice answer: {e}", exc_info=True)
        return twilio_client.generate_fallback_twiml()


@router.post("/voice/status")
async def voice_status(
    request: Request,
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
    CallDuration: Optional[int] = Form(None),
    RecordingUrl: Optional[str] = Form(None),
    RecordingSid: Optional[str] = Form(None),
    RecordingDuration: Optional[int] = Form(None),
):
    """
    Handle call status updates from Twilio.

    Called for: initiated, ringing, answered, completed, busy, no-answer, failed
    """
    call_service = request.app.state.call_service

    try:
        call = await call_service.get_call_by_sid(CallSid)
        if not call:
            logger.warning(f"Call not found for status update: {CallSid}")
            return {"status": "ignored"}

        # Map Twilio status to internal status
        status_map = {
            "initiated": CallStatus.INITIATED,
            "ringing": CallStatus.RINGING,
            "in-progress": CallStatus.IN_PROGRESS,
            "completed": CallStatus.COMPLETED,
            "busy": CallStatus.BUSY,
            "no-answer": CallStatus.NO_ANSWER,
            "failed": CallStatus.FAILED,
            "canceled": CallStatus.CANCELED,
        }

        from ..models.schemas import CallUpdate

        updates = CallUpdate(
            status=status_map.get(CallStatus, CallStatus.COMPLETED),
        )

        if CallDuration:
            updates.duration_seconds = CallDuration

        await call_service.update_call(call.id, updates)

        # If completed, trigger post-call processing
        if CallStatus == "completed":
            # Async task for analysis
            import asyncio

            asyncio.create_task(_process_completed_call(request, call.id))

        logger.info(f"Call {CallSid} status updated to {CallStatus}")
        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error handling call status: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/voice/recording")
async def voice_recording(
    request: Request,
    CallSid: str = Form(...),
    RecordingSid: str = Form(...),
    RecordingUrl: str = Form(...),
    RecordingDuration: int = Form(...),
):
    """Handle recording completion callback"""
    call_service = request.app.state.call_service

    try:
        call = await call_service.get_call_by_sid(CallSid)
        if call:
            await call_service.update_recording(
                call.id,
                recording_url=RecordingUrl,
                recording_sid=RecordingSid,
                duration_seconds=RecordingDuration,
            )

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error handling recording: {e}")
        return {"status": "error"}


@router.post("/voice/transcription")
async def voice_transcription(
    request: Request,
    CallSid: str = Form(...),
    TranscriptionSid: str = Form(...),
    TranscriptionText: str = Form(...),
    TranscriptionStatus: str = Form(...),
):
    """Handle transcription completion callback (for voicemails)"""
    call_service = request.app.state.call_service
    lead_service = request.app.state.lead_service

    try:
        call = await call_service.get_call_by_sid(CallSid)
        if call and TranscriptionStatus == "completed":
            # Add transcription as a note
            await call_service.add_transcript_entry(
                call.id,
                role="user",
                text=f"[Voicemail] {TranscriptionText}",
            )

            # Update call outcome
            from ..models.schemas import CallUpdate

            await call_service.update_call(
                call.id,
                CallUpdate(
                    outcome="voicemail",
                    follow_up_required=True,
                ),
            )

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error handling transcription: {e}")
        return {"status": "error"}


# =========================================================================
# WHATSAPP WEBHOOKS
# =========================================================================


@router.post("/whatsapp/incoming")
async def whatsapp_incoming(
    request: Request,
    MessageSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(...),
    Body: str = Form(...),
    NumMedia: int = Form(0),
    ProfileName: Optional[str] = Form(None),
):
    """
    Handle incoming WhatsApp messages.

    This could be:
    - A response to an appointment confirmation
    - A new inquiry
    - A follow-up question
    """
    tenant_service = request.app.state.tenant_service
    lead_service = request.app.state.lead_service
    notification_service = request.app.state.notification_service

    try:
        # Remove 'whatsapp:' prefix
        from_number = From.replace("whatsapp:", "")
        to_number = To.replace("whatsapp:", "")

        # Look up tenant
        tenant = await tenant_service.get_tenant_by_phone(to_number)
        if not tenant:
            logger.warning(f"No tenant for WhatsApp number: {to_number}")
            return {"status": "ignored"}

        # Get or create lead
        first_name = ProfileName.split()[0] if ProfileName else None
        lead, is_new = await lead_service.get_or_create_lead(
            tenant_id=tenant.id,
            phone=from_number,
            source=LeadSource.WHATSAPP,
            source_phone_number=to_number,
            first_name=first_name,
        )

        # Check for appointment confirmation responses
        body_lower = Body.lower().strip()
        if body_lower in ("yes", "confirm", "confirmed"):
            # Look for pending appointment
            appointment_service = request.app.state.appointment_service
            appointments = await appointment_service.list_appointments(
                tenant_id=tenant.id,
                lead_id=lead.id,
                status="scheduled",
                limit=1,
            )

            if appointments:
                from ..models.schemas import AppointmentStatus, AppointmentUpdate

                await appointment_service.update_appointment(
                    appointments[0].id,
                    AppointmentUpdate(status=AppointmentStatus.CONFIRMED),
                )

                # Send confirmation
                await notification_service.send_notification(
                    NotificationCreate(
                        tenant_id=tenant.id,
                        lead_id=lead.id,
                        channel=NotificationChannel.WHATSAPP,
                        to_address=from_number,
                        from_address=to_number,
                        body="Great! Your appointment has been confirmed. We look forward to seeing you!",
                        notification_type=NotificationType.TRANSACTIONAL,
                    )
                )

        # Store incoming message for context
        # Could trigger AI response for new inquiries

        logger.info(f"WhatsApp from {from_number}: {Body[:50]}...")
        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error handling WhatsApp: {e}")
        return {"status": "error"}


@router.post("/whatsapp/status")
async def whatsapp_status(
    request: Request,
    MessageSid: str = Form(...),
    MessageStatus: str = Form(...),
    ErrorCode: Optional[str] = Form(None),
    ErrorMessage: Optional[str] = Form(None),
):
    """Handle WhatsApp message delivery status"""
    notification_service = request.app.state.notification_service

    try:
        await notification_service.handle_delivery_status(
            external_id=MessageSid,
            status=MessageStatus,
            error_code=ErrorCode,
            error_message=ErrorMessage,
        )

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error handling WhatsApp status: {e}")
        return {"status": "error"}


# =========================================================================
# SMS WEBHOOKS
# =========================================================================


@router.post("/sms/incoming")
async def sms_incoming(
    request: Request,
    MessageSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(...),
    Body: str = Form(...),
):
    """Handle incoming SMS messages"""
    tenant_service = request.app.state.tenant_service
    lead_service = request.app.state.lead_service

    try:
        tenant = await tenant_service.get_tenant_by_phone(To)
        if not tenant:
            return {"status": "ignored"}

        # Get or create lead
        lead, is_new = await lead_service.get_or_create_lead(
            tenant_id=tenant.id,
            phone=From,
            source=LeadSource.SMS,
            source_phone_number=To,
        )

        # Similar logic to WhatsApp for confirmations
        # ...

        logger.info(f"SMS from {From}: {Body[:50]}...")
        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error handling SMS: {e}")
        return {"status": "error"}


# =========================================================================
# HELPER FUNCTIONS
# =========================================================================


async def _process_completed_call(request: Request, call_id: UUID):
    """Process a completed call (async task)"""
    try:
        call_service = request.app.state.call_service
        lead_service = request.app.state.lead_service

        call = await call_service.get_call(call_id)
        if not call:
            return

        # 1. Analyze call
        analysis = await call_service.analyze_call(call_id)

        # 2. Qualify lead if we have a transcript
        if call.lead_id and call.transcript:
            tenant_service = request.app.state.tenant_service
            tenant = await tenant_service.get_tenant(call.tenant_id)

            transcript_text = await call_service.get_transcript_text(call_id)

            qualification = await lead_service.qualify_lead(
                lead_id=call.lead_id,
                conversation_transcript=transcript_text,
                industry=tenant.industry if tenant else "general",
            )

            # 3. Sync to Odoo if configured
            try:
                await lead_service.sync_lead_to_odoo(call.lead_id)
            except Exception as e:
                logger.warning(f"Failed to sync lead to Odoo: {e}")

            # 4. Create follow-up sequence for hot/warm leads
            if qualification.temperature in ("hot", "warm"):
                await lead_service.create_follow_up_sequence(
                    lead_id=call.lead_id,
                )

        logger.info(f"Completed post-call processing for {call_id}")

    except Exception as e:
        logger.error(f"Error in post-call processing: {e}")
