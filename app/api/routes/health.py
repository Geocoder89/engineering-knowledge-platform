from fastapi import APIRouter, Response

from app.schemas.health import HealthResponse, ReadinessResponse
from app.services import readiness as readiness_service

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
)
def get_readiness(response: Response) -> ReadinessResponse:
    response.headers["Cache-Control"] = "no-store"
    if not readiness_service.is_database_ready():
        response.status_code = 503
        return ReadinessResponse(status="unavailable")
    return ReadinessResponse(status="ready")
