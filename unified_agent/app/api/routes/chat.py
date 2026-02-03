"""
Chat API Routes
RAG-powered chat with Text-to-SQL integration
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.core.jwt_auth import get_optional_userid, get_required_userid
from app.db import get_db, Tenant, Conversation, Message
from app.services import ChatService, ChatManager, TenantService

logger = get_logger(__name__)
router = APIRouter()


# ============================================
# REQUEST/RESPONSE MODELS
# ============================================

class ChatMessageRequest(BaseModel):
    """Request model for chat message"""
    message: str = Field(..., description="User message")
    tenant_id: str = Field(..., description="Tenant ID")
    session_id: Optional[str] = Field(default=None, description="Chat session ID")
    client_name: Optional[str] = Field(default="Guest", description="Client name")


class ChatMessageResponse(BaseModel):
    """Response model for chat message"""
    response: str = Field(..., description="AI response")
    session_id: str = Field(..., description="Chat session ID")
    sources: Optional[List[Dict[str, Any]]] = Field(default=None, description="Source documents or data")
    method: str = Field(..., description="Response method: database, rag, or direct")


class ChatHistoryResponse(BaseModel):
    """Response model for chat history"""
    session_id: str
    messages: List[Dict[str, Any]]
    tenant_id: str
    created_at: datetime


class WidgetConfigResponse(BaseModel):
    """Response model for widget configuration"""
    tenant_id: str
    tenant_name: str
    welcome_message: str
    primary_color: str
    logo_url: Optional[str]
    enable_voice: bool
    enable_chat: bool


# ============================================
# ENDPOINTS
# ============================================

@router.post("/message", response_model=ChatMessageResponse)
async def send_chat_message(
    request: ChatMessageRequest,
    db: Session = Depends(get_db),
    userid: Optional[int] = Depends(get_optional_userid)
):
    """
    Send a chat message and get AI response

    AI automatically decides whether to:
    1. Query the database using Text-to-SQL
    2. Use RAG with Pinecone for document search
    3. Answer directly using LLM
    4. Capture lead information

    JWT authentication (optional) extracts userid for data filtering.
    """
    try:
        # Log userid if present
        if userid:
            logger.info(f"[CHAT] Request authenticated - userid: {userid}")
        else:
            logger.debug("[CHAT] Request without JWT authentication")

        # Get tenant
        tenant_service = TenantService(db)
        tenant = tenant_service.get_tenant(request.tenant_id)

        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        if not tenant.enable_chat:
            raise HTTPException(status_code=403, detail="Chat is not enabled for this tenant")

        # Get or create conversation
        chat_manager = ChatManager(db)
        conversation = chat_manager.get_or_create_conversation(
            tenant_id=request.tenant_id,
            session_id=request.session_id,
            user_name=request.client_name or "Guest",
            userid=userid
        )

        # Save user message
        chat_manager.save_message(
            conversation=conversation,
            role="user",
            content=request.message
        )

        # Process message
        chat_service = ChatService(
            tenant=tenant,
            db=db,
            userid=userid
        )

        result = await chat_service.process_message(
            message=request.message,
            conversation=conversation,
            client_name=request.client_name
        )

        # Save assistant response
        chat_manager.save_message(
            conversation=conversation,
            role="assistant",
            content=result["response"],
            method=result.get("method"),
            sources=result.get("sources")
        )

        return ChatMessageResponse(
            response=result["response"],
            session_id=conversation.session_id,
            sources=result.get("sources"),
            method=result.get("method", "direct")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing chat message: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process message: {str(e)}"
        )


@router.get("/history/{session_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: str,
    db: Session = Depends(get_db),
    userid: Optional[int] = Depends(get_optional_userid)
):
    """Get chat history for a session"""
    try:
        chat_manager = ChatManager(db)
        history = chat_manager.get_conversation_history(session_id)

        if not history:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return ChatHistoryResponse(
            session_id=history["session_id"],
            messages=history["messages"],
            tenant_id=history["tenant_id"],
            created_at=datetime.fromisoformat(history["created_at"])
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chat history: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get chat history: {str(e)}"
        )


@router.get("/widget/config/{tenant_id}", response_model=WidgetConfigResponse)
async def get_widget_config(
    tenant_id: str,
    db: Session = Depends(get_db)
):
    """Get widget configuration for a tenant"""
    try:
        tenant_service = TenantService(db)
        tenant = tenant_service.get_tenant(tenant_id)

        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        return WidgetConfigResponse(
            tenant_id=tenant.id,
            tenant_name=tenant.name,
            welcome_message=tenant.welcome_message or "Hello! How can I help you?",
            primary_color=tenant.primary_color or "#4F46E5",
            logo_url=tenant.logo_url,
            enable_voice=tenant.enable_voice_calling and settings.enable_voice_calling,
            enable_chat=tenant.enable_chat and settings.enable_chat
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting widget config: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get widget config: {str(e)}"
        )


@router.post("/widget/voice-call")
async def start_widget_voice_call(
    tenant_id: str,
    client_name: Optional[str] = "Guest",
    db: Session = Depends(get_db),
    userid: Optional[int] = Depends(get_optional_userid)
):
    """Start a browser voice call from the widget"""
    try:
        # Get tenant
        tenant_service = TenantService(db)
        tenant = tenant_service.get_tenant(tenant_id)

        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        if not tenant.enable_voice_calling:
            raise HTTPException(status_code=403, detail="Voice calling not enabled")

        # Create voice call
        from app.services import VoiceCallingService
        voice_service = VoiceCallingService(tenant)

        result = await voice_service.create_browser_call(
            client_name=client_name,
            userid=userid
        )

        return {
            "success": True,
            "call_id": result["call_id"],
            "join_url": result["join_url"],
            "database_enabled": result.get("database_enabled", False)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting voice call: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start voice call: {str(e)}"
        )
