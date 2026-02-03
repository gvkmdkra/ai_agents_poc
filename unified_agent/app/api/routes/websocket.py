"""
WebSocket Routes
Handle real-time communication for voice calls and tool invocations
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from typing import Optional, Dict, Any
from datetime import datetime
import json

from app.core.config import settings
from app.core.logging import get_logger
from app.db import get_db_session, Call, Tenant
from app.services import TextToSQLService, VectorStore, TenantService

logger = get_logger(__name__)
router = APIRouter()


class UltravoxWebSocketHandler:
    """
    Handler for Ultravox WebSocket connections
    Processes tool invocations during voice calls
    """

    def __init__(
        self,
        websocket: WebSocket,
        tenant_id: str,
        userid: Optional[int] = None,
        db_access: bool = False
    ):
        self.websocket = websocket
        self.tenant_id = tenant_id
        self.userid = userid
        self.db_access = db_access

        self._text_to_sql = None
        self._vector_store = None
        self._tenant = None

        # Transcript collection
        self.transcript_parts = []
        self.call_start_time = datetime.utcnow()

    async def initialize(self):
        """Initialize services lazily"""
        with get_db_session() as db:
            tenant_service = TenantService(db)
            self._tenant = tenant_service.get_tenant(self.tenant_id)

            if not self._tenant:
                raise ValueError(f"Tenant not found: {self.tenant_id}")

            # Initialize Text-to-SQL if enabled
            if self.db_access and settings.enable_text_to_sql and self._tenant.pinecone_index_name:
                self._text_to_sql = TextToSQLService(
                    tenant_id=self.tenant_id,
                    index_name=self._tenant.pinecone_index_name,
                    userid=self.userid
                )

            # Initialize Vector Store for RAG
            if self._tenant.pinecone_drive_index:
                self._vector_store = VectorStore(index_name=self._tenant.pinecone_drive_index)

    async def handle_tool_invocation(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle tool invocation from Ultravox

        Args:
            message: Tool invocation message

        Returns:
            Tool response
        """
        tool_name = message.get("toolName", "")
        parameters = message.get("parameters", {})
        invocation_id = message.get("invocationId", "")

        logger.info(f"Tool invocation: {tool_name} with params: {parameters}")

        try:
            if tool_name == "query_database":
                return await self._handle_database_query(
                    query=parameters.get("query", ""),
                    invocation_id=invocation_id
                )

            elif tool_name == "end_call":
                return {
                    "invocationId": invocation_id,
                    "result": {"action": "hangup"}
                }

            else:
                return {
                    "invocationId": invocation_id,
                    "error": f"Unknown tool: {tool_name}"
                }

        except Exception as e:
            logger.error(f"Tool invocation error: {e}")
            return {
                "invocationId": invocation_id,
                "error": str(e)
            }

    async def _handle_database_query(
        self,
        query: str,
        invocation_id: str
    ) -> Dict[str, Any]:
        """Handle database query tool"""

        # Classify the query
        query_type = await self._classify_query(query)

        if query_type == "DATABASE":
            if not self.db_access or not self._text_to_sql:
                return {
                    "invocationId": invocation_id,
                    "result": "I don't have access to the database for this query. "
                             "Please log in to access your data."
                }

            # Process with Text-to-SQL (fast mode for voice)
            result = self._text_to_sql.process_query_fast(query)

            if result.get("success"):
                response = result.get("formatted_response", "Query processed successfully.")
            else:
                response = result.get("formatted_response", "I couldn't process that query.")

            return {
                "invocationId": invocation_id,
                "result": response
            }

        elif query_type == "RAG":
            return await self._handle_rag_query(query, invocation_id)

        else:  # DIRECT
            return await self._handle_direct_query(query, invocation_id)

    async def _handle_rag_query(
        self,
        query: str,
        invocation_id: str
    ) -> Dict[str, Any]:
        """Handle RAG document search query"""

        if not self._vector_store:
            return {
                "invocationId": invocation_id,
                "result": "Document search is not available."
            }

        try:
            results = self._vector_store.similarity_search(
                query=query,
                k=3,
                filter_dict={"tenant_id": self.tenant_id}
            )

            if results:
                # Build context from results
                context = "\n".join([r.get("content", "")[:500] for r in results[:2]])

                # Generate response using OpenAI
                from openai import OpenAI
                openai_client = OpenAI(api_key=settings.openai_api_key)

                response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": f"You are a helpful assistant. Answer based on this context:\n{context}"
                        },
                        {"role": "user", "content": query}
                    ],
                    temperature=0.3,
                    max_tokens=200
                )

                return {
                    "invocationId": invocation_id,
                    "result": response.choices[0].message.content
                }

            return {
                "invocationId": invocation_id,
                "result": "I couldn't find relevant information for your question."
            }

        except Exception as e:
            logger.error(f"RAG query error: {e}")
            return {
                "invocationId": invocation_id,
                "result": "I encountered an error searching for information."
            }

    async def _handle_direct_query(
        self,
        query: str,
        invocation_id: str
    ) -> Dict[str, Any]:
        """Handle direct conversational query"""

        try:
            from openai import OpenAI
            openai_client = OpenAI(api_key=settings.openai_api_key)

            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a helpful assistant for {self._tenant.name if self._tenant else 'our company'}. Be concise and conversational."
                    },
                    {"role": "user", "content": query}
                ],
                temperature=0.7,
                max_tokens=150
            )

            return {
                "invocationId": invocation_id,
                "result": response.choices[0].message.content
            }

        except Exception as e:
            logger.error(f"Direct query error: {e}")
            return {
                "invocationId": invocation_id,
                "result": "I'm having trouble responding right now."
            }

    async def _classify_query(self, query: str) -> str:
        """Classify query type"""
        try:
            from openai import OpenAI
            openai_client = OpenAI(api_key=settings.openai_api_key)

            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "user",
                    "content": f"""Classify this query: "{query}"

Return ONE word:
- DATABASE: Questions about data, counts, statistics, client info
- RAG: Questions about documentation, policies, procedures
- DIRECT: Greetings, thanks, general conversation"""
                }],
                temperature=0,
                max_tokens=10
            )

            classification = response.choices[0].message.content.strip().upper()
            return classification if classification in ["DATABASE", "RAG", "DIRECT"] else "DIRECT"

        except Exception:
            return "DIRECT"


@router.websocket("/ws/ultravox")
async def ultravox_websocket(
    websocket: WebSocket,
    tenant_id: str = Query(...),
    userid: Optional[int] = Query(default=None),
    db_access: str = Query(default="false")
):
    """
    WebSocket endpoint for Ultravox tool invocations

    Args:
        tenant_id: Tenant ID
        userid: User ID for database access
        db_access: Enable database access ("true" or "false")
    """
    await websocket.accept()

    handler = UltravoxWebSocketHandler(
        websocket=websocket,
        tenant_id=tenant_id,
        userid=userid,
        db_access=db_access.lower() == "true"
    )

    try:
        await handler.initialize()
        logger.info(f"WebSocket connected: tenant={tenant_id}, userid={userid}")

        while True:
            # Receive message
            data = await websocket.receive_text()
            message = json.loads(data)

            # Handle tool invocation
            if message.get("type") == "tool_invocation":
                response = await handler.handle_tool_invocation(message)
                await websocket.send_text(json.dumps(response))

            # Handle transcript updates
            elif message.get("type") == "transcript":
                handler.transcript_parts.append({
                    "role": message.get("role", "unknown"),
                    "text": message.get("text", ""),
                    "timestamp": datetime.utcnow().isoformat()
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: tenant={tenant_id}")

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
