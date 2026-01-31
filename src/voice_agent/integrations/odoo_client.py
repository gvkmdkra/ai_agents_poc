"""
Odoo CRM Integration Client

Handles:
- Lead creation and management
- Contact/Partner management
- Activity scheduling (calls, meetings)
- Calendar events
- Pipeline stage updates
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)


class OdooLeadPriority(str, Enum):
    """Odoo lead priority levels"""

    LOW = "0"  # Cold
    MEDIUM = "1"  # Warm
    HIGH = "2"  # Hot
    VERY_HIGH = "3"  # Very Hot


class OdooActivityType(Enum):
    """Common Odoo activity types"""

    CALL = 2
    MEETING = 1
    EMAIL = 4
    TODO = 3
    UPLOAD_DOCUMENT = 5


@dataclass
class OdooConfig:
    """Odoo API configuration"""

    url: str  # e.g., https://your-company.odoo.com
    database: str
    api_key: str  # API key for authentication
    company_id: int = 1
    default_sales_team_id: Optional[int] = None
    default_salesperson_id: Optional[int] = None


@dataclass
class OdooLead:
    """Odoo CRM Lead data structure"""

    # Required fields
    name: str  # Lead/Opportunity name
    phone: Optional[str] = None
    email: Optional[str] = None

    # Contact info
    contact_name: Optional[str] = None
    partner_name: Optional[str] = None  # Company name
    street: Optional[str] = None
    city: Optional[str] = None
    state_id: Optional[int] = None
    country_id: Optional[int] = None
    zip: Optional[str] = None

    # Lead details
    description: Optional[str] = None
    expected_revenue: Optional[float] = None
    probability: Optional[float] = None
    priority: OdooLeadPriority = OdooLeadPriority.MEDIUM

    # Source tracking
    source_id: Optional[int] = None  # Lead source
    campaign_id: Optional[int] = None
    medium_id: Optional[int] = None

    # Assignment
    user_id: Optional[int] = None  # Salesperson
    team_id: Optional[int] = None  # Sales team
    stage_id: Optional[int] = None  # Pipeline stage

    # Custom fields (x_ prefix in Odoo)
    custom_fields: dict[str, Any] = None

    def __post_init__(self):
        if self.custom_fields is None:
            self.custom_fields = {}


@dataclass
class OdooActivity:
    """Odoo activity/task data structure"""

    res_model: str  # e.g., 'crm.lead'
    res_id: int  # ID of the related record
    activity_type_id: int  # Activity type ID
    summary: str  # Activity title
    date_deadline: datetime
    user_id: Optional[int] = None  # Assigned to
    note: Optional[str] = None  # Description/notes


@dataclass
class OdooCalendarEvent:
    """Odoo calendar event data structure"""

    name: str  # Event title
    start: datetime
    stop: datetime
    partner_ids: list[int] = None  # Attendees (partner IDs)
    user_id: Optional[int] = None  # Organizer
    location: Optional[str] = None
    description: Optional[str] = None
    alarm_ids: list[int] = None  # Reminder alarm IDs
    videocall_location: Optional[str] = None  # Video call URL

    def __post_init__(self):
        if self.partner_ids is None:
            self.partner_ids = []
        if self.alarm_ids is None:
            self.alarm_ids = []


class OdooCRMClient:
    """
    Odoo CRM integration client using REST API.

    Handles CRUD operations for:
    - Leads (crm.lead)
    - Contacts/Partners (res.partner)
    - Activities (mail.activity)
    - Calendar Events (calendar.event)
    """

    def __init__(self, config: OdooConfig):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._base_url = f"{config.url}/api/v2"

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.config.api_key}",
                    "DATABASE": self.config.database,
                }
            )
        return self._session

    async def close(self):
        """Close the HTTP session"""
        if self._session:
            await self._session.close()
            self._session = None

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict[str, Any]:
        """
        Make an API request to Odoo.

        Args:
            method: HTTP method
            endpoint: API endpoint
            data: Request body
            params: Query parameters

        Returns:
            Response data
        """
        session = await self._get_session()
        url = f"{self._base_url}/{endpoint}"

        try:
            async with session.request(
                method,
                url,
                json=data,
                params=params,
            ) as response:
                response_data = await response.json()

                if response.status >= 400:
                    error_msg = response_data.get("error", {}).get("message", "Unknown error")
                    logger.error(f"Odoo API error: {error_msg}")
                    raise OdooAPIError(error_msg, response.status)

                return response_data

        except aiohttp.ClientError as e:
            logger.error(f"Odoo request failed: {e}")
            raise

    # =========================================================================
    # LEAD MANAGEMENT
    # =========================================================================

    async def create_lead(self, lead: OdooLead) -> dict[str, Any]:
        """
        Create a new lead in Odoo CRM.

        Args:
            lead: Lead data

        Returns:
            Created lead data including ID
        """
        # Build lead data
        lead_data = {
            "name": lead.name,
            "type": "lead",  # lead or opportunity
            "priority": lead.priority.value,
        }

        # Add optional fields
        if lead.phone:
            lead_data["phone"] = lead.phone
        if lead.email:
            lead_data["email_from"] = lead.email
        if lead.contact_name:
            lead_data["contact_name"] = lead.contact_name
        if lead.partner_name:
            lead_data["partner_name"] = lead.partner_name
        if lead.street:
            lead_data["street"] = lead.street
        if lead.city:
            lead_data["city"] = lead.city
        if lead.zip:
            lead_data["zip"] = lead.zip
        if lead.description:
            lead_data["description"] = lead.description
        if lead.expected_revenue:
            lead_data["expected_revenue"] = lead.expected_revenue
        if lead.probability is not None:
            lead_data["probability"] = lead.probability
        if lead.source_id:
            lead_data["source_id"] = lead.source_id
        if lead.campaign_id:
            lead_data["campaign_id"] = lead.campaign_id
        if lead.medium_id:
            lead_data["medium_id"] = lead.medium_id
        if lead.user_id:
            lead_data["user_id"] = lead.user_id
        elif self.config.default_salesperson_id:
            lead_data["user_id"] = self.config.default_salesperson_id
        if lead.team_id:
            lead_data["team_id"] = lead.team_id
        elif self.config.default_sales_team_id:
            lead_data["team_id"] = self.config.default_sales_team_id
        if lead.stage_id:
            lead_data["stage_id"] = lead.stage_id

        # Add custom fields
        for key, value in lead.custom_fields.items():
            # Ensure custom field names have x_ prefix
            field_name = key if key.startswith("x_") else f"x_{key}"
            lead_data[field_name] = value

        result = await self._request("POST", "crm.lead", data=lead_data)

        logger.info(f"Created Odoo lead: {result.get('id')}")
        return result

    async def update_lead(self, lead_id: int, updates: dict[str, Any]) -> dict[str, Any]:
        """
        Update an existing lead.

        Args:
            lead_id: Odoo lead ID
            updates: Fields to update

        Returns:
            Updated lead data
        """
        result = await self._request("PUT", f"crm.lead/{lead_id}", data=updates)
        logger.info(f"Updated Odoo lead: {lead_id}")
        return result

    async def get_lead(self, lead_id: int) -> dict[str, Any]:
        """
        Get a lead by ID.

        Args:
            lead_id: Odoo lead ID

        Returns:
            Lead data
        """
        return await self._request("GET", f"crm.lead/{lead_id}")

    async def search_leads(
        self,
        domain: Optional[list] = None,
        fields: Optional[list[str]] = None,
        limit: int = 100,
        offset: int = 0,
        order: str = "id desc",
    ) -> list[dict[str, Any]]:
        """
        Search for leads.

        Args:
            domain: Odoo domain filter (e.g., [('phone', '=', '+1234567890')])
            fields: Fields to return
            limit: Maximum records
            offset: Skip records
            order: Sort order

        Returns:
            List of matching leads
        """
        params = {
            "limit": limit,
            "offset": offset,
            "order": order,
        }
        if domain:
            params["domain"] = domain
        if fields:
            params["fields"] = ",".join(fields)

        result = await self._request("GET", "crm.lead", params=params)
        return result.get("records", [])

    async def find_lead_by_phone(self, phone: str) -> Optional[dict[str, Any]]:
        """
        Find a lead by phone number.

        Args:
            phone: Phone number to search

        Returns:
            Lead data or None if not found
        """
        # Normalize phone number for search
        phone_variants = [
            phone,
            phone.replace(" ", ""),
            phone.replace("-", ""),
        ]

        for variant in phone_variants:
            leads = await self.search_leads(
                domain=["|", ("phone", "=", variant), ("mobile", "=", variant)],
                limit=1,
            )
            if leads:
                return leads[0]

        return None

    async def update_lead_stage(self, lead_id: int, stage_id: int) -> dict[str, Any]:
        """
        Update lead pipeline stage.

        Args:
            lead_id: Odoo lead ID
            stage_id: New stage ID

        Returns:
            Updated lead data
        """
        return await self.update_lead(lead_id, {"stage_id": stage_id})

    async def convert_lead_to_opportunity(
        self,
        lead_id: int,
        partner_id: Optional[int] = None,
        create_partner: bool = True,
    ) -> dict[str, Any]:
        """
        Convert a lead to an opportunity.

        Args:
            lead_id: Odoo lead ID
            partner_id: Existing partner ID to link
            create_partner: Create new partner if none exists

        Returns:
            Converted opportunity data
        """
        data = {
            "lead_id": lead_id,
            "action": "convert",
        }
        if partner_id:
            data["partner_id"] = partner_id
        elif create_partner:
            data["action"] = "create"

        result = await self._request("POST", "crm.lead/convert", data=data)
        logger.info(f"Converted lead {lead_id} to opportunity")
        return result

    async def add_lead_note(self, lead_id: int, note: str, author: Optional[str] = None) -> dict[str, Any]:
        """
        Add a note/message to a lead.

        Args:
            lead_id: Odoo lead ID
            note: Note content
            author: Optional author name

        Returns:
            Created message data
        """
        data = {
            "res_id": lead_id,
            "model": "crm.lead",
            "body": note,
            "message_type": "comment",
        }
        if author:
            data["author_id"] = author

        result = await self._request("POST", "mail.message", data=data)
        logger.info(f"Added note to lead {lead_id}")
        return result

    # =========================================================================
    # CONTACT/PARTNER MANAGEMENT
    # =========================================================================

    async def create_partner(
        self,
        name: str,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        company: bool = False,
        parent_id: Optional[int] = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Create a new contact/partner.

        Args:
            name: Contact/company name
            phone: Phone number
            email: Email address
            company: True if this is a company, False for individual
            parent_id: Parent company ID for contacts
            **kwargs: Additional fields

        Returns:
            Created partner data
        """
        data = {
            "name": name,
            "is_company": company,
        }
        if phone:
            data["phone"] = phone
        if email:
            data["email"] = email
        if parent_id:
            data["parent_id"] = parent_id

        data.update(kwargs)

        result = await self._request("POST", "res.partner", data=data)
        logger.info(f"Created Odoo partner: {result.get('id')}")
        return result

    async def find_partner_by_phone(self, phone: str) -> Optional[dict[str, Any]]:
        """Find a partner by phone number"""
        result = await self._request(
            "GET",
            "res.partner",
            params={
                "domain": ["|", ("phone", "=", phone), ("mobile", "=", phone)],
                "limit": 1,
            },
        )
        records = result.get("records", [])
        return records[0] if records else None

    async def find_partner_by_email(self, email: str) -> Optional[dict[str, Any]]:
        """Find a partner by email"""
        result = await self._request(
            "GET",
            "res.partner",
            params={
                "domain": [("email", "=", email)],
                "limit": 1,
            },
        )
        records = result.get("records", [])
        return records[0] if records else None

    # =========================================================================
    # ACTIVITY MANAGEMENT
    # =========================================================================

    async def create_activity(self, activity: OdooActivity) -> dict[str, Any]:
        """
        Create a scheduled activity (call, meeting, task).

        Args:
            activity: Activity data

        Returns:
            Created activity data
        """
        data = {
            "res_model": activity.res_model,
            "res_id": activity.res_id,
            "activity_type_id": activity.activity_type_id,
            "summary": activity.summary,
            "date_deadline": activity.date_deadline.strftime("%Y-%m-%d"),
        }
        if activity.user_id:
            data["user_id"] = activity.user_id
        if activity.note:
            data["note"] = activity.note

        result = await self._request("POST", "mail.activity", data=data)
        logger.info(f"Created Odoo activity: {result.get('id')}")
        return result

    async def schedule_call(
        self,
        lead_id: int,
        summary: str,
        deadline: datetime,
        user_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Schedule a call activity for a lead.

        Args:
            lead_id: Odoo lead ID
            summary: Call summary/title
            deadline: When to make the call
            user_id: Assigned user
            note: Additional notes

        Returns:
            Created activity data
        """
        activity = OdooActivity(
            res_model="crm.lead",
            res_id=lead_id,
            activity_type_id=OdooActivityType.CALL.value,
            summary=summary,
            date_deadline=deadline,
            user_id=user_id,
            note=note,
        )
        return await self.create_activity(activity)

    async def complete_activity(self, activity_id: int, feedback: Optional[str] = None) -> dict[str, Any]:
        """
        Mark an activity as completed.

        Args:
            activity_id: Odoo activity ID
            feedback: Optional feedback/notes

        Returns:
            Result data
        """
        data = {"feedback": feedback} if feedback else {}
        result = await self._request("POST", f"mail.activity/{activity_id}/action_done", data=data)
        logger.info(f"Completed Odoo activity: {activity_id}")
        return result

    # =========================================================================
    # CALENDAR EVENTS
    # =========================================================================

    async def create_calendar_event(self, event: OdooCalendarEvent) -> dict[str, Any]:
        """
        Create a calendar event/meeting.

        Args:
            event: Calendar event data

        Returns:
            Created event data
        """
        data = {
            "name": event.name,
            "start": event.start.isoformat(),
            "stop": event.stop.isoformat(),
            "partner_ids": [(6, 0, event.partner_ids)],  # Odoo many2many format
        }
        if event.user_id:
            data["user_id"] = event.user_id
        if event.location:
            data["location"] = event.location
        if event.description:
            data["description"] = event.description
        if event.videocall_location:
            data["videocall_location"] = event.videocall_location
        if event.alarm_ids:
            data["alarm_ids"] = [(6, 0, event.alarm_ids)]

        result = await self._request("POST", "calendar.event", data=data)
        logger.info(f"Created Odoo calendar event: {result.get('id')}")
        return result

    async def schedule_meeting(
        self,
        title: str,
        start: datetime,
        duration_minutes: int = 30,
        lead_id: Optional[int] = None,
        partner_ids: Optional[list[int]] = None,
        location: Optional[str] = None,
        description: Optional[str] = None,
        video_link: Optional[str] = None,
        reminder_minutes: list[int] = None,
    ) -> dict[str, Any]:
        """
        Schedule a meeting with a lead.

        Args:
            title: Meeting title
            start: Start datetime
            duration_minutes: Meeting duration
            lead_id: Related lead ID
            partner_ids: Attendee partner IDs
            location: Meeting location
            description: Meeting description
            video_link: Video call URL
            reminder_minutes: Reminder times (e.g., [60, 1440] for 1h and 24h)

        Returns:
            Created event data including ID
        """
        stop = start + timedelta(minutes=duration_minutes)

        event = OdooCalendarEvent(
            name=title,
            start=start,
            stop=stop,
            partner_ids=partner_ids or [],
            location=location,
            description=description,
            videocall_location=video_link,
        )

        result = await self.create_calendar_event(event)

        # Link to lead if provided
        if lead_id and result.get("id"):
            await self._request(
                "POST",
                f"crm.lead/{lead_id}/calendar_event",
                data={"calendar_event_id": result["id"]},
            )

        return result

    # =========================================================================
    # PIPELINE STAGES
    # =========================================================================

    async def get_pipeline_stages(self, team_id: Optional[int] = None) -> list[dict[str, Any]]:
        """
        Get CRM pipeline stages.

        Args:
            team_id: Filter by sales team

        Returns:
            List of stage data
        """
        params = {"order": "sequence"}
        if team_id:
            params["domain"] = [("team_id", "=", team_id)]

        result = await self._request("GET", "crm.stage", params=params)
        return result.get("records", [])

    # =========================================================================
    # LEAD SOURCES
    # =========================================================================

    async def get_or_create_source(self, name: str) -> int:
        """
        Get or create a lead source.

        Args:
            name: Source name (e.g., "AI Voice Agent")

        Returns:
            Source ID
        """
        # Search for existing source
        result = await self._request(
            "GET",
            "utm.source",
            params={"domain": [("name", "=", name)], "limit": 1},
        )
        records = result.get("records", [])

        if records:
            return records[0]["id"]

        # Create new source
        result = await self._request("POST", "utm.source", data={"name": name})
        return result.get("id")


class OdooAPIError(Exception):
    """Odoo API error"""

    def __init__(self, message: str, status_code: int):
        self.message = message
        self.status_code = status_code
        super().__init__(f"Odoo API Error ({status_code}): {message}")
