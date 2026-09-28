from datetime import datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from app.core.exceptions import bad_request, conflict, forbidden, not_found
from app.models.evaluation import ProjectEvaluation
from app.models.execution import ExecutionRecord
from app.models.overtime import OvertimeRequest
from app.models.project import Project, ProjectMember
from app.models.task import Task, TaskAssignee
from app.models.user import User
from app.schemas.overtime import OvertimeCreate, OvertimeDecision
from app.services.notification_service import create_notification
from app.services.operation_log_service import log_operation
from app.services.visibility_service import has_global_project_access
from app.services.work_calendar_service import (
    AFTERNOON_END, AFTERNOON_START, MORNING_END, MORNING_START, is_workday,
)
from app.utils.model import model_to_dict
from app.utils.time import beijing_now

OVERTIME_STATUSES = {"pending", "approved", "rejected", "withdrawn"}


def unrecorded_overtime_filters() -> list:
    recorded = select(ExecutionRecord.overtime_request_id).where(
        ExecutionRecord.overtime_request_id.is_not(None),
        ExecutionRecord.is_deleted.is_(False),
    )
    return [OvertimeRequest.status.in_({"pending", "approved"}), OvertimeRequest.id.notin_(recorded)]


def assert_no_unrecorded_overtime(db: Session, *, task_id=None, project_id=None, exclude_id=None) -> None:
    filters = unrecorded_overtime_filters()
    if task_id is not None:
        filters.append(OvertimeRequest.task_id == task_id)
    if project_id is not None:
        filters.append(OvertimeRequest.project_id == project_id)
    if exclude_id is not None:
        filters.append(OvertimeRequest.id != exclude_id)
    if db.scalar(select(OvertimeRequest.id).where(*filters).limit(1).with_for_update()):
        raise bad_request("请先处理该任务/项目待审批或尚未填报的加班申请（可填报、驳回或撤回）")


def calculate_overtime_hours(db: Session, start: datetime, end: datetime) -> Decimal:
    midnight_boundary = end == datetime.combine(start.date() + timedelta(days=1), time.min)
    if end <= start or (start.date() != end.date() and not midnight_boundary):
        raise bad_request("加班必须在同一天内，结束时间须晚于开始时间；跨日请拆分申请")
    if any(t.second or t.microsecond or t.minute not in {0, 30} for t in (start, end)):
        raise bad_request("加班时间必须按半小时选择")
    if is_workday(db, start.date()):
        for opening, closing in ((MORNING_START, MORNING_END), (AFTERNOON_START, AFTERNOON_END)):
            if start < datetime.combine(start.date(), closing) and end > datetime.combine(start.date(), opening):
                raise bad_request("加班申请不能包含正常工作时段（08:30–12:00、13:00–17:30）")
    return (Decimal(int((end - start).total_seconds())) / Decimal(3600)).quantize(Decimal("0.01"))


def _validate_context(db: Session, project: Project, task: Task, user_id: int) -> None:
    if project.is_deleted or project.approval_status != "approved" or project.status == "completed":
        raise bad_request("只有已审批且未结束的项目可以申请或批准加班")
    if task.is_deleted or task.status == "completed":
        raise bad_request("已完成或已删除的任务不能申请或批准加班")
    if db.scalar(select(ProjectEvaluation.id).where(ProjectEvaluation.project_id == project.id).with_for_update()):
        raise bad_request("已评价项目不能申请加班")
    if db.scalar(select(Task.id).where(Task.parent_id == task.id, Task.is_deleted.is_(False)).limit(1).with_for_update()):
        raise bad_request("请选择末级任务，汇总任务不能申请加班")
    if not db.scalar(select(ProjectMember.id).where(
        ProjectMember.project_id == project.id, ProjectMember.user_id == user_id, ProjectMember.left_at.is_(None)
    ).with_for_update()) or not db.scalar(select(TaskAssignee.id).where(TaskAssignee.task_id == task.id, TaskAssignee.user_id == user_id).with_for_update()):
        raise forbidden("只能为自己参与的项目和自己负责的任务申请加班")
    person = db.get(User, user_id)
    if not person or person.is_deleted or person.status != "active":
        raise bad_request("加班申请人已停用或不存在")


def _check_conflicts(db: Session, user_id: int, start: datetime, end: datetime, exclude_id=None) -> None:
    filters = [
        OvertimeRequest.user_id == user_id,
        OvertimeRequest.status.in_({"pending", "approved"}),
        OvertimeRequest.start_time < end, OvertimeRequest.end_time > start,
    ]
    if exclude_id is not None:
        filters.append(OvertimeRequest.id != exclude_id)
    if db.scalar(select(OvertimeRequest.id).where(*filters).limit(1).with_for_update()):
        raise conflict("该时段已有待审批或已批准的加班申请，请勿重复申请")


