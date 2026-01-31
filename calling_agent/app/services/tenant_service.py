"""
Tenant Service
Manages tenant configurations for multi-client deployment
"""

import json
import secrets
from typing import Optional, Dict, List
from pathlib import Path
from datetime import datetime

from app.core.config import settings
from app.core.logging import get_logger
from app.models.tenant import TenantConfig, TenantAPIKey

logger = get_logger(__name__)


class TenantService:
    """Service for managing tenant configurations"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path or "tenants.json")
        self.tenants: Dict[str, TenantConfig] = {}
        self.api_keys: Dict[str, TenantAPIKey] = {}
        self._load_tenants()

    def _load_tenants(self):
        """Load tenant configurations from file"""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    data = json.load(f)

                for tenant_data in data.get("tenants", []):
                    tenant = TenantConfig(**tenant_data)
                    self.tenants[tenant.tenant_id] = tenant

                for key_data in data.get("api_keys", []):
                    api_key = TenantAPIKey(**key_data)
                    self.api_keys[api_key.api_key] = api_key

                logger.info(f"Loaded {len(self.tenants)} tenants")
            except Exception as e:
                logger.warning(f"Failed to load tenants: {e}")
                self._create_default_tenant()
        else:
            self._create_default_tenant()

    def _create_default_tenant(self):
        """Create a default tenant for development"""
        default_tenant = TenantConfig(
            tenant_id="default",
            tenant_name="Default Tenant",
            company_name="AI Calling Platform",
            agent_name="Assistant"
        )
        self.tenants["default"] = default_tenant

        # Create default API key
        default_key = TenantAPIKey(
            api_key=settings.secret_key or secrets.token_urlsafe(32),
            tenant_id="default",
            name="Default API Key"
        )
        self.api_keys[default_key.api_key] = default_key

        self._save_tenants()
        logger.info("Created default tenant configuration")

    def _save_tenants(self):
        """Save tenant configurations to file"""
        try:
            data = {
                "tenants": [t.model_dump(mode="json") for t in self.tenants.values()],
                "api_keys": [k.model_dump(mode="json") for k in self.api_keys.values()]
            }
            with open(self.config_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save tenants: {e}")

    def get_tenant(self, tenant_id: str) -> Optional[TenantConfig]:
        """Get tenant by ID"""
        return self.tenants.get(tenant_id)

    def get_tenant_by_api_key(self, api_key: str) -> Optional[TenantConfig]:
        """Get tenant by API key"""
        key_obj = self.api_keys.get(api_key)
        if key_obj and key_obj.is_active:
            # Check expiration
            if key_obj.expires_at and key_obj.expires_at < datetime.utcnow():
                return None
            # Update last used
            key_obj.last_used_at = datetime.utcnow()
            return self.tenants.get(key_obj.tenant_id)
        return None

    def create_tenant(self, config: TenantConfig) -> TenantConfig:
        """Create a new tenant"""
        if config.tenant_id in self.tenants:
            raise ValueError(f"Tenant {config.tenant_id} already exists")

        self.tenants[config.tenant_id] = config
        self._save_tenants()
        logger.info(f"Created tenant: {config.tenant_id}")
        return config

    def update_tenant(self, tenant_id: str, updates: Dict) -> Optional[TenantConfig]:
        """Update tenant configuration"""
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            return None

        # Update fields
        tenant_dict = tenant.model_dump()
        tenant_dict.update(updates)
        tenant_dict["updated_at"] = datetime.utcnow()

        updated_tenant = TenantConfig(**tenant_dict)
        self.tenants[tenant_id] = updated_tenant
        self._save_tenants()

        logger.info(f"Updated tenant: {tenant_id}")
        return updated_tenant

    def delete_tenant(self, tenant_id: str) -> bool:
        """Delete a tenant"""
        if tenant_id in self.tenants:
            del self.tenants[tenant_id]
            # Remove associated API keys
            self.api_keys = {
                k: v for k, v in self.api_keys.items()
                if v.tenant_id != tenant_id
            }
            self._save_tenants()
            logger.info(f"Deleted tenant: {tenant_id}")
            return True
        return False

    def list_tenants(self) -> List[TenantConfig]:
        """List all tenants"""
        return list(self.tenants.values())

    def create_api_key(
        self,
        tenant_id: str,
        name: str,
        permissions: Optional[List[str]] = None,
        expires_at: Optional[datetime] = None
    ) -> Optional[TenantAPIKey]:
        """Create a new API key for a tenant"""
        if tenant_id not in self.tenants:
            return None

        api_key = TenantAPIKey(
            api_key=secrets.token_urlsafe(32),
            tenant_id=tenant_id,
            name=name,
            permissions=permissions or ["calls:read", "calls:write"],
            expires_at=expires_at
        )

        self.api_keys[api_key.api_key] = api_key
        self._save_tenants()

        logger.info(f"Created API key for tenant: {tenant_id}")
        return api_key

    def revoke_api_key(self, api_key: str) -> bool:
        """Revoke an API key"""
        if api_key in self.api_keys:
            self.api_keys[api_key].is_active = False
            self._save_tenants()
            logger.info(f"Revoked API key")
            return True
        return False

    def validate_api_key(self, api_key: str, required_permission: Optional[str] = None) -> bool:
        """Validate an API key and optionally check permission"""
        key_obj = self.api_keys.get(api_key)
        if not key_obj or not key_obj.is_active:
            return False

        if key_obj.expires_at and key_obj.expires_at < datetime.utcnow():
            return False

        if required_permission and required_permission not in key_obj.permissions:
            return False

        return True


# Singleton instance
_tenant_service: Optional[TenantService] = None


def get_tenant_service() -> TenantService:
    """Get the TenantService singleton instance"""
    global _tenant_service
    if _tenant_service is None:
        _tenant_service = TenantService()
    return _tenant_service
