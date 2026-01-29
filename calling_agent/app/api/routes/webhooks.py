"""
Webhook routes for Twilio and Ultravox callbacks
"""

from typing import Optional
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import Response

from app.core.logging import get_logger
from app.models.call import CallStatus
from app.services.call_manager import get_call_manager
from app.services.telephony.twilio_service import TwilioService

logger = get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/twilio/voice")
async def handle_incoming_call(
    request: Request,
    CallSid: str = Form(...),
    AccountSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(...),
    CallStatus: str = Form(...),
    Direction: str = Form(...)
):
    """
    Handle incoming calls from Twilio

    This webhook is called when someone calls the Twilio phone number.
    """
    logger.info(f"Incoming call from {From} to {To}, SID: {CallSid}")

    manager = get_call_manager()

    result = await manager.handle_inbound_call(
        twilio_call_sid=CallSid,
        from_number=From,
        to_number=To
    )

    return Response(
        content=result.get("twiml", ""),
        media_type="application/xml"
    )


@router.post("/twilio/connect/{call_id}")
async def connect_call_to_ultravox(call_id: str):
    """
    Provide TwiML to connect an outbound call to Ultravox

    This webhook is called by Twilio when the outbound call is answered.
    """
    logger.info(f"Connecting call {call_id} to Ultravox")

    manager = get_call_manager()
    twiml = manager.get_twiml_for_call(call_id)

    if not twiml:
        logger.error(f"No TwiML available for call {call_id}")
        twilio_service = TwilioService()
        twiml = twilio_service.generate_hangup_twiml(
            "We're sorry, but we cannot complete your call at this time."
        )

    # Update call status
    await manager.update_call_status(call_id, CallStatus.IN_PROGRESS)

    return Response(
        content=twiml,
        media_type="application/xml"
    )


@router.post("/twilio/status/{call_id}")
async def handle_call_status(
    call_id: str,
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
    CallDuration: Optional[str] = Form(None),
    Timestamp: Optional[str] = Form(None)
):
    """
    Handle call status updates from Twilio

    This webhook receives status updates as the call progresses.
    """
    logger.info(f"Call {call_id} status update: {CallStatus}")

    manager = get_call_manager()
    twilio_service = TwilioService()

    # Map Twilio status to internal status
    internal_status = twilio_service.map_twilio_status(CallStatus)

    await manager.update_call_status(call_id, internal_status)

    return {"status": "received"}


@router.post("/twilio/status")
async def handle_call_status_generic(
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
    CallDuration: Optional[str] = Form(None)
):
    """
    Handle generic call status updates from Twilio

    This is used when call_id is not in the URL.
    """
    logger.info(f"Generic status update for {CallSid}: {CallStatus}")

    # Try to find the call by Twilio SID
    manager = get_call_manager()

    for call_id, record in manager.active_calls.items():
        if record.twilio_call_sid == CallSid:
            twilio_service = TwilioService()
            internal_status = twilio_service.map_twilio_status(CallStatus)
            await manager.update_call_status(call_id, internal_status)
            break

    return {"status": "received"}


@router.post("/twilio/amd")
async def handle_amd_result(
    CallSid: str = Form(...),
    AnsweredBy: Optional[str] = Form(None),
    MachineDetectionDuration: Optional[str] = Form(None)
):
    """
    Handle Answering Machine Detection results from Twilio
    """
    logger.info(f"AMD result for {CallSid}: {AnsweredBy}")

    manager = get_call_manager()

    # Find the call and update metadata
    for call_id, record in manager.active_calls.items():
        if record.twilio_call_sid == CallSid:
            record.metadata["answered_by"] = AnsweredBy
            record.metadata["amd_duration"] = MachineDetectionDuration

            # If answered by machine, we might want to leave a voicemail or hang up
            if AnsweredBy == "machine_start" or AnsweredBy == "machine_end_beep":
                logger.info(f"Call {call_id} answered by machine")
                # Could implement voicemail logic here
            break

    return {"status": "received"}


@router.post("/ultravox/events")
async def handle_ultravox_events(request: Request):
    """
    Handle webhook events from Ultravox

    Ultravox sends events for transcription updates, tool calls, etc.
    """
    try:
        body = await request.json()
        logger.debug(f"Ultravox event: {body}")

        event_type = body.get("type")
        call_id = body.get("metadata", {}).get("call_id")

        if not call_id:
            logger.warning("Ultravox event without call_id in metadata")
            return {"status": "received"}

        manager = get_call_manager()

        if event_type == "transcript":
            # Handle transcript update
            transcript_data = body.get("transcript", {})
            speaker = transcript_data.get("role", "unknown")
            text = transcript_data.get("text", "")

            if text:
                await manager.add_transcript_entry(
                    call_id=call_id,
                    speaker="agent" if speaker == "assistant" else "user",
                    text=text
                )

        elif event_type == "call.ended":
            # Handle call ended
            await manager.update_call_status(call_id, CallStatus.COMPLETED)

        elif event_type == "tool.call":
            # Handle tool calls from the agent
            tool_name = body.get("tool", {}).get("name")
            tool_params = body.get("tool", {}).get("parameters", {})
            logger.info(f"Tool call in {call_id}: {tool_name} with {tool_params}")
            # Implement tool handling logic here

        return {"status": "received"}

    except Exception as e:
        logger.error(f"Error handling Ultravox event: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/ultravox/transcript/{call_id}")
async def handle_transcript_update(
    call_id: str,
    request: Request
):
    """
    Handle transcript updates from Ultravox for a specific call
    """
    try:
        body = await request.json()
        logger.debug(f"Transcript update for {call_id}: {body}")

        manager = get_call_manager()

        speaker = body.get("role", "unknown")
        text = body.get("text", "")
        confidence = body.get("confidence")

        if text:
            await manager.add_transcript_entry(
                call_id=call_id,
                speaker="agent" if speaker == "assistant" else "user",
                text=text,
                confidence=confidence
            )

        return {"status": "received"}

    except Exception as e:
        logger.error(f"Error handling transcript update: {e}")
        return {"status": "error", "message": str(e)}
