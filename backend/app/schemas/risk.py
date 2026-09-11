from datetime import datetime

from pydantic import Field

from app.schemas.common import ORMModel


class RiskHandleRequest(ORMModel):
    status: str
    handling_note: str = Field(min_length=1, max_length=2000)


class RiskResponse(ORMModel):
    id: int
    fingerprint: str | None
    risk_type: str
    risk_level: str
    title: str | None
    project_id: int | None
    project_name: str | None = None
    task_id: int | None
    task_name: str | None = None
    user_id: int | None
    user_name: str | None = None
    status: str
    detail: str | None
    source_data: dict | None
    detected_at: datetime
    due_at: datetime | None
    handled_by: int | None
    handler_name: str | None = None
    handled_at: datetime | None
    handling_note: str | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime

