"""
Tenant API Routes

Endpoints for:
- Tenant management
- Phone number configuration
- Voice configuration
- Business hours
"""

import logging
from datetime import time
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from ..models.schemas import (
    Tenant,
    TenantCreate,
    TenantUpdate,
    TenantStatus,
    PhoneNumber,
    PhoneNumberCreate,
    PhoneType,
    VoiceConfig,
    VoiceConfigCreate,
    BusinessHours,
    APIResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenants", tags=["Tenants"])


# =========================================================================
# REQUEST/RESPONSE MODELS
# =========================================================================


class UpdateBusinessHoursRequest(BaseModel):
    open_time: Optional[str] = None  # "09:00"
    close_time: Optional[str] = None  # "17:00"
    is_closed: bool = False
    after_hours_action: str = "voicemail"
    after_hours_message: Optional[str] = None


class OnboardTenantRequest(BaseModel):
    name: str
    slug: str
    industry: str
    timezone: str = "UTC"

    # Voice configuration
    agent_name: str
    greeting_script: str
    system_prompt: str
    voice_provider: str = "elevenlabs"
    voice_id: Optional[str] = None
    language: str = "en-US"

    # Phone numbers to provision
    phone_numbers: Optional[list[str]] = None


class OnboardTenantResponse(BaseModel):
    tenant: Tenant
    voice_config: VoiceConfig
    phone_numbers: list[PhoneNumber]


# =========================================================================
# TENANT ENDPOINTS
# =========================================================================


@router.post("/", response_model=Tenant)
async def create_tenant(
    request: Request,
    data: TenantCreate,
):
    """Create a new tenant"""
    tenant_service = request.app.state.tenant_service

    try:
        tenant = await tenant_service.create_tenant(data)
        return tenant
    except Exception as e:
        logger.error(f"Failed to create tenant: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/onboard", response_model=OnboardTenantResponse)
async def onboard_tenant(
    request: Request,
    data: OnboardTenantRequest,
):
    """
    Complete tenant onboarding in one call.

    Creates:
    - Tenant record
    - Default voice configuration
    - Provisions phone numbers (if provided)
    - Sets up default business hours
    """
    tenant_service = request.app.state.tenant_service

    try:
        # 1. Create tenant
        tenant = await tenant_service.create_tenant(
            TenantCreate(
                name=data.name,
                slug=data.slug,
                industry=data.industry,
                timezone=data.timezone,
            )
        )

        # 2. Create voice configuration
        voice_config = await tenant_service.create_voice_config(
            VoiceConfigCreate(
                tenant_id=tenant.id,
                agent_name=data.agent_name,
                greeting_script=data.greeting_script,
                system_prompt=data.system_prompt,
                voice_provider=data.voice_provider,
                voice_id=data.voice_id,
                language=data.language,
            )
        )

        # Set as default
        await tenant_service.set_default_voice_config(tenant.id, voice_config.id)

        # 3. Add phone numbers
        phone_numbers = []
        if data.phone_numbers:
            for number in data.phone_numbers:
                phone = await tenant_service.add_phone_number(
                    PhoneNumberCreate(
                        tenant_id=tenant.id,
                        phone_number=number,
                        phone_type=PhoneType.ALL,
                        display_name=f"{data.name} Main Line",
                    )
                )
                phone_numbers.append(phone)

        return OnboardTenantResponse(
            tenant=tenant,
            voice_config=voice_config,
            phone_numbers=phone_numbers,
        )

    except Exception as e:
        logger.error(f"Failed to onboard tenant: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{tenant_id}", response_model=Tenant)
async def get_tenant(
    request: Request,
    tenant_id: UUID,
):
    """Get tenant by ID"""
    tenant_service = request.app.state.tenant_service

    tenant = await tenant_service.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    return tenant


@router.get("/by-slug/{slug}", response_model=Tenant)
async def get_tenant_by_slug(
    request: Request,
    slug: str,
):
    """Get tenant by slug"""
    tenant_service = request.app.state.tenant_service

    tenant = await tenant_service.get_tenant_by_slug(slug)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    return tenant


@router.patch("/{tenant_id}", response_model=Tenant)
async def update_tenant(
    request: Request,
    tenant_id: UUID,
    data: TenantUpdate,
):
    """Update a tenant"""
    tenant_service = request.app.state.tenant_service

    tenant = await tenant_service.update_tenant(tenant_id, data)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    return tenant


@router.get("/", response_model=list[Tenant])
async def list_tenants(
    request: Request,
    status: Optional[TenantStatus] = None,
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
):
    """List all tenants"""
    tenant_service = request.app.state.tenant_service

    tenants = await tenant_service.list_tenants(
        status=status,
        limit=limit,
        offset=offset,
    )

    return tenants


# =========================================================================
# PHONE NUMBER ENDPOINTS
# =========================================================================


@router.post("/{tenant_id}/phone-numbers", response_model=PhoneNumber)
async def add_phone_number(
    request: Request,
    tenant_id: UUID,
    data: PhoneNumberCreate,
):
    """Add a phone number to a tenant"""
    tenant_service = request.app.state.tenant_service

    # Ensure tenant_id matches
    data.tenant_id = tenant_id

    try:
        phone = await tenant_service.add_phone_number(data)
        return phone
    except Exception as e:
        logger.error(f"Failed to add phone number: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{tenant_id}/phone-numbers", response_model=list[PhoneNumber])
async def list_phone_numbers(
    request: Request,
    tenant_id: UUID,
    phone_type: Optional[PhoneType] = None,
):
    """List phone numbers for a tenant"""
    tenant_service = request.app.state.tenant_service

    phones = await tenant_service.list_phone_numbers(
        tenant_id=tenant_id,
        phone_type=phone_type,
    )

    return phones


@router.delete("/phone-numbers/{phone_number_id}", response_model=APIResponse)
async def deactivate_phone_number(
    request: Request,
    phone_number_id: UUID,
):
    """Deactivate a phone number"""
    tenant_service = request.app.state.tenant_service

    success = await tenant_service.deactivate_phone_number(phone_number_id)

    return APIResponse(
        success=success,
        message="Phone number deactivated" if success else "Phone number not found",
    )


# =========================================================================
# VOICE CONFIG ENDPOINTS
# =========================================================================


@router.post("/{tenant_id}/voice-configs", response_model=VoiceConfig)
async def create_voice_config(
    request: Request,
    tenant_id: UUID,
    data: VoiceConfigCreate,
):
    """Create a voice configuration"""
    tenant_service = request.app.state.tenant_service

    data.tenant_id = tenant_id

    try:
        config = await tenant_service.create_voice_config(data)
        return config
    except Exception as e:
        logger.error(f"Failed to create voice config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{tenant_id}/voice-configs", response_model=list[VoiceConfig])
async def list_voice_configs(
    request: Request,
    tenant_id: UUID,
):
    """List voice configurations for a tenant"""
    tenant_service = request.app.state.tenant_service

    configs = await tenant_service.list_voice_configs(tenant_id)
    return configs


@router.get("/{tenant_id}/voice-configs/default", response_model=Optional[VoiceConfig])
async def get_default_voice_config(
    request: Request,
    tenant_id: UUID,
):
    """Get the default voice configuration"""
    tenant_service = request.app.state.tenant_service

    config = await tenant_service.get_default_voice_config(tenant_id)
    return config


@router.post("/{tenant_id}/voice-configs/{config_id}/set-default", response_model=APIResponse)
async def set_default_voice_config(
    request: Request,
    tenant_id: UUID,
    config_id: UUID,
):
    """Set a voice configuration as the default"""
    tenant_service = request.app.state.tenant_service

    success = await tenant_service.set_default_voice_config(tenant_id, config_id)

    return APIResponse(
        success=success,
        message="Default voice config updated" if success else "Config not found",
    )


# =========================================================================
# BUSINESS HOURS ENDPOINTS
# =========================================================================


@router.get("/{tenant_id}/business-hours", response_model=list[BusinessHours])
async def get_business_hours(
    request: Request,
    tenant_id: UUID,
):
    """Get business hours for a tenant"""
    tenant_service = request.app.state.tenant_service

    hours = await tenant_service.get_business_hours(tenant_id)
    return hours


@router.put("/{tenant_id}/business-hours/{day_of_week}", response_model=BusinessHours)
async def update_business_hours(
    request: Request,
    tenant_id: UUID,
    day_of_week: int,
    data: UpdateBusinessHoursRequest,
):
    """
    Update business hours for a specific day.

    day_of_week: 0=Sunday, 1=Monday, ..., 6=Saturday
    """
    tenant_service = request.app.state.tenant_service

    if day_of_week < 0 or day_of_week > 6:
        raise HTTPException(status_code=400, detail="day_of_week must be 0-6")

    # Parse times
    open_time = None
    close_time = None

    if data.open_time:
        parts = data.open_time.split(":")
        open_time = time(int(parts[0]), int(parts[1]))

    if data.close_time:
        parts = data.close_time.split(":")
        close_time = time(int(parts[0]), int(parts[1]))

    hours = await tenant_service.update_business_hours(
        tenant_id=tenant_id,
        day_of_week=day_of_week,
        open_time=open_time,
        close_time=close_time,
        is_closed=data.is_closed,
        after_hours_action=data.after_hours_action,
        after_hours_message=data.after_hours_message,
    )

    return hours


@router.get("/{tenant_id}/is-open", response_model=dict)
async def check_if_open(
    request: Request,
    tenant_id: UUID,
):
    """Check if tenant is currently within business hours"""
    tenant_service = request.app.state.tenant_service

    is_open = await tenant_service.is_within_business_hours(tenant_id)

    return {"is_open": is_open}
