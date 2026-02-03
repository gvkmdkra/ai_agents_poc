"""
Chat Service
RAG-powered chat with Text-to-SQL integration
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.core.exceptions import ChatError
from app.db.models import Tenant, Conversation, Message
from .vector_store import VectorStore
from .text_to_sql_service import TextToSQLService

logger = get_logger(__name__)


class ChatService:
    """
    Chat service with intelligent routing between database, RAG, and direct responses
    """

    def __init__(
        self,
        tenant: Tenant,
        db: Session,
        userid: Optional[int] = None
    ):
        """
        Initialize chat service

        Args:
            tenant: Tenant configuration
            db: Database session
            userid: User ID for data filtering
        """
        self.tenant = tenant
        self.db = db
        self.userid = userid

        self._openai = OpenAI(api_key=settings.openai_api_key)

        # Initialize vector store for RAG
        if tenant.pinecone_drive_index:
            self._vector_store = VectorStore(index_name=tenant.pinecone_drive_index)
        else:
            self._vector_store = None

        # Initialize Text-to-SQL service
        if settings.enable_text_to_sql and tenant.pinecone_index_name:
            self._text_to_sql = TextToSQLService(
                tenant_id=tenant.id,
                index_name=tenant.pinecone_index_name,
                userid=userid
            )
        else:
            self._text_to_sql = None

    def classify_query(self, message: str) -> str:
        """
        Classify query to determine response method

        Args:
            message: User message

        Returns:
            Classification: database, rag, direct, or lead_capture
        """
        try:
            prompt = f"""Classify this user message into one category:

Message: "{message}"

Categories:
- database: Questions about specific data, counts, statistics, client info, user details, business metrics
- rag: Questions about documentation, policies, procedures, general knowledge
- lead_capture: User providing contact info (name, email, phone) or wanting to be contacted
- direct: Greetings, thanks, simple questions, conversational responses

