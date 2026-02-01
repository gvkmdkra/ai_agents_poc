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


# Static routes MUST come before dynamic routes with path parameters

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


@router.get("/dashboard/analytics")
async def get_dashboard_analytics(
    manager: CallManager = Depends(get_manager)
):
    """
    Get comprehensive dashboard analytics including:
    - Call statistics
    - Recent conversations summary
    - Top action items
    - Sentiment distribution
    """
    # Get all call history
    all_calls = await manager.get_call_history(limit=100)

    # Calculate statistics
    total_calls = len(all_calls)
    completed_calls = sum(1 for c in all_calls if c.status == CallStatus.COMPLETED)
    failed_calls = sum(1 for c in all_calls if c.status == CallStatus.FAILED)

    total_duration = sum(c.duration_seconds or 0 for c in all_calls)
    avg_duration = total_duration / completed_calls if completed_calls > 0 else 0

    # Get recent calls with summaries
    recent_conversations = []
    for call in all_calls[:10]:
        conv = {
            "call_id": call.call_id,
            "phone_number": call.phone_number,
            "status": call.status.value if call.status else "unknown",
            "duration_seconds": call.duration_seconds,
            "created_at": call.created_at.isoformat() if call.created_at else None,
            "transcript_length": len(call.transcript),
            "has_summary": call.summary is not None
        }
        if call.summary:
            conv["summary"] = call.summary.summary
            conv["key_points"] = call.summary.key_points
            conv["action_items"] = call.summary.action_items
            conv["sentiment"] = call.summary.sentiment
        recent_conversations.append(conv)

    # Aggregate action items from all calls
    all_action_items = []
    sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}

    for call in all_calls:
        if call.summary:
            if call.summary.action_items:
                for item in call.summary.action_items:
                    all_action_items.append({
                        "item": item,
                        "call_id": call.call_id,
                        "phone_number": call.phone_number,
                        "created_at": call.created_at.isoformat() if call.created_at else None
                    })
            if call.summary.sentiment:
                sentiment = call.summary.sentiment.lower()
                if sentiment in sentiment_counts:
                    sentiment_counts[sentiment] += 1

    return {
        "statistics": {
            "total_calls": total_calls,
            "completed_calls": completed_calls,
            "failed_calls": failed_calls,
            "success_rate": (completed_calls / total_calls * 100) if total_calls > 0 else 0,
            "total_duration_seconds": total_duration,
            "average_duration_seconds": avg_duration,
            "active_calls": len(manager.active_calls)
        },
        "recent_conversations": recent_conversations,
        "action_items": all_action_items[:20],  # Top 20 action items
        "sentiment_distribution": sentiment_counts
    }


# Dynamic routes with path parameters MUST come after static routes

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


@router.post("/{call_id}/analyze")
async def analyze_call(
    call_id: str,
    manager: CallManager = Depends(get_manager)
):
    """
    Generate AI analysis for a completed call including summary, key topics,
    sentiment, and action items.

    - **call_id**: Unique identifier of the call
    """
    record = await manager.get_call_status(call_id)

    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"Call {call_id} not found"
        )

    if record.status not in [CallStatus.COMPLETED]:
        raise HTTPException(
            status_code=400,
            detail="Call must be completed to generate analysis"
        )

    # Generate analysis using OpenAI
    transcript_data = [
        {"speaker": t.speaker, "text": t.text}
        for t in record.transcript
    ]

    if not transcript_data:
        return {
            "call_id": call_id,
            "analysis": {
                "summary": "No transcript available for this call.",
                "key_topics": [],
                "sentiment": "neutral",
                "action_items": [],
                "conversation_highlights": []
            }
        }

    result = await manager.openai.generate_call_analysis(
        transcript=transcript_data,
        call_metadata={
            "phone_number": record.phone_number,
            "duration_seconds": record.duration_seconds,
            "direction": record.direction.value if record.direction else "unknown"
        }
    )

    return {
        "call_id": call_id,
        "analysis": result.get("analysis", {}),
        "success": result.get("success", False)
    }
