"""Transactional notification outbox; SMTP runs only in the background worker."""
import logging
import smtplib
import ssl
from datetime import timedelta
from email.message import EmailMessage
from email.utils import format_datetime, parseaddr

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.notification import Notification
from app.models.user import User
from app.utils.time import BEIJING_TIMEZONE, beijing_now

logger = logging.getLogger(__name__)


def send_email(user: User, item: Notification) -> bool:
    if not settings.smtp_enabled or not settings.smtp_host or not settings.smtp_from or not user.email:
        return False
    message = EmailMessage()
    message["Subject"] = settings.smtp_subject_prefix + item.title
    message["From"] = settings.smtp_from
    message["To"] = user.email
    message["Date"] = format_datetime(beijing_now().replace(tzinfo=BEIJING_TIMEZONE))
    domain = parseaddr(settings.smtp_from)[1].partition("@")[2] or "project.internal"
    message["Message-ID"] = f"<notification-{item.id}@{domain}>"
    content = f"{item.content}\n\n此邮件由项目协同系统自动发送，请勿直接回复。"
    if settings.public_app_url:
        if item.related_type == "overtime":
            scope = "approvals" if item.event_type in {"overtime_requested", "overtime_withdrawn"} else "mine"
            path = f"/executions?tab=overtime&scope={scope}"
        else:
            path = "/notifications"
        content += f"\n进入系统：{settings.public_app_url.rstrip('/')}{path}"
    message.set_content(content)
    context = ssl.create_default_context(cafile=settings.smtp_ca_file or None) if (settings.smtp_use_ssl or settings.smtp_use_tls) else None
    connection = (
        smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds, context=context)
        if settings.smtp_use_ssl else
        smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds)
    )
    with connection as client:
        if settings.smtp_use_tls:
            client.starttls(context=context)
        if settings.smtp_username:
            client.login(settings.smtp_username, settings.smtp_password or "")
        client.send_message(message)
    return True


def dispatch_email_pending(db: Session, limit: int = 100) -> dict:
    result = {"attempted": 0, "delivered": 0, "failed": 0}
    if not settings.smtp_enabled:
        return result
    for _ in range(limit):
        # Locks held through the bounded SMTP operation avoid duplicate delivery
        # by concurrent workers. SMTP cannot guarantee exactly-once after a crash.
        item = db.scalar(select(Notification).where(
            Notification.email_status == "pending", Notification.is_deleted.is_(False),
            or_(Notification.email_next_attempt_at.is_(None), Notification.email_next_attempt_at <= beijing_now()),
        ).order_by(Notification.id).limit(1).with_for_update(skip_locked=True))
        if item is None:
            db.commit()
            break
        user = db.get(User, item.recipient_id)
        if not user or user.is_deleted or user.status != "active" or not user.email:
            item.email_status = "skipped"
            item.email_last_error = "收件人已停用或未配置邮箱"
            db.commit()
            continue
        result["attempted"] += 1
        item.email_attempts += 1
        try:
            if not send_email(user, item):
                item.email_status = "skipped"
            else:
                item.email_status = "sent"
                item.email_last_error = None
                item.email_next_attempt_at = None
                item.delivered_channels = list(dict.fromkeys([*(item.delivered_channels or []), "email"]))
                result["delivered"] += 1
        except (OSError, smtplib.SMTPException, ValueError) as exc:
            # Do not persist raw SMTP responses, credentials or message content.
            code = getattr(exc, "smtp_code", None)
            item.email_last_error = f"{type(exc).__name__}" + (f" (SMTP {code})" if code else "")
            item.email_status = "failed" if item.email_attempts >= settings.smtp_max_attempts else "pending"
            item.email_next_attempt_at = (
                beijing_now() + timedelta(minutes=min(5 * 2 ** (item.email_attempts - 1), 60))
                if item.email_status == "pending" else None
            )
            result["failed"] += 1
            logger.warning("Notification %s email attempt %s failed: %s", item.id, item.email_attempts, item.email_last_error)
        db.commit()
    return result
