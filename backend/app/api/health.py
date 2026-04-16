from fastapi import APIRouter

router = APIRouter()


@router.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    """Kubernetes liveness probe — confirms the process is alive."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness() -> dict[str, str]:
    """Kubernetes readiness probe — confirms the app is ready to serve traffic."""
    return {"status": "ok"}
