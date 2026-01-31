"""
Lead API Routes

Endpoints for:
- Lead CRUD operations
- Lead qualification
- CRM synchronization
- Follow-up management
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from ..models.schemas import (
    Lead,
    LeadCreate,
    LeadUpdate,
    LeadTemperature,
    LeadStatus,
    APIResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/leads", tags=["Leads"])


# =========================================================================
# REQUEST/RESPONSE MODELS
# =========================================================================


class QualifyLeadRequest(BaseModel):
    conversation_transcript: str
    industry: str = "general"


class QualifyLeadResponse(BaseModel):
    lead_id: UUID
    score: float
    temperature: str
    budget_mentioned: bool
    is_decision_maker: bool
    timeline: Optional[str]
    recommendations: list[str]
    summary: str


class SyncToOdooResponse(BaseModel):
    success: bool
    odoo_lead_id: Optional[int]
    message: Optional[str]


# =========================================================================
# ENDPOINTS
# =========================================================================


@router.post("/", response_model=Lead)
async def create_lead(
    request: Request,
    data: LeadCreate,
):
    """Create a new lead"""
    lead_service = request.app.state.lead_service

    try:
        lead = await lead_service.create_lead(data)
        return lead
    except Exception as e:
        logger.error(f"Failed to create lead: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{lead_id}", response_model=Lead)
async def get_lead(
    request: Request,
    lead_id: UUID,
):
    """Get lead by ID"""
    lead_service = request.app.state.lead_service

    lead = await lead_service.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    return lead


@router.patch("/{lead_id}", response_model=Lead)
async def update_lead(
    request: Request,
    lead_id: UUID,
    data: LeadUpdate,
):
    """Update a lead"""
    lead_service = request.app.state.lead_service

    lead = await lead_service.update_lead(lead_id, data)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    return lead


@router.get("/", response_model=list[Lead])
async def list_leads(
    request: Request,
    tenant_id: UUID,
    status: Optional[LeadStatus] = None,
    temperature: Optional[LeadTemperature] = None,
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
):
    """List leads with filters"""
    lead_service = request.app.state.lead_service

    leads = await lead_service.list_leads(
        tenant_id=tenant_id,
        status=status,
        temperature=temperature,
        limit=limit,
        offset=offset,
    )

    return leads


@router.get("/by-phone", response_model=Optional[Lead])
async def get_lead_by_phone(
    request: Request,
    tenant_id: UUID,
    phone: str,
):
    """Find a lead by phone number"""
    lead_service = request.app.state.lead_service

    lead = await lead_service.get_lead_by_phone(tenant_id, phone)
    return lead


@router.post("/{lead_id}/qualify", response_model=QualifyLeadResponse)
async def qualify_lead(
    request: Request,
    lead_id: UUID,
    data: QualifyLeadRequest,
):
    """
    Qualify a lead based on conversation transcript.

    Uses AI to analyze the conversation and calculate a lead score
    based on BANT criteria.
    """
    lead_service = request.app.state.lead_service

    try:
        result = await lead_service.qualify_lead(
            lead_id=lead_id,
            conversation_transcript=data.conversation_transcript,
            industry=data.industry,
        )

        return QualifyLeadResponse(
            lead_id=lead_id,
            score=result.score,
            temperature=result.temperature,
            budget_mentioned=result.budget_mentioned,
            is_decision_maker=result.is_decision_maker,
            timeline=result.timeline,
            recommendations=result.recommendations,
            summary=result.summary,
        )

    except Exception as e:
        logger.error(f"Failed to qualify lead: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{lead_id}/sync-odoo", response_model=SyncToOdooResponse)
async def sync_lead_to_odoo(
    request: Request,
    lead_id: UUID,
):
    """Sync lead to Odoo CRM"""
    lead_service = request.app.state.lead_service

    try:
        odoo_id = await lead_service.sync_lead_to_odoo(lead_id)
        return SyncToOdooResponse(
            success=True,
            odoo_lead_id=odoo_id,
            message="Lead synced successfully",
        )
    except Exception as e:
        logger.error(f"Failed to sync lead to Odoo: {e}")
        return SyncToOdooResponse(
            success=False,
            odoo_lead_id=None,
            message=str(e),
        )


@router.post("/{lead_id}/follow-up-sequence", response_model=APIResponse)
async def create_follow_up_sequence(
    request: Request,
    lead_id: UUID,
    sequence_type: str = "default",
):
    """Create automated follow-up sequence for a lead"""
    lead_service = request.app.state.lead_service

    try:
        tasks = await lead_service.create_follow_up_sequence(
            lead_id=lead_id,
            sequence_type=sequence_type,
        )

        return APIResponse(
            success=True,
            message=f"Created {len(tasks)} follow-up tasks",
            data={"tasks": tasks},
        )

    except Exception as e:
        logger.error(f"Failed to create follow-up sequence: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/follow-ups/pending")
async def get_pending_follow_ups(
    request: Request,
    tenant_id: Optional[UUID] = None,
    limit: int = Query(100, le=500),
):
    """Get pending follow-up tasks that are due"""
    lead_service = request.app.state.lead_service

    tasks = await lead_service.get_pending_follow_ups(
        tenant_id=tenant_id,
        limit=limit,
    )

    return {"tasks": tasks, "count": len(tasks)}
