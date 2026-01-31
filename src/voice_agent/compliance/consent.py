"""
Compliance & Consent Management

Implements:
- Call recording consent
- PII handling and masking
- Data retention policies
- Audit logging
- GDPR/CCPA compliance
"""

import asyncio
import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


# ============================================================================
# CONSENT MANAGEMENT
# ============================================================================


class ConsentType(str, Enum):
    CALL_RECORDING = "call_recording"
    DATA_PROCESSING = "data_processing"
    MARKETING = "marketing"
    AI_INTERACTION = "ai_interaction"
    DATA_SHARING = "data_sharing"


class ConsentStatus(str, Enum):
    GRANTED = "granted"
    DENIED = "denied"
    PENDING = "pending"
    WITHDRAWN = "withdrawn"


@dataclass
class ConsentRecord:
    """Record of consent given or denied"""
    id: UUID
    tenant_id: UUID
    lead_id: Optional[UUID]
    phone_number: str
    consent_type: ConsentType
    status: ConsentStatus
    method: str  # verbal, written, electronic
    timestamp: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    recording_reference: Optional[str] = None  # Reference to recording where consent was given
    expiry_date: Optional[datetime] = None
    metadata: dict = None


class ConsentManager:
    """
    Manages consent for call recording and data processing.

    Requirements:
    - Record consent before recording calls
    - Track consent per phone number
    - Allow withdrawal of consent
    - Maintain audit trail
    """

    def __init__(self, db_pool):
        self.db = db_pool

    async def record_consent(
        self,
        tenant_id: UUID,
        phone_number: str,
        consent_type: ConsentType,
        status: ConsentStatus,
        method: str = "verbal",
        lead_id: Optional[UUID] = None,
        recording_reference: Optional[str] = None,
        expiry_days: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> ConsentRecord:
        """
        Record a consent decision.

        Args:
            tenant_id: Tenant ID
            phone_number: Phone number giving consent
            consent_type: Type of consent
            status: Granted or denied
            method: How consent was obtained
            lead_id: Optional lead ID
            recording_reference: Reference to recording
            expiry_days: Days until consent expires
            metadata: Additional metadata
        """
        consent_id = uuid4()
        now = datetime.now()
        expiry = now + timedelta(days=expiry_days) if expiry_days else None

        async with self.db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO voice_consent_records (
                    id, tenant_id, lead_id, phone_number, consent_type,
                    status, method, timestamp, recording_reference,
                    expiry_date, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                consent_id,
                tenant_id,
                lead_id,
                phone_number,
                consent_type.value,
                status.value,
                method,
                now,
                recording_reference,
                expiry,
                json.dumps(metadata) if metadata else None,
            )

        logger.info(
            f"Recorded {status.value} consent for {consent_type.value} "
            f"from {self._mask_phone(phone_number)}"
        )

        return ConsentRecord(
            id=consent_id,
            tenant_id=tenant_id,
            lead_id=lead_id,
            phone_number=phone_number,
            consent_type=consent_type,
            status=status,
            method=method,
            timestamp=now,
            recording_reference=recording_reference,
            expiry_date=expiry,
            metadata=metadata,
        )

    async def check_consent(
        self,
        tenant_id: UUID,
        phone_number: str,
        consent_type: ConsentType,
    ) -> tuple[bool, Optional[ConsentRecord]]:
        """
        Check if valid consent exists.

        Returns:
            (has_consent, consent_record)
        """
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM voice_consent_records
                WHERE tenant_id = $1
                  AND phone_number = $2
                  AND consent_type = $3
                  AND status = 'granted'
                  AND (expiry_date IS NULL OR expiry_date > NOW())
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                tenant_id,
                phone_number,
                consent_type.value,
            )

            if row:
                record = self._row_to_record(row)
                return True, record

            return False, None

    async def withdraw_consent(
        self,
        tenant_id: UUID,
        phone_number: str,
        consent_type: ConsentType,
        reason: Optional[str] = None,
    ) -> bool:
        """Withdraw previously granted consent"""
        async with self.db.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE voice_consent_records
                SET status = 'withdrawn', metadata = metadata || $4
                WHERE tenant_id = $1
                  AND phone_number = $2
                  AND consent_type = $3
                  AND status = 'granted'
                """,
                tenant_id,
                phone_number,
                consent_type.value,
                json.dumps({"withdrawal_reason": reason, "withdrawn_at": datetime.now().isoformat()}),
            )

            withdrawn = "UPDATE" in result
            if withdrawn:
                logger.info(
                    f"Consent withdrawn for {consent_type.value} "
                    f"from {self._mask_phone(phone_number)}"
                )

            return withdrawn

    async def get_consent_prompt(self, tenant_id: UUID, language: str = "en-US") -> str:
        """
        Get the consent prompt script for a tenant.

        This is what the AI should say at the start of a call.
        """
        prompts = {
            "en-US": (
                "This call may be recorded for quality assurance and training purposes. "
                "By continuing this call, you consent to being recorded. "
                "If you do not wish to be recorded, please let me know now."
            ),
            "es-ES": (
                "Esta llamada puede ser grabada con fines de calidad y capacitación. "
                "Al continuar esta llamada, usted consiente ser grabado. "
                "Si no desea ser grabado, por favor hágamelo saber ahora."
            ),
            "fr-FR": (
                "Cet appel peut être enregistré à des fins de qualité et de formation. "
                "En poursuivant cet appel, vous consentez à être enregistré. "
                "Si vous ne souhaitez pas être enregistré, veuillez me le faire savoir maintenant."
            ),
        }

        return prompts.get(language, prompts["en-US"])

    def _mask_phone(self, phone: str) -> str:
        """Mask phone number for logging"""
        if len(phone) <= 4:
            return "***"
        return f"***{phone[-4:]}"

    def _row_to_record(self, row: dict) -> ConsentRecord:
        """Convert database row to ConsentRecord"""
        return ConsentRecord(
            id=row["id"],
            tenant_id=row["tenant_id"],
            lead_id=row["lead_id"],
            phone_number=row["phone_number"],
            consent_type=ConsentType(row["consent_type"]),
            status=ConsentStatus(row["status"]),
            method=row["method"],
            timestamp=row["timestamp"],
            recording_reference=row["recording_reference"],
            expiry_date=row["expiry_date"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else None,
        )


# ============================================================================
# PII HANDLING
# ============================================================================


class PIIHandler:
    """
    Handles Personally Identifiable Information (PII).

    Provides:
    - PII detection
    - PII masking
    - Secure hashing for matching
    """

    # Common PII patterns
    PATTERNS = {
        "ssn": r"\b\d{3}-?\d{2}-?\d{4}\b",
        "credit_card": r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone": r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b",
        "dob": r"\b(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-](?:19|20)\d{2}\b",
        "address": r"\b\d{1,5}\s+\w+\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct)\b",
    }

    REPLACEMENT_MAP = {
        "ssn": "[SSN REDACTED]",
        "credit_card": "[CARD REDACTED]",
        "email": "[EMAIL REDACTED]",
        "phone": "[PHONE REDACTED]",
        "dob": "[DOB REDACTED]",
        "address": "[ADDRESS REDACTED]",
    }

    def __init__(self, hash_salt: str = ""):
        self.hash_salt = hash_salt
        self._compiled_patterns = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in self.PATTERNS.items()
        }

    def detect_pii(self, text: str) -> dict[str, list[str]]:
        """
        Detect PII in text.

        Returns:
            Dictionary of PII type -> list of found values
        """
        found = {}
        for pii_type, pattern in self._compiled_patterns.items():
            matches = pattern.findall(text)
            if matches:
                found[pii_type] = matches
        return found

    def mask_pii(self, text: str) -> str:
        """
        Mask all PII in text.

        Returns:
            Text with PII replaced by placeholders
        """
        result = text
        for pii_type, pattern in self._compiled_patterns.items():
            replacement = self.REPLACEMENT_MAP.get(pii_type, "[REDACTED]")
            result = pattern.sub(replacement, result)
        return result

    def hash_pii(self, value: str, pii_type: str = "generic") -> str:
        """
        Create a secure hash of PII for matching without storing raw value.

        Args:
            value: PII value to hash
            pii_type: Type of PII (for salt variation)

        Returns:
            Hex hash string
        """
        salted = f"{self.hash_salt}:{pii_type}:{value.lower().strip()}"
        return hashlib.sha256(salted.encode()).hexdigest()

    def mask_for_logging(self, data: dict) -> dict:
        """
        Mask PII in a dictionary for safe logging.

        Args:
            data: Dictionary potentially containing PII

        Returns:
            Dictionary with PII masked
        """
        sensitive_keys = {"phone", "email", "ssn", "address", "credit_card", "dob", "password"}

        def mask_value(key: str, value: Any) -> Any:
            if isinstance(value, dict):
                return {k: mask_value(k, v) for k, v in value.items()}
            elif isinstance(value, list):
                return [mask_value(key, v) for v in value]
            elif isinstance(value, str):
                key_lower = key.lower()
                if any(s in key_lower for s in sensitive_keys):
                    if "phone" in key_lower and len(value) > 4:
                        return f"***{value[-4:]}"
                    elif "email" in key_lower and "@" in value:
                        parts = value.split("@")
                        return f"{parts[0][:2]}***@{parts[1]}"
                    else:
                        return "***"
                return self.mask_pii(value)
            return value

        return {k: mask_value(k, v) for k, v in data.items()}


# ============================================================================
# AUDIT LOGGING
# ============================================================================


class AuditEventType(str, Enum):
    # Data access
    DATA_READ = "data_read"
    DATA_CREATE = "data_create"
    DATA_UPDATE = "data_update"
    DATA_DELETE = "data_delete"

    # Authentication
    AUTH_LOGIN = "auth_login"
    AUTH_LOGOUT = "auth_logout"
    AUTH_FAILED = "auth_failed"

    # Consent
    CONSENT_GRANTED = "consent_granted"
    CONSENT_DENIED = "consent_denied"
    CONSENT_WITHDRAWN = "consent_withdrawn"

    # Calls
    CALL_STARTED = "call_started"
    CALL_ENDED = "call_ended"
    CALL_RECORDED = "call_recorded"
    CALL_ESCALATED = "call_escalated"

    # Data export/deletion
    DATA_EXPORT = "data_export"
    DATA_DELETION_REQUEST = "data_deletion_request"
    DATA_DELETION_COMPLETED = "data_deletion_completed"


@dataclass
class AuditEvent:
    """Audit event record"""
    id: UUID
    tenant_id: UUID
    event_type: AuditEventType
    actor_type: str  # user, system, api
    actor_id: Optional[str]
    resource_type: str
    resource_id: Optional[str]
    action: str
    details: dict
    ip_address: Optional[str]
    user_agent: Optional[str]
    timestamp: datetime


class AuditLogger:
    """
    Audit logging for compliance and security.

    Logs all significant events for:
    - Security monitoring
    - Compliance reporting
    - Forensic analysis
    """

    def __init__(self, db_pool):
        self.db = db_pool
        self._pii_handler = PIIHandler()

    async def log(
        self,
        tenant_id: UUID,
        event_type: AuditEventType,
        resource_type: str,
        action: str,
        actor_type: str = "system",
        actor_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditEvent:
        """
        Log an audit event.

        Args:
            tenant_id: Tenant ID
            event_type: Type of event
            resource_type: Type of resource affected
            action: Action description
            actor_type: Who performed the action
            actor_id: ID of the actor
            resource_id: ID of the affected resource
            details: Additional details (will be PII-masked)
            ip_address: Client IP address
            user_agent: Client user agent
        """
        event_id = uuid4()
        now = datetime.now()

        # Mask PII in details
        safe_details = self._pii_handler.mask_for_logging(details or {})

        async with self.db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO voice_audit_logs (
                    id, tenant_id, event_type, actor_type, actor_id,
                    resource_type, resource_id, action, details,
                    ip_address, user_agent, timestamp
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                """,
                event_id,
                tenant_id,
                event_type.value,
                actor_type,
                actor_id,
                resource_type,
                resource_id,
                action,
                json.dumps(safe_details),
                ip_address,
                user_agent,
                now,
            )

        return AuditEvent(
            id=event_id,
            tenant_id=tenant_id,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            details=safe_details,
            ip_address=ip_address,
            user_agent=user_agent,
            timestamp=now,
        )

    async def get_audit_trail(
        self,
        tenant_id: UUID,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Get audit trail with filters"""
        conditions = ["tenant_id = $1"]
        params = [tenant_id]
        param_count = 2

        if resource_type:
            conditions.append(f"resource_type = ${param_count}")
            params.append(resource_type)
            param_count += 1

        if resource_id:
            conditions.append(f"resource_id = ${param_count}")
            params.append(resource_id)
            param_count += 1

        if event_type:
            conditions.append(f"event_type = ${param_count}")
            params.append(event_type.value)
            param_count += 1

        if start_date:
            conditions.append(f"timestamp >= ${param_count}")
            params.append(start_date)
            param_count += 1

        if end_date:
            conditions.append(f"timestamp <= ${param_count}")
            params.append(end_date)
            param_count += 1

        params.append(limit)

        async with self.db.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT * FROM voice_audit_logs
                WHERE {' AND '.join(conditions)}
                ORDER BY timestamp DESC
                LIMIT ${param_count}
                """,
                *params,
            )

            return [self._row_to_event(row) for row in rows]

    def _row_to_event(self, row: dict) -> AuditEvent:
        """Convert database row to AuditEvent"""
        return AuditEvent(
            id=row["id"],
            tenant_id=row["tenant_id"],
            event_type=AuditEventType(row["event_type"]),
            actor_type=row["actor_type"],
            actor_id=row["actor_id"],
            resource_type=row["resource_type"],
            resource_id=row["resource_id"],
            action=row["action"],
            details=json.loads(row["details"]) if row["details"] else {},
            ip_address=row["ip_address"],
            user_agent=row["user_agent"],
            timestamp=row["timestamp"],
        )


