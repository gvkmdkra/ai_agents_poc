"""
Voice Calling API Routes
Outbound, inbound, and browser-based voice calls
"""

from fastapi import APIRouter, HTTPException, Depends, Header, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.core.jwt_auth import get_optional_userid
from app.db import get_db, Tenant, Call, generate_uuid
from app.services import VoiceCallingService, TenantService, APIKeyService
from app.api.middleware.auth import require_api_key

logger = get_logger(__name__)
router = APIRouter()


# ============================================
# REQUEST/RESPONSE MODELS
# ============================================

class InitiateCallRequest(BaseModel):
    """Request to initiate a voice call"""
    phone_number: Optional[str] = Field(default=None, description="Phone number for outbound call")
    client_name: Optional[str] = Field(default=None, description="Name of person being called")
    custom_prompt: Optional[str] = Field(default=None, description="Custom system prompt")
    call_type: str = Field(default="browser", description="Call type: browser, outbound")


class CallResponse(BaseModel):
    """Response for call operations"""
    success: bool
    call_id: str
    ultravox_call_id: Optional[str] = None
    twilio_call_sid: Optional[str] = None
    join_url: Optional[str] = None
    status: str
    message: Optional[str] = None


class CallStatusResponse(BaseModel):
    """Response for call status"""
    call_id: str
    status: str
    direction: str
    phone_number: Optional[str] = None
    client_name: Optional[str] = None
    started_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    transcript: Optional[str] = None
    summary: Optional[str] = None


class CallListResponse(BaseModel):
    """Response for listing calls"""
    calls: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int


# ============================================
# ENDPOINTS
# ============================================

@router.post("/initiate", response_model=CallResponse)
async def initiate_call(
    request: InitiateCallRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_api_key),
    userid: Optional[int] = Depends(get_optional_userid)
):
    """
    Initiate a voice call

    - For browser calls: Returns a join URL for WebRTC connection
    - For outbound calls: Dials the phone number via Twilio
    """
    try:
        if not tenant.enable_voice_calling:
            raise HTTPException(status_code=403, detail="Voice calling not enabled for this tenant")

        if not settings.enable_voice_calling:
            raise HTTPException(status_code=503, detail="Voice calling is disabled")

        # Create call record
        call = Call(
            tenant_id=tenant.id,
            direction=request.call_type,
            status="initiating",
            phone_number=request.phone_number,
            client_name=request.client_name,
            user_id=userid
        )
        db.add(call)
        db.commit()
        db.refresh(call)

        # Initialize voice service
        voice_service = VoiceCallingService(tenant)

        if request.call_type == "browser":
            # Browser-based WebRTC call
            result = await voice_service.create_browser_call(
                client_name=request.client_name,
                userid=userid,
                custom_prompt=request.custom_prompt
            )

            # Update call record
            call.ultravox_call_id = result["call_id"]
            call.status = "initiated"
            db.commit()

            return CallResponse(
                success=True,
                call_id=call.id,
                ultravox_call_id=result["call_id"],
                join_url=result["join_url"],
                status="initiated",
                message="Browser call initiated. Use join_url for WebRTC connection."
            )

        elif request.call_type == "outbound":
            # Outbound phone call via Twilio
            if not request.phone_number:
                raise HTTPException(status_code=400, detail="Phone number required for outbound calls")

            result = await voice_service.create_phone_call(
                phone_number=request.phone_number,
                client_name=request.client_name,
                userid=userid,
                custom_prompt=request.custom_prompt
            )

            # Update call record
            call.ultravox_call_id = result["ultravox_call_id"]
            call.twilio_call_sid = result["twilio_call_sid"]
            call.status = "dialing"
            db.commit()

            return CallResponse(
                success=True,
                call_id=call.id,
                ultravox_call_id=result["ultravox_call_id"],
                twilio_call_sid=result["twilio_call_sid"],
                status="dialing",
                message=f"Calling {request.phone_number}..."
            )

        else:
            raise HTTPException(status_code=400, detail=f"Invalid call type: {request.call_type}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating call: {e}", exc_info=True)

        # Update call status on failure
        if 'call' in locals():
            call.status = "failed"
            call.error_message = str(e)
            db.commit()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate call: {str(e)}"
        )


