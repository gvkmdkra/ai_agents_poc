"""
Call management API routes
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Depends

from app.core.logging import get_logger
from app.models.call import (
    CallRequest,
    CallResponse,
    CallRecord,
    CallStatus
)
from app.services.call_manager import get_call_manager, CallManager

logger = get_logger(__name__)

router = APIRouter(prefix="/calls", tags=["calls"])


def get_manager() -> CallManager:
    """Dependency to get call manager"""
    return get_call_manager()


@router.post("/initiate", response_model=CallResponse)
async def initiate_call(
    request: CallRequest,
    manager: CallManager = Depends(get_manager)
):
    """
    Initiate an outbound call

    - **phone_number**: Phone number to call (E.164 format, e.g., +14155551234)
    - **system_prompt**: Optional custom system prompt for the AI agent
    - **greeting_message**: Optional initial greeting message
    - **metadata**: Optional additional metadata
    - **max_duration_seconds**: Maximum call duration (default: 600)
    """
    logger.info(f"Received call request to {request.phone_number}")

    # Validate phone number format
    if not request.phone_number.startswith("+"):
        raise HTTPException(
            status_code=400,
            detail="Phone number must be in E.164 format (e.g., +14155551234)"
        )

    response = await manager.initiate_call(request)
    return response


@router.get("/{call_id}", response_model=CallRecord)
async def get_call(
    call_id: str,
    manager: CallManager = Depends(get_manager)
):
    """
    Get details of a specific call

    - **call_id**: Unique identifier of the call
    """
    record = await manager.get_call_status(call_id)

    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"Call {call_id} not found"
        )

    return record


@router.post("/{call_id}/end")
async def end_call(
    call_id: str,
    manager: CallManager = Depends(get_manager)
):
    """
    End an active call

    - **call_id**: Unique identifier of the call
    """
    result = await manager.end_call(call_id)

    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Failed to end call")
        )

    return result


@router.get("/", response_model=List[CallRecord])
async def list_calls(
    limit: int = Query(50, ge=1, le=100, description="Maximum number of calls to return"),
    status: Optional[CallStatus] = Query(None, description="Filter by call status"),
    manager: CallManager = Depends(get_manager)
):
    """
    List call history

    - **limit**: Maximum number of calls to return (1-100)
    - **status**: Optional status filter
    """
    records = await manager.get_call_history(limit=limit, status_filter=status)
    return records


@router.get("/{call_id}/transcript")
async def get_transcript(
    call_id: str,
    manager: CallManager = Depends(get_manager)
):
    """
    Get the transcript for a call

    - **call_id**: Unique identifier of the call
    """
    record = await manager.get_call_status(call_id)

    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"Call {call_id} not found"
        )

    return {
        "call_id": call_id,
        "transcript": [
            {
                "timestamp": t.timestamp.isoformat(),
                "speaker": t.speaker,
                "text": t.text,
                "confidence": t.confidence
            }
            for t in record.transcript
        ]
    }


@router.get("/{call_id}/summary")
async def get_summary(
    call_id: str,
    manager: CallManager = Depends(get_manager)
):
    """
    Get the summary for a completed call

    - **call_id**: Unique identifier of the call
    """
    record = await manager.get_call_status(call_id)

    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"Call {call_id} not found"
        )

    if not record.summary:
        raise HTTPException(
            status_code=404,
            detail="Summary not available for this call"
        )

    return record.summary


@router.get("/active/list")
async def list_active_calls(
    manager: CallManager = Depends(get_manager)
):
    """
    List all currently active calls
    """
    return {
        "active_calls": list(manager.active_calls.values()),
        "count": len(manager.active_calls)
    }
