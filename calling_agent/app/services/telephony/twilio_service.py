"""
Twilio Telephony Service
Handles phone call operations using Twilio API
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream

from app.core.config import settings
from app.core.logging import get_logger
from app.models.call import CallStatus

logger = get_logger(__name__)


class TwilioService:
    """Service for interacting with Twilio API"""

    def __init__(self):
        self.account_sid = settings.twilio_account_sid
        self.auth_token = settings.twilio_auth_token
        self.phone_number = settings.twilio_phone_number
        self.api_base_url = settings.api_base_url

        self.client = Client(self.account_sid, self.auth_token)

    async def initiate_call(
        self,
        to_number: str,
        twiml_url: Optional[str] = None,
        status_callback_url: Optional[str] = None,
        record: bool = False,
        machine_detection: bool = False,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Initiate an outbound call

        Args:
            to_number: Phone number to call (E.164 format)
            twiml_url: URL to fetch TwiML instructions
            status_callback_url: URL for call status updates
            record: Whether to record the call
            machine_detection: Enable answering machine detection
            timeout: Ring timeout in seconds

        Returns:
            Call information including SID
        """
        logger.info(f"Initiating call to {to_number}")

        try:
            call_params = {
                "to": to_number,
                "from_": self.phone_number,
                "timeout": timeout
            }

            if twiml_url:
                call_params["url"] = twiml_url
            else:
                # Default TwiML that will be overridden
                call_params["url"] = f"{self.api_base_url}/api/v1/webhooks/twilio/voice"

            if status_callback_url:
                call_params["status_callback"] = status_callback_url
                call_params["status_callback_event"] = [
                    "initiated", "ringing", "answered", "completed"
                ]
            else:
                call_params["status_callback"] = f"{self.api_base_url}/api/v1/webhooks/twilio/status"
                call_params["status_callback_event"] = [
                    "initiated", "ringing", "answered", "completed"
                ]

            if record:
                call_params["record"] = True

            if machine_detection:
                call_params["machine_detection"] = "Enable"
                call_params["async_amd"] = True
                call_params["async_amd_status_callback"] = f"{self.api_base_url}/api/v1/webhooks/twilio/amd"

            call = self.client.calls.create(**call_params)

            logger.info(f"Call initiated successfully: {call.sid}")
            return {
                "success": True,
                "call_sid": call.sid,
                "status": call.status,
                "to": call.to,
                "from": call.from_,
                "direction": call.direction,
                "created_at": datetime.utcnow().isoformat()
            }

        except TwilioRestException as e:
            logger.error(f"Twilio API error: {e.code} - {e.msg}")
            return {
                "success": False,
                "error": f"Twilio error: {e.msg}",
                "code": e.code
            }
        except Exception as e:
            logger.error(f"Failed to initiate call: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_call(self, call_sid: str) -> Dict[str, Any]:
        """
        Get information about a call

        Args:
            call_sid: Twilio call SID

        Returns:
            Call information
        """
        try:
            call = self.client.calls(call_sid).fetch()
            return {
                "success": True,
                "call_sid": call.sid,
                "status": call.status,
                "to": call.to,
                "from": call.from_,
                "direction": call.direction,
                "duration": call.duration,
                "start_time": str(call.start_time) if call.start_time else None,
                "end_time": str(call.end_time) if call.end_time else None
            }
        except TwilioRestException as e:
            logger.error(f"Failed to get call: {e.msg}")
            return {
                "success": False,
                "error": e.msg
            }
        except Exception as e:
            logger.error(f"Error getting call: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def end_call(self, call_sid: str) -> Dict[str, Any]:
        """
        End an active call

        Args:
            call_sid: Twilio call SID

        Returns:
            Result of the operation
        """
        logger.info(f"Ending call: {call_sid}")

        try:
            call = self.client.calls(call_sid).update(status="completed")
            return {
                "success": True,
                "call_sid": call.sid,
                "status": call.status,
                "message": "Call ended successfully"
            }
        except TwilioRestException as e:
            logger.error(f"Failed to end call: {e.msg}")
            return {
                "success": False,
                "error": e.msg
            }
        except Exception as e:
            logger.error(f"Error ending call: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def update_call(
        self,
        call_sid: str,
        twiml_url: Optional[str] = None,
        twiml: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update an in-progress call with new TwiML

        Args:
            call_sid: Twilio call SID
            twiml_url: URL to fetch new TwiML
            twiml: TwiML string directly

        Returns:
            Result of the operation
        """
        try:
            update_params = {}
            if twiml_url:
                update_params["url"] = twiml_url
            if twiml:
                update_params["twiml"] = twiml

            call = self.client.calls(call_sid).update(**update_params)
            return {
                "success": True,
                "call_sid": call.sid,
                "status": call.status
            }
        except TwilioRestException as e:
            logger.error(f"Failed to update call: {e.msg}")
            return {
                "success": False,
                "error": e.msg
            }
        except Exception as e:
            logger.error(f"Error updating call: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def list_calls(
        self,
        status: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        List recent calls

        Args:
            status: Filter by call status
            limit: Maximum number of calls to return

        Returns:
            List of calls
        """
        try:
            params = {"limit": limit}
            if status:
                params["status"] = status

            calls = self.client.calls.list(**params)
            call_list = []
            for call in calls:
                call_list.append({
                    "call_sid": call.sid,
                    "status": call.status,
                    "to": call.to,
                    "from": call.from_,
                    "direction": call.direction,
                    "duration": call.duration,
                    "start_time": str(call.start_time) if call.start_time else None
                })

            return {
                "success": True,
                "calls": call_list,
                "count": len(call_list)
            }
        except TwilioRestException as e:
            logger.error(f"Failed to list calls: {e.msg}")
            return {
                "success": False,
                "error": e.msg
            }
        except Exception as e:
            logger.error(f"Error listing calls: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def generate_connect_twiml(
        self,
        ultravox_join_url: str,
        greeting: Optional[str] = None
    ) -> str:
        """
        Generate TwiML to connect call to Ultravox

        Args:
            ultravox_join_url: WebSocket URL from Ultravox
            greeting: Optional greeting message before connecting

        Returns:
            TwiML string
        """
        response = VoiceResponse()

        if greeting:
            response.say(greeting, voice="Polly.Matthew")

        connect = Connect()
        stream = Stream(url=ultravox_join_url)
        connect.append(stream)
        response.append(connect)

        return str(response)

    def generate_hangup_twiml(self, message: Optional[str] = None) -> str:
        """
        Generate TwiML to hang up a call

        Args:
            message: Optional message before hanging up

        Returns:
            TwiML string
        """
        response = VoiceResponse()

        if message:
            response.say(message, voice="Polly.Matthew")

        response.hangup()
        return str(response)

    def generate_hold_twiml(
        self,
        hold_music_url: Optional[str] = None,
        message: Optional[str] = None
    ) -> str:
        """
        Generate TwiML to put caller on hold

        Args:
            hold_music_url: URL to hold music
            message: Message to play

        Returns:
            TwiML string
        """
        response = VoiceResponse()

        if message:
            response.say(message, voice="Polly.Matthew")

        if hold_music_url:
            response.play(hold_music_url, loop=0)
        else:
            # Default hold music
            response.play(
                "http://com.twilio.sounds.music.s3.amazonaws.com/MARKOVICHAMP-B8766.mp3",
                loop=0
            )

        return str(response)

    @staticmethod
    def map_twilio_status(twilio_status: str) -> CallStatus:
        """
        Map Twilio call status to internal CallStatus

        Args:
            twilio_status: Status from Twilio

        Returns:
            Internal CallStatus enum
        """
        status_mapping = {
            "queued": CallStatus.PENDING,
            "initiated": CallStatus.INITIATING,
            "ringing": CallStatus.RINGING,
            "in-progress": CallStatus.IN_PROGRESS,
            "completed": CallStatus.COMPLETED,
            "failed": CallStatus.FAILED,
            "no-answer": CallStatus.NO_ANSWER,
            "busy": CallStatus.BUSY,
            "canceled": CallStatus.CANCELLED
        }
        return status_mapping.get(twilio_status.lower(), CallStatus.PENDING)

    async def send_sms(
        self,
        to_number: str,
        message: str
    ) -> Dict[str, Any]:
        """
        Send an SMS message

        Args:
            to_number: Recipient phone number
            message: Message text

        Returns:
            Result of the operation
        """
        try:
            sms = self.client.messages.create(
                body=message,
                from_=self.phone_number,
                to=to_number
            )
            return {
                "success": True,
                "message_sid": sms.sid,
                "status": sms.status
            }
        except TwilioRestException as e:
            logger.error(f"Failed to send SMS: {e.msg}")
            return {
                "success": False,
                "error": e.msg
            }
        except Exception as e:
            logger.error(f"Error sending SMS: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
