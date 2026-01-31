"""
Lead Management Service

Handles:
- Lead creation and updates
- Lead qualification (Hot/Warm/Cold)
- CRM synchronization with Odoo
- Follow-up sequence management
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID, uuid4

from ..integrations.odoo_client import OdooCRMClient, OdooLead, OdooLeadPriority
from ..integrations.openai_client import OpenAIVoiceClient, LeadQualificationResult
from ..models.schemas import (
    Lead,
    LeadCreate,
    LeadUpdate,
    LeadTemperature,
    LeadStatus,
    LeadSource,
    FollowUpTaskCreate,
)

logger = logging.getLogger(__name__)


class LeadService:
    """
    Service for managing leads across the voice agent platform.

    Responsibilities:
    - CRUD operations for leads
    - AI-powered lead qualification
    - Odoo CRM synchronization
    - Follow-up sequence automation
    """

    def __init__(
        self,
        db_pool,  # asyncpg connection pool
        odoo_client: Optional[OdooCRMClient] = None,
        openai_client: Optional[OpenAIVoiceClient] = None,
    ):
        self.db = db_pool
        self.odoo = odoo_client
        self.openai = openai_client

    # =========================================================================
    # CRUD OPERATIONS
    # =========================================================================

    async def create_lead(self, lead_data: LeadCreate) -> Lead:
        """
        Create a new lead.

        Args:
            lead_data: Lead creation data

        Returns:
            Created lead
        """
        async with self.db.acquire() as conn:
            # Generate full name
            full_name = None
            if lead_data.first_name or lead_data.last_name:
                full_name = f"{lead_data.first_name or ''} {lead_data.last_name or ''}".strip()

            # Insert lead
            row = await conn.fetchrow(
                """
                INSERT INTO voice_leads (
                    tenant_id, first_name, last_name, full_name, phone, email,
                    company_name, job_title, source, source_phone_number,
                    source_campaign, custom_fields
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                RETURNING *
                """,
                lead_data.tenant_id,
                lead_data.first_name,
                lead_data.last_name,
                full_name,
                lead_data.phone,
                lead_data.email,
                lead_data.company_name,
                lead_data.job_title,
                lead_data.source.value,
                lead_data.source_phone_number,
                lead_data.source_campaign,
                lead_data.custom_fields,
            )

            logger.info(f"Created lead: {row['id']} for tenant {lead_data.tenant_id}")

            return self._row_to_lead(row)

    async def get_lead(self, lead_id: UUID) -> Optional[Lead]:
        """Get a lead by ID"""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM voice_leads WHERE id = $1",
                lead_id,
            )
            return self._row_to_lead(row) if row else None

    async def get_lead_by_phone(self, tenant_id: UUID, phone: str) -> Optional[Lead]:
        """Find a lead by phone number within a tenant"""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM voice_leads
                WHERE tenant_id = $1 AND phone = $2
                ORDER BY created_at DESC
                LIMIT 1
                """,
                tenant_id,
                phone,
            )
            return self._row_to_lead(row) if row else None

    async def update_lead(self, lead_id: UUID, updates: LeadUpdate) -> Optional[Lead]:
        """Update a lead"""
        # Build dynamic update query
        set_clauses = []
        params = []
        param_count = 1

        update_dict = updates.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            if value is not None:
                set_clauses.append(f"{field} = ${param_count}")
                params.append(value)
                param_count += 1

        if not set_clauses:
            return await self.get_lead(lead_id)

        params.append(lead_id)

        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                UPDATE voice_leads
                SET {', '.join(set_clauses)}, updated_at = NOW()
                WHERE id = ${param_count}
                RETURNING *
                """,
                *params,
            )

            logger.info(f"Updated lead: {lead_id}")
            return self._row_to_lead(row) if row else None

    async def list_leads(
        self,
        tenant_id: UUID,
        status: Optional[LeadStatus] = None,
        temperature: Optional[LeadTemperature] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Lead]:
        """List leads for a tenant with optional filters"""
        conditions = ["tenant_id = $1"]
        params = [tenant_id]
        param_count = 2

        if status:
            conditions.append(f"status = ${param_count}")
            params.append(status.value)
            param_count += 1

        if temperature:
            conditions.append(f"lead_temperature = ${param_count}")
            params.append(temperature.value)
            param_count += 1

        params.extend([limit, offset])

        async with self.db.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT * FROM voice_leads
                WHERE {' AND '.join(conditions)}
                ORDER BY created_at DESC
                LIMIT ${param_count} OFFSET ${param_count + 1}
                """,
                *params,
            )

            return [self._row_to_lead(row) for row in rows]

    # =========================================================================
    # LEAD QUALIFICATION
    # =========================================================================

    async def qualify_lead(
        self,
        lead_id: UUID,
        conversation_transcript: str,
        industry: str,
    ) -> LeadQualificationResult:
        """
        Qualify a lead based on conversation transcript.

        Uses AI to analyze the conversation and calculate a lead score
        based on BANT criteria (Budget, Authority, Need, Timeline).

        Args:
            lead_id: Lead ID to qualify
            conversation_transcript: Full conversation text
            industry: Industry context

        Returns:
            Qualification result with score and recommendations
        """
        if not self.openai:
            raise ValueError("OpenAI client not configured")

        # Get AI qualification
        result = await self.openai.qualify_lead(
            conversation_transcript=conversation_transcript,
            industry=industry,
        )

        # Update lead with qualification data
        await self._update_lead_qualification(lead_id, result)

        logger.info(
            f"Qualified lead {lead_id}: score={result.score}, "
            f"temperature={result.temperature}"
        )

        return result

    async def _update_lead_qualification(
        self,
        lead_id: UUID,
        qualification: LeadQualificationResult,
    ):
        """Update lead with qualification results"""
        qualification_data = {
            "budget_mentioned": qualification.budget_mentioned,
            "budget_range": qualification.budget_range,
            "is_decision_maker": qualification.is_decision_maker,
            "need_identified": qualification.need_identified,
            "timeline": qualification.timeline,
            "pain_points": qualification.pain_points,
            "buying_signals": qualification.buying_signals,
            "objections": qualification.objections,
            "qualified_at": datetime.now().isoformat(),
        }

        async with self.db.acquire() as conn:
            await conn.execute(
                """
                UPDATE voice_leads
                SET
                    lead_score = $1,
                    qualification_data = $2,
                    budget_mentioned = $3,
                    budget_range = $4,
                    is_decision_maker = $5,
                    need_identified = $6,
                    timeline = $7,
                    updated_at = NOW()
                WHERE id = $8
                """,
                qualification.score,
                qualification_data,
                qualification.budget_mentioned,
                qualification.budget_range,
                qualification.is_decision_maker,
                qualification.need_identified,
                qualification.timeline,
                lead_id,
            )

    async def get_or_create_lead(
        self,
        tenant_id: UUID,
        phone: str,
        source: LeadSource,
        source_phone_number: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        email: Optional[str] = None,
    ) -> tuple[Lead, bool]:
        """
        Get existing lead by phone or create new one.

        Args:
            tenant_id: Tenant ID
            phone: Customer phone number
            source: Lead source
            source_phone_number: Inbound number called
            first_name: Optional first name
            last_name: Optional last name
            email: Optional email

        Returns:
            Tuple of (Lead, is_new)
        """
        # Try to find existing lead
        existing = await self.get_lead_by_phone(tenant_id, phone)
        if existing:
            return existing, False

        # Create new lead
        lead_data = LeadCreate(
            tenant_id=tenant_id,
            phone=phone,
            source=source,
            source_phone_number=source_phone_number,
            first_name=first_name,
            last_name=last_name,
            email=email,
        )

        new_lead = await self.create_lead(lead_data)
        return new_lead, True

    # =========================================================================
    # ODOO CRM SYNC
    # =========================================================================

    async def sync_lead_to_odoo(self, lead_id: UUID) -> Optional[int]:
        """
        Sync a lead to Odoo CRM.

        Args:
            lead_id: Lead ID to sync

        Returns:
            Odoo lead ID if successful
        """
        if not self.odoo:
            logger.warning("Odoo client not configured, skipping sync")
            return None

        lead = await self.get_lead(lead_id)
        if not lead:
            raise ValueError(f"Lead not found: {lead_id}")

        # Map temperature to Odoo priority
        priority_map = {
            LeadTemperature.HOT: OdooLeadPriority.VERY_HIGH,
            LeadTemperature.WARM: OdooLeadPriority.MEDIUM,
            LeadTemperature.COLD: OdooLeadPriority.LOW,
        }

        # Create Odoo lead
        odoo_lead = OdooLead(
            name=lead.full_name or f"Lead from {lead.phone}",
            phone=lead.phone,
            email=lead.email,
            contact_name=lead.full_name,
            partner_name=lead.company_name,
            description=self._build_lead_description(lead),
            priority=priority_map.get(lead.lead_temperature, OdooLeadPriority.MEDIUM),
            custom_fields={
                "lead_score": lead.lead_score,
                "source_system": "voice_agent",
                "original_id": str(lead.id),
            },
        )

        try:
            result = await self.odoo.create_lead(odoo_lead)
            odoo_id = result.get("id")

            # Update local lead with Odoo ID
            async with self.db.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE voice_leads
                    SET
                        odoo_lead_id = $1,
                        odoo_sync_status = 'synced',
                        odoo_last_sync = NOW()
                    WHERE id = $2
                    """,
                    odoo_id,
                    lead_id,
                )

            logger.info(f"Synced lead {lead_id} to Odoo: {odoo_id}")
            return odoo_id

        except Exception as e:
            logger.error(f"Failed to sync lead to Odoo: {e}")

            # Update sync status
            async with self.db.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE voice_leads
                    SET
                        odoo_sync_status = 'failed',
                        odoo_sync_error = $1
                    WHERE id = $2
                    """,
                    str(e),
                    lead_id,
                )

            raise

    def _build_lead_description(self, lead: Lead) -> str:
        """Build Odoo lead description from lead data"""
        lines = [
            f"Source: {lead.source.value}",
            f"Lead Score: {lead.lead_score:.2f}",
            f"Temperature: {lead.lead_temperature.value if lead.lead_temperature else 'Unknown'}",
        ]

        if lead.qualification_data:
            if lead.qualification_data.get("need_identified"):
                lines.append(f"Need: {lead.qualification_data['need_identified']}")
            if lead.qualification_data.get("timeline"):
                lines.append(f"Timeline: {lead.qualification_data['timeline']}")
            if lead.qualification_data.get("pain_points"):
                lines.append(f"Pain Points: {', '.join(lead.qualification_data['pain_points'])}")

        return "\n".join(lines)

    async def update_odoo_lead_stage(
        self,
        lead_id: UUID,
        stage_id: int,
    ) -> bool:
        """
        Update lead stage in Odoo.

        Args:
            lead_id: Local lead ID
            stage_id: Odoo stage ID

        Returns:
            True if successful
        """
        if not self.odoo:
            return False

        lead = await self.get_lead(lead_id)
        if not lead or not lead.odoo_lead_id:
            return False

        try:
            await self.odoo.update_lead_stage(lead.odoo_lead_id, stage_id)
            return True
        except Exception as e:
            logger.error(f"Failed to update Odoo stage: {e}")
            return False

    # =========================================================================
    # FOLLOW-UP SEQUENCES
    # =========================================================================

    async def create_follow_up_sequence(
        self,
        lead_id: UUID,
        sequence_type: str = "default",
    ) -> list[dict]:
        """
        Create a follow-up task sequence for a lead.

        Sequences are based on lead temperature:
        - Hot: Aggressive follow-up (1h, 24h, 48h, 7d)
        - Warm: Moderate follow-up (24h, 3d, 7d, 14d)
        - Cold: Long-term nurture (7d, 30d, 60d, 90d)

        Args:
            lead_id: Lead ID
            sequence_type: Sequence template to use

        Returns:
            List of created follow-up tasks
        """
        lead = await self.get_lead(lead_id)
        if not lead:
            raise ValueError(f"Lead not found: {lead_id}")

        # Define sequences based on temperature
        sequences = {
            LeadTemperature.HOT: [
                ("call", "Follow-up call", timedelta(hours=1)),
                ("email", "Value proposition email", timedelta(hours=24)),
                ("call", "Check-in call", timedelta(hours=48)),
                ("whatsapp", "Special offer", timedelta(days=7)),
            ],
            LeadTemperature.WARM: [
                ("email", "Thank you email", timedelta(hours=24)),
                ("call", "Nurture call", timedelta(days=3)),
                ("email", "Case study", timedelta(days=7)),
                ("call", "Re-engagement call", timedelta(days=14)),
            ],
            LeadTemperature.COLD: [
                ("email", "Introduction email", timedelta(days=7)),
                ("email", "Newsletter", timedelta(days=30)),
                ("email", "Re-engagement", timedelta(days=60)),
                ("email", "Final attempt", timedelta(days=90)),
            ],
        }

        temperature = lead.lead_temperature or LeadTemperature.COLD
        sequence = sequences.get(temperature, sequences[LeadTemperature.COLD])
        sequence_id = str(uuid4())

        tasks = []
        now = datetime.now()

        async with self.db.acquire() as conn:
            for i, (task_type, title, delay) in enumerate(sequence, 1):
                scheduled_for = now + delay

                row = await conn.fetchrow(
                    """
                    INSERT INTO voice_follow_up_tasks (
                        tenant_id, lead_id, task_type, title,
                        scheduled_for, sequence_id, sequence_step,
                        is_ai_task
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING *
                    """,
                    lead.tenant_id,
                    lead_id,
                    task_type,
                    title,
                    scheduled_for,
                    sequence_id,
                    i,
                    True,
                )

                tasks.append(dict(row))

        logger.info(
            f"Created follow-up sequence for lead {lead_id}: "
            f"{len(tasks)} tasks, sequence={sequence_id}"
        )

        return tasks

    async def get_pending_follow_ups(
        self,
        tenant_id: Optional[UUID] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get pending follow-up tasks that are due"""
        async with self.db.acquire() as conn:
            if tenant_id:
                rows = await conn.fetch(
                    """
                    SELECT ft.*, l.phone, l.email, l.full_name
                    FROM voice_follow_up_tasks ft
                    JOIN voice_leads l ON ft.lead_id = l.id
                    WHERE ft.tenant_id = $1
                      AND ft.status = 'pending'
                      AND ft.scheduled_for <= NOW()
                    ORDER BY ft.scheduled_for
                    LIMIT $2
                    """,
                    tenant_id,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT ft.*, l.phone, l.email, l.full_name
                    FROM voice_follow_up_tasks ft
                    JOIN voice_leads l ON ft.lead_id = l.id
                    WHERE ft.status = 'pending'
                      AND ft.scheduled_for <= NOW()
                    ORDER BY ft.scheduled_for
                    LIMIT $1
                    """,
                    limit,
                )

            return [dict(row) for row in rows]

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _row_to_lead(self, row: dict) -> Lead:
        """Convert database row to Lead model"""
        return Lead(
            id=row["id"],
            tenant_id=row["tenant_id"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            full_name=row["full_name"],
            phone=row["phone"],
            email=row["email"],
            company_name=row["company_name"],
            job_title=row["job_title"],
            lead_score=row["lead_score"],
            lead_temperature=LeadTemperature(row["lead_temperature"]) if row["lead_temperature"] else None,
            qualification_data=row["qualification_data"] or {},
            source=LeadSource(row["source"]),
            source_phone_number=row["source_phone_number"],
            odoo_lead_id=row["odoo_lead_id"],
            odoo_sync_status=row["odoo_sync_status"],
            status=LeadStatus(row["status"]),
            assigned_to=row["assigned_to"],
            total_calls=row["total_calls"],
            total_messages=row["total_messages"],
            last_contact_at=row["last_contact_at"],
            next_follow_up_at=row["next_follow_up_at"],
            tags=row["tags"] or [],
            custom_fields=row["custom_fields"] or {},
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
