"""
Appointment & Scheduling Service

Handles:
- Appointment creation and management
- Calendar integration (Odoo)
- Reminder scheduling
- Availability checking
"""

import asyncio
import logging
from datetime import datetime, timedelta, time
from typing import Any, Optional
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from ..integrations.odoo_client import OdooCRMClient, OdooCalendarEvent
from ..models.schemas import (
    Appointment,
    AppointmentCreate,
    AppointmentUpdate,
    AppointmentStatus,
    MeetingType,
)

logger = logging.getLogger(__name__)


class AppointmentService:
    """
    Service for managing appointments and scheduling.

    Responsibilities:
    - CRUD operations for appointments
    - Availability checking
    - Calendar sync with Odoo
    - Reminder scheduling
    """

    def __init__(
        self,
        db_pool,
        odoo_client: Optional[OdooCRMClient] = None,
    ):
        self.db = db_pool
        self.odoo = odoo_client

    # =========================================================================
    # CRUD OPERATIONS
    # =========================================================================

    async def create_appointment(self, data: AppointmentCreate) -> Appointment:
        """
        Create a new appointment.

        Args:
            data: Appointment creation data

        Returns:
            Created appointment
        """
        async with self.db.acquire() as conn:
            # Get lead info for appointment
            lead_info = await conn.fetchrow(
                """
                SELECT full_name, phone, email FROM voice_leads WHERE id = $1
                """,
                data.lead_id,
            )

            row = await conn.fetchrow(
                """
                INSERT INTO voice_appointments (
                    tenant_id, lead_id, call_id, title, description,
                    appointment_type, scheduled_at, duration_minutes, timezone,
                    meeting_type, location, meeting_link,
                    lead_name, lead_phone, lead_email,
                    assigned_agent_id, agent_name, agent_email
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                    $13, $14, $15, $16, $17, $18
                )
                RETURNING *
                """,
                data.tenant_id,
                data.lead_id,
                data.call_id,
                data.title,
                data.description,
                data.appointment_type,
                data.scheduled_at,
                data.duration_minutes,
                data.timezone,
                data.meeting_type.value,
                data.location,
                data.meeting_link,
                lead_info["full_name"] if lead_info else None,
                lead_info["phone"] if lead_info else None,
                lead_info["email"] if lead_info else None,
                data.assigned_agent_id,
                data.agent_name,
                data.agent_email,
            )

            appointment = self._row_to_appointment(row)

            logger.info(
                f"Created appointment {appointment.id} for lead {data.lead_id} "
                f"at {data.scheduled_at}"
            )

            # Sync to Odoo if available
            if self.odoo:
                try:
                    await self._sync_to_odoo(appointment)
                except Exception as e:
                    logger.error(f"Failed to sync appointment to Odoo: {e}")

            return appointment

    async def get_appointment(self, appointment_id: UUID) -> Optional[Appointment]:
        """Get an appointment by ID"""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM voice_appointments WHERE id = $1",
                appointment_id,
            )
            return self._row_to_appointment(row) if row else None

    async def update_appointment(
        self,
        appointment_id: UUID,
        updates: AppointmentUpdate,
    ) -> Optional[Appointment]:
        """Update an appointment"""
        set_clauses = []
        params = []
        param_count = 1

        update_dict = updates.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            if value is not None:
                if isinstance(value, MeetingType):
                    value = value.value
                elif isinstance(value, AppointmentStatus):
                    value = value.value
                set_clauses.append(f"{field} = ${param_count}")
                params.append(value)
                param_count += 1

        if not set_clauses:
            return await self.get_appointment(appointment_id)

        params.append(appointment_id)

        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                UPDATE voice_appointments
                SET {', '.join(set_clauses)}, updated_at = NOW()
                WHERE id = ${param_count}
                RETURNING *
                """,
                *params,
            )

            if row:
                logger.info(f"Updated appointment: {appointment_id}")
                return self._row_to_appointment(row)
            return None

    async def cancel_appointment(
        self,
        appointment_id: UUID,
        reason: Optional[str] = None,
    ) -> Optional[Appointment]:
        """Cancel an appointment"""
        return await self.update_appointment(
            appointment_id,
            AppointmentUpdate(
                status=AppointmentStatus.CANCELLED,
                cancellation_reason=reason,
            ),
        )

    async def reschedule_appointment(
        self,
        appointment_id: UUID,
        new_datetime: datetime,
        duration_minutes: Optional[int] = None,
    ) -> Optional[Appointment]:
        """Reschedule an appointment to a new time"""
        # Get original appointment
        original = await self.get_appointment(appointment_id)
        if not original:
            return None

        # Mark original as rescheduled
        await self.update_appointment(
            appointment_id,
            AppointmentUpdate(status=AppointmentStatus.RESCHEDULED),
        )

        # Create new appointment
        new_appointment = await self.create_appointment(
            AppointmentCreate(
                tenant_id=original.tenant_id,
                lead_id=original.lead_id,
                call_id=original.call_id,
                title=original.title,
                description=original.description,
                appointment_type=original.appointment_type,
                scheduled_at=new_datetime,
                duration_minutes=duration_minutes or original.duration_minutes,
                timezone=original.timezone,
                meeting_type=original.meeting_type,
                location=original.location,
                meeting_link=original.meeting_link,
                assigned_agent_id=original.assigned_agent_id,
                agent_name=original.agent_name,
                agent_email=original.agent_email,
            )
        )

        # Link to original
        async with self.db.acquire() as conn:
            await conn.execute(
                """
                UPDATE voice_appointments
                SET rescheduled_from = $1
                WHERE id = $2
                """,
                appointment_id,
                new_appointment.id,
            )

        logger.info(
            f"Rescheduled appointment {appointment_id} to {new_appointment.id} "
            f"at {new_datetime}"
        )

        return new_appointment

    async def list_appointments(
        self,
        tenant_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        status: Optional[AppointmentStatus] = None,
        lead_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Appointment]:
        """List appointments with filters"""
        conditions = ["tenant_id = $1"]
        params = [tenant_id]
        param_count = 2

        if start_date:
            conditions.append(f"scheduled_at >= ${param_count}")
            params.append(start_date)
            param_count += 1

        if end_date:
            conditions.append(f"scheduled_at <= ${param_count}")
            params.append(end_date)
            param_count += 1

        if status:
            conditions.append(f"status = ${param_count}")
            params.append(status.value)
            param_count += 1

        if lead_id:
            conditions.append(f"lead_id = ${param_count}")
            params.append(lead_id)
            param_count += 1

        params.extend([limit, offset])

        async with self.db.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT * FROM voice_appointments
                WHERE {' AND '.join(conditions)}
                ORDER BY scheduled_at
                LIMIT ${param_count} OFFSET ${param_count + 1}
                """,
                *params,
            )

            return [self._row_to_appointment(row) for row in rows]

    # =========================================================================
    # AVAILABILITY CHECKING
    # =========================================================================

    async def get_available_slots(
        self,
        tenant_id: UUID,
        date: datetime,
        duration_minutes: int = 30,
        agent_id: Optional[UUID] = None,
    ) -> list[dict[str, datetime]]:
        """
        Get available time slots for a given date.

        Args:
            tenant_id: Tenant ID
            date: Date to check
            duration_minutes: Required duration
            agent_id: Optional specific agent

        Returns:
            List of available slots with start/end times
        """
        # Get business hours for this day
        day_of_week = date.weekday()  # 0=Monday in Python

        async with self.db.acquire() as conn:
            # Get business hours
            bh = await conn.fetchrow(
                """
                SELECT * FROM voice_business_hours
                WHERE tenant_id = $1 AND day_of_week = $2
                """,
                tenant_id,
                (day_of_week + 1) % 7,  # Convert to 0=Sunday
            )

            if not bh or bh["is_closed"]:
                return []

            open_time = bh["open_time"] or time(9, 0)
            close_time = bh["close_time"] or time(17, 0)

            # Get existing appointments for the day
            start_of_day = datetime.combine(date.date(), open_time)
            end_of_day = datetime.combine(date.date(), close_time)

            query = """
                SELECT scheduled_at, duration_minutes
                FROM voice_appointments
                WHERE tenant_id = $1
                  AND scheduled_at >= $2
                  AND scheduled_at < $3
                  AND status NOT IN ('cancelled', 'rescheduled')
            """
            params = [tenant_id, start_of_day, end_of_day]

            if agent_id:
                query += " AND assigned_agent_id = $4"
                params.append(agent_id)

            existing = await conn.fetch(query, *params)

        # Build occupied time ranges
        occupied = []
        for apt in existing:
            start = apt["scheduled_at"]
            end = start + timedelta(minutes=apt["duration_minutes"])
            occupied.append((start, end))

        # Sort by start time
        occupied.sort(key=lambda x: x[0])

        # Find available slots
        slots = []
        current = start_of_day

        for occ_start, occ_end in occupied:
            # Check if there's a slot before this appointment
            if current + timedelta(minutes=duration_minutes) <= occ_start:
                # Add slots in 30-minute increments
                slot_start = current
                while slot_start + timedelta(minutes=duration_minutes) <= occ_start:
                    slots.append({
                        "start": slot_start,
                        "end": slot_start + timedelta(minutes=duration_minutes),
                    })
                    slot_start += timedelta(minutes=30)

            current = max(current, occ_end)

        # Check remaining time after last appointment
        while current + timedelta(minutes=duration_minutes) <= end_of_day:
            slots.append({
                "start": current,
                "end": current + timedelta(minutes=duration_minutes),
            })
            current += timedelta(minutes=30)

        return slots

    async def is_slot_available(
        self,
        tenant_id: UUID,
        start_time: datetime,
        duration_minutes: int,
        agent_id: Optional[UUID] = None,
    ) -> bool:
        """
        Check if a specific time slot is available.

        Args:
            tenant_id: Tenant ID
            start_time: Proposed start time
            duration_minutes: Duration needed
            agent_id: Optional specific agent

        Returns:
            True if slot is available
        """
        end_time = start_time + timedelta(minutes=duration_minutes)

        async with self.db.acquire() as conn:
            query = """
                SELECT COUNT(*) as count
                FROM voice_appointments
                WHERE tenant_id = $1
                  AND status NOT IN ('cancelled', 'rescheduled')
                  AND (
                    (scheduled_at <= $2 AND scheduled_at + (duration_minutes || ' minutes')::interval > $2)
                    OR (scheduled_at < $3 AND scheduled_at + (duration_minutes || ' minutes')::interval >= $3)
                    OR (scheduled_at >= $2 AND scheduled_at + (duration_minutes || ' minutes')::interval <= $3)
                  )
            """
            params = [tenant_id, start_time, end_time]

            if agent_id:
                query += " AND assigned_agent_id = $4"
                params.append(agent_id)

            result = await conn.fetchval(query, *params)

            return result == 0

    # =========================================================================
    # REMINDERS
    # =========================================================================

    async def get_pending_reminders(
        self,
        reminder_type: str = "24h",
    ) -> list[Appointment]:
        """
        Get appointments that need reminders sent.

        Args:
            reminder_type: "24h" or "1h"

        Returns:
            List of appointments needing reminders
        """
        if reminder_type == "24h":
            time_threshold = datetime.now() + timedelta(hours=24)
            sent_field = "reminder_24h_sent"
        else:
            time_threshold = datetime.now() + timedelta(hours=1)
            sent_field = "reminder_1h_sent"

        async with self.db.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT * FROM voice_appointments
                WHERE status IN ('scheduled', 'confirmed')
                  AND scheduled_at <= $1
                  AND scheduled_at > NOW()
                  AND {sent_field} = false
                ORDER BY scheduled_at
                """,
                time_threshold,
            )

            return [self._row_to_appointment(row) for row in rows]

    async def mark_reminder_sent(
        self,
        appointment_id: UUID,
        reminder_type: str,
    ):
        """Mark a reminder as sent"""
        field = "reminder_24h_sent" if reminder_type == "24h" else "reminder_1h_sent"
        sent_at_field = f"{field.replace('_sent', '_sent_at')}"

        async with self.db.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE voice_appointments
                SET {field} = true, {sent_at_field} = NOW()
                WHERE id = $1
                """,
                appointment_id,
            )

        logger.info(f"Marked {reminder_type} reminder sent for appointment {appointment_id}")

    async def mark_confirmation_sent(self, appointment_id: UUID):
        """Mark appointment confirmation as sent"""
        async with self.db.acquire() as conn:
            await conn.execute(
                """
                UPDATE voice_appointments
                SET confirmation_sent = true, confirmation_sent_at = NOW()
                WHERE id = $1
                """,
                appointment_id,
            )

    # =========================================================================
    # ODOO SYNC
    # =========================================================================

    async def _sync_to_odoo(self, appointment: Appointment) -> Optional[int]:
        """Sync appointment to Odoo calendar"""
        if not self.odoo:
            return None

        try:
            # Get partner ID from lead
            partner_ids = []
            async with self.db.acquire() as conn:
                lead = await conn.fetchrow(
                    """
                    SELECT odoo_partner_id FROM voice_leads WHERE id = $1
                    """,
                    appointment.lead_id,
                )
                if lead and lead["odoo_partner_id"]:
                    partner_ids.append(lead["odoo_partner_id"])

            event = OdooCalendarEvent(
                name=appointment.title,
                start=appointment.scheduled_at,
                stop=appointment.scheduled_at + timedelta(minutes=appointment.duration_minutes),
                partner_ids=partner_ids,
                location=appointment.location,
                description=appointment.description,
                videocall_location=appointment.meeting_link,
            )

            result = await self.odoo.create_calendar_event(event)
            odoo_event_id = result.get("id")

            if odoo_event_id:
                async with self.db.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE voice_appointments
                        SET odoo_event_id = $1
                        WHERE id = $2
                        """,
                        odoo_event_id,
                        appointment.id,
                    )

            logger.info(f"Synced appointment {appointment.id} to Odoo: {odoo_event_id}")
            return odoo_event_id

        except Exception as e:
            logger.error(f"Failed to sync appointment to Odoo: {e}")
            raise

    # =========================================================================
    # TODAY'S APPOINTMENTS
    # =========================================================================

    async def get_todays_appointments(
        self,
        tenant_id: UUID,
        timezone: str = "UTC",
    ) -> list[Appointment]:
        """Get all appointments for today"""
        tz = ZoneInfo(timezone)
        now = datetime.now(tz)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        return await self.list_appointments(
            tenant_id=tenant_id,
            start_date=start_of_day,
            end_date=end_of_day,
            status=None,  # All statuses
        )

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _row_to_appointment(self, row: dict) -> Appointment:
        """Convert database row to Appointment model"""
        return Appointment(
            id=row["id"],
            tenant_id=row["tenant_id"],
            lead_id=row["lead_id"],
            call_id=row["call_id"],
            title=row["title"],
            description=row["description"],
            appointment_type=row["appointment_type"],
            scheduled_at=row["scheduled_at"],
            duration_minutes=row["duration_minutes"],
            timezone=row["timezone"],
            meeting_type=MeetingType(row["meeting_type"]),
            location=row["location"],
            meeting_link=row["meeting_link"],
            lead_name=row["lead_name"],
            lead_phone=row["lead_phone"],
            lead_email=row["lead_email"],
            assigned_agent_id=row["assigned_agent_id"],
            agent_name=row["agent_name"],
            agent_email=row["agent_email"],
            status=AppointmentStatus(row["status"]),
            confirmation_sent=row["confirmation_sent"],
            reminder_24h_sent=row["reminder_24h_sent"],
            reminder_1h_sent=row["reminder_1h_sent"],
            odoo_event_id=row["odoo_event_id"],
            outcome=row["outcome"],
            outcome_notes=row["outcome_notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
