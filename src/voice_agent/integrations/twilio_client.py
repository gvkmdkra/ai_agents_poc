"""
Twilio Integration Client

Handles:
- Voice calls (inbound/outbound)
- SMS messaging
- WhatsApp messaging
- Media streams for real-time audio
- Call recording and transcription
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlencode

from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream, Gather
from twilio.twiml.messaging_response import MessagingResponse
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)


@dataclass
class TwilioConfig:
    """Twilio configuration"""

    account_sid: str
    auth_token: str
    # Webhook URLs
    voice_answer_url: str
    voice_status_url: str
    voice_fallback_url: str
    media_stream_url: str  # WebSocket URL for real-time audio
    # Default settings
    default_caller_id: Optional[str] = None
    recording_enabled: bool = True
    transcription_enabled: bool = True


class TwilioClient:
    """
    Twilio client for voice, SMS, and WhatsApp communications.

    Supports:
    - Programmable Voice for inbound/outbound calls
    - Media Streams for real-time audio processing
    - SMS and WhatsApp messaging
    - Call recording with transcription
    """

    def __init__(self, config: TwilioConfig):
        self.config = config
        self.client = Client(config.account_sid, config.auth_token)
        logger.info("TwilioClient initialized")

    # =========================================================================
    # VOICE CALLS
    # =========================================================================

    async def initiate_outbound_call(
        self,
        to_number: str,
        from_number: str,
        tenant_id: str,
        lead_id: Optional[str] = None,
        voice_config_id: Optional[str] = None,
        custom_params: Optional[dict] = None,
    ) -> dict[str, Any]:
        """
        Initiate an outbound AI voice call.

        Args:
            to_number: Destination phone number (E.164 format)
            from_number: Caller ID (must be a verified Twilio number)
            tenant_id: Tenant identifier for routing
            lead_id: Optional lead ID for context
            voice_config_id: Optional voice configuration ID
            custom_params: Additional parameters to pass to webhook

        Returns:
            Call details including SID and status
        """
        try:
            # Build webhook URL with parameters
            params = {
                "tenant_id": tenant_id,
                "direction": "outbound",
            }
            if lead_id:
                params["lead_id"] = lead_id
            if voice_config_id:
                params["voice_config_id"] = voice_config_id
            if custom_params:
                params.update(custom_params)

            answer_url = f"{self.config.voice_answer_url}?{urlencode(params)}"
            status_url = f"{self.config.voice_status_url}?{urlencode(params)}"

            # Create the call
            call = await asyncio.to_thread(
                self.client.calls.create,
                to=to_number,
                from_=from_number,
                url=answer_url,
                status_callback=status_url,
                status_callback_event=["initiated", "ringing", "answered", "completed"],
                status_callback_method="POST",
                record=self.config.recording_enabled,
                recording_status_callback=f"{self.config.voice_status_url}/recording",
                recording_status_callback_event=["completed"],
                machine_detection="Enable",
                machine_detection_timeout=5,
            )

            logger.info(f"Outbound call initiated: {call.sid} to {to_number}")

            return {
                "call_sid": call.sid,
                "status": call.status,
                "direction": "outbound",
                "from_number": from_number,
                "to_number": to_number,
            }

        except TwilioRestException as e:
            logger.error(f"Failed to initiate outbound call: {e}")
            raise

    def generate_answer_twiml(
        self,
        tenant_id: str,
        voice_config_id: Optional[str] = None,
        call_sid: Optional[str] = None,
        greeting_text: Optional[str] = None,
    ) -> str:
        """
        Generate TwiML response for answering a call with Media Streams.

        This connects the call to a WebSocket for real-time audio processing
        with Ultravox.

        Args:
            tenant_id: Tenant identifier
            voice_config_id: Voice configuration ID
            call_sid: Twilio call SID
            greeting_text: Optional initial greeting (if not using streaming)

        Returns:
            TwiML XML string
        """
        response = VoiceResponse()

        # Add a brief pause for call connection
        response.pause(length=1)

        # Connect to Media Stream for real-time audio
        connect = Connect()

        # Build stream URL with parameters
        stream_params = {
            "tenant_id": tenant_id,
        }
        if voice_config_id:
            stream_params["voice_config_id"] = voice_config_id
        if call_sid:
            stream_params["call_sid"] = call_sid

        stream_url = f"{self.config.media_stream_url}?{urlencode(stream_params)}"

        stream = Stream(url=stream_url)
        stream.parameter(name="tenant_id", value=tenant_id)
        if voice_config_id:
            stream.parameter(name="voice_config_id", value=voice_config_id)
        if call_sid:
            stream.parameter(name="call_sid", value=call_sid)

        connect.append(stream)
        response.append(connect)

        return str(response)

    def generate_fallback_twiml(
        self,
        message: str = "We're sorry, but we're experiencing technical difficulties. Please try again later.",
        voice: str = "Polly.Joanna",
    ) -> str:
        """
        Generate fallback TwiML for error scenarios.

        Args:
            message: Error message to play
            voice: Twilio voice to use

        Returns:
            TwiML XML string
        """
        response = VoiceResponse()
        response.say(message, voice=voice)
        response.hangup()
        return str(response)

    def generate_voicemail_twiml(
        self,
        greeting: str,
        recording_callback_url: str,
        max_length: int = 120,
        voice: str = "Polly.Joanna",
    ) -> str:
        """
        Generate TwiML for voicemail recording.

        Args:
            greeting: Voicemail greeting message
            recording_callback_url: URL to receive recording
            max_length: Maximum recording length in seconds
            voice: Twilio voice to use

        Returns:
            TwiML XML string
        """
        response = VoiceResponse()
        response.say(greeting, voice=voice)
        response.record(
            max_length=max_length,
            recording_status_callback=recording_callback_url,
            recording_status_callback_event="completed",
            transcribe=self.config.transcription_enabled,
            play_beep=True,
        )
        response.say("Thank you for your message. Goodbye.", voice=voice)
        response.hangup()
        return str(response)

    def generate_transfer_twiml(
        self,
        transfer_to: str,
        whisper_message: Optional[str] = None,
        caller_id: Optional[str] = None,
    ) -> str:
        """
        Generate TwiML for warm transfer to human agent.

        Args:
            transfer_to: Phone number to transfer to
            whisper_message: Message to play to agent before connecting
            caller_id: Caller ID for the transfer

        Returns:
            TwiML XML string
        """
        response = VoiceResponse()

        dial = response.dial(
            caller_id=caller_id or self.config.default_caller_id,
            timeout=30,
            action=f"{self.config.voice_status_url}/transfer-complete",
        )

        if whisper_message:
            dial.number(
                transfer_to,
                url=f"{self.config.voice_answer_url}/whisper?message={whisper_message}",
            )
        else:
            dial.number(transfer_to)

        return str(response)

    async def get_call(self, call_sid: str) -> dict[str, Any]:
        """
        Get call details by SID.

        Args:
            call_sid: Twilio call SID

        Returns:
            Call details
        """
        try:
            call = await asyncio.to_thread(
                self.client.calls(call_sid).fetch
            )

            return {
                "call_sid": call.sid,
                "status": call.status,
                "direction": call.direction,
                "from_number": call.from_,
                "to_number": call.to,
                "duration": call.duration,
                "start_time": call.start_time,
                "end_time": call.end_time,
            }

        except TwilioRestException as e:
            logger.error(f"Failed to get call {call_sid}: {e}")
            raise

    async def end_call(self, call_sid: str) -> dict[str, Any]:
        """
        End an active call.

        Args:
            call_sid: Twilio call SID

        Returns:
            Updated call details
        """
        try:
            call = await asyncio.to_thread(
                self.client.calls(call_sid).update,
                status="completed",
            )

            logger.info(f"Call ended: {call_sid}")

            return {
                "call_sid": call.sid,
                "status": call.status,
            }

        except TwilioRestException as e:
            logger.error(f"Failed to end call {call_sid}: {e}")
            raise

    # =========================================================================
    # SMS & WHATSAPP
    # =========================================================================

    async def send_sms(
        self,
        to_number: str,
        from_number: str,
        body: str,
        status_callback: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Send an SMS message.

        Args:
            to_number: Recipient phone number
            from_number: Sender phone number (Twilio number)
            body: Message content
            status_callback: Optional webhook for delivery status

        Returns:
            Message details
        """
        try:
            message = await asyncio.to_thread(
                self.client.messages.create,
                to=to_number,
                from_=from_number,
                body=body,
                status_callback=status_callback,
            )

            logger.info(f"SMS sent: {message.sid} to {to_number}")

            return {
                "message_sid": message.sid,
                "status": message.status,
                "to": to_number,
                "from": from_number,
            }

        except TwilioRestException as e:
            logger.error(f"Failed to send SMS: {e}")
            raise

    async def send_whatsapp(
        self,
        to_number: str,
        from_number: str,
        body: str,
        media_url: Optional[str] = None,
        template_sid: Optional[str] = None,
        template_variables: Optional[dict] = None,
        status_callback: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Send a WhatsApp message.

        Args:
            to_number: Recipient phone number (without 'whatsapp:' prefix)
            from_number: Sender WhatsApp number (without 'whatsapp:' prefix)
            body: Message content
            media_url: Optional media URL to include
            template_sid: Optional template SID for template messages
            template_variables: Variables for template
            status_callback: Optional webhook for delivery status

        Returns:
            Message details
        """
        try:
            # Add WhatsApp prefix
            to_whatsapp = f"whatsapp:{to_number}"
            from_whatsapp = f"whatsapp:{from_number}"

            create_params = {
                "to": to_whatsapp,
                "from_": from_whatsapp,
                "status_callback": status_callback,
            }

            if template_sid:
                create_params["content_sid"] = template_sid
                if template_variables:
                    create_params["content_variables"] = template_variables
            else:
                create_params["body"] = body

            if media_url:
                create_params["media_url"] = [media_url]

            message = await asyncio.to_thread(
                self.client.messages.create,
                **create_params,
            )

            logger.info(f"WhatsApp sent: {message.sid} to {to_number}")

            return {
                "message_sid": message.sid,
                "status": message.status,
                "to": to_number,
                "from": from_number,
            }

        except TwilioRestException as e:
            logger.error(f"Failed to send WhatsApp: {e}")
            raise

    # =========================================================================
    # PHONE NUMBER MANAGEMENT
    # =========================================================================

    async def list_phone_numbers(self) -> list[dict[str, Any]]:
        """
        List all phone numbers in the account.

        Returns:
            List of phone number details
        """
        try:
            numbers = await asyncio.to_thread(
                self.client.incoming_phone_numbers.list
            )

            return [
                {
                    "sid": num.sid,
                    "phone_number": num.phone_number,
                    "friendly_name": num.friendly_name,
                    "capabilities": {
                        "voice": num.capabilities.get("voice", False),
                        "sms": num.capabilities.get("sms", False),
                        "mms": num.capabilities.get("mms", False),
                    },
                }
                for num in numbers
            ]

        except TwilioRestException as e:
            logger.error(f"Failed to list phone numbers: {e}")
            raise

    async def configure_phone_number(
        self,
        phone_number_sid: str,
        voice_url: str,
        voice_fallback_url: str,
        sms_url: Optional[str] = None,
        status_callback_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Configure webhooks for a phone number.

        Args:
            phone_number_sid: Twilio phone number SID
            voice_url: URL for incoming voice calls
            voice_fallback_url: Fallback URL if primary fails
            sms_url: Optional URL for incoming SMS
            status_callback_url: Optional status callback URL

        Returns:
            Updated phone number details
        """
        try:
            update_params = {
                "voice_url": voice_url,
                "voice_fallback_url": voice_fallback_url,
                "voice_method": "POST",
                "voice_fallback_method": "POST",
            }

            if sms_url:
                update_params["sms_url"] = sms_url
                update_params["sms_method"] = "POST"

            if status_callback_url:
                update_params["status_callback"] = status_callback_url
                update_params["status_callback_method"] = "POST"

            number = await asyncio.to_thread(
                self.client.incoming_phone_numbers(phone_number_sid).update,
                **update_params,
            )

            logger.info(f"Phone number configured: {number.phone_number}")

            return {
                "sid": number.sid,
                "phone_number": number.phone_number,
                "voice_url": number.voice_url,
                "sms_url": number.sms_url,
            }

        except TwilioRestException as e:
            logger.error(f"Failed to configure phone number: {e}")
            raise

    # =========================================================================
    # RECORDINGS
    # =========================================================================

    async def get_recording(self, recording_sid: str) -> dict[str, Any]:
        """
        Get recording details and URL.

        Args:
            recording_sid: Twilio recording SID

        Returns:
            Recording details with download URL
        """
        try:
            recording = await asyncio.to_thread(
                self.client.recordings(recording_sid).fetch
            )

            return {
                "recording_sid": recording.sid,
                "call_sid": recording.call_sid,
                "duration": recording.duration,
                "status": recording.status,
                "url": f"https://api.twilio.com{recording.uri.replace('.json', '.mp3')}",
            }

        except TwilioRestException as e:
            logger.error(f"Failed to get recording: {e}")
            raise

    async def delete_recording(self, recording_sid: str) -> bool:
        """
        Delete a recording.

        Args:
            recording_sid: Twilio recording SID

        Returns:
            True if deleted successfully
        """
        try:
            await asyncio.to_thread(
                self.client.recordings(recording_sid).delete
            )

            logger.info(f"Recording deleted: {recording_sid}")
            return True

        except TwilioRestException as e:
            logger.error(f"Failed to delete recording: {e}")
            raise

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def validate_webhook_signature(
        self,
        signature: str,
        url: str,
        params: dict,
    ) -> bool:
        """
        Validate Twilio webhook signature for security.

        Args:
            signature: X-Twilio-Signature header value
            url: Full webhook URL
            params: Request parameters

        Returns:
            True if signature is valid
        """
        from twilio.request_validator import RequestValidator

        validator = RequestValidator(self.config.auth_token)
        return validator.validate(url, params, signature)
