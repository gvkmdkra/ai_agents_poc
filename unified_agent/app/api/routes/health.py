"""
Health Check Routes
System health and readiness endpoints
"""

from fastapi import APIRouter, Depends
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.db import get_db

logger = get_logger(__name__)
router = APIRouter()

# Track startup time
_startup_time = datetime.utcnow()


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint
    Returns immediately to indicate the service is running
    """
    return {
        "status": "healthy",
        "service": "unified-ai-agent",
        "version": settings.app_version,
        "environment": settings.environment,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/health/ready")
async def readiness_check(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Readiness check - verifies all dependencies are available
    """
    checks = {
        "database": False,
        "openai": False,
        "pinecone": False,
        "ultravox": False,
        "twilio": False
    }

    errors = []

    # Check database
    try:
        db.execute("SELECT 1")
        checks["database"] = True
    except Exception as e:
        errors.append(f"Database: {str(e)}")

    # Check OpenAI
    if settings.openai_api_key:
        checks["openai"] = True
    else:
        errors.append("OpenAI: API key not configured")

    # Check Pinecone
    if settings.pinecone_api_key:
        checks["pinecone"] = True
    else:
        errors.append("Pinecone: API key not configured")

    # Check Ultravox
    if settings.ultravox_api_key:
        checks["ultravox"] = True
    else:
        errors.append("Ultravox: API key not configured")

    # Check Twilio
    if settings.twilio_account_sid and settings.twilio_auth_token:
        checks["twilio"] = True
    else:
        errors.append("Twilio: Credentials not configured")

    # Determine overall status
    required_checks = ["database", "openai"]
    all_required_passed = all(checks.get(c, False) for c in required_checks)

    return {
        "status": "ready" if all_required_passed else "not_ready",
        "checks": checks,
        "errors": errors if errors else None,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/health/live")
async def liveness_check() -> Dict[str, Any]:
    """
    Liveness check - indicates the process is running
    Used by Kubernetes liveness probes
    """
    uptime = datetime.utcnow() - _startup_time

    return {
        "status": "alive",
        "uptime_seconds": int(uptime.total_seconds()),
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/health/detailed")
async def detailed_health_check(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Detailed health check with system information
    """
    import psutil
    import sys

    # Get system metrics
    try:
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=0.1)
        disk = psutil.disk_usage('/')

        system_metrics = {
            "memory_percent": memory.percent,
            "memory_available_mb": memory.available // (1024 * 1024),
            "cpu_percent": cpu_percent,
            "disk_percent": disk.percent
        }
    except Exception:
        system_metrics = None

    # Get database stats
    try:
        from sqlalchemy import text
        result = db.execute(text("SELECT COUNT(*) FROM tenants")).fetchone()
        tenant_count = result[0] if result else 0

        result = db.execute(text("SELECT COUNT(*) FROM calls")).fetchone()
        call_count = result[0] if result else 0

        result = db.execute(text("SELECT COUNT(*) FROM conversations")).fetchone()
        conversation_count = result[0] if result else 0

        db_stats = {
            "tenants": tenant_count,
            "calls": call_count,
            "conversations": conversation_count
        }
    except Exception:
        db_stats = None

    uptime = datetime.utcnow() - _startup_time

    return {
        "status": "healthy",
        "service": {
            "name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "python_version": sys.version
        },
        "uptime": {
            "seconds": int(uptime.total_seconds()),
            "human": str(uptime)
        },
        "system": system_metrics,
        "database": db_stats,
        "features": {
            "voice_calling": settings.enable_voice_calling,
            "chat": settings.enable_chat,
            "text_to_sql": settings.enable_text_to_sql,
            "rag": settings.enable_rag,
            "lead_capture": settings.enable_lead_capture,
            "analytics": settings.enable_analytics
        },
        "timestamp": datetime.utcnow().isoformat()
    }
