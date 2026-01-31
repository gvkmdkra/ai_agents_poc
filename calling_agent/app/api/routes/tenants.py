"""
Tenant Management API Routes
Manage tenant configurations and API keys
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime

from app.core.logging import get_logger
from app.models.tenant import TenantConfig, TenantAPIKey
from app.services.tenant_service import get_tenant_service, TenantService

logger = get_logger(__name__)

router = APIRouter(prefix="/tenants", tags=["tenants"])


def get_service() -> TenantService:
    """Dependency to get tenant service"""
    return get_tenant_service()


@router.get("/", response_model=List[TenantConfig])
async def list_tenants(
    service: TenantService = Depends(get_service)
):
    """
    List all tenants

    **Note**: In production, this endpoint should be admin-only.
    """
    return service.list_tenants()


@router.get("/{tenant_id}", response_model=TenantConfig)
async def get_tenant(
    tenant_id: str,
    service: TenantService = Depends(get_service)
):
    """
    Get a specific tenant by ID
    """
    tenant = service.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant not found: {tenant_id}")
    return tenant


@router.post("/", response_model=TenantConfig)
async def create_tenant(
    config: TenantConfig,
    service: TenantService = Depends(get_service)
):
    """
    Create a new tenant

    **Note**: In production, this endpoint should be admin-only.
    """
    try:
        return service.create_tenant(config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{tenant_id}", response_model=TenantConfig)
async def update_tenant(
    tenant_id: str,
    updates: dict,
    service: TenantService = Depends(get_service)
):
    """
    Update a tenant configuration
    """
    tenant = service.update_tenant(tenant_id, updates)
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant not found: {tenant_id}")
    return tenant


@router.delete("/{tenant_id}")
async def delete_tenant(
    tenant_id: str,
    service: TenantService = Depends(get_service)
):
    """
    Delete a tenant

    **Note**: In production, this endpoint should be admin-only.
    """
    if not service.delete_tenant(tenant_id):
        raise HTTPException(status_code=404, detail=f"Tenant not found: {tenant_id}")
    return {"message": f"Tenant {tenant_id} deleted"}


@router.post("/{tenant_id}/api-keys", response_model=TenantAPIKey)
async def create_api_key(
    tenant_id: str,
    name: str,
    permissions: Optional[List[str]] = None,
    expires_in_days: Optional[int] = None,
    service: TenantService = Depends(get_service)
):
    """
    Create a new API key for a tenant
    """
    expires_at = None
    if expires_in_days:
        from datetime import timedelta
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

    api_key = service.create_api_key(
        tenant_id=tenant_id,
        name=name,
        permissions=permissions,
        expires_at=expires_at
    )

    if not api_key:
        raise HTTPException(status_code=404, detail=f"Tenant not found: {tenant_id}")

    return api_key


@router.delete("/api-keys/{api_key}")
async def revoke_api_key(
    api_key: str,
    service: TenantService = Depends(get_service)
):
    """
    Revoke an API key
    """
    if not service.revoke_api_key(api_key):
        raise HTTPException(status_code=404, detail="API key not found")
    return {"message": "API key revoked"}
