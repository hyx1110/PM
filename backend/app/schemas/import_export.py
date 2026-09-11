from datetime import datetime

from app.schemas.common import ORMModel


class ImportRowError(ORMModel):
    row: int
    field: str | None = None
    message: str


class ImportJobResponse(ORMModel):
    id: int
    resource_type: str
    original_filename: str
    status: str
    total_rows: int
    success_rows: int
    failed_rows: int
    errors: list[dict] | None
    operator_id: int
    operator_name: str | None = None
    created_at: datetime
    updated_at: datetime

