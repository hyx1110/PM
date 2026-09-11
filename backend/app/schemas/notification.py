from datetime import datetime

from pydantic import Field

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


class NotificationPreferenceUpdate(ORMModel):
    in_app_enabled: bool = True
    email_enabled: bool = False
    wecom_enabled: bool = False
    dingtalk_enabled: bool = False
    upcoming_hours: int = Field(default=24, ge=1, le=168)


class NotificationPreferenceResponse(NotificationPreferenceUpdate):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

