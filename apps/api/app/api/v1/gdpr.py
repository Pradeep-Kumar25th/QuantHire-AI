"""GDPR compliance endpoints — not yet implemented."""

from fastapi import APIRouter, HTTPException, status

router = APIRouter()


def _not_implemented(operation: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"GDPR {operation} is not implemented yet. Contact your administrator.",
    )


@router.post("/export")
async def export_user_data() -> None:
    """Export all user data (GDPR Article 15)."""
    _not_implemented("data export")


@router.delete("/delete")
async def delete_user_data() -> None:
    """Delete all user data (GDPR Article 17)."""
    _not_implemented("data deletion")


@router.post("/consent")
async def update_consent() -> None:
    """Update user consent preferences."""
    _not_implemented("consent update")


@router.get("/consent")
async def get_consent() -> None:
    """Get current consent status."""
    _not_implemented("consent retrieval")
