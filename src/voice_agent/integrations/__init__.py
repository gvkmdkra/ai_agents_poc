"""Voice Agent Integrations"""

from .twilio_client import TwilioClient
from .ultravox_client import UltravoxClient
from .odoo_client import OdooCRMClient
from .openai_client import OpenAIVoiceClient

__all__ = [
    "TwilioClient",
    "UltravoxClient",
    "OdooCRMClient",
    "OpenAIVoiceClient",
]
