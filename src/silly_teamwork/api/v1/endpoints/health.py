from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Application liveness probe")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
