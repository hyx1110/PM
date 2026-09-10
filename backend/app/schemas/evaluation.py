from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.common import ORMModel


class EvaluationUpsert(ORMModel):
    achievement_rate: Decimal = Field(ge=0, le=100)
    achievement_quality: Decimal = Field(ge=0, le=100)
    comment: str | None = None


class EvaluationResponse(ORMModel):
    id: int
    task_id: int
    evaluator_id: int
    evaluator_name: str | None = None
    achievement_rate: Decimal
    achievement_quality: Decimal
    comment: str | None
    evaluated_at: datetime
    created_at: datetime
    updated_at: datetime

