"""
FastAPI main application entry point.
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.routers import timepoint, feed, email

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup/shutdown events.
    """
    logger.info("Starting TIMEPOINT AI backend")
    
    # Configure Logfire if token present
    if settings.LOGFIRE_TOKEN:
        try:
            import logfire
            logfire.configure(token=settings.LOGFIRE_TOKEN)
            logfire.instrument_fastapi(app)
            logger.info("Logfire instrumentation enabled")
        except Exception as e:
            logger.warning(f"Logfire setup failed: {e}")
            
    yield
    
    logger.info("Shutting down TIMEPOINT AI backend")

def create_app() -> FastAPI:
    """
    Application factory.
    """
    app = FastAPI(
        title=settings.SITE_NAME,
        description="Time Portal API - Google Generative AI Suite",
        version="1.0.0",
        docs_url="/api/docs" if settings.DEBUG else None,
        lifespan=lifespan
    )

    # Configure CORS
    # Allow frontend origins
    origins = settings.ALLOWED_ORIGINS
    # Add common dev ports just in case
    origins.extend(["http://localhost:5173", "http://localhost:4321"])
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(timepoint.router, prefix="/api/timepoint", tags=["timepoint"])
    app.include_router(feed.router, prefix="/api/feed", tags=["feed"])
    app.include_router(email.router, prefix="/api/email", tags=["email"])

    @app.get("/")
    async def root():
        """API Root."""
        return {
            "service": "TIMEPOINT AI API",
            "status": "running",
            "version": "1.0.0",
            "docs": "/api/docs"
        }

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "service": "timepoint-flash"
        }

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=5000,
        reload=settings.DEBUG
    )
