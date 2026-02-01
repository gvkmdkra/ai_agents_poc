"""
OpenAI LLM Service
Handles interactions with OpenAI API for chat, embeddings, and transcription
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
import openai
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class OpenAIService:
    """Service for interacting with OpenAI API"""

    def __init__(self):
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self.embedding_model = settings.openai_embedding_model

        self.client = AsyncOpenAI(api_key=self.api_key)

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 500,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a chat completion

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Optional model override
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            system_prompt: Optional system prompt to prepend

        Returns:
            Completion response
        """
        logger.debug(f"Generating chat completion with {len(messages)} messages")

        try:
            full_messages = []

            if system_prompt:
                full_messages.append({
                    "role": "system",
                    "content": system_prompt
                })

            full_messages.extend(messages)

            response = await self.client.chat.completions.create(
                model=model or self.model,
                messages=full_messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

            return {
                "success": True,
                "content": response.choices[0].message.content,
                "role": response.choices[0].message.role,
                "finish_reason": response.choices[0].finish_reason,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }

        except openai.APIError as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return {
                "success": False,
                "error": f"API error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Failed to generate completion: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def generate_call_summary(
        self,
        transcript: List[Dict[str, str]],
        call_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a summary of a call from its transcript

        Args:
            transcript: List of transcript entries
            call_metadata: Optional call metadata

        Returns:
            Summary response
        """
        logger.info("Generating call summary")

        # Format transcript for the prompt
        formatted_transcript = "\n".join([
            f"{entry.get('speaker', 'Unknown')}: {entry.get('text', '')}"
            for entry in transcript
        ])

        system_prompt = """You are an expert at summarizing phone conversations.
Generate a concise summary of the call including:
1. Main topic/purpose of the call
2. Key points discussed
3. Any action items or next steps
4. Overall sentiment of the conversation

Format your response as JSON with keys: summary, key_points (array), action_items (array), sentiment"""

        messages = [
            {
                "role": "user",
                "content": f"Please summarize this call transcript:\n\n{formatted_transcript}"
            }
        ]

        if call_metadata:
            messages[0]["content"] += f"\n\nCall metadata: {call_metadata}"

        result = await self.chat_completion(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=800
        )

        return result

    async def generate_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate embeddings for texts

        Args:
            texts: List of texts to embed
            model: Optional model override

        Returns:
            Embeddings response
        """
        logger.debug(f"Generating embeddings for {len(texts)} texts")

        try:
            response = await self.client.embeddings.create(
                model=model or self.embedding_model,
                input=texts
            )

            embeddings = [item.embedding for item in response.data]

            return {
                "success": True,
                "embeddings": embeddings,
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }

        except openai.APIError as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return {
                "success": False,
                "error": f"API error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def transcribe_audio(
        self,
        audio_file_path: str,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transcribe audio using Whisper

        Args:
            audio_file_path: Path to audio file
            language: Optional language hint

        Returns:
            Transcription response
        """
        logger.info(f"Transcribing audio: {audio_file_path}")

        try:
            with open(audio_file_path, "rb") as audio_file:
                params = {"file": audio_file, "model": "whisper-1"}
                if language:
                    params["language"] = language

                response = await self.client.audio.transcriptions.create(**params)

            return {
                "success": True,
                "text": response.text
            }

        except openai.APIError as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return {
                "success": False,
                "error": f"API error: {str(e)}"
            }
        except FileNotFoundError:
            logger.error(f"Audio file not found: {audio_file_path}")
            return {
                "success": False,
                "error": "Audio file not found"
            }
        except Exception as e:
            logger.error(f"Failed to transcribe audio: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def analyze_intent(
        self,
        text: str,
        possible_intents: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Analyze the intent of a text

        Args:
            text: Text to analyze
            possible_intents: Optional list of possible intents

        Returns:
            Intent analysis
        """
        system_prompt = """You are an intent classifier. Analyze the given text and identify the user's intent.
Return your response as JSON with keys: intent, confidence (0-1), entities (dict)"""

        if possible_intents:
            system_prompt += f"\n\nPossible intents: {', '.join(possible_intents)}"

        messages = [
            {
                "role": "user",
                "content": f"Analyze this text: {text}"
            }
        ]

        return await self.chat_completion(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=200
        )

    async def generate_call_analysis(
        self,
        transcript: List[Dict[str, str]],
        call_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive analysis of a call including summary, key topics,
        sentiment, action items, and conversation highlights.

        Args:
            transcript: List of transcript entries
            call_metadata: Optional call metadata

        Returns:
            Analysis response with structured data
        """
        logger.info("Generating comprehensive call analysis")

        # Format transcript for the prompt
        formatted_transcript = "\n".join([
            f"{entry.get('speaker', 'Unknown').upper()}: {entry.get('text', '')}"
            for entry in transcript
        ])

        system_prompt = """You are an expert conversation analyst. Analyze the provided call transcript and generate a comprehensive analysis.

You MUST respond with valid JSON in this exact format:
{
    "summary": "A 2-3 sentence summary of the entire conversation",
    "key_topics": ["topic1", "topic2", "topic3"],
    "sentiment": "positive" | "neutral" | "negative",
    "action_items": ["action item 1", "action item 2"],
    "conversation_highlights": [
        {"speaker": "agent|user", "text": "important quote", "significance": "why this is notable"}
    ],
    "customer_intent": "What the customer wanted",
    "resolution_status": "resolved" | "pending" | "escalated" | "unknown",
    "follow_up_required": true | false,
    "key_entities": {
        "names": [],
        "dates": [],
        "products": [],
        "issues": []
    }
}"""

        user_content = f"Analyze this call transcript:\n\n{formatted_transcript}"

        if call_metadata:
            user_content += f"\n\nCall Metadata:\n- Phone: {call_metadata.get('phone_number', 'Unknown')}\n- Duration: {call_metadata.get('duration_seconds', 0)} seconds\n- Direction: {call_metadata.get('direction', 'Unknown')}"

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.3,
                max_tokens=1500
            )

            content = response.choices[0].message.content

            # Parse JSON response
            import json
            try:
                # Try to extract JSON from the response
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]

                analysis = json.loads(content.strip())
                return {
                    "success": True,
                    "analysis": analysis
                }
            except json.JSONDecodeError:
                # If JSON parsing fails, return raw content
                return {
                    "success": True,
                    "analysis": {
                        "summary": content,
                        "key_topics": [],
                        "sentiment": "neutral",
                        "action_items": [],
                        "conversation_highlights": [],
                        "raw_response": True
                    }
                }

        except Exception as e:
            logger.error(f"Failed to generate call analysis: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "analysis": {}
            }

    async def generate_response(
        self,
        user_input: str,
        context: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        agent_persona: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a conversational response

        Args:
            user_input: User's input text
            context: Optional context information
            conversation_history: Previous conversation messages
            agent_persona: Agent's persona/role description

        Returns:
            Generated response
        """
        system_prompt = agent_persona or """You are a helpful and professional customer service agent.
Respond naturally and helpfully to the user's queries.
Keep responses concise and suitable for voice conversation."""

        if context:
            system_prompt += f"\n\nContext: {context}"

        messages = conversation_history or []
        messages.append({
            "role": "user",
            "content": user_input
        })

        return await self.chat_completion(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=300
        )
