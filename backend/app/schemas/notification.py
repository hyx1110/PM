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
    status: str
    read_at: datetime | None
    created_at: datetime