# ============================================================================
# DATA RETENTION
# ============================================================================


class DataRetentionManager:
    """
    Manages data retention policies.

    Handles:
    - Automatic data deletion after retention period
    - GDPR/CCPA deletion requests
    - Data export for portability
    """

    # Default retention periods (days)
    DEFAULT_RETENTION = {
        "call_recordings": 90,
        "transcripts": 365,
        "leads": 730,  # 2 years
        "audit_logs": 2555,  # 7 years
        "analytics": 365,
    }

    def __init__(self, db_pool, audit_logger: AuditLogger):
        self.db = db_pool
        self.audit = audit_logger

    async def get_retention_policy(self, tenant_id: UUID) -> dict:
        """Get retention policy for a tenant"""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT retention_policy FROM voice_tenants WHERE id = $1
                """,
                tenant_id,
            )

            if row and row["retention_policy"]:
                return json.loads(row["retention_policy"])

            return self.DEFAULT_RETENTION.copy()

    async def process_deletion_request(
        self,
        tenant_id: UUID,
        phone_number: Optional[str] = None,
        email: Optional[str] = None,
        request_type: str = "gdpr",  # gdpr, ccpa, manual
    ) -> dict:
        """
        Process a data deletion request (right to be forgotten).

        Args:
            tenant_id: Tenant ID
            phone_number: Phone number to delete data for
            email: Email to delete data for
            request_type: Type of deletion request

        Returns:
            Summary of deleted data
        """
        deleted_counts = {}

        async with self.db.acquire() as conn:
            # Find leads matching the criteria
            conditions = ["tenant_id = $1"]
            params = [tenant_id]
            param_count = 2

            if phone_number:
                conditions.append(f"phone = ${param_count}")
                params.append(phone_number)
                param_count += 1

            if email:
                conditions.append(f"email = ${param_count}")
                params.append(email)
                param_count += 1

            # Get lead IDs
            leads = await conn.fetch(
                f"""
                SELECT id FROM voice_leads
                WHERE {' AND '.join(conditions)}
                """,
                *params,
            )

            lead_ids = [row["id"] for row in leads]

            if lead_ids:
                # Delete calls and related data
                result = await conn.execute(
                    """
                    DELETE FROM voice_calls WHERE lead_id = ANY($1)
                    """,
                    lead_ids,
                )
                deleted_counts["calls"] = int(result.split()[-1])

                # Delete appointments
                result = await conn.execute(
                    """
                    DELETE FROM voice_appointments WHERE lead_id = ANY($1)
                    """,
                    lead_ids,
                )
                deleted_counts["appointments"] = int(result.split()[-1])

                # Delete notifications
                result = await conn.execute(
                    """
                    DELETE FROM voice_notifications WHERE lead_id = ANY($1)
                    """,
                    lead_ids,
                )
                deleted_counts["notifications"] = int(result.split()[-1])

                # Delete leads
                result = await conn.execute(
                    """
                    DELETE FROM voice_leads WHERE id = ANY($1)
                    """,
                    lead_ids,
                )
                deleted_counts["leads"] = int(result.split()[-1])

        # Log the deletion
        await self.audit.log(
            tenant_id=tenant_id,
            event_type=AuditEventType.DATA_DELETION_COMPLETED,
            resource_type="user_data",
            action=f"{request_type} deletion completed",
            details={
                "request_type": request_type,
                "deleted_counts": deleted_counts,
            },
        )

        logger.info(f"Processed {request_type} deletion request: {deleted_counts}")

        return deleted_counts

    async def export_user_data(
        self,
        tenant_id: UUID,
        phone_number: Optional[str] = None,
        email: Optional[str] = None,
    ) -> dict:
        """
        Export all data for a user (data portability).

        Returns:
            Dictionary containing all user data
        """
        export_data = {
            "export_date": datetime.now().isoformat(),
            "leads": [],
            "calls": [],
            "appointments": [],
            "consent_records": [],
        }

        async with self.db.acquire() as conn:
            # Get leads
            conditions = ["tenant_id = $1"]
            params = [tenant_id]
            param_count = 2

            if phone_number:
                conditions.append(f"phone = ${param_count}")
                params.append(phone_number)
                param_count += 1

            if email:
                conditions.append(f"email = ${param_count}")
                params.append(email)
                param_count += 1

            leads = await conn.fetch(
                f"""
                SELECT * FROM voice_leads
                WHERE {' AND '.join(conditions)}
                """,
                *params,
            )

            export_data["leads"] = [dict(row) for row in leads]
            lead_ids = [row["id"] for row in leads]

            if lead_ids:
                # Get calls
                calls = await conn.fetch(
                    """
                    SELECT * FROM voice_calls WHERE lead_id = ANY($1)
                    """,
                    lead_ids,
                )
                export_data["calls"] = [dict(row) for row in calls]

                # Get appointments
                appointments = await conn.fetch(
                    """
                    SELECT * FROM voice_appointments WHERE lead_id = ANY($1)
                    """,
                    lead_ids,
                )
                export_data["appointments"] = [dict(row) for row in appointments]

            # Get consent records
            if phone_number:
                consent = await conn.fetch(
                    """
                    SELECT * FROM voice_consent_records
                    WHERE tenant_id = $1 AND phone_number = $2
                    """,
                    tenant_id,
                    phone_number,
                )
                export_data["consent_records"] = [dict(row) for row in consent]

        # Log the export
        await self.audit.log(
            tenant_id=tenant_id,
            event_type=AuditEventType.DATA_EXPORT,
            resource_type="user_data",
            action="Data export completed",
            details={
                "record_counts": {
                    k: len(v) for k, v in export_data.items()
                    if isinstance(v, list)
                },
            },
        )

        return export_data
