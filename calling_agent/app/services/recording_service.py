"""
Recording Service
Downloads and processes call recordings from Twilio
Includes transcription via Whisper and speaker diarization via GPT-4
"""

import os
import time
import tempfile
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

import requests
from openai import OpenAI

from app.core.config import settings
from app.core.logging import get_logger
from app.core.exceptions import ServiceError

logger = get_logger(__name__)


class RecordingService:
    """
    Service for downloading and processing call recordings
    - Downloads recordings from Twilio
    - Transcribes audio using OpenAI Whisper
    - Performs speaker diarization using GPT-4
    - Generates structured summaries
    """

    def __init__(self):
        self.openai_client = OpenAI(api_key=settings.openai_api_key)
        self.recordings_dir = Path(settings.recordings_dir)
        self.transcripts_dir = Path(settings.transcripts_dir)
        self.summaries_dir = Path(settings.summaries_dir)

        # Create directories if they don't exist
        for directory in [self.recordings_dir, self.transcripts_dir, self.summaries_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    def _debug_log(self, message: str, start_time: Optional[float] = None) -> float:
        """Enhanced debug logging with timestamps and elapsed time"""
        current_time = time.time()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        if start_time:
            elapsed = current_time - start_time
            logger.debug(f"[{timestamp}] [{elapsed:.3f}s elapsed] {message}")
        else:
            logger.debug(f"[{timestamp}] {message}")
        return current_time

    async def download_recording(
        self,
        call_sid: str,
        recording_sid: str,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None
    ) -> Optional[str]:
        """
        Download a recording from Twilio

        Args:
            call_sid: Twilio call SID
            recording_sid: Twilio recording SID
            account_sid: Optional Twilio account SID (uses settings if not provided)
            auth_token: Optional Twilio auth token (uses settings if not provided)

        Returns:
            Path to downloaded file or None if failed
        """
        start_time = self._debug_log(f"Starting recording download for call {call_sid}")

        try:
            account_sid = account_sid or settings.twilio_account_sid
            auth_token = auth_token or settings.twilio_auth_token

            recording_url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Recordings/{recording_sid}.wav"

            self._debug_log(f"Downloading from {recording_url}")

            response = requests.get(
                recording_url,
                auth=(account_sid, auth_token),
                stream=True,
                timeout=60
            )
            response.raise_for_status()

            audio_file_path = self.recordings_dir / f"recording_{call_sid}_{recording_sid}.wav"

            with open(audio_file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            self._debug_log(f"Recording downloaded to {audio_file_path}", start_time)
            return str(audio_file_path)

        except Exception as e:
            self._debug_log(f"Recording download error: {e}", start_time)
            logger.error(f"Failed to download recording: {e}")
            return None

    async def transcribe_audio(self, audio_file_path: str) -> Optional[str]:
        """
        Transcribe audio using OpenAI Whisper

        Args:
            audio_file_path: Path to the audio file

        Returns:
            Transcription text or None if failed
        """
        start_time = self._debug_log(f"Starting transcription for {audio_file_path}")

        try:
            if not os.path.exists(audio_file_path):
                self._debug_log(f"Audio file not found: {audio_file_path}")
                return None

            self._debug_log("Starting Whisper transcription")

            with open(audio_file_path, "rb") as audio_file:
                transcription = self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )

            self._debug_log(f"Whisper transcription completed", start_time)
            return transcription

        except Exception as e:
            self._debug_log(f"Transcription error: {e}", start_time)
            logger.error(f"Failed to transcribe audio: {e}")
            return None

    async def format_transcript_with_speakers(
        self,
        raw_transcription: str,
        phone_number: str,
        agent_name: str = "Agent"
    ) -> Optional[str]:
        """
        Format transcription with speaker labels using GPT-4

        Args:
            raw_transcription: Raw transcription text
            phone_number: Caller's phone number
            agent_name: Name of the AI agent

        Returns:
            Formatted transcript with speaker labels
        """
        if not raw_transcription:
            return None

        start_time = self._debug_log("Assigning speaker labels using GPT-4...")

        try:
            prompt = f"""
            Below is a raw transcript of a conversation between an Agent named {agent_name} and a Caller with the phone number {phone_number}.
            The Agent is conducting a structured phone conversation.

            Your task is to:
            1. Split the transcript into sentences.
            2. Assign speaker labels to each sentence: "Agent" for {agent_name}, "Caller" for the other party.
            3. Identify and flag any vague or unclear responses with a note in square brackets.
            4. Return the formatted transcript with each line in the format: "Speaker: Sentence"

            Raw Transcript:
            {raw_transcription}

            Example Output Format:
            Agent: Hello, this is {agent_name}.
            Caller: Hi, {agent_name}.
            Agent: Is this a good time to speak?
            Caller: Yes, we can discuss.
            """

            self._debug_log("Starting GPT-4 speaker diarization")

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert in speaker diarization. Assign speaker labels to each sentence in the transcript based on context and conversational patterns."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.3
            )

            formatted_transcript = response.choices[0].message.content.strip()
            self._debug_log("GPT-4 speaker diarization completed", start_time)

            return formatted_transcript

        except Exception as e:
            self._debug_log(f"GPT-4 diarization error: {e}", start_time)
            logger.error(f"Failed to format transcript: {e}")
            # Fallback: return raw transcription
            return raw_transcription

    async def generate_summary(
        self,
        transcription: str,
        client_name: str,
        purpose: str
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a structured summary of the call using GPT-4

        Args:
            transcription: Call transcription
            client_name: Client/organization name
            purpose: Purpose of the call

        Returns:
            Structured summary as a dictionary
        """
        start_time = self._debug_log("Generating summary with GPT-4")

        try:
            if not transcription:
                self._debug_log("No transcription available for summary")
                return None

            current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            prompt = f"""
            Create a structured summary of the following call transcription.
            Client Name: {client_name}
            Purpose: {purpose}
            Transcription: {transcription}

            Return a JSON object with the following structure:
            {{
                "call_timestamp": "{current_timestamp}",
                "client_name": "{client_name}",
                "purpose": "{purpose}",
                "summary": "A brief summary of the call (2-3 sentences)",
                "key_points": ["Key point 1", "Key point 2", ...],
                "action_items": ["Action item 1", ...],
                "issues": ["Issue 1", ...],
                "sentiment": "positive/neutral/negative"
            }}

            Highlight any unclear or incomplete responses in the "issues" field.
            """

            self._debug_log("Starting GPT-4 summary generation")

            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "Generate a concise and accurate summary in JSON format based on the provided transcription and call details."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.5
            )

            import json
            summary_json = json.loads(response.choices[0].message.content.strip())
            self._debug_log("GPT-4 summary generation completed", start_time)

            return summary_json

        except Exception as e:
            self._debug_log(f"Summary generation error: {e}", start_time)
            logger.error(f"Failed to generate summary: {e}")
            return None

    async def process_call_recording(
        self,
        call_sid: str,
        recording_sid: str,
        phone_number: str,
        client_name: str,
        purpose: str,
        agent_name: str = "Agent",
        cleanup: bool = True
    ) -> Dict[str, Any]:
        """
        Complete pipeline for processing a call recording

        Args:
            call_sid: Twilio call SID
            recording_sid: Twilio recording SID
            phone_number: Caller's phone number
            client_name: Client/organization name
            purpose: Purpose of the call
            agent_name: Name of the AI agent
            cleanup: Whether to delete the audio file after processing

        Returns:
            Dictionary with transcription, formatted transcript, and summary
        """
        overall_start = self._debug_log(f"=== STARTING RECORDING PROCESSING === call_sid: {call_sid}")

        result = {
            "call_sid": call_sid,
            "recording_sid": recording_sid,
            "phone_number": phone_number,
            "client_name": client_name,
            "purpose": purpose,
            "raw_transcription": None,
            "formatted_transcription": None,
            "summary": None,
            "processed_at": datetime.utcnow().isoformat()
        }

        try:
            # Step 1: Download recording
            audio_file_path = await self.download_recording(call_sid, recording_sid)
            if not audio_file_path:
                result["error"] = "Failed to download recording"
                return result

            # Step 2: Transcribe audio
            raw_transcription = await self.transcribe_audio(audio_file_path)
            result["raw_transcription"] = raw_transcription

            if raw_transcription:
                # Step 3: Format with speaker labels
                formatted_transcription = await self.format_transcript_with_speakers(
                    raw_transcription, phone_number, agent_name
                )
                result["formatted_transcription"] = formatted_transcription

                # Step 4: Generate summary
                summary = await self.generate_summary(raw_transcription, client_name, purpose)
                result["summary"] = summary

                # Save transcript to file
                transcript_file = self.transcripts_dir / f"transcript_{call_sid}.txt"
                with open(transcript_file, "w") as f:
                    f.write(formatted_transcription or raw_transcription)

                # Save summary to file
                if summary:
                    import json
                    summary_file = self.summaries_dir / f"summary_{call_sid}.json"
                    with open(summary_file, "w") as f:
                        json.dump(summary, f, indent=2)

            # Cleanup temporary audio file
            if cleanup and audio_file_path and os.path.exists(audio_file_path):
                os.remove(audio_file_path)
                self._debug_log("Temporary audio file cleaned up")

            self._debug_log("=== RECORDING PROCESSING COMPLETED ===", overall_start)
            return result

        except Exception as e:
            self._debug_log(f"Recording processing error: {e}", overall_start)
            logger.error(f"Failed to process recording: {e}")
            result["error"] = str(e)
            return result

    async def grammar_check(self, text: str) -> str:
        """
        Check and correct grammar using GPT-4

        Args:
            text: Text to check

        Returns:
            Corrected text
        """
        start_time = self._debug_log(f"Grammar checking text")

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "Correct the input text for grammar, spelling, and clarity while preserving the original meaning. Return only the corrected text."
                    },
                    {"role": "user", "content": text}
                ],
                max_tokens=150,
                temperature=0.3
            )

            corrected_text = response.choices[0].message.content.strip()
            self._debug_log(f"Grammar check completed", start_time)
            return corrected_text

        except Exception as e:
            self._debug_log(f"Grammar check error: {e}", start_time)
            return text


# Singleton instance
_recording_service: Optional[RecordingService] = None


def get_recording_service() -> RecordingService:
    """Get recording service singleton"""
    global _recording_service
    if _recording_service is None:
        _recording_service = RecordingService()
    return _recording_service
