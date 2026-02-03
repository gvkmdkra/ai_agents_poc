"""
Tenant Management API Routes
Admin endpoints for tenant and API key management
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.db import get_db, Tenant
from app.services import TenantService, APIKeyService
from app.api.middleware.auth import require_api_key, require_admin_key

logger = get_logger(__name__)
router = APIRouter()


# ============================================
# REQUEST/RESPONSE MODELS
# ============================================

class CreateTenantRequest(BaseModel):
    """Request to create a tenant"""
    name: str = Field(..., description="Tenant name")
    slug: str = Field(..., description="URL-friendly identifier")
    system_prompt: Optional[str] = Field(default=None, description="Custom system prompt")
    welcome_message: Optional[str] = Field(default=None, description="Welcome message")
    voice: Optional[str] = Field(default="lily", description="Voice for voice calls")
    primary_color: Optional[str] = Field(default="#4F46E5", description="Primary brand color")
    logo_url: Optional[str] = Field(default=None, description="Logo URL")
    pinecone_index_name: Optional[str] = Field(default=None, description="Pinecone index for Text-to-SQL")
    pinecone_drive_index: Optional[str] = Field(default=None, description="Pinecone index for RAG")
    enable_voice_calling: bool = Field(default=True)
    enable_chat: bool = Field(default=True)
    enable_text_to_sql: bool = Field(default=True)
    enable_lead_capture: bool = Field(default=True)


class UpdateTenantRequest(BaseModel):
    """Request to update a tenant"""
    name: Optional[str] = None
    system_prompt: Optional[str] = None
    welcome_message: Optional[str] = None
    voice: Optional[str] = None
    primary_color: Optional[str] = None
    logo_url: Optional[str] = None
    pinecone_index_name: Optional[str] = None
    pinecone_drive_index: Optional[str] = None
    enable_voice_calling: Optional[bool] = None
    enable_chat: Optional[bool] = None
    enable_text_to_sql: Optional[bool] = None
    enable_lead_capture: Optional[bool] = None


class TenantResponse(BaseModel):
    """Response for tenant operations"""
    id: str
    name: str
    slug: str
    is_active: bool
    enable_voice_calling: bool
    enable_chat: bool
    enable_text_to_sql: bool
    enable_lead_capture: bool
    created_at: datetime
    updated_at: datetime


class CreateAPIKeyRequest(BaseModel):
    """Request to create an API key"""
    name: str = Field(..., description="Key name/description")
    can_call: bool = Field(default=True, description="Allow voice calling")
    can_chat: bool = Field(default=True, description="Allow chat")
    can_admin: bool = Field(default=False, description="Allow admin operations")
    expires_at: Optional[datetime] = Field(default=None, description="Expiration date")


class APIKeyResponse(BaseModel):
    """Response for API key operations"""
    id: str
    name: str
    key: Optional[str] = None  # Only returned on creation
    key_preview: Optional[str] = None
    is_active: bool
    can_call: bool
    can_chat: bool
    can_admin: bool
    last_used_at: Optional[datetime]
    usage_count: int
    expires_at: Optional[datetime]
    created_at: datetime


# ============================================
# TENANT ENDPOINTS
# ============================================

@router.get("/", response_model=List[TenantResponse])
async def list_tenants(
    include_inactive: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: Tenant = Depends(require_admin_key)
):
    """List all tenants (admin only)"""
    try:
        tenant_service = TenantService(db)
        tenants = tenant_service.list_tenants(
            include_inactive=include_inactive,
            limit=limit,
            offset=offset
        )

        return [
            TenantResponse(
                id=t.id,
                name=t.name,
                slug=t.slug,
                is_active=t.is_active,
                enable_voice_calling=t.enable_voice_calling,
                enable_chat=t.enable_chat,
                enable_text_to_sql=t.enable_text_to_sql,
                enable_lead_capture=t.enable_lead_capture,
                created_at=t.created_at,
                updated_at=t.updated_at
            )
            for t in tenants
        ]

    except Exception as e:
        logger.error(f"Error listing tenants: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=TenantResponse)
async def create_tenant(
    request: CreateTenantRequest,
    db: Session = Depends(get_db),
    _: Tenant = Depends(require_admin_key)
):
    """Create a new tenant (admin only)"""
    try:
        tenant_service = TenantService(db)
        tenant = tenant_service.create_tenant(**request.model_dump())

        return TenantResponse(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            is_active=tenant.is_active,
            enable_voice_calling=tenant.enable_voice_calling,
            enable_chat=tenant.enable_chat,
            enable_text_to_sql=tenant.enable_text_to_sql,
            enable_lead_capture=tenant.enable_lead_capture,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at
        )

    except Exception as e:
        logger.error(f"Error creating tenant: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    db: Session = Depends(get_db),
    _: Tenant = Depends(require_api_key)
):
    """Get tenant details"""
    try:
        tenant_service = TenantService(db)
        tenant = tenant_service.get_tenant(tenant_id)

        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        return TenantResponse(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            is_active=tenant.is_active,
            enable_voice_calling=tenant.enable_voice_calling,
            enable_chat=tenant.enable_chat,
            enable_text_to_sql=tenant.enable_text_to_sql,
            enable_lead_capture=tenant.enable_lead_capture,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tenant: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: str,
    request: UpdateTenantRequest,
    db: Session = Depends(get_db),
    _: Tenant = Depends(require_admin_key)
):
    """Update tenant settings (admin only)"""
    try:
        tenant_service = TenantService(db)

        # Filter out None values
        update_data = {k: v for k, v in request.model_dump().items() if v is not None}

        tenant = tenant_service.update_tenant(tenant_id, **update_data)

        return TenantResponse(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            is_active=tenant.is_active,
            enable_voice_calling=tenant.enable_voice_calling,
            enable_chat=tenant.enable_chat,
            enable_text_to_sql=tenant.enable_text_to_sql,
            enable_lead_capture=tenant.enable_lead_capture,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating tenant: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{tenant_id}")
async def delete_tenant(
    tenant_id: str,
    db: Session = Depends(get_db),
    _: Tenant = Depends(require_admin_key)
):
    """Deactivate a tenant (admin only)"""
    try:
        tenant_service = TenantService(db)
        tenant_service.delete_tenant(tenant_id)

        return {"success": True, "message": "Tenant deactivated"}

    except Exception as e:
        logger.error(f"Error deleting tenant: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


# ============================================
# API KEY ENDPOINTS
# ============================================

@router.post("/{tenant_id}/api-keys", response_model=APIKeyResponse)
async def create_api_key(
    tenant_id: str,
    request: CreateAPIKeyRequest,
    db: Session = Depends(get_db),
    _: Tenant = Depends(require_admin_key)
):
    """Create a new API key for a tenant (admin only)"""
    try:
        api_key_service = APIKeyService(db)
        result = api_key_service.create_api_key(
            tenant_id=tenant_id,
            name=request.name,
            can_call=request.can_call,
            can_chat=request.can_chat,
            can_admin=request.can_admin,
            expires_at=request.expires_at
        )

        return APIKeyResponse(
            id=result["id"],
            name=result["name"],
            key=result["key"],  # Only returned on creation
            is_active=True,
            can_call=request.can_call,
            can_chat=request.can_chat,
            can_admin=request.can_admin,
            last_used_at=None,
            usage_count=0,
            expires_at=request.expires_at,
            created_at=datetime.fromisoformat(result["created_at"])
        )

    except Exception as e:
        logger.error(f"Error creating API key: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{tenant_id}/api-keys", response_model=List[APIKeyResponse])
async def list_api_keys(
    tenant_id: str,
    db: Session = Depends(get_db),
    _: Tenant = Depends(require_admin_key)
):
    """List API keys for a tenant (admin only)"""
    try:
        api_key_service = APIKeyService(db)
        keys = api_key_service.list_api_keys(tenant_id)

        return [
            APIKeyResponse(
                id=k["id"],
                name=k["name"],
                key_preview=k["key_preview"],
                is_active=k["is_active"],
                can_call=k["can_call"],
                can_chat=k["can_chat"],
                can_admin=k["can_admin"],
                last_used_at=datetime.fromisoformat(k["last_used_at"]) if k["last_used_at"] else None,
                usage_count=k["usage_count"],
                expires_at=datetime.fromisoformat(k["expires_at"]) if k["expires_at"] else None,
                created_at=datetime.fromisoformat(k["created_at"])
            )
            for k in keys
        ]

    except Exception as e:
        logger.error(f"Error listing API keys: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{tenant_id}/api-keys/{key_id}")
async def revoke_api_key(
    tenant_id: str,
    key_id: str,
    db: Session = Depends(get_db),
    _: Tenant = Depends(require_admin_key)
):
    """Revoke an API key (admin only)"""
    try:
        api_key_service = APIKeyService(db)
        success = api_key_service.revoke_api_key(key_id)

        if not success:
            raise HTTPException(status_code=404, detail="API key not found")

        return {"success": True, "message": "API key revoked"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking API key: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
