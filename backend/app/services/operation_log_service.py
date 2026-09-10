import logging
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.models.operation_log import OperationLog

logger = logging.getLogger(__name__)


def log_operation(
    db: Session,
    *,
    operator_id: int | None,
    module: str,
    action: str,
    object_type: str,
    object_id: str | int,
    before_data: dict[str, Any] | None = None,
    after_data: dict[str, Any] | None = None,
    reason: str | None = None,
    ip_address: str | None = None,
) -> None:
    try:
        with db.begin_nested():
            db.add(
                OperationLog(
                    operator_id=operator_id,
                    module=module,
                    action=action,
                    object_type=object_type,
                    object_id=str(object_id),
                    before_data=jsonable_encoder(before_data) if before_data is not None else None,
                    after_data=jsonable_encoder(after_data) if after_data is not None else None,
                    reason=reason,
                    ip_address=ip_address,
                )
            )
            db.flush()
    except Exception:
        logger.exception("failed to persist operation log")