def _lock_context(db: Session, task_id: int, user_id: int) -> tuple[Project, Task]:
    project_id = db.scalar(select(Task.project_id).where(Task.id == task_id))
    project = db.scalar(select(Project).where(Project.id == project_id).with_for_update().execution_options(populate_existing=True))
    task = db.scalar(select(Task).where(Task.id == task_id).with_for_update().execution_options(populate_existing=True))
    if not project or not task:
        raise not_found("项目或任务不存在")
    # Serializes one person's requests even when they belong to different projects.
    db.scalar(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))
    return project, task


def create_request(db: Session, payload: OvertimeCreate, user: User) -> dict:
    project, task = _lock_context(db, payload.task_id, user.id)
    _validate_context(db, project, task, user.id)
    if payload.start_time <= beijing_now():
        raise bad_request("请在加班开始前提交申请")
    if payload.start_time.date() < task.planned_start or (payload.end_time - timedelta(microseconds=1)).date() > task.planned_end:
        raise bad_request("加班日期必须位于任务计划起止日期内，请先由项目负责人调整计划")
    hours = calculate_overtime_hours(db, payload.start_time, payload.end_time)
    _check_conflicts(db, user.id, payload.start_time, payload.end_time)
    approver_id = project.manager_id
    if approver_id == user.id:
        from app.services.project_service import get_department_manager
        approver_id = get_department_manager(db, project.department_id).id
    if approver_id == user.id:
        raise bad_request("不能审批自己的加班；请先配置其他有效部门主管作为审批人")
    approver = db.get(User, approver_id)
    if not approver or approver.is_deleted or approver.status != "active":
        raise bad_request("项目加班审批人未启用，请联系管理员")
    item = OvertimeRequest(
        **payload.model_dump(), project_id=project.id, user_id=user.id,
        approver_id=approver_id, hours=hours, status="pending",
    )
    db.add(item)
    db.flush()
    create_notification(db, approver_id, "overtime_requested", "你有一条加班申请待审批",
        f"{user.name} 申请为项目“{project.name}”的任务“{task.name}”加班："
        f"{item.start_time:%Y-%m-%d %H:%M} 至 {item.end_time:%H:%M}，共 {hours}h。原因：{item.reason}",
        related_type="overtime", related_id=item.id)
    log_operation(db, operator_id=user.id, module="overtime", action="create", object_type="overtime_request", object_id=item.id, after_data=model_to_dict(item))
    db.commit()
    return request_detail(db, item.id, user)


def _recorded_expression():
    return select(ExecutionRecord.id).where(
        ExecutionRecord.overtime_request_id == OvertimeRequest.id,
        ExecutionRecord.is_deleted.is_(False),
    ).order_by(ExecutionRecord.id.desc()).limit(1).correlate(OvertimeRequest).scalar_subquery()


