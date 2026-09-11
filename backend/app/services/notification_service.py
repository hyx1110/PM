import smtplib
from datetime import datetime
from email.message import EmailMessage

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import not_found
from app.models.notification import Notification, NotificationPreference
from app.models.user import User
from app.schemas.notification import NotificationPreferenceUpdate


def get_or_create_preference(db: Session, user_id: int) -> NotificationPreference:
    preference = db.scalar(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    if not preference:
        preference = NotificationPreference(user_id=user_id)
        db.add(preference)
        db.flush()
    return preference


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
    preference = get_or_create_preference(db, recipient_id)
    if not preference.in_app_enabled and not any(
        (preference.email_enabled, preference.wecom_enabled, preference.dingtalk_enabled)
    ):
        return None
    delivered = ["in_app"] if preference.in_app_enabled else []
    item = Notification(
        recipient_id=recipient_id,
        event_type=event_type,
        title=title,
        content=content,
        level=level,
        related_type=related_type,
        related_id=str(related_id) if related_id is not None else None,
        delivered_channels=delivered,
    )
    db.add(item)
    db.flush()
    return item


def list_notifications(
    db: Session, user_id: int, page: int, page_size: int, status: str | None
) -> dict:
    filters = [Notification.recipient_id == user_id]
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
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def unread_count(db: Session, user_id: int) -> int:
    return db.scalar(
        select(func.count(Notification.id)).where(
            Notification.recipient_id == user_id, Notification.status == "unread"
        )
    ) or 0


def mark_read(db: Session, notification_id: int, user_id: int) -> Notification:
    item = db.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.recipient_id == user_id
        )
    )
    if not item:
        raise not_found("notification not found")
    if item.status == "unread":
        item.status = "read"
        item.read_at = datetime.now()
        db.commit()
        db.refresh(item)
    return item


def mark_all_read(db: Session, user_id: int) -> int:
    result = db.execute(
        update(Notification)
        .where(Notification.recipient_id == user_id, Notification.status == "unread")
        .values(status="read", read_at=datetime.now())
    )
    db.commit()
    return result.rowcount or 0


def update_preference(
    db: Session, user_id: int, payload: NotificationPreferenceUpdate
) -> NotificationPreference:
    item = get_or_create_preference(db, user_id)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def _send_email(user: User, item: Notification) -> bool:
    if not settings.smtp_host or not settings.smtp_from or not user.email:
        return False
    message = EmailMessage()
    message["Subject"] = item.title
    message["From"] = settings.smtp_from
    message["To"] = user.email
    message.set_content(item.content)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as client:
        if settings.smtp_use_tls:
            client.starttls()
        if settings.smtp_username:
            client.login(settings.smtp_username, settings.smtp_password or "")
        client.send_message(message)
    return True


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
    rows = db.execute(
        select(Notification, NotificationPreference, User)
        .join(User, User.id == Notification.recipient_id)
        .join(NotificationPreference, NotificationPreference.user_id == Notification.recipient_id)
        .order_by(Notification.created_at.desc())
        .limit(max(limit, 500))
    ).all()
    delivered_count = 0
    failed_count = 0
    for item, preference, user in rows:
        delivered = list(item.delivered_channels or [])
        channels = [
            ("email", preference.email_enabled, lambda: _send_email(user, item)),
            ("wecom", preference.wecom_enabled, lambda: _send_webhook(settings.wecom_webhook_url, item, "wecom")),
            ("dingtalk", preference.dingtalk_enabled, lambda: _send_webhook(settings.dingtalk_webhook_url, item, "dingtalk")),
        ]
        changed = False
        for channel, enabled, sender in channels:
            if not enabled or channel in delivered:
                continue
            try:
                if sender():
                    delivered.append(channel)
                    delivered_count += 1
                    changed = True
            except (OSError, smtplib.SMTPException, httpx.HTTPError):
                failed_count += 1
        if changed:
            item.delivered_channels = delivered
    db.commit()
    return {"delivered": delivered_count, "failed": failed_count}
