"""
Health check and status endpoints
"""

from datetime import datetime
from fastapi import APIRouter

from app.core.config import settings
from app.core.logging import get_logger
from app.services.call_manager import get_call_manager

logger = get_logger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """
    Basic health check endpoint
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.environment
    }


@router.get("/ready")
async def readiness_check():
    """
    Readiness check - verifies the service is ready to handle requests
    """
    manager = get_call_manager()

    # Check if essential services are configured
    checks = {
        "openai": bool(settings.openai_api_key),
        "ultravox": bool(settings.ultravox_api_key),
        "twilio": bool(settings.twilio_account_sid and settings.twilio_auth_token)
    }

    all_ready = all(checks.values())

    return {
        "status": "ready" if all_ready else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks,
        "active_calls": len(manager.active_calls)
    }


@router.get("/info")
async def service_info():
    """
    Get service information and configuration (non-sensitive)
    """
    return {
        "service": "Calling Agent",
        "version": "1.0.0",
        "environment": settings.environment,
        "api_base_url": settings.api_base_url,
        "twilio_phone": settings.twilio_phone_number,
        "ultravox_voice": settings.ultravox_default_voice,
        "openai_model": settings.openai_model
    }


@router.get("/stats")
async def get_statistics():
    """
    Get service statistics
    """
    manager = get_call_manager()

    # Calculate stats from history
    total_calls = len(manager.call_history)
    completed_calls = sum(1 for c in manager.call_history if c.status == "completed")
    failed_calls = sum(1 for c in manager.call_history if c.status == "failed")

    total_duration = sum(
        c.duration_seconds or 0
        for c in manager.call_history
        if c.duration_seconds
    )

    return {
        "active_calls": len(manager.active_calls),
        "total_calls_processed": total_calls,
        "completed_calls": completed_calls,
        "failed_calls": failed_calls,
        "total_duration_seconds": total_duration,
        "average_duration_seconds": total_duration / completed_calls if completed_calls > 0 else 0
    }
