"""
Appointment API Routes

Endpoints for:
- Appointment scheduling
- Availability checking
- Reminders
- Calendar sync
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from ..models.schemas import (
    Appointment,
    AppointmentCreate,
    AppointmentUpdate,
    AppointmentStatus,
    MeetingType,
    APIResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/appointments", tags=["Appointments"])


# =========================================================================
# REQUEST/RESPONSE MODELS
# =========================================================================


class RescheduleRequest(BaseModel):
    new_datetime: datetime
    duration_minutes: Optional[int] = None


class AvailabilitySlot(BaseModel):
    start: datetime
    end: datetime


class CheckAvailabilityResponse(BaseModel):
    available: bool
    suggested_slots: Optional[list[AvailabilitySlot]] = None


# =========================================================================
# ENDPOINTS
# =========================================================================


@router.post("/", response_model=Appointment)
async def create_appointment(
    request: Request,
    data: AppointmentCreate,
):
    """
    Schedule a new appointment.

    Creates an appointment and optionally syncs to Odoo calendar.
    """
    appointment_service = request.app.state.appointment_service

    try:
        appointment = await appointment_service.create_appointment(data)
        return appointment
    except Exception as e:
        logger.error(f"Failed to create appointment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{appointment_id}", response_model=Appointment)
async def get_appointment(
    request: Request,
    appointment_id: UUID,
):
    """Get appointment by ID"""
    appointment_service = request.app.state.appointment_service

    appointment = await appointment_service.get_appointment(appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    return appointment


@router.patch("/{appointment_id}", response_model=Appointment)
async def update_appointment(
    request: Request,
    appointment_id: UUID,
    data: AppointmentUpdate,
):
    """Update an appointment"""
    appointment_service = request.app.state.appointment_service

    appointment = await appointment_service.update_appointment(appointment_id, data)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    return appointment


@router.post("/{appointment_id}/cancel", response_model=Appointment)
async def cancel_appointment(
    request: Request,
    appointment_id: UUID,
    reason: Optional[str] = None,
):
    """Cancel an appointment"""
    appointment_service = request.app.state.appointment_service

    appointment = await appointment_service.cancel_appointment(
        appointment_id=appointment_id,
        reason=reason,
    )

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    return appointment


@router.post("/{appointment_id}/reschedule", response_model=Appointment)
async def reschedule_appointment(
    request: Request,
    appointment_id: UUID,
    data: RescheduleRequest,
):
    """Reschedule an appointment to a new time"""
    appointment_service = request.app.state.appointment_service

    appointment = await appointment_service.reschedule_appointment(
        appointment_id=appointment_id,
        new_datetime=data.new_datetime,
        duration_minutes=data.duration_minutes,
    )

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    return appointment


@router.get("/", response_model=list[Appointment])
async def list_appointments(
    request: Request,
    tenant_id: UUID,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    status: Optional[AppointmentStatus] = None,
    lead_id: Optional[UUID] = None,
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
):
    """List appointments with filters"""
    appointment_service = request.app.state.appointment_service

    appointments = await appointment_service.list_appointments(
        tenant_id=tenant_id,
        start_date=start_date,
        end_date=end_date,
        status=status,
        lead_id=lead_id,
        limit=limit,
        offset=offset,
    )

    return appointments


@router.get("/today", response_model=list[Appointment])
async def get_todays_appointments(
    request: Request,
    tenant_id: UUID,
    timezone: str = "UTC",
):
    """Get all appointments for today"""
    appointment_service = request.app.state.appointment_service

    appointments = await appointment_service.get_todays_appointments(
        tenant_id=tenant_id,
        timezone=timezone,
    )

    return appointments


@router.get("/availability", response_model=list[AvailabilitySlot])
async def get_available_slots(
    request: Request,
    tenant_id: UUID,
    date: datetime,
    duration_minutes: int = 30,
    agent_id: Optional[UUID] = None,
):
    """Get available time slots for a given date"""
    appointment_service = request.app.state.appointment_service

    slots = await appointment_service.get_available_slots(
        tenant_id=tenant_id,
        date=date,
        duration_minutes=duration_minutes,
        agent_id=agent_id,
    )

    return [AvailabilitySlot(**slot) for slot in slots]


@router.get("/check-availability", response_model=CheckAvailabilityResponse)
async def check_slot_availability(
    request: Request,
    tenant_id: UUID,
    start_time: datetime,
    duration_minutes: int = 30,
    agent_id: Optional[UUID] = None,
):
    """Check if a specific time slot is available"""
    appointment_service = request.app.state.appointment_service

    is_available = await appointment_service.is_slot_available(
        tenant_id=tenant_id,
        start_time=start_time,
        duration_minutes=duration_minutes,
        agent_id=agent_id,
    )

    response = CheckAvailabilityResponse(available=is_available)

    # If not available, suggest alternatives
    if not is_available:
        slots = await appointment_service.get_available_slots(
            tenant_id=tenant_id,
            date=start_time,
            duration_minutes=duration_minutes,
            agent_id=agent_id,
        )
        response.suggested_slots = [AvailabilitySlot(**slot) for slot in slots[:5]]

    return response


@router.get("/reminders/pending")
async def get_pending_reminders(
    request: Request,
    reminder_type: str = Query("24h", regex="^(24h|1h)$"),
):
    """Get appointments that need reminders sent"""
    appointment_service = request.app.state.appointment_service

    appointments = await appointment_service.get_pending_reminders(reminder_type)

    return {
        "reminder_type": reminder_type,
        "appointments": appointments,
        "count": len(appointments),
    }


@router.post("/{appointment_id}/send-reminder", response_model=APIResponse)
async def send_reminder(
    request: Request,
    appointment_id: UUID,
    reminder_type: str = Query("24h", regex="^(24h|1h)$"),
):
    """Manually send a reminder for an appointment"""
    appointment_service = request.app.state.appointment_service
    notification_service = request.app.state.notification_service

    appointment = await appointment_service.get_appointment(appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # Get tenant for company name
    tenant_service = request.app.state.tenant_service
    tenant = await tenant_service.get_tenant(appointment.tenant_id)

    # Send reminder via WhatsApp if phone available
    if appointment.lead_phone:
        from ..models.schemas import NotificationChannel

        # Get from number
        phone_numbers = await tenant_service.list_phone_numbers(
            tenant_id=appointment.tenant_id,
            phone_type=PhoneType.WHATSAPP,
        )

        if phone_numbers:
            await notification_service.send_reminder(
                tenant_id=appointment.tenant_id,
                lead_id=appointment.lead_id,
                appointment_id=appointment_id,
                reminder_type=reminder_type,
                channel=NotificationChannel.WHATSAPP,
                to_address=appointment.lead_phone,
                from_address=phone_numbers[0].phone_number,
                template_data={
                    "name": appointment.lead_name or "there",
                    "company": tenant.name if tenant else "us",
                    "date": appointment.scheduled_at.strftime("%B %d, %Y"),
                    "time": appointment.scheduled_at.strftime("%I:%M %p"),
                    "location": appointment.location,
                    "meeting_link": appointment.meeting_link,
                },
            )

            # Mark reminder as sent
            await appointment_service.mark_reminder_sent(appointment_id, reminder_type)

            return APIResponse(
                success=True,
                message=f"{reminder_type} reminder sent successfully",
            )

    return APIResponse(
        success=False,
        message="No phone number available for reminder",
    )


@router.post("/{appointment_id}/send-confirmation", response_model=APIResponse)
async def send_confirmation(
    request: Request,
    appointment_id: UUID,
):
    """Send appointment confirmation"""
    appointment_service = request.app.state.appointment_service
    notification_service = request.app.state.notification_service
    tenant_service = request.app.state.tenant_service

    appointment = await appointment_service.get_appointment(appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    tenant = await tenant_service.get_tenant(appointment.tenant_id)

    if appointment.lead_phone:
        from ..models.schemas import NotificationChannel, PhoneType

        phone_numbers = await tenant_service.list_phone_numbers(
            tenant_id=appointment.tenant_id,
            phone_type=PhoneType.WHATSAPP,
        )

        if phone_numbers:
            await notification_service.send_appointment_confirmation(
                tenant_id=appointment.tenant_id,
                lead_id=appointment.lead_id,
                appointment_id=appointment_id,
                channel=NotificationChannel.WHATSAPP,
                to_address=appointment.lead_phone,
                from_address=phone_numbers[0].phone_number,
                template_data={
                    "name": appointment.lead_name or "there",
                    "company": tenant.name if tenant else "us",
                    "date": appointment.scheduled_at.strftime("%B %d, %Y"),
                    "time": appointment.scheduled_at.strftime("%I:%M %p"),
                    "location": appointment.location,
                    "meeting_link": appointment.meeting_link,
                },
            )

            await appointment_service.mark_confirmation_sent(appointment_id)

            return APIResponse(
                success=True,
                message="Confirmation sent successfully",
            )

    return APIResponse(
        success=False,
        message="No phone number available for confirmation",
    )
