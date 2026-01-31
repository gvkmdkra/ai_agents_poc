"""
Call API Routes

Endpoints for:
- Initiating outbound calls
- Managing active calls
- Call history and analytics
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from ..models.schemas import (
    Call,
    CallDirection,
    CallStatus,
    APIResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calls", tags=["Calls"])


# =========================================================================
# REQUEST/RESPONSE MODELS
# =========================================================================


class InitiateCallRequest(BaseModel):
    tenant_id: UUID
    to_number: str
    from_number: str
    lead_id: Optional[UUID] = None
    voice_config_id: Optional[UUID] = None
    campaign_id: Optional[str] = None


class InitiateCallResponse(BaseModel):
    call_id: UUID
    twilio_call_sid: str
    status: str


class EscalateCallRequest(BaseModel):
    reason: str
    transfer_to: Optional[str] = None


class CallStatsResponse(BaseModel):
    total_calls: int
    inbound_calls: int
    outbound_calls: int
    completed_calls: int
    escalated_calls: int
    avg_duration: Optional[float]
    avg_turns: Optional[float]
    avg_sentiment: Optional[float]
    total_cost: Optional[float]


# =========================================================================
# ENDPOINTS
# =========================================================================


@router.post("/initiate", response_model=InitiateCallResponse)
async def initiate_call(
    request: Request,
    data: InitiateCallRequest,
):
    """
    Initiate an outbound AI voice call.

    This starts an outbound call that will be handled by the AI voice agent.
    The call will ring the recipient and connect them to the AI when answered.
    """
    call_service = request.app.state.call_service

    try:
        call = await call_service.initiate_outbound_call(
            tenant_id=data.tenant_id,
            to_number=data.to_number,
            from_number=data.from_number,
            lead_id=data.lead_id,
            voice_config_id=data.voice_config_id,
        )

        return InitiateCallResponse(
            call_id=call.id,
            twilio_call_sid=call.twilio_call_sid,
            status=call.status.value,
        )

    except Exception as e:
        logger.error(f"Failed to initiate call: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{call_id}", response_model=Call)
async def get_call(
    request: Request,
    call_id: UUID,
):
    """Get call details by ID"""
    call_service = request.app.state.call_service

    call = await call_service.get_call(call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    return call


@router.get("/", response_model=list[Call])
async def list_calls(
    request: Request,
    tenant_id: UUID,
    lead_id: Optional[UUID] = None,
    status: Optional[CallStatus] = None,
    direction: Optional[CallDirection] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
):
    """List calls with filters"""
    call_service = request.app.state.call_service

    calls = await call_service.list_calls(
        tenant_id=tenant_id,
        lead_id=lead_id,
        status=status,
        direction=direction,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )

    return calls


@router.get("/active", response_model=list[Call])
async def get_active_calls(
    request: Request,
    tenant_id: Optional[UUID] = None,
):
    """Get all currently active calls"""
    call_service = request.app.state.call_service

    calls = await call_service.get_active_calls(tenant_id)
    return calls


@router.post("/{call_id}/end", response_model=Call)
async def end_call(
    request: Request,
    call_id: UUID,
    outcome: Optional[str] = None,
    follow_up_required: bool = False,
):
    """End an active call"""
    call_service = request.app.state.call_service

    call = await call_service.end_call(
        call_id=call_id,
        outcome=outcome,
        follow_up_required=follow_up_required,
    )

    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    return call


@router.post("/{call_id}/escalate", response_model=APIResponse)
async def escalate_call(
    request: Request,
    call_id: UUID,
    data: EscalateCallRequest,
):
    """Escalate a call to a human agent"""
    call_service = request.app.state.call_service

    success = await call_service.escalate_to_human(
        call_id=call_id,
        reason=data.reason,
        transfer_to=data.transfer_to,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Call not found or already ended")

    return APIResponse(
        success=True,
        message="Call escalated to human agent",
    )


@router.get("/{call_id}/transcript")
async def get_call_transcript(
    request: Request,
    call_id: UUID,
    format: str = Query("json", regex="^(json|text)$"),
):
    """Get call transcript"""
    call_service = request.app.state.call_service

    if format == "text":
        transcript = await call_service.get_transcript_text(call_id)
        return {"transcript": transcript}
    else:
        transcript = await call_service.get_transcript(call_id)
        return {"transcript": transcript}


@router.post("/{call_id}/analyze", response_model=APIResponse)
async def analyze_call(
    request: Request,
    call_id: UUID,
):
    """Analyze a completed call (sentiment, summary, etc.)"""
    call_service = request.app.state.call_service

    try:
        analysis = await call_service.analyze_call(call_id)
        return APIResponse(
            success=True,
            data=analysis,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=CallStatsResponse)
async def get_call_stats(
    request: Request,
    tenant_id: UUID,
    start_date: datetime,
    end_date: datetime,
):
    """Get call statistics for a date range"""
    call_service = request.app.state.call_service

    stats = await call_service.get_call_stats(
        tenant_id=tenant_id,
        start_date=start_date,
        end_date=end_date,
    )

    return CallStatsResponse(**stats)
