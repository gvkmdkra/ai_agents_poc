"""
Utility Functions

Common helpers for the voice agent system.
"""

import re
import secrets
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo


def normalize_phone_number(phone: str) -> str:
    """
    Normalize a phone number to E.164 format.

    Examples:
        "(555) 123-4567" -> "+15551234567"
        "555.123.4567" -> "+15551234567"
        "+1 555 123 4567" -> "+15551234567"

    Args:
        phone: Phone number in any format

    Returns:
        Normalized E.164 format phone number
    """
    # Remove all non-digit characters except leading +
    if phone.startswith("+"):
        cleaned = "+" + re.sub(r"[^\d]", "", phone[1:])
    else:
        cleaned = re.sub(r"[^\d]", "", phone)

    # If no country code, assume US (+1)
    if not cleaned.startswith("+"):
        if len(cleaned) == 10:
            cleaned = "+1" + cleaned
        elif len(cleaned) == 11 and cleaned.startswith("1"):
            cleaned = "+" + cleaned
        else:
            # Just add + for international numbers
            cleaned = "+" + cleaned

    return cleaned


def format_phone_number(phone: str, format_type: str = "national") -> str:
    """
    Format a phone number for display.

    Args:
        phone: E.164 format phone number
        format_type: "national", "international", or "e164"

    Returns:
        Formatted phone number
    """
    # Normalize first
    normalized = normalize_phone_number(phone)

    if format_type == "e164":
        return normalized

    # Extract country code and number
    if normalized.startswith("+1") and len(normalized) == 12:
        # US number
        number = normalized[2:]
        if format_type == "national":
            return f"({number[:3]}) {number[3:6]}-{number[6:]}"
        else:
            return f"+1 ({number[:3]}) {number[3:6]}-{number[6:]}"

    # For other countries, just format with spaces
    if format_type == "international":
        return normalized
    else:
        # Remove country code for national
        return normalized.lstrip("+")


def parse_datetime(
    date_str: str,
    timezone: str = "UTC",
    formats: Optional[list[str]] = None,
) -> Optional[datetime]:
    """
    Parse a datetime string with multiple format support.

    Args:
        date_str: Date/time string to parse
        timezone: Timezone to apply
        formats: List of formats to try

    Returns:
        Parsed datetime or None
    """
    if not date_str:
        return None

    default_formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
    ]

    formats = formats or default_formats
    tz = ZoneInfo(timezone)

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            # Apply timezone if naive
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tz)
            return dt
        except ValueError:
            continue

    return None


def generate_meeting_link(
    provider: str = "google_meet",
    meeting_id: Optional[str] = None,
) -> str:
    """
    Generate a video meeting link.

    Args:
        provider: "google_meet", "zoom", "teams"
        meeting_id: Optional custom meeting ID

    Returns:
        Meeting URL
    """
    if not meeting_id:
        meeting_id = secrets.token_urlsafe(8)

    if provider == "google_meet":
        # Format: xxx-xxxx-xxx
        formatted_id = f"{meeting_id[:3]}-{meeting_id[3:7]}-{meeting_id[7:10]}"
        return f"https://meet.google.com/{formatted_id}"

    elif provider == "zoom":
        # Numeric meeting ID
        numeric_id = "".join(filter(str.isdigit, meeting_id))[:10] or secrets.randbelow(9000000000) + 1000000000
        return f"https://zoom.us/j/{numeric_id}"

    elif provider == "teams":
        return f"https://teams.microsoft.com/l/meetup-join/{meeting_id}"

    else:
        # Generic
        return f"https://meet.example.com/{meeting_id}"


def calculate_time_slots(
    start_time: datetime,
    end_time: datetime,
    duration_minutes: int = 30,
    break_minutes: int = 0,
) -> list[dict[str, datetime]]:
    """
    Calculate available time slots between two times.

    Args:
        start_time: Start of availability window
        end_time: End of availability window
        duration_minutes: Duration of each slot
        break_minutes: Break between slots

    Returns:
        List of slot dictionaries with start/end times
    """
    slots = []
    current = start_time
    slot_duration = timedelta(minutes=duration_minutes)
    break_duration = timedelta(minutes=break_minutes)

    while current + slot_duration <= end_time:
        slots.append({
            "start": current,
            "end": current + slot_duration,
        })
        current += slot_duration + break_duration

    return slots


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add when truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix


def mask_phone_number(phone: str, visible_digits: int = 4) -> str:
    """
    Mask a phone number for privacy.

    Args:
        phone: Phone number to mask
        visible_digits: Number of digits to show at end

    Returns:
        Masked phone number (e.g., "***-***-1234")
    """
    normalized = normalize_phone_number(phone)
    if len(normalized) <= visible_digits:
        return normalized

    masked_part = "*" * (len(normalized) - visible_digits - 1)  # -1 for +
    return "+" + masked_part + normalized[-visible_digits:]


def sanitize_for_tts(text: str) -> str:
    """
    Sanitize text for text-to-speech.

    Removes or replaces characters that cause TTS issues.

    Args:
        text: Text to sanitize

    Returns:
        Sanitized text
    """
    # Replace common problematic patterns
    replacements = {
        "&": " and ",
        "@": " at ",
        "#": " number ",
        "%": " percent ",
        "$": " dollars ",
        "+": " plus ",
        "=": " equals ",
        "<": " less than ",
        ">": " greater than ",
        "/": " slash ",
        "\\": " ",
        "_": " ",
        "|": " ",
        "~": " ",
        "`": "",
        "\"": "",
        "'": "",
    }

    result = text
    for char, replacement in replacements.items():
        result = result.replace(char, replacement)

    # Remove multiple spaces
    result = re.sub(r"\s+", " ", result)

    return result.strip()


def format_duration(seconds: int) -> str:
    """
    Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "5m 30s", "1h 15m")
    """
    if seconds < 60:
        return f"{seconds}s"

    minutes = seconds // 60
    remaining_seconds = seconds % 60

    if minutes < 60:
        if remaining_seconds:
            return f"{minutes}m {remaining_seconds}s"
        return f"{minutes}m"

    hours = minutes // 60
    remaining_minutes = minutes % 60

    if remaining_minutes:
        return f"{hours}h {remaining_minutes}m"
    return f"{hours}h"


def extract_name_from_email(email: str) -> Optional[str]:
    """
    Extract a name from an email address.

    Args:
        email: Email address

    Returns:
        Extracted name or None
    """
    if not email or "@" not in email:
        return None

    local_part = email.split("@")[0]

    # Replace common separators with spaces
    name = re.sub(r"[._-]", " ", local_part)

    # Capitalize each word
    name = " ".join(word.capitalize() for word in name.split())

    # Filter out numeric-only parts
    parts = [p for p in name.split() if not p.isdigit()]

    return " ".join(parts) if parts else None
