"""Offer endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.post("/")
async def generate_offer() -> dict:
    """Generate an offer (placeholder)."""
    return {"message": "Offer generation endpoint - to be implemented"}


@router.get("/{offer_id}")
async def get_offer() -> dict:
    """Get offer by ID (placeholder)."""
    return {"message": "Offer retrieval endpoint - to be implemented"}