@router.get("/{call_id}", response_model=CallStatusResponse)
async def get_call_status(
    call_id: str,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_api_key)
):
    """Get call status and details"""
    try:
        call = db.query(Call).filter(
            Call.id == call_id,
            Call.tenant_id == tenant.id
        ).first()

        if not call:
            raise HTTPException(status_code=404, detail="Call not found")

        return CallStatusResponse(
            call_id=call.id,
            status=call.status,
            direction=call.direction,
            phone_number=call.phone_number,
            client_name=call.client_name,
            started_at=call.started_at,
            duration_seconds=call.duration_seconds,
            transcript=call.transcript,
            summary=call.summary
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting call status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get call status: {str(e)}"
        )


@router.get("/", response_model=CallListResponse)
async def list_calls(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = None,
    direction: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_api_key)
):
    """List calls for the tenant"""
    try:
        query = db.query(Call).filter(Call.tenant_id == tenant.id)

        if status:
            query = query.filter(Call.status == status)

        if direction:
            query = query.filter(Call.direction == direction)

        total = query.count()
        calls = query.order_by(Call.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()

        return CallListResponse(
            calls=[
                {
                    "call_id": c.id,
                    "status": c.status,
                    "direction": c.direction,
                    "phone_number": c.phone_number,
                    "client_name": c.client_name,
                    "duration_seconds": c.duration_seconds,
                    "created_at": c.created_at.isoformat(),
                    "started_at": c.started_at.isoformat() if c.started_at else None,
                    "ended_at": c.ended_at.isoformat() if c.ended_at else None
                }
                for c in calls
            ],
            total=total,
            page=page,
            page_size=page_size
        )

    except Exception as e:
        logger.error(f"Error listing calls: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list calls: {str(e)}"
        )


@router.post("/{call_id}/end")
async def end_call(
    call_id: str,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_api_key)
):
    """End an active call"""
    try:
        call = db.query(Call).filter(
            Call.id == call_id,
            Call.tenant_id == tenant.id
        ).first()

        if not call:
            raise HTTPException(status_code=404, detail="Call not found")

        if call.status in ["completed", "failed", "cancelled"]:
            return {"success": True, "message": "Call already ended"}

        # End the call via Ultravox
        if call.ultravox_call_id:
            from app.services import UltravoxService
            ultravox = UltravoxService()
            await ultravox.end_call(call.ultravox_call_id)

        # Update call record
        call.status = "cancelled"
        call.ended_at = datetime.utcnow()
        if call.started_at:
            call.duration_seconds = int((call.ended_at - call.started_at).total_seconds())
        db.commit()

        return {"success": True, "message": "Call ended"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ending call: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to end call: {str(e)}"
        )


@router.get("/dashboard/analytics")
async def get_call_analytics(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(require_api_key)
):
    """Get call analytics for dashboard"""
    try:
        from datetime import timedelta
        from sqlalchemy import func

        start_date = datetime.utcnow() - timedelta(days=days)

        # Get call statistics
        stats = db.query(
            func.count(Call.id).label("total_calls"),
            func.sum(Call.duration_seconds).label("total_duration"),
            func.avg(Call.duration_seconds).label("avg_duration")
        ).filter(
            Call.tenant_id == tenant.id,
            Call.created_at >= start_date
        ).first()

        # Get calls by status
        status_counts = db.query(
            Call.status,
            func.count(Call.id).label("count")
        ).filter(
            Call.tenant_id == tenant.id,
            Call.created_at >= start_date
        ).group_by(Call.status).all()

        # Get calls by direction
        direction_counts = db.query(
            Call.direction,
            func.count(Call.id).label("count")
        ).filter(
            Call.tenant_id == tenant.id,
            Call.created_at >= start_date
        ).group_by(Call.direction).all()

        return {
            "period_days": days,
            "total_calls": stats.total_calls or 0,
            "total_duration_seconds": stats.total_duration or 0,
            "average_duration_seconds": round(stats.avg_duration or 0, 2),
            "by_status": {s.status: s.count for s in status_counts},
            "by_direction": {d.direction: d.count for d in direction_counts}
        }

    except Exception as e:
        logger.error(f"Error getting analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get analytics: {str(e)}"
        )
