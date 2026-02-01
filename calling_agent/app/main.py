"""
Calling Agent - Main Application Entry Point

A voice AI agent that handles phone calls using Ultravox and Twilio.
Enterprise-ready with multi-tenant support, rate limiting, and webhook security.
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
    CallingAgentException,
    AuthenticationError,
    RateLimitError
)
from app.api.routes import calls, webhooks, health, tenants

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler for startup and shutdown events
    """
    # Startup
    logger.info("=" * 60)
    logger.info("Starting Calling Agent - Enterprise Edition")
    logger.info(f"Version: 2.0.0")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"API Base URL: {settings.api_base_url}")
    logger.info(f"Twilio Phone: {settings.twilio_phone_number}")
    logger.info(f"Database Type: {settings.database_type}")
    logger.info("=" * 60)

    # Initialize services
    from app.services.call_manager import initialize_call_manager
    from app.services.tenant_service import get_tenant_service

    # Initialize tenant service
    tenant_service = get_tenant_service()
    logger.info(f"Loaded {len(tenant_service.tenants)} tenant(s)")

    # Initialize call manager with database
    manager = await initialize_call_manager()
    if manager._db_initialized:
        logger.info(f"Database ({settings.database_type}) initialized successfully")
    else:
        logger.info("Using file-based storage (database not configured)")
    logger.info(f"Loaded {len(manager.active_calls)} active calls")

    logger.info("All services initialized successfully")

    yield

    # Shutdown
    logger.info("Shutting down Calling Agent")

    # Clean up any active calls
    for call_id in list(manager.active_calls.keys()):
        try:
            await manager.end_call(call_id)
        except Exception as e:
            logger.error(f"Error ending call {call_id}: {e}")

    # Close database connection
    await manager.close_database()
    logger.info("Database connection closed")

    logger.info("Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Calling Agent API",
    description="""
    ## Enterprise Voice AI Agent

    Voice AI Agent that handles phone calls using Ultravox and Twilio.
    Designed for multi-tenant enterprise deployments.

    ### Features

    - **Multi-Tenant Support**: Configure different settings per client
    - **Outbound Calls**: Initiate AI-powered outbound calls
    - **Inbound Calls**: Handle incoming calls with voice AI
    - **Real-time Transcription**: Get live transcripts of calls
    - **Call Summaries**: Automatic summarization of completed calls
    - **Webhook Integration**: Receive status updates and events
    - **Rate Limiting**: Prevent abuse with configurable limits
    - **API Key Authentication**: Secure API access

    ### Authentication

    Include your API key in requests using one of these methods:
    - Header: `X-API-Key: your-api-key`
    - Bearer Token: `Authorization: Bearer your-api-key`
    - Query Parameter: `?api_key=your-api-key`

    ### Rate Limits

    - **Requests**: 60 requests/minute per tenant
    - **Calls**: 100 calls/hour per tenant
    - **Concurrent**: 10 concurrent calls per tenant
    """,
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins + ["*"],  # Allow all in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Custom Exception Handlers
@app.exception_handler(CallingAgentException)
async def calling_agent_exception_handler(request: Request, exc: CallingAgentException):
    """Handle custom calling agent exceptions"""
    logger.warning(f"CallingAgentException: {exc.error_code} - {exc.message}")
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
app.include_router(health.router)
app.include_router(calls.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")
app.include_router(tenants.router, prefix="/api/v1")

# Mount static files for frontend
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")


# Root endpoint - serve frontend
@app.get("/", include_in_schema=False)
async def root():
    """Serve the frontend UI"""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse({
        "service": "Calling Agent",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health"
    })


@app.get("/api")
async def api_info():
    """API information endpoint"""
    return {
        "service": "Calling Agent API",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "calls": "/api/v1/calls",
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
