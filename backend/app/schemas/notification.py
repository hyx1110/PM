from datetime import datetime

from app.schemas.common import ORMModel


class NotificationResponse(ORMModel):
    id: int
    recipient_id: int
    event_type: str
    title: str
    content: str
    level: str
    related_type: str | None
    related_id: str | None
    delivered_channels: list | None
    email_status: str = "skipped"
    email_attempts: int = 0
    email_last_error: str | None = None
    email_next_attempt_at: datetime | None = None
    status: str
    read_at: datetime | None
    created_at: datetime
