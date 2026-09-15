from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.models.project import Project
from app.models.risk import RiskRecord
from app.models.task import Task
from app.models.user import User


class RiskRepository:
    def get(self, db: Session, risk_id: int) -> RiskRecord | None:
        return db.get(RiskRecord, risk_id)

    def by_fingerprint(self, db: Session, fingerprint: str) -> RiskRecord | None:
        return db.scalar(select(RiskRecord).where(RiskRecord.fingerprint == fingerprint))

    def list(
        self,
        db: Session,
        page: int,
        page_size: int,
        *,
        status: str | None = None,
        risk_type: str | None = None,
        risk_level: str | None = None,
        project_id: int | None = None,
        user_id: int | None = None,
        viewer_id: int | None = None,
        visible_project_ids: set[int] | None = None,
    ) -> tuple[list[dict], int]:
        filters = []
        if status:
            filters.append(RiskRecord.status == status)
        if risk_type:
            filters.append(RiskRecord.risk_type == risk_type)
        if risk_level:
            filters.append(RiskRecord.risk_level == risk_level)
        if project_id:
            filters.append(RiskRecord.project_id == project_id)
        if user_id:
            filters.append(RiskRecord.user_id == user_id)
        if visible_project_ids is not None:
            filters.append(
                (RiskRecord.project_id.in_(visible_project_ids or {-1}))
                | (RiskRecord.user_id == (viewer_id or -1))
            )
        total = db.scalar(select(func.count(RiskRecord.id)).where(*filters)) or 0
        handler = aliased(User)
        rows = db.execute(
            select(
                RiskRecord,
                Project.name.label("project_name"),
                Task.name.label("task_name"),
                User.name.label("user_name"),
                handler.name.label("handler_name"),
            )
            .outerjoin(Project, Project.id == RiskRecord.project_id)
            .outerjoin(Task, Task.id == RiskRecord.task_id)
            .outerjoin(User, User.id == RiskRecord.user_id)
            .outerjoin(handler, handler.id == RiskRecord.handled_by)
            .where(*filters)
            .order_by(RiskRecord.status, RiskRecord.risk_level, RiskRecord.detected_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        items = []
        for item, project_name, task_name, user_name, handler_name in rows:
            data = {column.name: getattr(item, column.name) for column in RiskRecord.__table__.columns}
            data.update(
                project_name=project_name,
                task_name=task_name,
                user_name=user_name,
                handler_name=handler_name,
            )
            items.append(data)
        return items, total


risk_repository = RiskRepository()
