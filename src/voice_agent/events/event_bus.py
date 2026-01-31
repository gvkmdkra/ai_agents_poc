"""
Event Bus for Async Processing

Implements:
- Event-driven architecture
- Async CRM sync
- Decoupled service communication
- Event sourcing patterns
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional
from uuid import UUID, uuid4

import redis.asyncio as redis

logger = logging.getLogger(__name__)


# ============================================================================
# EVENT TYPES
# ============================================================================


class EventType(str, Enum):
    # Call Events
    CALL_STARTED = "call.started"
    CALL_ANSWERED = "call.answered"
    CALL_ENDED = "call.ended"
    CALL_RECORDING_READY = "call.recording_ready"
    CALL_TRANSCRIPTION_READY = "call.transcription_ready"

    # Lead Events
    LEAD_CREATED = "lead.created"
    LEAD_UPDATED = "lead.updated"
    LEAD_QUALIFIED = "lead.qualified"
    LEAD_SCORE_CHANGED = "lead.score_changed"
    LEAD_ASSIGNED = "lead.assigned"

    # Appointment Events
    APPOINTMENT_SCHEDULED = "appointment.scheduled"
    APPOINTMENT_CONFIRMED = "appointment.confirmed"
    APPOINTMENT_CANCELLED = "appointment.cancelled"
    APPOINTMENT_REMINDER_DUE = "appointment.reminder_due"
    APPOINTMENT_COMPLETED = "appointment.completed"

    # CRM Sync Events
    CRM_SYNC_REQUESTED = "crm.sync_requested"
    CRM_SYNC_COMPLETED = "crm.sync_completed"
    CRM_SYNC_FAILED = "crm.sync_failed"

    # Notification Events
    NOTIFICATION_REQUESTED = "notification.requested"
    NOTIFICATION_SENT = "notification.sent"
    NOTIFICATION_FAILED = "notification.failed"

    # AI Events
    AI_RESPONSE_GENERATED = "ai.response_generated"
    AI_ESCALATION_TRIGGERED = "ai.escalation_triggered"
    AI_TIMEOUT = "ai.timeout"


@dataclass
class Event:
    """Base event structure"""
    id: UUID
    type: EventType
    tenant_id: UUID
    timestamp: datetime
    payload: dict
    source: str  # Service that emitted the event
    correlation_id: Optional[UUID] = None  # For tracking related events
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            "id": str(self.id),
            "type": self.type.value,
            "tenant_id": str(self.tenant_id),
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
            "source": self.source,
            "correlation_id": str(self.correlation_id) if self.correlation_id else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Event":
        """Create from dictionary"""
        return cls(
            id=UUID(data["id"]),
            type=EventType(data["type"]),
            tenant_id=UUID(data["tenant_id"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            payload=data["payload"],
            source=data["source"],
            correlation_id=UUID(data["correlation_id"]) if data.get("correlation_id") else None,
            metadata=data.get("metadata", {}),
        )


# ============================================================================
# EVENT HANDLERS
# ============================================================================


class EventHandler(ABC):
    """Base class for event handlers"""

    @property
    @abstractmethod
    def event_types(self) -> list[EventType]:
        """Event types this handler processes"""
        pass

    @abstractmethod
    async def handle(self, event: Event) -> None:
        """Handle an event"""
        pass


class CRMSyncHandler(EventHandler):
    """
    Handles CRM sync events asynchronously.

    Decouples CRM operations from the real-time voice path.
    """

    def __init__(self, odoo_client):
        self.odoo = odoo_client

    @property
    def event_types(self) -> list[EventType]:
        return [
            EventType.LEAD_CREATED,
            EventType.LEAD_UPDATED,
            EventType.LEAD_QUALIFIED,
            EventType.APPOINTMENT_SCHEDULED,
            EventType.CALL_ENDED,
        ]

    async def handle(self, event: Event) -> None:
        """Handle CRM sync events"""
        try:
            if event.type == EventType.LEAD_CREATED:
                await self._sync_new_lead(event)
            elif event.type == EventType.LEAD_UPDATED:
                await self._sync_lead_update(event)
            elif event.type == EventType.LEAD_QUALIFIED:
                await self._sync_qualification(event)
            elif event.type == EventType.APPOINTMENT_SCHEDULED:
                await self._sync_appointment(event)
            elif event.type == EventType.CALL_ENDED:
                await self._sync_call_activity(event)

            logger.info(f"CRM sync completed for event {event.id}")

        except Exception as e:
            logger.error(f"CRM sync failed for event {event.id}: {e}")
            raise

    async def _sync_new_lead(self, event: Event):
        """Sync new lead to CRM"""
        lead_data = event.payload
        await self.odoo.create_lead({
            "name": lead_data.get("full_name", "New Lead"),
            "phone": lead_data.get("phone"),
            "email_from": lead_data.get("email"),
            "partner_name": lead_data.get("company_name"),
            "description": lead_data.get("notes", ""),
            "x_source": "ai_voice_agent",
            "x_call_id": str(event.correlation_id) if event.correlation_id else None,
        })

    async def _sync_lead_update(self, event: Event):
        """Sync lead updates to CRM"""
        lead_data = event.payload
        odoo_id = lead_data.get("odoo_lead_id")
        if odoo_id:
            await self.odoo.update_lead(odoo_id, lead_data.get("updates", {}))

    async def _sync_qualification(self, event: Event):
        """Sync qualification data to CRM"""
        data = event.payload
        odoo_id = data.get("odoo_lead_id")
        if odoo_id:
            priority_map = {"hot": "3", "warm": "2", "cold": "1"}
            await self.odoo.update_lead(odoo_id, {
                "priority": priority_map.get(data.get("temperature"), "1"),
                "x_lead_score": data.get("score"),
                "description": data.get("qualification_summary"),
            })

    async def _sync_appointment(self, event: Event):
        """Sync appointment to CRM calendar"""
        data = event.payload
        await self.odoo.create_calendar_event({
            "name": data.get("title"),
            "start": data.get("scheduled_at"),
            "stop": data.get("end_at"),
            "partner_ids": [data.get("odoo_partner_id")] if data.get("odoo_partner_id") else [],
            "description": data.get("description"),
        })

    async def _sync_call_activity(self, event: Event):
        """Sync call as activity in CRM"""
        data = event.payload
        odoo_id = data.get("odoo_lead_id")
        if odoo_id:
            await self.odoo.create_activity({
                "res_model": "crm.lead",
                "res_id": odoo_id,
                "activity_type_id": 2,  # Phone Call
                "summary": f"AI Call - {data.get('outcome', 'Completed')}",
                "note": data.get("summary", ""),
            })


class NotificationHandler(EventHandler):
    """Handles notification events"""

    def __init__(self, notification_service):
        self.notifications = notification_service

    @property
    def event_types(self) -> list[EventType]:
        return [
            EventType.NOTIFICATION_REQUESTED,
            EventType.APPOINTMENT_REMINDER_DUE,
            EventType.LEAD_QUALIFIED,
        ]

    async def handle(self, event: Event) -> None:
        """Handle notification events"""
        if event.type == EventType.NOTIFICATION_REQUESTED:
            await self._send_notification(event)
        elif event.type == EventType.APPOINTMENT_REMINDER_DUE:
            await self._send_reminder(event)
        elif event.type == EventType.LEAD_QUALIFIED:
            await self._notify_sales_team(event)

    async def _send_notification(self, event: Event):
        """Send requested notification"""
        data = event.payload
        await self.notifications.send(
            channel=data.get("channel"),
            to=data.get("to"),
            template=data.get("template"),
            data=data.get("template_data", {}),
        )

    async def _send_reminder(self, event: Event):
        """Send appointment reminder"""
        data = event.payload
        await self.notifications.send_reminder(
            appointment_id=UUID(data.get("appointment_id")),
            reminder_type=data.get("reminder_type"),
        )

    async def _notify_sales_team(self, event: Event):
        """Notify sales team of hot lead"""
        data = event.payload
        if data.get("temperature") == "hot":
            # Send priority notification to assigned agent
            agent_email = data.get("assigned_agent_email")
            if agent_email:
                await self.notifications.send_email(
                    to=agent_email,
                    subject="🔥 Hot Lead Alert",
                    template="hot_lead_alert",
                    data=data,
                )


# ============================================================================
# EVENT BUS IMPLEMENTATION
# ============================================================================


class EventBus:
    """
    Redis-backed event bus for async event processing.

    Features:
    - Pub/Sub for real-time events
    - Stream for reliable delivery
    - Consumer groups for scaling
    - Dead letter queue for failed events
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        service_name: str = "voice-agent",
    ):
        self.redis = redis_client
        self.service_name = service_name
        self._handlers: dict[EventType, list[EventHandler]] = {}
        self._running = False
        self._consumer_tasks: list[asyncio.Task] = []

    def register_handler(self, handler: EventHandler):
        """Register an event handler"""
        for event_type in handler.event_types:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)
            logger.info(f"Registered handler {handler.__class__.__name__} for {event_type.value}")

    async def publish(self, event: Event):
        """
        Publish an event to the bus.

        Events are added to a Redis Stream for reliable delivery.
        """
        stream_key = f"events:{event.type.value}"

        # Add to stream
        await self.redis.xadd(
            stream_key,
            {"data": json.dumps(event.to_dict())},
            maxlen=10000,  # Keep last 10k events
        )

        # Also publish to pub/sub for real-time subscribers
        await self.redis.publish(
            f"events:realtime:{event.type.value}",
            json.dumps(event.to_dict()),
        )

        logger.debug(f"Published event {event.id} of type {event.type.value}")

    async def emit(
        self,
        event_type: EventType,
        tenant_id: UUID,
        payload: dict,
        correlation_id: Optional[UUID] = None,
    ) -> Event:
        """
        Convenience method to create and publish an event.

        Args:
            event_type: Type of event
            tenant_id: Tenant ID
            payload: Event payload
            correlation_id: Optional correlation ID

        Returns:
            The published event
        """
        event = Event(
            id=uuid4(),
            type=event_type,
            tenant_id=tenant_id,
            timestamp=datetime.now(),
            payload=payload,
            source=self.service_name,
            correlation_id=correlation_id,
        )

        await self.publish(event)
        return event

    async def start_consumers(self, concurrency: int = 3):
        """Start event consumers"""
        self._running = True

        # Create consumer tasks for each event type with handlers
        for event_type in self._handlers.keys():
            for i in range(concurrency):
                task = asyncio.create_task(
                    self._consume_stream(event_type, f"consumer-{i}")
                )
                self._consumer_tasks.append(task)

        logger.info(f"Started {len(self._consumer_tasks)} event consumers")

    async def stop_consumers(self):
        """Stop all consumers"""
        self._running = False

        for task in self._consumer_tasks:
            task.cancel()

        await asyncio.gather(*self._consumer_tasks, return_exceptions=True)
        self._consumer_tasks.clear()

        logger.info("Stopped all event consumers")

    async def _consume_stream(self, event_type: EventType, consumer_name: str):
        """Consume events from a stream"""
        stream_key = f"events:{event_type.value}"
        group_name = f"{self.service_name}-{event_type.value}"

        # Create consumer group if not exists
        try:
            await self.redis.xgroup_create(stream_key, group_name, id="0", mkstream=True)
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

        while self._running:
            try:
                # Read from stream
                messages = await self.redis.xreadgroup(
                    groupname=group_name,
                    consumername=consumer_name,
                    streams={stream_key: ">"},
                    count=10,
                    block=5000,  # 5 second timeout
                )

                for stream, entries in messages:
                    for entry_id, data in entries:
                        await self._process_message(
                            event_type, entry_id, data, stream_key, group_name
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Consumer error for {event_type.value}: {e}")
                await asyncio.sleep(1)

    async def _process_message(
        self,
        event_type: EventType,
        entry_id: str,
        data: dict,
        stream_key: str,
        group_name: str,
    ):
        """Process a single message from the stream"""
        try:
            event_data = json.loads(data[b"data"])
            event = Event.from_dict(event_data)

            # Get handlers for this event type
            handlers = self._handlers.get(event_type, [])

            for handler in handlers:
                try:
                    await handler.handle(event)
                except Exception as e:
                    logger.error(
                        f"Handler {handler.__class__.__name__} failed for event {event.id}: {e}"
                    )
                    # Move to dead letter queue
                    await self._move_to_dlq(event, str(e))

            # Acknowledge the message
            await self.redis.xack(stream_key, group_name, entry_id)

        except Exception as e:
            logger.error(f"Failed to process message {entry_id}: {e}")

    async def _move_to_dlq(self, event: Event, error: str):
        """Move failed event to dead letter queue"""
        dlq_key = f"events:dlq:{event.type.value}"

        await self.redis.xadd(
            dlq_key,
            {
                "data": json.dumps(event.to_dict()),
                "error": error,
                "failed_at": datetime.now().isoformat(),
            },
            maxlen=1000,
        )

        logger.warning(f"Moved event {event.id} to DLQ: {error}")

    async def get_dlq_events(
        self,
        event_type: EventType,
        count: int = 100,
    ) -> list[dict]:
        """Get events from dead letter queue"""
        dlq_key = f"events:dlq:{event_type.value}"

        entries = await self.redis.xrange(dlq_key, count=count)

        return [
            {
                "id": entry_id,
                "event": json.loads(data[b"data"]),
                "error": data.get(b"error", b"").decode(),
                "failed_at": data.get(b"failed_at", b"").decode(),
            }
            for entry_id, data in entries
        ]

    async def retry_dlq_event(self, event_type: EventType, entry_id: str) -> bool:
        """Retry a dead letter queue event"""
        dlq_key = f"events:dlq:{event_type.value}"

        entries = await self.redis.xrange(dlq_key, min=entry_id, max=entry_id)

        if not entries:
            return False

        _, data = entries[0]
        event = Event.from_dict(json.loads(data[b"data"]))

        # Re-publish the event
        await self.publish(event)

        # Remove from DLQ
        await self.redis.xdel(dlq_key, entry_id)

        logger.info(f"Retried DLQ event {event.id}")
        return True


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================


_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance"""
    global _event_bus
    if _event_bus is None:
        raise RuntimeError("Event bus not initialized. Call init_event_bus() first.")
    return _event_bus


async def init_event_bus(
    redis_client: redis.Redis,
    service_name: str = "voice-agent",
) -> EventBus:
    """Initialize the global event bus"""
    global _event_bus
    _event_bus = EventBus(redis_client, service_name)
    return _event_bus


async def emit_event(
    event_type: EventType,
    tenant_id: UUID,
    payload: dict,
    correlation_id: Optional[UUID] = None,
) -> Event:
    """Emit an event using the global event bus"""
    return await get_event_bus().emit(
        event_type=event_type,
        tenant_id=tenant_id,
        payload=payload,
        correlation_id=correlation_id,
    )
