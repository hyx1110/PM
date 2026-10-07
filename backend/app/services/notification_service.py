import smtplib

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import not_found
from app.models.notification import Notification
from app.models.user import User
from app.services.email_service import dispatch_email_pending
from app.services.business_text_service import BOOKING_CONTEXT_PREFIXES, booking_contexts, numeric_id, readable_booking_notification
from app.utils.model import model_to_dict
from app.utils.time import beijing_now


def create_notification(
    db: Session,
    recipient_id: int,
    event_type: str,
    title: str,
    content: str,
    *,
    level: str = "info",
    related_type: str | None = None,
    related_id: int | str | None = None,
) -> Notification | None:
    # Notification preferences are no longer user-facing. Every business
    # notification is therefore persisted to the in-app notification center.
    if related_type in {"schedule", "schedule_booking"} and not content.startswith(BOOKING_CONTEXT_PREFIXES):
        booking_id = numeric_id(related_id)
        context = booking_contexts(db, {booking_id} if booking_id is not None else set()).get(booking_id)
        content = readable_booking_notification(event_type, content, context or "关联预约资料已不存在，无法还原人员、项目及任务信息。")
    delivered = ["in_app"]
    recipient = db.get(User, recipient_id) if settings.smtp_enabled else None
    item = Notification(
        recipient_id=recipient_id,
        event_type=event_type,
        title=title,
        content=content,
        level=level,
        related_type=related_type,
        related_id=str(related_id) if related_id is not None else None,
        delivered_channels=delivered,
        email_status=("pending" if recipient and recipient.email else "skipped") if settings.smtp_enabled else "disabled",
        email_attempts=0,
    )
    db.add(item)
    db.flush()
    return item


def list_notifications(
    db: Session, user_id: int, page: int, page_size: int, status: str | None
) -> dict:
    filters = [
        Notification.recipient_id == user_id,
        Notification.is_deleted.is_(False),
    ]
    if status:
        filters.append(Notification.status == status)
    total = db.scalar(select(func.count(Notification.id)).where(*filters)) or 0
    items = db.scalars(
        select(Notification)
        .where(*filters)
        .order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    # Legacy notifications have no event-time name snapshot. Enrich their
    # display only, without replacing history or changing read/email state.
    legacy = [item for item in items if item.related_type in {"schedule", "schedule_booking"} and not item.content.startswith(BOOKING_CONTEXT_PREFIXES)]
    ids = {uid for item in legacy if (uid := numeric_id(item.related_id)) is not None}
    contexts = booking_contexts(db, ids, include_time=False)
    legacy_ids = {item.id for item in legacy}
    output = []
    for item in items:
        data = model_to_dict(item)
        if item.id in legacy_ids:
            context = contexts.get(numeric_id(item.related_id), "关联预约资料已不存在，无法还原人员、项目及任务信息。")
            data["content"] = readable_booking_notification(item.event_type, item.content, context)
        output.append(data)
    return {"items": output, "total": total, "page": page, "page_size": page_size}


def unread_count(db: Session, user_id: int) -> int:
    return db.scalar(
        select(func.count(Notification.id)).where(
            Notification.recipient_id == user_id,
            Notification.status == "unread",
            Notification.is_deleted.is_(False),
        )
    ) or 0


def mark_read(db: Session, notification_id: int, user_id: int) -> Notification:
    item = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_id == user_id,
            Notification.is_deleted.is_(False),
        )
    )
    if not item:
        raise not_found("notification not found")
    if item.status == "unread":
        item.status = "read"
        item.read_at = beijing_now()
        db.commit()
        db.refresh(item)
    return item


def mark_all_read(db: Session, user_id: int) -> int:
    result = db.execute(
        update(Notification)
        .where(
            Notification.recipient_id == user_id,
            Notification.status == "unread",
            Notification.is_deleted.is_(False),
        )
        .values(status="read", read_at=beijing_now())
    )
    db.commit()
    return result.rowcount or 0


def delete_notification(db: Session, notification_id: int, user_id: int) -> None:
    item = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_id == user_id,
            Notification.is_deleted.is_(False),
        )
    )
    if not item:
        raise not_found("notification not found")
    item.is_deleted = True
    if item.status == "unread":
        item.status = "read"
        item.read_at = beijing_now()
    db.commit()


def delete_read_notifications(db: Session, user_id: int) -> int:
    result = db.execute(
        update(Notification)
        .where(
            Notification.recipient_id == user_id,
            Notification.status == "read",
            Notification.is_deleted.is_(False),
        )
        .values(is_deleted=True)
    )
    db.commit()
    return result.rowcount or 0


def _send_webhook(url: str | None, item: Notification, channel: str) -> bool:
    if not url:
        return False
    if channel == "wecom":
        payload = {"msgtype": "text", "text": {"content": f"{item.title}\n{item.content}"}}
    else:
        payload = {"msgtype": "text", "text": {"content": f"{item.title}\n{item.content}"}}
    response = httpx.post(url, json=payload, timeout=10)
    response.raise_for_status()
    return True


def dispatch_pending(db: Session, limit: int = 100) -> dict:
    email_result = dispatch_email_pending(db, limit)
    external_channels_configured = bool(
        settings.wecom_webhook_url
        or settings.dingtalk_webhook_url
    )
    if not external_channels_configured:
        return email_result
    delivered_count = email_result["delivered"]
    failed_count = email_result["failed"]
    attempted_notifications = email_result["attempted"]
    page = 0
    scan_size = max(limit, 100)
    while attempted_notifications < limit:
        rows = db.execute(
            select(Notification, User)
            .join(User, User.id == Notification.recipient_id)
            .where(
                Notification.is_deleted.is_(False),
                User.status == "active",
                User.is_deleted.is_(False),
            )
            .order_by(Notification.id.desc())
            .offset(page * scan_size)
            .limit(scan_size)
        ).all()
        if not rows:
            break
        page += 1
        for item, user in rows:
            delivered = list(item.delivered_channels or [])
            channels = [
                (
                    "wecom",
                    bool(settings.wecom_webhook_url),
                    lambda: _send_webhook(
                        settings.wecom_webhook_url, item, "wecom"
                    ),
                ),
                (
                    "dingtalk",
                    bool(settings.dingtalk_webhook_url),
                    lambda: _send_webhook(
                        settings.dingtalk_webhook_url, item, "dingtalk"
                    ),
                ),
            ]
            pending_channels = [
                (channel, sender)
                for channel, available, sender in channels
                if available and channel not in delivered
            ]
            if not pending_channels:
                continue
            attempted_notifications += 1
            changed = False
            for channel, sender in pending_channels:
                try:
                    if sender():
                        delivered.append(channel)
                        delivered_count += 1
                        changed = True
                except (OSError, smtplib.SMTPException, httpx.HTTPError):
                    failed_count += 1
            if changed:
                item.delivered_channels = delivered
            if attempted_notifications >= limit:
                break
    db.commit()
    return {
        "attempted": attempted_notifications,
        "delivered": delivered_count,
        "failed": failed_count,
    }
