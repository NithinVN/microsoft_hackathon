from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.v1.router import api_router
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown lifecycle events."""
    logger.info("Initializing IncidentMind backend service...")
    logger.info("Environment: %s | Debug: %s", settings.APP_ENV, settings.DEBUG)
    logger.info("Active LLM Model Target: %s", settings.GROQ_MODEL)
    logger.info("Hindsight Endpoint Target: %s", settings.HINDSIGHT_API_URL)
    await init_db()
    yield
    logger.info("Shutting down IncidentMind backend service...")


app = FastAPI(
    title=settings.APP_NAME,
    description="IncidentMind - AI-powered Incident Response Agent with organizational memory powered by Hindsight Cloud.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    lifespan=lifespan,
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API v1 router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["Root"])
async def root() -> JSONResponse:
    """Root entrypoint with service metadata."""
    return JSONResponse(
        content={
            "app": settings.APP_NAME,
            "version": "1.0.0",
            "api_v1_prefix": settings.API_V1_PREFIX,
            "docs": "/docs",
            "health": f"{settings.API_V1_PREFIX}/health",
        }
    )


@app.get("/health", tags=["Health"])
async def root_health_alias() -> JSONResponse:
    """Convenience alias for /api/v1/health."""
    from backend.app.api.v1.endpoints.health import get_health

    health_data = await get_health()
    return JSONResponse(content=health_data.model_dump())