Return ONLY one word: database, rag, lead_capture, or direct"""

            response = self._openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=10
            )

            classification = response.choices[0].message.content.strip().lower()

            if classification not in ["database", "rag", "lead_capture", "direct"]:
                return "direct"

            logger.debug(f"Query classified as: {classification}")
            return classification

        except Exception as e:
            logger.error(f"Classification failed: {e}")
            return "direct"

    async def process_message(
        self,
        message: str,
        conversation: Conversation,
        client_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a chat message and generate response

        Args:
            message: User message
            conversation: Conversation object
            client_name: Client name for personalization

        Returns:
            Response with content and metadata
        """
        try:
            # Classify the message
            method = self.classify_query(message)

            response_text = None
            sources = None

            # Process based on classification
            if method == "database":
                response_text, sources = await self._handle_database_query(message)

            elif method == "rag":
                response_text, sources = await self._handle_rag_query(message, conversation)

            elif method == "lead_capture":
                response_text = await self._handle_lead_capture(message, conversation, client_name)

            else:  # direct
                response_text = await self._handle_direct_response(message, conversation)

            return {
                "response": response_text,
                "method": method,
                "sources": sources
            }

        except Exception as e:
            logger.error(f"Message processing failed: {e}")
            raise ChatError(f"Failed to process message: {e}")

    async def _handle_database_query(
        self,
        message: str
    ) -> tuple[str, Optional[List[Dict[str, Any]]]]:
        """Handle database query using Text-to-SQL"""

        if not self._text_to_sql:
            return "Database queries are not available for this configuration.", None

        if not self.userid:
            return "Please log in to access database information.", None

        result = self._text_to_sql.process_query(message)

        if result.get("success"):
            sources = None
            if result.get("result"):
                sources = [{"type": "database", "data": result["result"]}]

            return result.get("formatted_response", "Query processed."), sources
        else:
            return result.get("error", "Failed to process database query."), None

    async def _handle_rag_query(
        self,
        message: str,
        conversation: Conversation
    ) -> tuple[str, Optional[List[Dict[str, Any]]]]:
        """Handle RAG document search query"""

        if not self._vector_store:
            # Fallback to direct response if no RAG configured
            return await self._handle_direct_response(message, conversation), None

        # Search for relevant documents
        search_results = self._vector_store.similarity_search(
            query=message,
            k=3,
            filter_dict={"tenant_id": self.tenant.id}
        )

        # Build context from results
        context_docs = [r.get("content", "") for r in search_results if r.get("content")]

        # Get conversation history
        history = self._get_conversation_history(conversation)

        # Build messages with context
        messages = [
            {
                "role": "system",
                "content": f"""You are a helpful AI assistant for {self.tenant.name}.
{self.tenant.system_prompt or ''}

Use the following context to answer questions:

Context:
{chr(10).join(context_docs) if context_docs else 'No specific context available.'}

Be helpful, accurate, and concise."""
            }
        ]

        messages.extend(history)
        messages.append({"role": "user", "content": message})

        # Get response
        response = self._openai.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            temperature=0.7
        )

        # Format sources
        sources = None
        if search_results:
            sources = [
                {
                    "type": "document",
                    "content": r.get("content", "")[:200],
                    "score": r.get("score"),
                    "metadata": r.get("metadata", {})
                }
                for r in search_results
            ]

        return response.choices[0].message.content, sources

    async def _handle_lead_capture(
        self,
        message: str,
        conversation: Conversation,
        client_name: Optional[str]
    ) -> str:
        """Handle lead capture intent"""

        # Extract contact information using LLM
        extract_prompt = f"""Extract contact information from this message:

Message: "{message}"

Return a JSON object with these fields (null if not found):
- name: string or null
- email: string or null
- phone: string or null
- company: string or null
- message: any additional message or request

Return ONLY valid JSON."""

        response = self._openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": extract_prompt}],
            temperature=0
        )

        # Generate a friendly response
        return f"""Thank you for your interest! I've noted your information.
Someone from our team will be in touch with you shortly.

Is there anything else I can help you with in the meantime?"""

    async def _handle_direct_response(
        self,
        message: str,
        conversation: Conversation
    ) -> str:
        """Handle direct conversational response"""

        history = self._get_conversation_history(conversation)

        messages = [
            {
                "role": "system",
                "content": f"""You are a helpful AI assistant for {self.tenant.name}.
{self.tenant.system_prompt or ''}

Be friendly, helpful, and conversational."""
            }
        ]

        messages.extend(history)
        messages.append({"role": "user", "content": message})

        response = self._openai.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            temperature=0.7
        )

        return response.choices[0].message.content

    def _get_conversation_history(
        self,
        conversation: Conversation,
        limit: int = 10
    ) -> List[Dict[str, str]]:
        """Get conversation history for context"""

        messages = self.db.query(Message).filter(
            Message.conversation_id == conversation.id
        ).order_by(Message.created_at).limit(limit).all()

        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]


class ChatManager:
    """
    Manager for chat operations
    Handles conversation creation, message storage, etc.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_or_create_conversation(
        self,
        tenant_id: str,
        session_id: Optional[str] = None,
        user_name: str = "Guest",
        userid: Optional[int] = None
    ) -> Conversation:
        """Get existing or create new conversation"""

        if session_id:
            conversation = self.db.query(Conversation).filter(
                Conversation.session_id == session_id
            ).first()

            if conversation:
                return conversation

        # Create new conversation
        conversation = Conversation(
            tenant_id=tenant_id,
            user_name=user_name,
            user_id=userid,
            metadata={"userid": userid} if userid else {}
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)

        return conversation

    def save_message(
        self,
        conversation: Conversation,
        role: str,
        content: str,
        method: Optional[str] = None,
        sources: Optional[List[Dict[str, Any]]] = None
    ) -> Message:
        """Save a message to the conversation"""

        message = Message(
            conversation_id=conversation.id,
            role=role,
            content=content,
            method=method,
            sources=sources,
            message_metadata={"method": method} if method else None
        )
        self.db.add(message)

        # Update conversation
        conversation.message_count += 1
        conversation.last_message_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(message)

        return message

    def get_conversation_history(
        self,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get full conversation history"""

        conversation = self.db.query(Conversation).filter(
            Conversation.session_id == session_id
        ).first()

        if not conversation:
            return None

        messages = self.db.query(Message).filter(
            Message.conversation_id == conversation.id
        ).order_by(Message.created_at).all()

        return {
            "session_id": conversation.session_id,
            "tenant_id": conversation.tenant_id,
            "user_name": conversation.user_name,
            "created_at": conversation.created_at.isoformat(),
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "method": msg.method,
                    "created_at": msg.created_at.isoformat()
                }
                for msg in messages
            ]
        }
