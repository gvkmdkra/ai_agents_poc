"""
Notification Service

Handles:
- WhatsApp messaging
- SMS messaging
- Email sending (via SendGrid)
- Reminder scheduling
- Follow-up notifications
"""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional
from uuid import UUID

import aiohttp
from jinja2 import Template

from ..integrations.twilio_client import TwilioClient
from ..models.schemas import (
    Notification,
    NotificationCreate,
    NotificationChannel,
    NotificationType,
    NotificationStatus,
)

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service for multi-channel notifications.

    Supports:
    - WhatsApp messages (via Twilio)
    - SMS messages (via Twilio)
    - Email (via SendGrid)
    - Template-based messaging
    """

    def __init__(
        self,
        db_pool,
        twilio_client: Optional[TwilioClient] = None,
        sendgrid_api_key: Optional[str] = None,
    ):
        self.db = db_pool
        self.twilio = twilio_client
        self.sendgrid_key = sendgrid_api_key

        # Message templates
        self.templates = {
            "appointment_confirmation": {
                "whatsapp": """Hi {{name}}!

Your appointment with {{company}} has been scheduled for:

Date: {{date}}
Time: {{time}}
{{#if location}}Location: {{location}}{{/if}}
{{#if meeting_link}}Join here: {{meeting_link}}{{/if}}

Reply YES to confirm or RESCHEDULE to change the time.

Looking forward to speaking with you!""",

                "sms": """Hi {{name}}, your appt with {{company}} is confirmed for {{date}} at {{time}}. Reply YES to confirm.""",

                "email_subject": "Appointment Confirmed - {{company}}",
                "email_body": """
<h2>Your Appointment is Confirmed!</h2>

<p>Hi {{name}},</p>

<p>Thank you for scheduling time with us. Here are your appointment details:</p>

<table>
    <tr><td><strong>Date:</strong></td><td>{{date}}</td></tr>
    <tr><td><strong>Time:</strong></td><td>{{time}}</td></tr>
    {{#if location}}<tr><td><strong>Location:</strong></td><td>{{location}}</td></tr>{{/if}}
    {{#if meeting_link}}<tr><td><strong>Meeting Link:</strong></td><td><a href="{{meeting_link}}">Join Meeting</a></td></tr>{{/if}}
</table>

<p>If you need to reschedule, please reply to this email or call us.</p>

<p>Best regards,<br>{{company}}</p>
""",
            },
            "reminder_24h": {
                "whatsapp": """Hi {{name}}, this is a reminder that your appointment with {{company}} is tomorrow at {{time}}.

{{#if location}}Location: {{location}}{{/if}}
{{#if meeting_link}}Join here: {{meeting_link}}{{/if}}

See you soon!""",

                "sms": """Reminder: Your appt with {{company}} is tomorrow at {{time}}. {{#if location}}Location: {{location}}{{/if}}""",
            },
            "reminder_1h": {
                "whatsapp": """Hi {{name}}, your appointment with {{company}} starts in 1 hour at {{time}}.

{{#if meeting_link}}Join here: {{meeting_link}}{{/if}}

See you shortly!""",

                "sms": """Your {{company}} appt starts in 1 hour at {{time}}. {{#if meeting_link}}Join: {{meeting_link}}{{/if}}""",
            },
            "follow_up": {
                "whatsapp": """Hi {{name}}, thank you for your interest in {{company}}!

{{message}}

Feel free to reply if you have any questions.

Best regards,
{{agent_name}}""",

                "email_subject": "Following up - {{company}}",
                "email_body": """
<p>Hi {{name}},</p>

{{message}}

<p>Best regards,<br>{{agent_name}}<br>{{company}}</p>
""",
            },
        }

    # =========================================================================
    # SEND NOTIFICATIONS
    # =========================================================================

    async def send_notification(self, data: NotificationCreate) -> Notification:
        """
        Send a notification through the specified channel.

        Args:
            data: Notification data

        Returns:
            Sent notification record
        """
        # Create notification record
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO voice_notifications (
                    tenant_id, lead_id, appointment_id, call_id,
                    channel, to_address, from_address, subject, body,
                    notification_type, scheduled_for, priority,
                    template_id, template_data
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                RETURNING *
                """,
                data.tenant_id,
                data.lead_id,
                data.appointment_id,
                data.call_id,
                data.channel.value,
                data.to_address,
                data.from_address,
                data.subject,
                data.body,
                data.notification_type.value,
                data.scheduled_for,
                data.priority,
                data.template_id,
                data.template_data,
            )

        notification = self._row_to_notification(row)

        # If scheduled for later, just return
        if data.scheduled_for and data.scheduled_for > datetime.now():
            logger.info(f"Scheduled notification {notification.id} for {data.scheduled_for}")
            return notification

        # Send immediately
        try:
            result = await self._send(notification)
            notification = await self._update_status(
                notification.id,
                NotificationStatus.SENT if result["success"] else NotificationStatus.FAILED,
                external_id=result.get("external_id"),
                error_message=result.get("error"),
            )
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            notification = await self._update_status(
                notification.id,
                NotificationStatus.FAILED,
                error_message=str(e),
            )

        return notification

    async def _send(self, notification: Notification) -> dict[str, Any]:
        """Internal send method"""
        if notification.channel == NotificationChannel.WHATSAPP:
            return await self._send_whatsapp(notification)
        elif notification.channel == NotificationChannel.SMS:
            return await self._send_sms(notification)
        elif notification.channel == NotificationChannel.EMAIL:
            return await self._send_email(notification)
        else:
            raise ValueError(f"Unsupported channel: {notification.channel}")

    async def _send_whatsapp(self, notification: Notification) -> dict[str, Any]:
        """Send WhatsApp message via Twilio"""
        if not self.twilio:
            raise ValueError("Twilio client not configured")

        result = await self.twilio.send_whatsapp(
            to_number=notification.to_address,
            from_number=notification.from_address,
            body=notification.body,
        )

        return {
            "success": True,
            "external_id": result.get("message_sid"),
        }

    async def _send_sms(self, notification: Notification) -> dict[str, Any]:
        """Send SMS via Twilio"""
        if not self.twilio:
            raise ValueError("Twilio client not configured")

        result = await self.twilio.send_sms(
            to_number=notification.to_address,
            from_number=notification.from_address,
            body=notification.body,
        )

        return {
            "success": True,
            "external_id": result.get("message_sid"),
        }

    async def _send_email(self, notification: Notification) -> dict[str, Any]:
        """Send email via SendGrid"""
        if not self.sendgrid_key:
            raise ValueError("SendGrid not configured")

        async with aiohttp.ClientSession() as session:
            payload = {
                "personalizations": [
                    {
                        "to": [{"email": notification.to_address}],
                        "subject": notification.subject,
                    }
                ],
                "from": {"email": notification.from_address},
                "content": [
                    {"type": "text/html", "value": notification.body}
                ],
            }

            async with session.post(
                "https://api.sendgrid.com/v3/mail/send",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.sendgrid_key}",
                    "Content-Type": "application/json",
                },
            ) as response:
                if response.status in (200, 202):
                    message_id = response.headers.get("X-Message-Id")
                    return {"success": True, "external_id": message_id}
                else:
                    error = await response.text()
                    return {"success": False, "error": error}

    # =========================================================================
    # TEMPLATE-BASED NOTIFICATIONS
    # =========================================================================

    async def send_appointment_confirmation(
        self,
        tenant_id: UUID,
        lead_id: UUID,
        appointment_id: UUID,
        channel: NotificationChannel,
        to_address: str,
        from_address: str,
        template_data: dict[str, Any],
    ) -> Notification:
        """
        Send appointment confirmation notification.

        Args:
            tenant_id: Tenant ID
            lead_id: Lead ID
            appointment_id: Appointment ID
            channel: Notification channel
            to_address: Recipient address
            from_address: Sender address
            template_data: Template variables

        Returns:
            Sent notification
        """
        template = self.templates["appointment_confirmation"]
        body = self._render_template(
            template.get(channel.value, template.get("whatsapp")),
            template_data,
        )

        subject = None
        if channel == NotificationChannel.EMAIL:
            subject = self._render_template(template["email_subject"], template_data)
            body = self._render_template(template["email_body"], template_data)

        return await self.send_notification(
            NotificationCreate(
                tenant_id=tenant_id,
                lead_id=lead_id,
                appointment_id=appointment_id,
                channel=channel,
                to_address=to_address,
                from_address=from_address,
                subject=subject,
                body=body,
                notification_type=NotificationType.CONFIRMATION,
                template_id="appointment_confirmation",
                template_data=template_data,
            )
        )

    async def send_reminder(
        self,
        tenant_id: UUID,
        lead_id: UUID,
        appointment_id: UUID,
        reminder_type: str,  # "24h" or "1h"
        channel: NotificationChannel,
        to_address: str,
        from_address: str,
        template_data: dict[str, Any],
    ) -> Notification:
        """Send appointment reminder"""
        template_name = f"reminder_{reminder_type}"
        template = self.templates.get(template_name, self.templates["reminder_24h"])

        body = self._render_template(
            template.get(channel.value, template.get("whatsapp")),
            template_data,
        )

        notification_type = (
            NotificationType.REMINDER_24H
            if reminder_type == "24h"
            else NotificationType.REMINDER_1H
        )

        return await self.send_notification(
            NotificationCreate(
                tenant_id=tenant_id,
                lead_id=lead_id,
                appointment_id=appointment_id,
                channel=channel,
                to_address=to_address,
                from_address=from_address,
                body=body,
                notification_type=notification_type,
                template_id=template_name,
                template_data=template_data,
            )
        )

    async def send_follow_up(
        self,
        tenant_id: UUID,
        lead_id: UUID,
        channel: NotificationChannel,
        to_address: str,
        from_address: str,
        template_data: dict[str, Any],
        scheduled_for: Optional[datetime] = None,
    ) -> Notification:
        """Send follow-up message"""
        template = self.templates["follow_up"]

        subject = None
        if channel == NotificationChannel.EMAIL:
            subject = self._render_template(template["email_subject"], template_data)
            body = self._render_template(template["email_body"], template_data)
        else:
            body = self._render_template(template[channel.value], template_data)

        return await self.send_notification(
            NotificationCreate(
                tenant_id=tenant_id,
                lead_id=lead_id,
                channel=channel,
                to_address=to_address,
                from_address=from_address,
                subject=subject,
                body=body,
                notification_type=NotificationType.FOLLOW_UP,
                scheduled_for=scheduled_for,
                template_id="follow_up",
                template_data=template_data,
            )
        )

    def _render_template(self, template_str: str, data: dict[str, Any]) -> str:
        """Render a message template with data"""
        # Simple mustache-style rendering
        result = template_str
        for key, value in data.items():
            result = result.replace(f"{{{{{key}}}}}", str(value) if value else "")

        # Handle conditionals (basic)
        import re
        # Remove conditional blocks for missing values
        result = re.sub(r'\{\{#if \w+\}\}.*?\{\{/if\}\}', '', result, flags=re.DOTALL)

        return result.strip()

    # =========================================================================
    # SCHEDULED NOTIFICATIONS
    # =========================================================================

    async def process_scheduled_notifications(self, limit: int = 100) -> int:
        """
        Process pending scheduled notifications.

        Args:
            limit: Maximum notifications to process

        Returns:
            Number of notifications processed
        """
        async with self.db.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM voice_notifications
                WHERE status = 'pending'
                  AND (scheduled_for IS NULL OR scheduled_for <= NOW())
                ORDER BY priority DESC, scheduled_for
                LIMIT $1
                FOR UPDATE SKIP LOCKED
                """,
                limit,
            )

        processed = 0
        for row in rows:
            notification = self._row_to_notification(row)

            try:
                result = await self._send(notification)
                await self._update_status(
                    notification.id,
                    NotificationStatus.SENT if result["success"] else NotificationStatus.FAILED,
                    external_id=result.get("external_id"),
                    error_message=result.get("error"),
                )
                processed += 1
            except Exception as e:
                logger.error(f"Failed to process notification {notification.id}: {e}")
                await self._update_status(
                    notification.id,
                    NotificationStatus.FAILED,
                    error_message=str(e),
                )

        logger.info(f"Processed {processed} scheduled notifications")
        return processed

    # =========================================================================
    # STATUS UPDATES
    # =========================================================================

    async def _update_status(
        self,
        notification_id: UUID,
        status: NotificationStatus,
        external_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Notification:
        """Update notification status"""
        async with self.db.acquire() as conn:
            update_fields = ["status = $1"]
            params = [status.value]

            if status == NotificationStatus.SENT:
                update_fields.append("sent_at = NOW()")
            elif status == NotificationStatus.FAILED:
                update_fields.append("failed_at = NOW()")

            if external_id:
                update_fields.append(f"external_id = ${len(params) + 1}")
                params.append(external_id)

            if error_message:
                update_fields.append(f"error_message = ${len(params) + 1}")
                params.append(error_message)

            params.append(notification_id)

            row = await conn.fetchrow(
                f"""
                UPDATE voice_notifications
                SET {', '.join(update_fields)}
                WHERE id = ${len(params)}
                RETURNING *
                """,
                *params,
            )

            return self._row_to_notification(row)

    async def handle_delivery_status(
        self,
        external_id: str,
        status: str,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        """
        Handle delivery status webhook from Twilio/SendGrid.

        Args:
            external_id: Twilio MessageSid or SendGrid Message ID
            status: Delivery status
            error_code: Optional error code
            error_message: Optional error message
        """
        # Map external statuses to internal
        status_map = {
            # Twilio statuses
            "delivered": NotificationStatus.DELIVERED,
            "read": NotificationStatus.READ,
            "failed": NotificationStatus.FAILED,
            "undelivered": NotificationStatus.FAILED,
            # SendGrid statuses
            "bounce": NotificationStatus.BOUNCED,
            "open": NotificationStatus.READ,
        }

        internal_status = status_map.get(status.lower())
        if not internal_status:
            return

        async with self.db.acquire() as conn:
            update_fields = ["status = $1", "external_status = $2"]
            params = [internal_status.value, status]

            if internal_status == NotificationStatus.DELIVERED:
                update_fields.append("delivered_at = NOW()")
            elif internal_status == NotificationStatus.READ:
                update_fields.append("read_at = NOW()")
            elif internal_status == NotificationStatus.FAILED:
                update_fields.append("failed_at = NOW()")

            if error_code:
                update_fields.append(f"error_code = ${len(params) + 1}")
                params.append(error_code)

            if error_message:
                update_fields.append(f"error_message = ${len(params) + 1}")
                params.append(error_message)

            params.append(external_id)

            await conn.execute(
                f"""
                UPDATE voice_notifications
                SET {', '.join(update_fields)}
                WHERE external_id = ${len(params)}
                """,
                *params,
            )

        logger.info(f"Updated notification status: {external_id} -> {status}")

    # =========================================================================
    # QUERIES
    # =========================================================================

    async def get_notification(self, notification_id: UUID) -> Optional[Notification]:
        """Get a notification by ID"""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM voice_notifications WHERE id = $1",
                notification_id,
            )
            return self._row_to_notification(row) if row else None

    async def list_notifications(
        self,
        tenant_id: UUID,
        lead_id: Optional[UUID] = None,
        channel: Optional[NotificationChannel] = None,
        status: Optional[NotificationStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Notification]:
        """List notifications with filters"""
        conditions = ["tenant_id = $1"]
        params = [tenant_id]
        param_count = 2

        if lead_id:
            conditions.append(f"lead_id = ${param_count}")
            params.append(lead_id)
            param_count += 1

        if channel:
            conditions.append(f"channel = ${param_count}")
            params.append(channel.value)
            param_count += 1

        if status:
            conditions.append(f"status = ${param_count}")
            params.append(status.value)
            param_count += 1

        params.extend([limit, offset])

        async with self.db.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT * FROM voice_notifications
                WHERE {' AND '.join(conditions)}
                ORDER BY created_at DESC
                LIMIT ${param_count} OFFSET ${param_count + 1}
                """,
                *params,
            )

            return [self._row_to_notification(row) for row in rows]

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _row_to_notification(self, row: dict) -> Notification:
        """Convert database row to Notification model"""
        return Notification(
            id=row["id"],
            tenant_id=row["tenant_id"],
            lead_id=row["lead_id"],
            appointment_id=row["appointment_id"],
            channel=NotificationChannel(row["channel"]),
            direction=row["direction"],
            to_address=row["to_address"],
            from_address=row["from_address"],
            subject=row["subject"],
            body=row["body"],
            notification_type=NotificationType(row["notification_type"]),
            status=NotificationStatus(row["status"]),
            external_id=row["external_id"],
            scheduled_for=row["scheduled_for"],
            sent_at=row["sent_at"],
            delivered_at=row["delivered_at"],
            read_at=row["read_at"],
            error_message=row["error_message"],
            cost_usd=float(row["cost_usd"]) if row["cost_usd"] else None,
            created_at=row["created_at"],
        )
