from datetime import datetime
from typing import Any

from app.schemas.common import ORMModel


class OperationLogResponse(ORMModel):
    id: int
    operator_id: int | None
    operator_name: str | None = None
    change_summary: str
    module: str
    action: str
    object_type: str
    object_id: str
    before_data: dict[str, Any] | None
    after_data: dict[str, Any] | None
    reason: str | None
    ip_address: str | None
    created_at: datetime
