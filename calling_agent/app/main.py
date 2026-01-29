"""
Calling Agent - Main Application Entry Point

A voice AI agent that handles phone calls using Ultravox and Twilio.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.api.routes import calls, webhooks, health

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
    logger.info("Starting Calling Agent")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"API Base URL: {settings.api_base_url}")
    logger.info(f"Twilio Phone: {settings.twilio_phone_number}")
    logger.info("=" * 60)

    # Initialize services
    from app.services.call_manager import get_call_manager
    manager = get_call_manager()
    logger.info(f"Loaded {len(manager.call_history)} historical call records")

    yield

    # Shutdown
    logger.info("Shutting down Calling Agent")
    # Clean up any active calls
    for call_id in list(manager.active_calls.keys()):
        try:
            await manager.end_call(call_id)
        except Exception as e:
            logger.error(f"Error ending call {call_id}: {e}")


# Create FastAPI application
app = FastAPI(
    title="Calling Agent API",
    description="""
    Voice AI Agent that handles phone calls using Ultravox and Twilio.

    ## Features

    - **Outbound Calls**: Initiate AI-powered outbound calls
    - **Inbound Calls**: Handle incoming calls with voice AI
    - **Real-time Transcription**: Get live transcripts of calls
    - **Call Summaries**: Automatic summarization of completed calls
    - **Webhook Integration**: Receive status updates and events

    ## Authentication

    API authentication is not implemented in this demo version.
    In production, implement proper API key or OAuth authentication.
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.debug else "An unexpected error occurred"
        }
    )


# Include routers
app.include_router(health.router)
app.include_router(calls.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint - service information"""
    return {
        "service": "Calling Agent",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.debug
    )
