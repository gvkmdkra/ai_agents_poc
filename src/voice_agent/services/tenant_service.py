"""
Tenant Service

Handles:
- Tenant (client) management
- Phone number configuration
- Voice configuration
- Business hours
"""

import logging
from datetime import time
from typing import Any, Optional
from uuid import UUID

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
    BusinessHoursCreate,
)

logger = logging.getLogger(__name__)


class TenantService:
    """
    Service for managing tenants (clients) and their configurations.

    Responsibilities:
    - Tenant CRUD
    - Phone number management
    - Voice configuration
    - Business hours
    """

    def __init__(self, db_pool):
        self.db = db_pool

    # =========================================================================
    # TENANT MANAGEMENT
    # =========================================================================

    async def create_tenant(self, data: TenantCreate) -> Tenant:
        """
        Create a new tenant.

        Args:
            data: Tenant creation data

        Returns:
            Created tenant
        """
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO voice_tenants (
                    name, slug, industry, timezone, settings, subscription_plan
                ) VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *
                """,
                data.name,
                data.slug,
                data.industry,
                data.timezone,
                data.settings,
                data.subscription_plan,
            )

            tenant = self._row_to_tenant(row)
            logger.info(f"Created tenant: {tenant.id} ({tenant.slug})")

            # Create default business hours (Mon-Fri 9-5)
            await self._create_default_business_hours(tenant.id)

            return tenant

    async def get_tenant(self, tenant_id: UUID) -> Optional[Tenant]:
        """Get a tenant by ID"""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM voice_tenants WHERE id = $1",
                tenant_id,
            )
            return self._row_to_tenant(row) if row else None

    async def get_tenant_by_slug(self, slug: str) -> Optional[Tenant]:
        """Get a tenant by slug"""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM voice_tenants WHERE slug = $1",
                slug,
            )
            return self._row_to_tenant(row) if row else None

    async def update_tenant(
        self,
        tenant_id: UUID,
        updates: TenantUpdate,
    ) -> Optional[Tenant]:
        """Update a tenant"""
        set_clauses = []
        params = []
        param_count = 1

        update_dict = updates.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            if value is not None:
                if isinstance(value, TenantStatus):
                    value = value.value
                set_clauses.append(f"{field} = ${param_count}")
                params.append(value)
                param_count += 1

        if not set_clauses:
            return await self.get_tenant(tenant_id)

        params.append(tenant_id)

        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                UPDATE voice_tenants
                SET {', '.join(set_clauses)}, updated_at = NOW()
                WHERE id = ${param_count}
                RETURNING *
                """,
                *params,
            )

            return self._row_to_tenant(row) if row else None

    async def list_tenants(
        self,
        status: Optional[TenantStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Tenant]:
        """List all tenants"""
        async with self.db.acquire() as conn:
            if status:
                rows = await conn.fetch(
                    """
                    SELECT * FROM voice_tenants
                    WHERE status = $1
                    ORDER BY created_at DESC
                    LIMIT $2 OFFSET $3
                    """,
                    status.value,
                    limit,
                    offset,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM voice_tenants
                    ORDER BY created_at DESC
                    LIMIT $1 OFFSET $2
                    """,
                    limit,
                    offset,
                )

            return [self._row_to_tenant(row) for row in rows]

    # =========================================================================
    # PHONE NUMBER MANAGEMENT
    # =========================================================================

    async def add_phone_number(self, data: PhoneNumberCreate) -> PhoneNumber:
        """
        Add a phone number to a tenant.

        Args:
            data: Phone number data

        Returns:
            Created phone number record
        """
        # Extract country code
        country_code = None
        if data.phone_number.startswith("+"):
            # Simple extraction (first 1-3 digits after +)
            country_code = data.phone_number[1:4].rstrip("0123456789"[:7])

        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO voice_phone_numbers (
                    tenant_id, phone_number, phone_type, twilio_sid,
                    twilio_phone_sid, display_name, purpose, language, country_code
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING *
                """,
                data.tenant_id,
                data.phone_number,
                data.phone_type.value,
                data.twilio_sid,
                data.twilio_phone_sid,
                data.display_name,
                data.purpose,
                data.language,
                country_code,
            )

            phone = self._row_to_phone_number(row)
            logger.info(f"Added phone number: {phone.phone_number} to tenant {data.tenant_id}")
            return phone

    async def get_phone_number(self, phone_number: str) -> Optional[PhoneNumber]:
        """Get phone number record by number"""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM voice_phone_numbers
                WHERE phone_number = $1 AND is_active = true
                """,
                phone_number,
            )
            return self._row_to_phone_number(row) if row else None

    async def get_tenant_by_phone(self, phone_number: str) -> Optional[Tenant]:
        """
        Get tenant associated with a phone number.

        This is the key lookup for routing incoming calls.

        Args:
            phone_number: The Twilio phone number called

        Returns:
            Tenant if found, None otherwise
        """
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT t.* FROM voice_tenants t
                JOIN voice_phone_numbers p ON p.tenant_id = t.id
                WHERE p.phone_number = $1 AND p.is_active = true AND t.status = 'active'
                """,
                phone_number,
            )
            return self._row_to_tenant(row) if row else None

    async def list_phone_numbers(
        self,
        tenant_id: UUID,
        phone_type: Optional[PhoneType] = None,
    ) -> list[PhoneNumber]:
        """List phone numbers for a tenant"""
        async with self.db.acquire() as conn:
            if phone_type:
                rows = await conn.fetch(
                    """
                    SELECT * FROM voice_phone_numbers
                    WHERE tenant_id = $1 AND phone_type = $2 AND is_active = true
                    ORDER BY created_at
                    """,
                    tenant_id,
                    phone_type.value,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM voice_phone_numbers
                    WHERE tenant_id = $1 AND is_active = true
                    ORDER BY created_at
                    """,
                    tenant_id,
                )

            return [self._row_to_phone_number(row) for row in rows]

    async def deactivate_phone_number(self, phone_number_id: UUID) -> bool:
        """Deactivate a phone number"""
        async with self.db.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE voice_phone_numbers
                SET is_active = false
                WHERE id = $1
                """,
                phone_number_id,
            )
            return "UPDATE 1" in result

    # =========================================================================
    # VOICE CONFIGURATION
    # =========================================================================

    async def create_voice_config(self, data: VoiceConfigCreate) -> VoiceConfig:
        """
        Create a voice configuration for a tenant.

        Args:
            data: Voice config data

        Returns:
            Created voice config
        """
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO voice_configs (
                    tenant_id, agent_name, agent_role, greeting_script,
                    system_prompt, voice_provider, voice_id, voice_name,
                    language, accent, speaking_rate, pitch,
                    industry_knowledge_base, faq_document,
                    max_conversation_turns, escalation_keywords
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                RETURNING *
                """,
                data.tenant_id,
                data.agent_name,
                data.agent_role,
                data.greeting_script,
                data.system_prompt,
                data.voice_provider,
                data.voice_id,
                data.voice_name,
                data.language,
                data.accent,
                data.speaking_rate,
                data.pitch,
                data.industry_knowledge_base,
                data.faq_document,
                data.max_conversation_turns,
                data.escalation_keywords,
            )

            config = self._row_to_voice_config(row)
            logger.info(f"Created voice config: {config.id} for tenant {data.tenant_id}")
            return config

    async def get_voice_config(self, config_id: UUID) -> Optional[VoiceConfig]:
        """Get a voice configuration by ID"""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM voice_configs WHERE id = $1",
                config_id,
            )
            return self._row_to_voice_config(row) if row else None

    async def get_default_voice_config(self, tenant_id: UUID) -> Optional[VoiceConfig]:
        """Get the default voice configuration for a tenant"""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM voice_configs
                WHERE tenant_id = $1
                ORDER BY is_default DESC, created_at
                LIMIT 1
                """,
                tenant_id,
            )
            return self._row_to_voice_config(row) if row else None

    async def list_voice_configs(self, tenant_id: UUID) -> list[VoiceConfig]:
        """List all voice configurations for a tenant"""
        async with self.db.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM voice_configs
                WHERE tenant_id = $1
                ORDER BY is_default DESC, created_at
                """,
                tenant_id,
            )
            return [self._row_to_voice_config(row) for row in rows]

    async def set_default_voice_config(self, tenant_id: UUID, config_id: UUID) -> bool:
        """Set a voice configuration as the default"""
        async with self.db.acquire() as conn:
            # Unset all defaults for this tenant
            await conn.execute(
                """
                UPDATE voice_configs
                SET is_default = false
                WHERE tenant_id = $1
                """,
                tenant_id,
            )

            # Set new default
            result = await conn.execute(
                """
                UPDATE voice_configs
                SET is_default = true
                WHERE id = $1 AND tenant_id = $2
                """,
                config_id,
                tenant_id,
            )

            return "UPDATE 1" in result

    # =========================================================================
    # BUSINESS HOURS
    # =========================================================================

    async def _create_default_business_hours(self, tenant_id: UUID):
        """Create default business hours (Mon-Fri 9-5)"""
        async with self.db.acquire() as conn:
            for day in range(7):
                is_closed = day in (0, 6)  # Sunday=0, Saturday=6
                await conn.execute(
                    """
                    INSERT INTO voice_business_hours (
                        tenant_id, day_of_week, open_time, close_time,
                        is_closed, after_hours_action
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (tenant_id, day_of_week) DO NOTHING
                    """,
                    tenant_id,
                    day,
                    time(9, 0) if not is_closed else None,
                    time(17, 0) if not is_closed else None,
                    is_closed,
                    "voicemail",
                )

    async def get_business_hours(self, tenant_id: UUID) -> list[BusinessHours]:
        """Get all business hours for a tenant"""
        async with self.db.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM voice_business_hours
                WHERE tenant_id = $1
                ORDER BY day_of_week
                """,
                tenant_id,
            )
            return [self._row_to_business_hours(row) for row in rows]

    async def update_business_hours(
        self,
        tenant_id: UUID,
        day_of_week: int,
        open_time: Optional[time] = None,
        close_time: Optional[time] = None,
        is_closed: bool = False,
        after_hours_action: str = "voicemail",
        after_hours_message: Optional[str] = None,
    ) -> BusinessHours:
        """Update business hours for a specific day"""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO voice_business_hours (
                    tenant_id, day_of_week, open_time, close_time,
                    is_closed, after_hours_action, after_hours_message
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (tenant_id, day_of_week)
                DO UPDATE SET
                    open_time = EXCLUDED.open_time,
                    close_time = EXCLUDED.close_time,
                    is_closed = EXCLUDED.is_closed,
                    after_hours_action = EXCLUDED.after_hours_action,
                    after_hours_message = EXCLUDED.after_hours_message
                RETURNING *
                """,
                tenant_id,
                day_of_week,
                open_time,
                close_time,
                is_closed,
                after_hours_action,
                after_hours_message,
            )
            return self._row_to_business_hours(row)

    async def is_within_business_hours(self, tenant_id: UUID) -> bool:
        """Check if current time is within business hours"""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return False

        tz = ZoneInfo(tenant.timezone)
        now = datetime.now(tz)
        current_day = (now.weekday() + 1) % 7  # Convert to 0=Sunday
        current_time = now.time()

        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM voice_business_hours
                WHERE tenant_id = $1 AND day_of_week = $2
                """,
                tenant_id,
                current_day,
            )

            if not row or row["is_closed"]:
                return False

            open_time = row["open_time"]
            close_time = row["close_time"]

            if not open_time or not close_time:
                return False

            return open_time <= current_time <= close_time

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _row_to_tenant(self, row: dict) -> Tenant:
        """Convert database row to Tenant model"""
        return Tenant(
            id=row["id"],
            name=row["name"],
            slug=row["slug"],
            industry=row["industry"],
            timezone=row["timezone"],
            status=TenantStatus(row["status"]),
            subscription_plan=row["subscription_plan"],
            monthly_minutes_limit=row["monthly_minutes_limit"],
            minutes_used=row["minutes_used"],
            settings=row["settings"] or {},
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_phone_number(self, row: dict) -> PhoneNumber:
        """Convert database row to PhoneNumber model"""
        return PhoneNumber(
            id=row["id"],
            tenant_id=row["tenant_id"],
            phone_number=row["phone_number"],
            phone_type=PhoneType(row["phone_type"]),
            twilio_sid=row["twilio_sid"],
            country_code=row["country_code"],
            display_name=row["display_name"],
            purpose=row["purpose"],
            language=row["language"],
            is_active=row["is_active"],
            created_at=row["created_at"],
        )

    def _row_to_voice_config(self, row: dict) -> VoiceConfig:
        """Convert database row to VoiceConfig model"""
        return VoiceConfig(
            id=row["id"],
            tenant_id=row["tenant_id"],
            agent_name=row["agent_name"],
            agent_role=row["agent_role"],
            greeting_script=row["greeting_script"],
            system_prompt=row["system_prompt"],
            voice_provider=row["voice_provider"],
            voice_id=row["voice_id"],
            voice_name=row["voice_name"],
            language=row["language"],
            accent=row["accent"],
            speaking_rate=row["speaking_rate"],
            pitch=row["pitch"],
            max_conversation_turns=row["max_conversation_turns"],
            escalation_keywords=row["escalation_keywords"] or [],
            is_default=row["is_default"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_business_hours(self, row: dict) -> BusinessHours:
        """Convert database row to BusinessHours model"""
        return BusinessHours(
            id=row["id"],
            tenant_id=row["tenant_id"],
            day_of_week=row["day_of_week"],
            open_time=row["open_time"],
            close_time=row["close_time"],
            is_closed=row["is_closed"],
            after_hours_action=row["after_hours_action"],
            after_hours_message=row["after_hours_message"],
        )
