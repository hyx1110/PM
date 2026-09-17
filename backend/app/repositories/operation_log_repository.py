from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.operation_log import OperationLog
from app.models.user import User
from app.services.operation_log_service import describe_change


class OperationLogRepository:
    def list(
        self,
        db: Session,
        page: int,
        page_size: int,
        operator_id: int | None = None,
        module: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> tuple[list[dict], int]:
        filters = []
        if operator_id:
            filters.append(OperationLog.operator_id == operator_id)
        if module:
            filters.append(OperationLog.module == module)
        if start_date:
            filters.append(OperationLog.created_at >= datetime.combine(start_date, time.min))
        if end_date:
            filters.append(OperationLog.created_at < datetime.combine(end_date + timedelta(days=1), time.min))
        total = db.scalar(select(func.count(OperationLog.id)).where(*filters)) or 0
        rows = db.execute(
            select(OperationLog, User.name.label("operator_name"))
            .outerjoin(User, User.id == OperationLog.operator_id)
            .where(*filters)
            .order_by(OperationLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return [
            {
                **{col.name: getattr(item, col.name) for col in OperationLog.__table__.columns},
                "operator_name": operator_name,
                "change_summary": (
                    f"{operator_name or '系统'} "
                    + describe_change(
                        item.action,
                        item.object_type,
                        item.object_id,
                        item.before_data,
                        item.after_data,
                    )
                ),
            }
            for item, operator_name in rows
        ], total


operation_log_repository = OperationLogRepository()
