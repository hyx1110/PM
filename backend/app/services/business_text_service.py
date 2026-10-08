"""Human-readable references shared by audit logs and booking notifications.

IDs remain in structured records for traceability; display text uses business
names. Lookups are batched for a page, and never change stored business state.
"""
import re
from collections import defaultdict

from sqlalchemy import literal, select
from sqlalchemy.orm import Session

from app.models.organization import Department, Organization
from app.models.project import Project
from app.models.rbac import Permission, Role
from app.models.schedule import ScheduleBooking
from app.models.task import Task
from app.models.user import User


REFERENCE_FIELDS = {
    "uploaded_by": "user",
    **dict.fromkeys(("user_id", "user_ids", "manager_id", "owner_id", "owner_ids", "member_ids", "add_member_ids", "remove_member_ids", "supervisor_id", "created_by", "requested_by", "reviewed_by", "approved_by", "approver_id", "operator_id"), "user"),
    "project_id": "project", "task_id": "task", "parent_id": "task",
    "department_id": "department", "organization_id": "organization",
    "role_ids": "role", "role_id": "role", "permission_ids": "permission",
}
REFERENCE_MODELS = {"user": User, "project": Project, "task": Task, "department": Department,
                    "organization": Organization, "role": Role, "permission": Permission}
REFERENCE_LABELS = {"user": "人员", "project": "项目", "task": "任务", "department": "部门",
                    "organization": "组织", "role": "角色", "permission": "权限"}
BOOKING_CONTEXT_PREFIXES = ("被预约人：", "关联预约资料已不存在，")


def numeric_id(value):
    try:
        return int(value) if value is not None and str(value).isdigit() else None
    except (ValueError, TypeError):
        return None


def field_reference(key: str, object_type: str) -> str | None:
    if key == "parent_id":
        return "organization" if object_type == "organization" else "task" if object_type == "task" else None
    return REFERENCE_FIELDS.get(key)


def load_reference_labels(db: Session, records: list[tuple]) -> dict[str, str]:
    requested = defaultdict(set)
    for object_type, object_id, before, after in records:
        for data in (before or {}, after or {}):
            for field, value in data.items():
                kind = field_reference(field, object_type)
                if kind:
                    for uid in (value if isinstance(value, list) else [value]):
                        if (parsed := numeric_id(uid)) is not None:
                            requested[kind].add(parsed)
        if object_type in REFERENCE_MODELS and (parsed := numeric_id(object_id)) is not None:
            requested[object_type].add(parsed)
    labels = {}
    for kind, ids in requested.items():
        model = REFERENCE_MODELS[kind]
        extra = User.employee_no if kind == "user" else literal(None)
        statement = select(model.id, model.name, extra).where(model.id.in_(ids))
        if kind == "task":
            statement = select(Task.id, Task.name, Project.name).outerjoin(Project, Project.id == Task.project_id).where(Task.id.in_(ids))
        for uid, name, extra_value in db.execute(statement).all():
            labels[f"{kind}:{uid}"] = f"{name}（工号 {extra_value}）" if kind == "user" and extra_value else name
            if kind == "task" and extra_value:
                labels[f"task_project:{uid}"] = extra_value
    # Per-snapshot names take precedence in describe_change, not here: a later
    # rename must not overwrite an older log's event-time name.
    return labels


def reference_label(labels: dict, kind: str, value) -> str:
    if value is None:
        return "未设置"
    return labels.get(f"{kind}:{value}") or f"{REFERENCE_LABELS.get(kind, '关联资料')}名称未留存/资料已删除"


def booking_contexts(db: Session, ids: set[int], *, include_time: bool = True) -> dict[int, str]:
    if not ids:
        return {}
    rows = db.execute(select(
        ScheduleBooking.id, User.name, User.employee_no, Project.name, Task.name,
        ScheduleBooking.start_time, ScheduleBooking.end_time,
    ).outerjoin(User, User.id == ScheduleBooking.user_id)
      .outerjoin(Project, Project.id == ScheduleBooking.project_id)
      .outerjoin(Task, Task.id == ScheduleBooking.task_id)
      .where(ScheduleBooking.id.in_(ids))).all()
    result = {}
    for uid, name, employee_no, project_name, task_name, start, end in rows:
        person = f"{name}（工号 {employee_no}）" if name and employee_no else name or "人员资料已删除"
        text = f"被预约人：{person}；项目：{project_name or '项目资料已删除'}；任务：{task_name or '任务资料已删除'}。"
        if include_time:
            text += f"预约时间：{start:%Y-%m-%d %H:%M} 至 {end:%Y-%m-%d %H:%M}（北京时间）。"
        result[uid] = text
    return result


def readable_booking_notification(event_type: str, content: str, context: str) -> str:
    # Replace only technical booking references, not arbitrary numbers/reasons.
    detail = re.sub(r"(?:预约|排期)\s*#\s*\d+", "该预约", content)
    outcomes = {
        "schedule_confirmation_required": "待本人确认",
        "schedule_confirmed": "已确认",
        "schedule_rejected": "已拒绝",
        "schedule_withdrawn": "已撤回预约",
        "schedule_rejected_due_to_conflict": "因时段冲突自动关闭",
        "schedule_auto_cancelled": "时段结束前未确认，已自动取消",
    }
    outcome = outcomes.get(event_type)
    return context + "\n" + (f"处理结果：{outcome}。" if outcome else "") + detail
