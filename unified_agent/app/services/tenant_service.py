"""
Tenant Service
Multi-tenant management and API key validation
"""

import secrets
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.core.exceptions import TenantNotFoundError, AuthenticationError, ValidationError
from app.db.models import Tenant, APIKey, generate_uuid

logger = get_logger(__name__)


class TenantService:
    """
    Service for tenant management operations
    """

    def __init__(self, db: Session):
        self.db = db

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID"""
        return self.db.query(Tenant).filter(
            Tenant.id == tenant_id,
            Tenant.is_active == True
        ).first()

    def get_tenant_by_slug(self, slug: str) -> Optional[Tenant]:
        """Get tenant by slug"""
        return self.db.query(Tenant).filter(
            Tenant.slug == slug,
            Tenant.is_active == True
        ).first()

    def get_tenant_by_api_key(self, api_key: str) -> Optional[Tenant]:
        """
        Get tenant by API key

        Args:
            api_key: API key string

        Returns:
            Tenant if valid key, None otherwise
        """
        key_record = self.db.query(APIKey).filter(
            APIKey.key == api_key,
            APIKey.is_active == True
        ).first()

        if not key_record:
            return None

        # Check expiration
        if key_record.expires_at and key_record.expires_at < datetime.utcnow():
            logger.warning(f"Expired API key used: {api_key[:8]}...")
            return None

        # Update usage
        key_record.last_used_at = datetime.utcnow()
        key_record.usage_count += 1
        self.db.commit()

        return self.get_tenant(key_record.tenant_id)

    def list_tenants(
        self,
        include_inactive: bool = False,
        limit: int = 100,
        offset: int = 0
    ) -> List[Tenant]:
        """List all tenants"""
        query = self.db.query(Tenant)

        if not include_inactive:
            query = query.filter(Tenant.is_active == True)

        return query.offset(offset).limit(limit).all()

    def create_tenant(
        self,
        name: str,
        slug: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Tenant:
        """
        Create a new tenant

        Args:
            name: Tenant name
            slug: URL-friendly identifier
            system_prompt: Custom system prompt
            **kwargs: Additional tenant fields

        Returns:
            Created tenant
        """
        # Check for duplicate slug
        existing = self.db.query(Tenant).filter(Tenant.slug == slug).first()
        if existing:
            raise ValidationError(f"Tenant with slug '{slug}' already exists", field="slug")

        tenant = Tenant(
            name=name,
            slug=slug,
            system_prompt=system_prompt,
            **kwargs
        )

        self.db.add(tenant)
        self.db.commit()
        self.db.refresh(tenant)

        logger.info(f"Created tenant: {tenant.id} ({tenant.name})")
        return tenant

    def update_tenant(
        self,
        tenant_id: str,
        **kwargs
    ) -> Tenant:
        """Update tenant settings"""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            raise TenantNotFoundError(tenant_id)

        for key, value in kwargs.items():
            if hasattr(tenant, key):
                setattr(tenant, key, value)

        tenant.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(tenant)

        logger.info(f"Updated tenant: {tenant_id}")
        return tenant

    def delete_tenant(self, tenant_id: str) -> bool:
        """Soft delete a tenant"""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            raise TenantNotFoundError(tenant_id)

        tenant.is_active = False
        tenant.updated_at = datetime.utcnow()
        self.db.commit()

        logger.info(f"Deactivated tenant: {tenant_id}")
        return True


class APIKeyService:
    """
    Service for API key management
    """

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def generate_api_key() -> str:
        """Generate a secure API key"""
        return f"ua_{secrets.token_urlsafe(32)}"

    def create_api_key(
        self,
        tenant_id: str,
        name: str,
        can_call: bool = True,
        can_chat: bool = True,
        can_admin: bool = False,
        expires_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Create a new API key for a tenant

        Args:
            tenant_id: Tenant ID
            name: Key name/description
            can_call: Allow voice calling
            can_chat: Allow chat
            can_admin: Allow admin operations
            expires_at: Optional expiration date

        Returns:
            API key info (key is only returned on creation)
        """
        # Verify tenant exists
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise TenantNotFoundError(tenant_id)

        # Generate key
        key = self.generate_api_key()

        api_key = APIKey(
            tenant_id=tenant_id,
            key=key,
            name=name,
            can_call=can_call,
            can_chat=can_chat,
            can_admin=can_admin,
            expires_at=expires_at
        )

        self.db.add(api_key)
        self.db.commit()
        self.db.refresh(api_key)

        logger.info(f"Created API key for tenant {tenant_id}: {name}")

        return {
            "id": api_key.id,
            "key": key,  # Only returned on creation
            "name": name,
            "tenant_id": tenant_id,
            "created_at": api_key.created_at.isoformat()
        }

    def list_api_keys(self, tenant_id: str) -> List[Dict[str, Any]]:
        """List API keys for a tenant (keys are masked)"""
        keys = self.db.query(APIKey).filter(
            APIKey.tenant_id == tenant_id
        ).all()

        return [
            {
                "id": k.id,
                "name": k.name,
                "key_preview": f"{k.key[:8]}...{k.key[-4:]}",
                "is_active": k.is_active,
                "can_call": k.can_call,
                "can_chat": k.can_chat,
                "can_admin": k.can_admin,
                "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
                "usage_count": k.usage_count,
                "expires_at": k.expires_at.isoformat() if k.expires_at else None,
                "created_at": k.created_at.isoformat()
            }
            for k in keys
        ]

    def revoke_api_key(self, key_id: str) -> bool:
        """Revoke an API key"""
        api_key = self.db.query(APIKey).filter(APIKey.id == key_id).first()
        if not api_key:
            return False

        api_key.is_active = False
        self.db.commit()

        logger.info(f"Revoked API key: {key_id}")
        return True

    def validate_api_key(
        self,
        api_key: str,
        require_call: bool = False,
        require_chat: bool = False,
        require_admin: bool = False
    ) -> Tenant:
        """
        Validate API key and return tenant

        Args:
            api_key: API key string
            require_call: Require call permission
            require_chat: Require chat permission
            require_admin: Require admin permission

        Returns:
            Tenant if valid

        Raises:
            AuthenticationError: If validation fails
        """
        key_record = self.db.query(APIKey).filter(
            APIKey.key == api_key,
            APIKey.is_active == True
        ).first()

        if not key_record:
            raise AuthenticationError("Invalid API key")

        # Check expiration
        if key_record.expires_at and key_record.expires_at < datetime.utcnow():
            raise AuthenticationError("API key has expired")

        # Check permissions
        if require_call and not key_record.can_call:
            raise AuthenticationError("API key does not have calling permission")

        if require_chat and not key_record.can_chat:
            raise AuthenticationError("API key does not have chat permission")

        if require_admin and not key_record.can_admin:
            raise AuthenticationError("API key does not have admin permission")

        # Update usage
        key_record.last_used_at = datetime.utcnow()
        key_record.usage_count += 1
        self.db.commit()

        # Get tenant
        tenant = self.db.query(Tenant).filter(
            Tenant.id == key_record.tenant_id,
            Tenant.is_active == True
        ).first()

        if not tenant:
            raise AuthenticationError("Tenant not found or inactive")

        return tenant