def list_requests(db: Session, user: User, page=1, page_size=20, *, scope="mine", status=None, request_id=None) -> dict:
    if scope not in {"mine", "approvals", "related"}:
        raise bad_request("无效的加班查询范围")
    if status and status not in OVERTIME_STATUSES:
        raise bad_request("无效的加班状态")
    filters = [Project.is_deleted.is_(False), Task.is_deleted.is_(False)]
    if scope == "mine":
        filters.append(OvertimeRequest.user_id == user.id)
    elif scope == "approvals":
        filters.append(OvertimeRequest.approver_id == user.id)
    elif not has_global_project_access(db, user):
        filters.append(or_(OvertimeRequest.user_id == user.id, OvertimeRequest.approver_id == user.id, Project.manager_id == user.id))
    if status:
        filters.append(OvertimeRequest.status == status)
    if request_id is not None:
        filters.append(OvertimeRequest.id == request_id)
    applicant, approver = aliased(User), aliased(User)
    statement = select(OvertimeRequest, Project.name, Task.name, applicant.name, approver.name,
        _recorded_expression().label("execution_id"), Task.status, Project.status).join(
        Project, Project.id == OvertimeRequest.project_id).join(Task, Task.id == OvertimeRequest.task_id).join(
        applicant, applicant.id == OvertimeRequest.user_id).join(approver, approver.id == OvertimeRequest.approver_id).where(*filters)
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = db.execute(statement.order_by(OvertimeRequest.created_at.desc(), OvertimeRequest.id.desc()).offset((page-1)*page_size).limit(page_size)).all()
    now = beijing_now()
    items = []
    for item, project_name, task_name, user_name, approver_name, execution_id, task_status, project_status in rows:
        items.append({**model_to_dict(item), "project_name": project_name, "task_name": task_name,
            "user_name": user_name, "approver_name": approver_name, "execution_id": execution_id,
            "can_review": item.status == "pending" and item.approver_id == user.id and item.user_id != user.id,
            "can_withdraw": item.user_id == user.id and item.status in {"pending", "approved"} and not execution_id,
            "can_record": item.user_id == user.id and item.status == "approved" and not execution_id
                and item.end_time <= now and task_status != "completed" and project_status != "completed",
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def request_detail(db: Session, request_id: int, user: User) -> dict:
    rows = list_requests(db, user, scope="related", request_id=request_id)["items"]
    if not rows:
        raise not_found("加班申请不存在或无权查看")
    return rows[0]


def _locked_request(db: Session, request_id: int):
    identity = db.execute(select(OvertimeRequest.task_id, OvertimeRequest.user_id).where(OvertimeRequest.id == request_id)).first()
    if not identity:
        raise not_found("加班申请不存在")
    project, task = _lock_context(db, identity.task_id, identity.user_id)
    item = db.scalar(select(OvertimeRequest).where(OvertimeRequest.id == request_id).with_for_update().execution_options(populate_existing=True))
    return project, task, item


def decide_request(db: Session, request_id: int, payload: OvertimeDecision, user: User, approved: bool) -> dict:
    project, task, item = _locked_request(db, request_id)
    if item.approver_id != user.id or item.user_id == user.id:
        raise forbidden("只有该申请指定的项目经理或部门主管可以审批，且不能自审")
    if item.status != "pending":
        raise bad_request("该申请已处理，请刷新列表")
    note = (payload.note or "").strip()
    if not approved and not note:
        raise bad_request("驳回加班申请时必须填写原因")
    if approved:
        _validate_context(db, project, task, item.user_id)
        if item.start_time <= beijing_now():
            raise bad_request("加班时间已开始或已过去，请驳回后重新申请未来时段")
        if item.start_time.date() < task.planned_start or (item.end_time - timedelta(microseconds=1)).date() > task.planned_end:
            raise bad_request("加班日期已超出当前任务计划，请先调整计划")
        item.hours = calculate_overtime_hours(db, item.start_time, item.end_time)
        _check_conflicts(db, item.user_id, item.start_time, item.end_time, item.id)
    before = model_to_dict(item)
    item.status = "approved" if approved else "rejected"
    item.reviewed_by, item.reviewed_at, item.review_note = user.id, beijing_now(), note or None
    create_notification(db, item.user_id, "overtime_reviewed", "加班申请已批准" if approved else "加班申请已驳回",
        f"项目“{project.name}” / 任务“{task.name}”，{item.start_time:%Y-%m-%d %H:%M} 至 {item.end_time:%H:%M}，{item.hours}h。"
        + ("加班结束后请在任务执行中填报实际工时。" if approved else f"原因：{note}"), related_type="overtime", related_id=item.id)
    log_operation(db, operator_id=user.id, module="overtime", action="approve" if approved else "reject", object_type="overtime_request", object_id=item.id, before_data=before, after_data=model_to_dict(item))
    db.commit()
    return request_detail(db, item.id, user)


def withdraw_request(db: Session, request_id: int, user: User) -> dict:
    project, task, item = _locked_request(db, request_id)
    if item.user_id != user.id:
        raise forbidden("只能撤回自己的加班申请")
    if item.status not in {"pending", "approved"}:
        raise bad_request("只能撤回待审批或已批准的加班")
    if db.scalar(select(ExecutionRecord.id).where(ExecutionRecord.overtime_request_id == item.id, ExecutionRecord.is_deleted.is_(False)).limit(1).with_for_update()):
        raise bad_request("该加班已填报执行记录，请先删除相应执行记录再撤回")
    before = model_to_dict(item)
    item.status, item.withdrawn_at = "withdrawn", beijing_now()
    create_notification(db, item.approver_id, "overtime_withdrawn", "加班申请已撤回",
        f"{user.name} 已撤回项目“{project.name}” / 任务“{task.name}”的加班申请。", related_type="overtime", related_id=item.id)
    log_operation(db, operator_id=user.id, module="overtime", action="withdraw", object_type="overtime_request", object_id=item.id, before_data=before, after_data=model_to_dict(item))
    db.commit()
    return request_detail(db, item.id, user)


def resolve_execution_hours(db: Session, request_id: int, task_id: int, user_id: int,
    actual_start, actual_end, supplied_hours, *, exclude_execution_id=None) -> Decimal:
    # Caller holds the project's execution lock; withdrawal/approval use that lock too.
    item = db.scalar(select(OvertimeRequest).where(OvertimeRequest.id == request_id).with_for_update().execution_options(populate_existing=True))
    if not item or item.status != "approved" or item.user_id != user_id or item.task_id != task_id:
        raise bad_request("请选择该执行人、该任务已批准且未撤回的加班申请")
    if item.end_time > beijing_now():
        raise bad_request("加班尚未结束，不能提前填报实际工时")
    if actual_start != item.start_time.date() or actual_end != (item.end_time - timedelta(microseconds=1)).date():
        raise bad_request("加班执行的开始和结束日期必须与申请日期一致")
    filters = [ExecutionRecord.overtime_request_id == item.id, ExecutionRecord.is_deleted.is_(False)]
    if exclude_execution_id is not None:
        filters.append(ExecutionRecord.id != exclude_execution_id)
    if db.scalar(select(ExecutionRecord.id).where(*filters).limit(1).with_for_update()):
        raise conflict("该加班申请已填报，请编辑原执行记录，不要重复新增")
    hours = supplied_hours if supplied_hours is not None else item.hours
    if hours <= 0 or hours > item.hours or hours % Decimal("0.5"):
        raise bad_request(f"实际加班须以 0.5h 为单位，且不得超过批准的 {item.hours}h")
    return hours
