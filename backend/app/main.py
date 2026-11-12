from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import init_db
import logging
from app.api.v1 import api_v1_router
from app.services.executor import recover_interrupted_jobs

# Configure structured application logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("repopilot")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database schema & storage folders
    init_db()
    settings.storage_path
    settings.uploads_path
    settings.extracted_path
    settings.workspaces_path
    settings.snapshots_path
    recovered = recover_interrupted_jobs()
    if recovered > 0:
        logger.info(f"Startup recovery: cleaned up {recovered} interrupted job(s) from previous run.")
    yield
    # Shutdown logic if needed


app = FastAPI(
    title=settings.APP_NAME,
    description="RepoPilot AI — Automated Repository Ingestion, Safety Validation, and AST Analysis Engine",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
origins = settings.CORS_ORIGINS
if isinstance(origins, str):
    origins = [origins]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Formats all HTTP exceptions into standard structured JSON without leaking tracebacks."""
    if isinstance(exc.detail, dict):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": {
                "error_code": f"HTTP_{exc.status_code}",
                "message": str(exc.detail),
                "details": {},
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Formats validation errors into clean structured JSON."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": {
                "error_code": "REQUEST_VALIDATION_ERROR",
                "message": "Input validation failed.",
                "details": {"errors": exc.errors()},
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catches unexpected exceptions, logs them internally, and returns structured safe error."""
    # In production/debug we mask internal server paths
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": {
                "error_code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected server error occurred during processing.",
                "details": {},
            }
        },
    )


# Register API v1
app.include_router(api_v1_router)


@app.get("/api/v1/health", tags=["Health"])
def health_check():
    """Health check endpoint to verify backend operational readiness."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "version": "1.0.0",
    }


@app.get("/", tags=["Root"])
def root():
    return {
        "app": settings.APP_NAME,
        "docs": "/docs",
        "api_v1": "/api/v1",
    }
