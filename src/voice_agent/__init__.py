"""
AI Voice Agent Module

Multi-tenant voice agent system with:
- Twilio (Voice, SMS, WhatsApp)
- Ultravox (Real-time Voice AI)
- OpenAI (LLM Backend)
- Odoo CRM (Lead Management)
"""

from .models.schemas import (
    Tenant,
    TenantCreate,
    Lead,
    LeadCreate,
    LeadUpdate,
    LeadTemperature,
    Call,
    CallCreate,
    Appointment,
    AppointmentCreate,
    Notification,
    NotificationCreate,
)

__all__ = [
    "Tenant",
    "TenantCreate",
    "Lead",
    "LeadCreate",
    "LeadUpdate",
    "LeadTemperature",
    "Call",
    "CallCreate",
    "Appointment",
    "AppointmentCreate",
    "Notification",
    "NotificationCreate",
]
