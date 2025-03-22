from fastapi import APIRouter, HTTPException

from api.types import ToggleFlag
from seguimiento_parlamentario.core.db import get_db

# Router configuration
router = APIRouter(prefix="/config", tags=["Configurations"])

# Database connection
db = get_db()


@router.put("/commission/{commission_id}/extraction")
def update_extraction_enabled(commission_id: int, payload: ToggleFlag):
    """
    Enable or disable automatic extraction for a given commission.

    Args:
        commission_id (int): ID of the commission.
        payload (ToggleFlag): Object with an `enabled` flag.

    Returns:
        dict: Success message with the new extraction status.

    Raises:
        HTTPException: If database update fails.
    """
    try:
        db.update_extraction_enabled(commission_id, payload.enabled)
        return {
            "message": f"Extraction enabled set to {payload.enabled} for commission {commission_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/commission/{commission_id}/processing")
def update_processing_enabled(commission_id: int, payload: ToggleFlag):
    """
    Enable or disable automatic processing for a given commission.

    Args:
        commission_id (int): ID of the commission.
        payload (ToggleFlag): Object with an `enabled` flag.

    Returns:
        dict: Success message with the new processing status.

    Raises:
        HTTPException: If database update fails.
    """
    try:
        db.update_processing_enabled(commission_id, payload.enabled)
        return {
            "message": f"Automatic processing enabled set to {payload.enabled} for commission {commission_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
