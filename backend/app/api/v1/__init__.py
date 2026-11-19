from fastapi import APIRouter
from app.api.v1.repositories import router as repositories_router
from app.api.v1.files import router as files_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.diagnostics import router as diagnostics_router
from app.api.v1.validations import router as validations_router
from app.api.v1.runner_callbacks import router as runner_callbacks_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(repositories_router)
api_v1_router.include_router(files_router)
api_v1_router.include_router(jobs_router)
api_v1_router.include_router(diagnostics_router)
api_v1_router.include_router(validations_router)
api_v1_router.include_router(runner_callbacks_router)
