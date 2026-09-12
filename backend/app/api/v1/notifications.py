from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.responses import success
from app.models.user import User
from app.schemas.notification import NotificationPreferenceUpdate
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["通知中心"])


@router.get("")
def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    current_user: User = Depends(require_permission("notification:view")),
    db: Session = Depends(get_db),
):
    return success(notification_service.list_notifications(db, current_user.id, page, page_size, status))


@router.get("/unread-count")
def get_unread_count(
    current_user: User = Depends(require_permission("notification:view")),
    db: Session = Depends(get_db),
):
    return success({"count": notification_service.unread_count(db, current_user.id)})


@router.get("/preferences")
def get_preferences(
    current_user: User = Depends(require_permission("notification:view")),
    db: Session = Depends(get_db),
):
    item = notification_service.get_or_create_preference(db, current_user.id)
    db.commit()
    db.refresh(item)
    return success(item)


@router.put("/preferences")
def update_preferences(
    payload: NotificationPreferenceUpdate,
    current_user: User = Depends(require_permission("notification:view")),
    db: Session = Depends(get_db),
):
    return success(notification_service.update_preference(db, current_user.id, payload))


@router.post("/read-all")
def read_all(
    current_user: User = Depends(require_permission("notification:view")),
    db: Session = Depends(get_db),
):
    return success({"updated": notification_service.mark_all_read(db, current_user.id)})


@router.delete("/read")
def delete_read(
    current_user: User = Depends(require_permission("notification:view")),
    db: Session = Depends(get_db),
):
    return success({"deleted": notification_service.delete_read_notifications(db, current_user.id)})


@router.post("/{notification_id}/read")
def read_one(
    notification_id: int,
    current_user: User = Depends(require_permission("notification:view")),
    db: Session = Depends(get_db),
):
    return success(notification_service.mark_read(db, notification_id, current_user.id))


@router.delete("/{notification_id}")
def delete_one(
    notification_id: int,
    current_user: User = Depends(require_permission("notification:view")),
    db: Session = Depends(get_db),
):
    notification_service.delete_notification(db, notification_id, current_user.id)
    return success(None)
