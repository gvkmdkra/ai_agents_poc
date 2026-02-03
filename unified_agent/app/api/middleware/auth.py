"""
Authentication Middleware
API key validation and tenant resolution
"""

from fastapi import Depends, Header, HTTPException, status
from typing import Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.db import get_db, Tenant
from app.services import APIKeyService

logger = get_logger(__name__)


async def get_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None),
    api_key: Optional[str] = None  # Query parameter
) -> Optional[str]:
    """
    Extract API key from various sources

    Priority:
    1. X-API-Key header
    2. Authorization header (Bearer token)
    3. Query parameter
    """
    # Check X-API-Key header
    if x_api_key:
        return x_api_key

    # Check Authorization header
    if authorization:
        if authorization.startswith("Bearer "):
            return authorization[7:]
        return authorization

    # Check query parameter
    if api_key:
        return api_key

    return None


async def require_api_key(
    key: Optional[str] = Depends(get_api_key),
    db: Session = Depends(get_db)
) -> Tenant:
    """
    Dependency that requires a valid API key
    Returns the associated tenant

    Raises:
        HTTPException: If API key is missing or invalid
    """
    if not key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    api_key_service = APIKeyService(db)

    try:
        tenant = api_key_service.validate_api_key(key)
        logger.debug(f"API key validated for tenant: {tenant.id}")
        return tenant

    except Exception as e:
        logger.warning(f"Invalid API key attempt: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
            headers={"WWW-Authenticate": "ApiKey"}
        )


async def require_call_permission(
    key: Optional[str] = Depends(get_api_key),
    db: Session = Depends(get_db)
) -> Tenant:
    """
    Dependency that requires an API key with calling permission
    """
    if not key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    api_key_service = APIKeyService(db)

    try:
        tenant = api_key_service.validate_api_key(key, require_call=True)
        return tenant

    except Exception as e:
        logger.warning(f"Call permission denied: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key does not have calling permission"
        )


async def require_chat_permission(
    key: Optional[str] = Depends(get_api_key),
    db: Session = Depends(get_db)
) -> Tenant:
    """
    Dependency that requires an API key with chat permission
    """
    if not key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    api_key_service = APIKeyService(db)

    try:
        tenant = api_key_service.validate_api_key(key, require_chat=True)
        return tenant

    except Exception as e:
        logger.warning(f"Chat permission denied: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key does not have chat permission"
        )


async def require_admin_key(
    key: Optional[str] = Depends(get_api_key),
    db: Session = Depends(get_db)
) -> Tenant:
    """
    Dependency that requires an API key with admin permission
    """
    if not key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    api_key_service = APIKeyService(db)

    try:
        tenant = api_key_service.validate_api_key(key, require_admin=True)
        return tenant

    except Exception as e:
        logger.warning(f"Admin permission denied: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin API key required"
        )


async def optional_api_key(
    key: Optional[str] = Depends(get_api_key),
    db: Session = Depends(get_db)
) -> Optional[Tenant]:
    """
    Dependency that optionally validates API key
    Returns tenant if valid key provided, None otherwise
    """
    if not key:
        return None

    try:
        api_key_service = APIKeyService(db)
        return api_key_service.validate_api_key(key)
    except Exception:
        return None
