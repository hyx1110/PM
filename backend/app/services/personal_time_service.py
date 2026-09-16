from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, conflict, forbidden, not_found
from app.models.personal_time import PersonalTimeBlock
from app.models.user import User
from app.repositories.personal_time_repository import personal_time_repository
from app.repositories.schedule_repository import schedule_repository
from app.schemas.personal_time import PersonalTimeCreate
from app.services.operation_log_service import log_operation
from app.services.work_calendar_service import calculate_work_hours
from app.utils.model import model_to_dict
from app.services.visibility_service import visible_schedule_user_ids
from app.utils.time import beijing_now


def _serialize(item: PersonalTimeBlock, user_name: str | None = None) -> dict:
    data = model_to_dict(item)
    data["user_name"] = user_name
    return data


def list_blocks(
    db: Session,
    user: User,
    page: int,
    page_size: int,
    **filters,
) -> dict:
    items, total = personal_time_repository.list(
        db,
        page,
        page_size,
        visible_user_ids=visible_schedule_user_ids(db, user),
        **filters,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def list_my_blocks(
    db: Session,
    user: User,
    page: int,
    page_size: int,
    *,
    status: str | None = None,
) -> dict:
    return list_blocks(
        db,
        user,
        page,
        page_size,
        user_id=user.id,
        status=status,
        sort_order="desc",
    )


def create_block(
    db: Session,
    payload: PersonalTimeCreate,
    user: User,
) -> dict:
    locked_user = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if not locked_user or locked_user.is_deleted or locked_user.status != "active":
        raise not_found("user not found")
    hours = calculate_work_hours(db, payload.start_time, payload.end_time)
    conflicts = schedule_repository.find_conflicts(
        db, user.id, payload.start_time, payload.end_time
    )
    conflicts.extend(
        personal_time_repository.find_conflicts(
            db, user.id, payload.start_time, payload.end_time
        )
    )
    if conflicts:
        raise conflict(
            "该时间段已有项目预约或个人安排",
            40901,
            {"conflicts": conflicts},
        )
    item = PersonalTimeBlock(
        user_id=user.id,
        time_type=payload.time_type,
        start_time=payload.start_time,
        end_time=payload.end_time,
        planned_hours=hours,
        status="active",
        remark=payload.remark,
    )
    db.add(item)
    db.flush()
    log_operation(
        db,
        operator_id=user.id,
        module="schedule",
        action="create_personal_time",
        object_type="personal_time_block",
        object_id=item.id,
        after_data=model_to_dict(item),
    )
    db.commit()
    db.refresh(item)
    return _serialize(item, user.name)


def withdraw_block(db: Session, block_id: int, user: User) -> dict:
    item = personal_time_repository.get_for_update(db, block_id)
    if not item:
        raise not_found("personal time block not found")
    if item.user_id != user.id:
        raise forbidden("只能撤回自己的个人时间安排")
    if item.status != "active":
        raise bad_request("该个人时间安排已经撤回")
    before = model_to_dict(item)
    item.status = "withdrawn"
    item.withdrawn_at = beijing_now()
    log_operation(
        db,
        operator_id=user.id,
        module="schedule",
        action="withdraw_personal_time",
        object_type="personal_time_block",
        object_id=item.id,
        before_data=before,
        after_data=model_to_dict(item),
    )
    db.commit()
    db.refresh(item)
    return _serialize(item, user.name)
