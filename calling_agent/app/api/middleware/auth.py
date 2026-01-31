"""
Authentication Middleware
Handles API key authentication and tenant resolution
"""

from typing import Optional, Tuple
from fastapi import Request, HTTPException
from fastapi.security import APIKeyHeader

from app.core.logging import get_logger
from app.core.exceptions import InvalidAPIKeyError, TenantNotFoundError, TenantInactiveError
from app.services.tenant_service import get_tenant_service
from app.models.tenant import TenantConfig

logger = get_logger(__name__)

# API Key header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key(request: Request) -> Optional[str]:
    """Extract API key from request"""
    # Try header first
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return api_key

    # Try query parameter
    api_key = request.query_params.get("api_key")
    if api_key:
        return api_key

    # Try Authorization header (Bearer token)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]

    return None


async def authenticate_request(
    request: Request,
    required_permission: Optional[str] = None
) -> Tuple[TenantConfig, str]:
    """
    Authenticate a request and return tenant config

    Args:
        request: FastAPI request
        required_permission: Optional permission to check

    Returns:
        Tuple of (TenantConfig, api_key)

    Raises:
        InvalidAPIKeyError: If API key is invalid
        TenantNotFoundError: If tenant not found
        TenantInactiveError: If tenant is inactive
    """
    api_key = await get_api_key(request)

    if not api_key:
        raise InvalidAPIKeyError("API key is required")

    tenant_service = get_tenant_service()

    # Validate API key
    if not tenant_service.validate_api_key(api_key, required_permission):
        raise InvalidAPIKeyError()

    # Get tenant
    tenant = tenant_service.get_tenant_by_api_key(api_key)
    if not tenant:
        raise TenantNotFoundError("unknown")

    if not tenant.is_active:
        raise TenantInactiveError(tenant.tenant_id)

    # Store tenant in request state for later use
    request.state.tenant = tenant
    request.state.api_key = api_key

    return tenant, api_key


async def get_current_tenant(request: Request) -> TenantConfig:
    """
    Dependency to get current tenant from authenticated request

    Usage:
        @router.get("/endpoint")
        async def endpoint(tenant: TenantConfig = Depends(get_current_tenant)):
            ...
    """
    if hasattr(request.state, "tenant"):
        return request.state.tenant

    tenant, _ = await authenticate_request(request)
    return tenant


async def optional_tenant(request: Request) -> Optional[TenantConfig]:
    """
    Dependency to optionally get tenant (doesn't require authentication)

    Usage:
        @router.get("/endpoint")
        async def endpoint(tenant: Optional[TenantConfig] = Depends(optional_tenant)):
            ...
    """
    try:
        api_key = await get_api_key(request)
        if not api_key:
            return None

        tenant_service = get_tenant_service()
        return tenant_service.get_tenant_by_api_key(api_key)
    except Exception:
        return None


def require_permission(permission: str):
    """
    Decorator/dependency factory for permission-based access control

    Usage:
        @router.get("/endpoint")
        async def endpoint(tenant: TenantConfig = Depends(require_permission("calls:write"))):
            ...
    """
    async def permission_checker(request: Request) -> TenantConfig:
        tenant, _ = await authenticate_request(request, required_permission=permission)
        return tenant

    return permission_checker
