"""
OpenAI Integration Client for Voice Agent

Handles:
- Conversation generation (GPT-4o)
- Lead qualification analysis
- Sentiment analysis
- Intent detection
- Conversation summarization
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class ConversationRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """Conversation message"""

    role: ConversationRole
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[list] = None


@dataclass
class LeadQualificationResult:
    """Result of lead qualification analysis"""

    score: float  # 0.0 to 1.0
    temperature: str  # hot, warm, cold
    budget_mentioned: bool
    budget_range: Optional[str]
    is_decision_maker: bool
    need_identified: Optional[str]
    timeline: Optional[str]
    pain_points: list[str]
    buying_signals: list[str]
    objections: list[str]
    recommendations: list[str]
    summary: str


@dataclass
class SentimentResult:
    """Result of sentiment analysis"""

    score: float  # -1.0 to 1.0
    label: str  # positive, negative, neutral
    confidence: float
    emotions: dict[str, float]  # joy, frustration, confusion, etc.
    trend: str  # improving, declining, stable


@dataclass
class IntentResult:
    """Result of intent detection"""

    primary_intent: str
    confidence: float
    secondary_intents: list[str]
    entities: dict[str, Any]


@dataclass
class OpenAIConfig:
    """OpenAI client configuration"""

    api_key: str
    conversation_model: str = "gpt-4o"
    classification_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    temperature: float = 0.7
    max_tokens: int = 4096


class OpenAIVoiceClient:
    """
    OpenAI client for voice agent intelligence.

    Provides:
    - Conversation generation
    - Lead qualification scoring
    - Sentiment analysis
    - Intent detection
    - Conversation summarization
    """

    def __init__(self, config: OpenAIConfig):
        self.config = config
        self.client = AsyncOpenAI(api_key=config.api_key)

    # =========================================================================
    # CONVERSATION GENERATION
    # =========================================================================

    async def generate_response(
        self,
        messages: list[Message],
        system_prompt: str,
        tools: Optional[list[dict]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Generate a conversational response.

        Args:
            messages: Conversation history
            system_prompt: System prompt for the AI
            tools: Optional function tools
            temperature: Override default temperature
            max_tokens: Override default max tokens

        Returns:
            Generated response with content and optional tool calls
        """
        # Build messages list
        formatted_messages = [{"role": "system", "content": system_prompt}]

        for msg in messages:
            message_dict = {"role": msg.role.value, "content": msg.content}
            if msg.name:
                message_dict["name"] = msg.name
            if msg.tool_call_id:
                message_dict["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                message_dict["tool_calls"] = msg.tool_calls
            formatted_messages.append(message_dict)

        # API call parameters
        params = {
            "model": self.config.conversation_model,
            "messages": formatted_messages,
            "temperature": temperature or self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
        }

        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        try:
            response = await self.client.chat.completions.create(**params)
            choice = response.choices[0]

            result = {
                "content": choice.message.content,
                "role": choice.message.role,
                "finish_reason": choice.finish_reason,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
            }

            if choice.message.tool_calls:
                result["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in choice.message.tool_calls
                ]

            return result

        except Exception as e:
            logger.error(f"OpenAI generation error: {e}")
            raise

    # =========================================================================
    # LEAD QUALIFICATION
    # =========================================================================

    async def qualify_lead(
        self,
        conversation_transcript: str,
        industry: str,
        custom_criteria: Optional[dict] = None,
    ) -> LeadQualificationResult:
        """
        Analyze conversation and qualify the lead.

        Uses BANT framework:
        - Budget: Financial capacity signals
        - Authority: Decision-maker identification
        - Need: Problem/pain point clarity
        - Timeline: Purchase urgency

        Args:
            conversation_transcript: Full conversation text
            industry: Industry context (real_estate, insurance, etc.)
            custom_criteria: Optional custom qualification criteria

        Returns:
            LeadQualificationResult with score and details
        """
        system_prompt = f"""You are an expert lead qualification analyst for the {industry} industry.

Analyze the conversation transcript and provide a detailed lead qualification assessment using the BANT framework:
- Budget: Did they mention budget, price range, or financial capacity?
- Authority: Are they the decision maker or influencer?
- Need: What specific need or problem are they trying to solve?
- Timeline: How urgent is their need? (immediate, 1-3 months, 6+ months, unknown)

Also identify:
- Buying signals (positive indicators)
- Objections or concerns
- Pain points mentioned
- Recommended next steps

Provide a qualification score from 0.0 to 1.0 where:
- 0.75-1.0 = Hot lead (ready to buy, high intent)
- 0.45-0.74 = Warm lead (interested, needs nurturing)
- 0.0-0.44 = Cold lead (early stage, low intent)

Respond in JSON format."""

        user_prompt = f"""Analyze this conversation and qualify the lead:

TRANSCRIPT:
{conversation_transcript}

{f"CUSTOM CRITERIA: {json.dumps(custom_criteria)}" if custom_criteria else ""}

Respond with a JSON object containing:
{{
    "score": <float 0.0-1.0>,
    "temperature": "<hot|warm|cold>",
    "budget_mentioned": <boolean>,
    "budget_range": "<string or null>",
    "is_decision_maker": <boolean>,
    "need_identified": "<string or null>",
    "timeline": "<immediate|1-3 months|6+ months|unknown>",
    "pain_points": ["<list of pain points>"],
    "buying_signals": ["<list of positive indicators>"],
    "objections": ["<list of concerns/objections>"],
    "recommendations": ["<list of recommended next steps>"],
    "summary": "<2-3 sentence summary>"
}}"""

        try:
            response = await self.client.chat.completions.create(
                model=self.config.classification_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)

            return LeadQualificationResult(
                score=result.get("score", 0.0),
                temperature=result.get("temperature", "cold"),
                budget_mentioned=result.get("budget_mentioned", False),
                budget_range=result.get("budget_range"),
                is_decision_maker=result.get("is_decision_maker", False),
                need_identified=result.get("need_identified"),
                timeline=result.get("timeline"),
                pain_points=result.get("pain_points", []),
                buying_signals=result.get("buying_signals", []),
                objections=result.get("objections", []),
                recommendations=result.get("recommendations", []),
                summary=result.get("summary", ""),
            )

        except Exception as e:
            logger.error(f"Lead qualification error: {e}")
            # Return default cold lead on error
            return LeadQualificationResult(
                score=0.0,
                temperature="cold",
                budget_mentioned=False,
                budget_range=None,
                is_decision_maker=False,
                need_identified=None,
                timeline="unknown",
                pain_points=[],
                buying_signals=[],
                objections=[],
                recommendations=["Follow up to gather more information"],
                summary="Unable to qualify lead due to analysis error.",
            )

    # =========================================================================
    # SENTIMENT ANALYSIS
    # =========================================================================

    async def analyze_sentiment(
        self,
        text: str,
        previous_sentiment: Optional[float] = None,
    ) -> SentimentResult:
        """
        Analyze sentiment of text (typically a user message).

        Args:
            text: Text to analyze
            previous_sentiment: Previous sentiment score for trend analysis

        Returns:
            SentimentResult with score and emotions
        """
        system_prompt = """You are a sentiment analysis expert. Analyze the emotional tone and sentiment of the given text.

Provide:
1. Sentiment score from -1.0 (very negative) to 1.0 (very positive)
2. Sentiment label (positive, negative, neutral)
3. Confidence level (0.0 to 1.0)
4. Detected emotions with intensity scores

Respond in JSON format."""

        user_prompt = f"""Analyze the sentiment of this text:

"{text}"

{f"Previous sentiment score was: {previous_sentiment}" if previous_sentiment is not None else ""}

Respond with:
{{
    "score": <float -1.0 to 1.0>,
    "label": "<positive|negative|neutral>",
    "confidence": <float 0.0-1.0>,
    "emotions": {{
        "joy": <float 0.0-1.0>,
        "frustration": <float 0.0-1.0>,
        "confusion": <float 0.0-1.0>,
        "interest": <float 0.0-1.0>,
        "urgency": <float 0.0-1.0>,
        "satisfaction": <float 0.0-1.0>
    }},
    "trend": "<improving|declining|stable>"
}}"""

        try:
            response = await self.client.chat.completions.create(
                model=self.config.classification_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)

            return SentimentResult(
                score=result.get("score", 0.0),
                label=result.get("label", "neutral"),
                confidence=result.get("confidence", 0.5),
                emotions=result.get("emotions", {}),
                trend=result.get("trend", "stable"),
            )

        except Exception as e:
            logger.error(f"Sentiment analysis error: {e}")
            return SentimentResult(
                score=0.0,
                label="neutral",
                confidence=0.0,
                emotions={},
                trend="stable",
            )

    # =========================================================================
    # INTENT DETECTION
    # =========================================================================

    async def detect_intent(
        self,
        text: str,
        context: Optional[str] = None,
        possible_intents: Optional[list[str]] = None,
    ) -> IntentResult:
        """
        Detect user intent from text.

        Args:
            text: User message
            context: Conversation context
            possible_intents: List of expected intents to match

        Returns:
            IntentResult with primary and secondary intents
        """
        default_intents = [
            "inquiry",  # General information request
            "schedule_appointment",  # Wants to book a meeting
            "pricing_question",  # Asking about costs
            "speak_to_human",  # Wants human agent
            "complaint",  # Has a problem/complaint
            "feedback",  # Providing feedback
            "purchase_intent",  # Ready to buy
            "comparison",  # Comparing options
            "technical_support",  # Needs tech help
            "account_inquiry",  # Account-related question
            "greeting",  # Simple greeting
            "goodbye",  # Ending conversation
            "confirmation",  # Confirming something
            "rejection",  # Declining/refusing
            "unclear",  # Intent not clear
        ]

        intents = possible_intents or default_intents

        system_prompt = f"""You are an intent classification expert for customer service conversations.

Classify the user's intent into one of these categories:
{json.dumps(intents, indent=2)}

Also extract any relevant entities (names, dates, numbers, locations, etc.)

Respond in JSON format."""

        user_prompt = f"""Classify the intent of this message:

"{text}"

{f"Conversation context: {context}" if context else ""}

Respond with:
{{
    "primary_intent": "<main intent>",
    "confidence": <float 0.0-1.0>,
    "secondary_intents": ["<other possible intents>"],
    "entities": {{
        "names": ["<extracted names>"],
        "dates": ["<extracted dates>"],
        "numbers": ["<extracted numbers>"],
        "locations": ["<extracted locations>"],
        "products": ["<extracted product mentions>"]
    }}
}}"""

        try:
            response = await self.client.chat.completions.create(
                model=self.config.classification_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)

            return IntentResult(
                primary_intent=result.get("primary_intent", "unclear"),
                confidence=result.get("confidence", 0.5),
                secondary_intents=result.get("secondary_intents", []),
                entities=result.get("entities", {}),
            )

        except Exception as e:
            logger.error(f"Intent detection error: {e}")
            return IntentResult(
                primary_intent="unclear",
                confidence=0.0,
                secondary_intents=[],
                entities={},
            )

    # =========================================================================
    # CONVERSATION SUMMARIZATION
    # =========================================================================

    async def summarize_conversation(
        self,
        transcript: str,
        include_action_items: bool = True,
    ) -> dict[str, Any]:
        """
        Generate a summary of the conversation.

        Args:
            transcript: Full conversation transcript
            include_action_items: Include extracted action items

        Returns:
            Summary with key points and action items
        """
        system_prompt = """You are an expert at summarizing customer conversations.

Create a concise summary that captures:
1. Main topic/purpose of the conversation
2. Key information exchanged
3. Customer's needs/concerns
4. Outcome/resolution
5. Action items (if requested)

Be concise but comprehensive."""

        user_prompt = f"""Summarize this conversation:

{transcript}

Respond with:
{{
    "summary": "<2-3 sentence summary>",
    "main_topic": "<primary topic>",
    "customer_need": "<what customer wanted>",
    "key_points": ["<important points discussed>"],
    "outcome": "<how conversation ended>",
    {"\"action_items\": [\"<next steps>]\"," if include_action_items else ""}
    "follow_up_required": <boolean>
}}"""

        try:
            response = await self.client.chat.completions.create(
                model=self.config.classification_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
            )

            return json.loads(response.choices[0].message.content)

        except Exception as e:
            logger.error(f"Summarization error: {e}")
            return {
                "summary": "Unable to generate summary.",
                "main_topic": "unknown",
                "customer_need": "unknown",
                "key_points": [],
                "outcome": "unknown",
                "action_items": [],
                "follow_up_required": True,
            }

    # =========================================================================
    # ESCALATION DETECTION
    # =========================================================================

    async def should_escalate(
        self,
        message: str,
        conversation_history: Optional[str] = None,
        escalation_keywords: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Determine if conversation should escalate to human agent.

        Args:
            message: Current user message
            conversation_history: Previous conversation context
            escalation_keywords: Custom keywords triggering escalation

        Returns:
            Escalation decision with reason
        """
        default_keywords = [
            "speak to human",
            "talk to someone",
            "real person",
            "manager",
            "supervisor",
            "complaint",
            "lawyer",
            "legal",
            "sue",
            "report",
        ]

        keywords = escalation_keywords or default_keywords

        system_prompt = f"""You are an expert at determining when customer conversations should be escalated to a human agent.

Escalation triggers:
1. Explicit request to speak to a human
2. Signs of significant frustration or anger
3. Complex issues requiring human judgment
4. Legal or compliance concerns
5. High-value customer situations
6. AI unable to adequately help

Keywords that typically trigger escalation:
{json.dumps(keywords)}

Respond in JSON format."""

        user_prompt = f"""Should this conversation be escalated to a human agent?

Current message: "{message}"

{f"Conversation history: {conversation_history}" if conversation_history else ""}

Respond with:
{{
    "should_escalate": <boolean>,
    "confidence": <float 0.0-1.0>,
    "reason": "<why escalation is needed or not>",
    "urgency": "<low|medium|high>",
    "suggested_department": "<sales|support|management|legal|other>"
}}"""

        try:
            response = await self.client.chat.completions.create(
                model=self.config.classification_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )

            return json.loads(response.choices[0].message.content)

        except Exception as e:
            logger.error(f"Escalation detection error: {e}")
            # Default to not escalating on error
            return {
                "should_escalate": False,
                "confidence": 0.0,
                "reason": "Unable to determine escalation need",
                "urgency": "low",
                "suggested_department": "support",
            }

    # =========================================================================
    # EMBEDDINGS
    # =========================================================================

    async def create_embedding(self, text: str) -> list[float]:
        """
        Create an embedding vector for text.

        Useful for:
        - FAQ matching
        - Knowledge base search
        - Similar conversation retrieval

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        try:
            response = await self.client.embeddings.create(
                model=self.config.embedding_model,
                input=text,
            )
            return response.data[0].embedding

        except Exception as e:
            logger.error(f"Embedding creation error: {e}")
            raise

    async def create_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Create embedding vectors for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        try:
            response = await self.client.embeddings.create(
                model=self.config.embedding_model,
                input=texts,
            )
            return [item.embedding for item in response.data]

        except Exception as e:
            logger.error(f"Batch embedding error: {e}")
            raise
