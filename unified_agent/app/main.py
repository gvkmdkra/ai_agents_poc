"""
Unified AI Agent - Main Application Entry Point

A unified AI agent platform that combines:
- Voice Calling (Ultravox + Twilio)
- RAG-powered Chat (Pinecone + OpenAI)
- Text-to-SQL Database Queries
- Multi-tenant Support
- Lead Capture

Enterprise-ready with rate limiting, webhook security, and comprehensive logging.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.exceptions import (
    UnifiedAgentException,
    AuthenticationError,
    RateLimitError
)
from app.api.routes import calls, chat, webhooks, health, tenants, websocket
from app.db import init_database, close_database

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent
STATIC_DIR = PROJECT_ROOT / "static"

# Setup logging
setup_logging(
    level=settings.log_level,
    format_type=settings.log_format
)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler for startup and shutdown events
    """
    # Startup
    logger.info("=" * 60)
    logger.info("Starting Unified AI Agent")
    logger.info(f"Version: {settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"API Base URL: {settings.api_base_url}")
    logger.info(f"Database Type: {settings.database_type}")
    logger.info("=" * 60)

    # Initialize database
    try:
        init_database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

    # Log feature status
    features = []
    if settings.enable_voice_calling:
        features.append("Voice Calling")
    if settings.enable_chat:
        features.append("Chat")
    if settings.enable_text_to_sql:
        features.append("Text-to-SQL")
    if settings.enable_rag:
        features.append("RAG")
    if settings.enable_lead_capture:
        features.append("Lead Capture")
    if settings.enable_analytics:
        features.append("Analytics")

    logger.info(f"Enabled features: {', '.join(features)}")
    logger.info("All services initialized successfully")

    yield

    # Shutdown
    logger.info("Shutting down Unified AI Agent")
    await close_database()
    logger.info("Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Unified AI Agent API",
    description="""
    ## Unified AI Agent Platform

    A comprehensive AI agent that combines voice calling, chat, and database querying capabilities.

    ### Features

    - **Voice Calling**: Outbound and inbound calls via Twilio + Ultravox AI
    - **Chat**: RAG-powered chat with document search
    - **Text-to-SQL**: Natural language database queries
    - **Multi-Tenant**: Full multi-tenant support with API key authentication
    - **Lead Capture**: Automatic lead extraction from conversations
    - **Analytics**: Call and chat analytics dashboard

    ### Authentication

    Include your API key using one of these methods:
    - Header: `X-API-Key: your-api-key`
    - Bearer Token: `Authorization: Bearer your-api-key`

    For database access, include a JWT token with user information.

    ### Rate Limits

    - **Requests**: 60 requests/minute per tenant
    - **Calls**: 100 calls/hour per tenant
    - **Concurrent Calls**: 10 per tenant
    """,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Configure CORS
cors_origins = settings.cors_origins
if settings.debug:
    cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests"""
    logger.debug(
        f"[REQUEST] {request.method} {request.url.path}",
        origin=request.headers.get("origin", "None")
    )
    response = await call_next(request)
    logger.debug(f"[RESPONSE] {response.status_code}")
    return response


# Custom Exception Handlers
@app.exception_handler(UnifiedAgentException)
async def unified_agent_exception_handler(request: Request, exc: UnifiedAgentException):
    """Handle custom exceptions"""
    logger.warning(f"UnifiedAgentException: {exc.error_code} - {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )


@app.exception_handler(AuthenticationError)
async def auth_exception_handler(request: Request, exc: AuthenticationError):
    """Handle authentication errors"""
    logger.warning(f"AuthenticationError: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
        headers={"WWW-Authenticate": "Bearer"}
    )


@app.exception_handler(RateLimitError)
async def rate_limit_exception_handler(request: Request, exc: RateLimitError):
    """Handle rate limit errors"""
    logger.warning(f"RateLimitError: {exc.message}")
    retry_after = exc.details.get("retry_after_seconds", 60)
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
        headers={"Retry-After": str(retry_after)}
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "details": {"exception": str(exc)} if settings.debug else {}
        }
    )


# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(calls.router, prefix="/api/v1/calls", tags=["Voice Calling"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])
app.include_router(tenants.router, prefix="/api/v1/tenants", tags=["Tenants"])
app.include_router(websocket.router, tags=["WebSocket"])

# Mount static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# Root endpoint
@app.get("/", include_in_schema=False)
async def root():
    """API root endpoint"""
    return {
        "service": "Unified AI Agent",
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
        "features": {
            "voice_calling": settings.enable_voice_calling,
            "chat": settings.enable_chat,
            "text_to_sql": settings.enable_text_to_sql,
            "rag": settings.enable_rag,
            "lead_capture": settings.enable_lead_capture,
            "analytics": settings.enable_analytics
        }
    }


@app.get("/api", include_in_schema=False)
async def api_info():
    """API information endpoint"""
    return {
        "service": "Unified AI Agent API",
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "calls": "/api/v1/calls",
            "chat": "/api/v1/chat",
            "webhooks": "/api/v1/webhooks",
            "tenants": "/api/v1/tenants"
        }
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.debug
    )
