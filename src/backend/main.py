"""
FastAPI main application entry point.

Configures CORS, routers, and lifespan events for database and background tasks.
"""

import logging
import socket
from contextlib import asynccontextmanager
from datetime import datetime

# Force IPv4 to avoid IPv6 timeouts
old_getaddrinfo = socket.getaddrinfo
def new_getaddrinfo(*args, **kwargs):
    responses = old_getaddrinfo(*args, **kwargs)
    return [response for response in responses if response[0] == socket.AF_INET]
socket.getaddrinfo = new_getaddrinfo

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.backend.config import settings
from src.backend.database import close_db, init_db
from src.backend.polymarket.client import polymarket_client
from src.backend.news.aggregator import news_aggregator
from src.backend.routes import markets, news, debate
from src.backend.tasks.update_markets import get_scheduler, update_top_markets

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.

    Handles startup and shutdown events.
    """
    logger.info("Starting Polymarket News Tracker API...")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Run initial market update
    try:
        await update_top_markets()
        logger.info("Initial market data loaded")
    except Exception as e:
        logger.error(f"Failed to load initial market data: {e}")

    # Start background scheduler
    scheduler = get_scheduler()
    scheduler.start()
    logger.info("Background scheduler started")

    yield

    # Shutdown
    logger.info("Shutting down...")
    scheduler.shutdown()
    await polymarket_client.close()
    await news_aggregator.close()
    await close_db()
    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Polymarket News Tracker API",
    description="API for tracking top Polymarket markets with real-time news",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(markets.router)
app.include_router(news.router)
app.include_router(debate.router)


@app.get("/api/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0",
    }


@app.get("/")
async def root() -> dict:
    """Root endpoint with API info."""
    return {
        "name": "Polymarket News Tracker API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
