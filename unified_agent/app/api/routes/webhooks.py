"""
Webhook Routes
Handle callbacks from Twilio and Ultravox
"""

from fastapi import APIRouter, HTTPException, Request, Response, Depends, Query
from fastapi.responses import PlainTextResponse
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.db import get_db, Call
from app.services import UltravoxService

logger = get_logger(__name__)
router = APIRouter()


# ============================================
# TWILIO WEBHOOKS
# ============================================

@router.post("/twilio/voice")
async def twilio_voice_webhook(
    request: Request,
    call_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db)
):
    """
    Handle incoming Twilio voice webhooks
    Returns TwiML to connect to Ultravox
    """
    try:
        form_data = await request.form()
        logger.info(f"Twilio voice webhook: {dict(form_data)}")

        # Get Ultravox call info
        if call_id:
            call = db.query(Call).filter(Call.id == call_id).first()
            if call and call.ultravox_call_id:
                # Get Ultravox join URL
                ultravox = UltravoxService()
                call_info = await ultravox.get_call_status(call.ultravox_call_id)
                join_url = call_info.get("joinUrl", "")

                # Generate TwiML to connect to Ultravox
                twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{join_url}" />
    </Connect>
</Response>"""
                return PlainTextResponse(content=twiml, media_type="application/xml")

        # Default response
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Sorry, we couldn't connect your call. Please try again later.</Say>
    <Hangup/>
</Response>"""
        return PlainTextResponse(content=twiml, media_type="application/xml")

    except Exception as e:
        logger.error(f"Twilio voice webhook error: {e}", exc_info=True)
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>An error occurred. Please try again later.</Say>
    <Hangup/>
</Response>"""
        return PlainTextResponse(content=twiml, media_type="application/xml")


@router.post("/twilio/status")
async def twilio_status_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle Twilio call status updates"""
    try:
        form_data = await request.form()
        logger.info(f"Twilio status webhook: {dict(form_data)}")

        call_sid = form_data.get("CallSid")
        call_status = form_data.get("CallStatus")
        duration = form_data.get("CallDuration")

        if call_sid:
            call = db.query(Call).filter(Call.twilio_call_sid == call_sid).first()

            if call:
                # Update call status
                status_map = {
                    "initiated": "initiating",
                    "ringing": "ringing",
                    "in-progress": "in_progress",
                    "completed": "completed",
                    "busy": "busy",
                    "no-answer": "no_answer",
                    "failed": "failed",
                    "canceled": "cancelled"
                }

                call.status = status_map.get(call_status, call_status)

                if call_status == "in-progress" and not call.started_at:
                    call.started_at = datetime.utcnow()

                if call_status in ["completed", "busy", "no-answer", "failed", "canceled"]:
                    call.ended_at = datetime.utcnow()
                    if duration:
                        call.duration_seconds = int(duration)

                db.commit()
                logger.info(f"Updated call {call.id} status to {call.status}")

        return {"status": "received"}

    except Exception as e:
        logger.error(f"Twilio status webhook error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.get("/twiml")
async def get_twiml(
    call_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """Get TwiML for connecting to Ultravox"""
    try:
        call = db.query(Call).filter(Call.id == call_id).first()

        if not call or not call.ultravox_call_id:
            twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Call not found. Goodbye.</Say>
    <Hangup/>
</Response>"""
            return PlainTextResponse(content=twiml, media_type="application/xml")

        # Get Ultravox join URL
        ultravox = UltravoxService()
        call_info = await ultravox.get_call_status(call.ultravox_call_id)
        join_url = call_info.get("joinUrl", "")

        if not join_url:
            twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Unable to connect. Please try again.</Say>
    <Hangup/>
</Response>"""
            return PlainTextResponse(content=twiml, media_type="application/xml")

        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{join_url}" />
    </Connect>
</Response>"""
        return PlainTextResponse(content=twiml, media_type="application/xml")

    except Exception as e:
        logger.error(f"TwiML generation error: {e}", exc_info=True)
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>An error occurred.</Say>
    <Hangup/>
</Response>"""
        return PlainTextResponse(content=twiml, media_type="application/xml")


# ============================================
# ULTRAVOX WEBHOOKS
# ============================================

@router.post("/ultravox/status")
async def ultravox_status_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle Ultravox call status updates"""
    try:
        data = await request.json()
        logger.info(f"Ultravox status webhook: {data}")

        ultravox_call_id = data.get("callId")
        status = data.get("status")
        end_reason = data.get("endReason")

        if ultravox_call_id:
            call = db.query(Call).filter(
                Call.ultravox_call_id == ultravox_call_id
            ).first()

            if call:
                # Map Ultravox status
                if status == "ended":
                    call.status = "completed"
                    call.ended_at = datetime.utcnow()
                    if call.started_at:
                        call.duration_seconds = int(
                            (call.ended_at - call.started_at).total_seconds()
                        )
                elif status == "active":
                    call.status = "in_progress"
                    if not call.started_at:
                        call.started_at = datetime.utcnow()

                # Store transcript if available
                transcript = data.get("transcript")
                if transcript:
                    call.transcript = transcript

                db.commit()
                logger.info(f"Updated call {call.id} from Ultravox webhook")

        return {"status": "received"}

    except Exception as e:
        logger.error(f"Ultravox webhook error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.post("/ultravox/transcript")
async def ultravox_transcript_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle Ultravox transcript updates"""
    try:
        data = await request.json()
        logger.debug(f"Ultravox transcript webhook: {data}")

        ultravox_call_id = data.get("callId")
        transcript = data.get("transcript")

        if ultravox_call_id and transcript:
            call = db.query(Call).filter(
                Call.ultravox_call_id == ultravox_call_id
            ).first()

            if call:
                call.transcript = transcript
                db.commit()

        return {"status": "received"}

    except Exception as e:
        logger.error(f"Ultravox transcript webhook error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
