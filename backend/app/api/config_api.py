"""Config API — expose runtime configuration to the frontend (H6)."""
from __future__ import annotations

from fastapi import APIRouter

from app.config import BrandingConfig, load_branding

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/branding", response_model=BrandingConfig)
async def get_branding() -> BrandingConfig:
    """Return the current branding configuration.

    The frontend fetches this once on startup to configure the UI title, accent
    colour, agent name, and spinner phrases.
    """
    return load_branding()
