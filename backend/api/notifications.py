from fastapi import APIRouter, Depends, HTTPException

from services.auth_service import get_current_user
from services.notification_service import (
    get_notifications_for_user,
    mark_notification_read,
)

router = APIRouter()


@router.get("")
def list_notifications(user: dict = Depends(get_current_user)):
    result = get_notifications_for_user(user["id"])
    return {"success": True, "data": result, "error": None}


@router.post("/{notification_id}/read")
def read_notification(notification_id: str, user: dict = Depends(get_current_user)):
    result = mark_notification_read(notification_id, user["id"])
    if not result:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"success": True, "data": result, "error": None}