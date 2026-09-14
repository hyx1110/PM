from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.personal_time import PersonalTimeBlock
from app.models.user import User

PERSONAL_TIME_TYPE_LABELS = {
    "training": "培训",
    "meeting": "会议",
    "leave": "休假",
    "business_trip": "出差",
    "other": "其他安排",
}


class PersonalTimeRepository:
    def get(self, db: Session, block_id: int) -> PersonalTimeBlock | None:
        return db.get(PersonalTimeBlock, block_id)

    def get_for_update(self, db: Session, block_id: int) -> PersonalTimeBlock | None:
        return db.scalar(
            select(PersonalTimeBlock)
            .where(PersonalTimeBlock.id == block_id)
            .with_for_update()
        )

    def list(
        self,
        db: Session,
        page: int,
        page_size: int,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        user_id: int | None = None,
        status: str | None = None,
        sort_order: str = "asc",
        visible_user_ids: set[int] | None = None,
    ) -> tuple[list[dict], int]:
        filters = []
        if start_date:
            filters.append(
                PersonalTimeBlock.end_time > datetime.combine(start_date, time.min)
            )
        if end_date:
            filters.append(
                PersonalTimeBlock.start_time
                < datetime.combine(end_date + timedelta(days=1), time.min)
            )
        if user_id:
            filters.append(PersonalTimeBlock.user_id == user_id)
        if status:
            filters.append(PersonalTimeBlock.status == status)
        if visible_user_ids is not None:
            filters.append(
                PersonalTimeBlock.user_id.in_(visible_user_ids or {-1})
            )
        base = select(PersonalTimeBlock).where(*filters)
        total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
        start_order = (
            PersonalTimeBlock.start_time.desc()
            if sort_order == "desc"
            else PersonalTimeBlock.start_time.asc()
        )
        rows = db.execute(
            select(PersonalTimeBlock, User.name.label("user_name"))
            .join(User, User.id == PersonalTimeBlock.user_id)
            .where(*filters)
            .order_by(start_order, PersonalTimeBlock.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        items = []
        for item, user_name in rows:
            data = {
                column.name: getattr(item, column.name)
                for column in PersonalTimeBlock.__table__.columns
            }
            data["user_name"] = user_name
            items.append(data)
        return items, total

    def find_conflicts(
        self,
        db: Session,
        user_id: int,
        start_time: datetime,
        end_time: datetime,
        exclude_id: int | None = None,
    ) -> list[dict]:
        statement = (
            select(PersonalTimeBlock, User.name.label("user_name"))
            .join(User, User.id == PersonalTimeBlock.user_id)
            .where(
                PersonalTimeBlock.user_id == user_id,
                PersonalTimeBlock.status == "active",
                PersonalTimeBlock.start_time < end_time,
                PersonalTimeBlock.end_time > start_time,
            )
        )
        if exclude_id:
            statement = statement.where(PersonalTimeBlock.id != exclude_id)
        rows = db.execute(statement.order_by(PersonalTimeBlock.start_time)).all()
        return [
            {
                "conflict_type": "personal_time",
                "conflict_id": item.id,
                "schedule_id": None,
                "personal_time_id": item.id,
                "project_id": None,
                "project_name": "个人时间安排",
                "task_id": None,
                "task_name": PERSONAL_TIME_TYPE_LABELS.get(
                    item.time_type, item.time_type
                ),
                "personal_time_type": item.time_type,
                "user_id": item.user_id,
                "user_name": user_name,
                "start_time": item.start_time,
                "end_time": item.end_time,
            }
            for item, user_name in rows
        ]


personal_time_repository = PersonalTimeRepository()
