"""Interview endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.post("/")
async def schedule_interview() -> dict:
    """Schedule an interview (placeholder)."""
    return {"message": "Interview scheduling endpoint - to be implemented"}


@router.get("/{interview_id}")
async def get_interview() -> dict:
    """Get interview by ID (placeholder)."""
    return {"message": "Interview retrieval endpoint - to be implemented"}

