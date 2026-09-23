from datetime import datetime, time, timedelta
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from app.core.dependencies import get_role_codes
from app.core.exceptions import bad_request, conflict, forbidden, not_found
from app.models.execution import ExecutionRecord
from app.models.organization import Department, Organization
from app.models.project import Project, ProjectMember, ProjectResourceRequest
from app.models.schedule import ScheduleBooking
from app.models.task import Task, TaskAssignee
from app.models.user import User
from app.repositories.project_repository import booked_schedule_predicate, project_repository
from app.schemas.project import (
    PROJECT_FILTER_STATUSES,
    ProjectCreate,
    ProjectDecision,
    ProjectResourceRequestCreate,
    ProjectUpdate,
)
from app.services.notification_service import create_notification
from app.services.operation_log_service import log_operation
from app.services.schedule_lifecycle_service import synchronize_schedule_statuses
from app.services.visibility_service import has_global_project_access, related_project_ids, related_user_ids
from app.utils.model import model_to_dict
from app.utils.time import beijing_now
from app.utils.personnel_scope import resolve_personnel_scope_user_ids

PROJECT_CREATOR_ROLES = {"project_manager", "functional_manager", "department_manager", "super_admin"}
PROJECT_CLOSED_STATUSES = {"completed"}


def visible_project_ids(db: Session, user: User) -> set[int] | None:
    people = related_user_ids(db, user)
    return None if people is None else related_project_ids(db, people)


def manageable_project_ids(db: Session, user: User) -> set[int] | None:
    """Global project administrators or the exact project owner may maintain it."""
    if has_global_project_access(db, user):
        return None
    return set(
        db.scalars(
            select(Project.id).where(
                Project.manager_id == user.id,
                Project.is_deleted.is_(False),
            )
        ).all()
    )


def assert_project_visible(db: Session, project_id: int, user: User) -> Project:
    project = project_repository.get(db, project_id)
    if not project:
        raise not_found("project not found")
    is_pending_approver = (
        project.approval_status == "pending" and project.approver_id == user.id
    )
    visible = visible_project_ids(db, user)
    if visible is not None and project.id not in visible and not is_pending_approver:
        raise forbidden("只能查看本人参与或权限范围内的项目")
    return project


def assert_project_manageable(db: Session, project_id: int, user: User) -> Project:
    project = project_repository.get(db, project_id)
    if not project:
        raise not_found("project not found")
    allowed = project.manager_id == user.id or has_global_project_access(db, user)
    if not allowed:
        raise forbidden("只有项目负责人、部门主管或超级管理员可以维护项目")
    return project


def assert_project_approved(db: Session, project_id: int) -> Project:
    project = project_repository.get(db, project_id)
    if not project:
        raise not_found("project not found")
    if project.approval_status != "approved":
        raise bad_request("项目尚未通过审批，不能执行该操作")
    if project.status in PROJECT_CLOSED_STATUSES:
        raise bad_request("已完成项目不能继续增加业务数据")
    return project


def assert_project_owner_for_resource_request(
    db: Session, project_id: int, user: User
) -> Project:
    project = db.scalar(
        select(Project)
        .where(Project.id == project_id, Project.is_deleted.is_(False))
        .with_for_update()
    )
    if not project:
        raise not_found("project not found")
    if project.approval_status != "approved":
        raise bad_request("项目尚未通过审批，不能执行该操作")
    if project.status in PROJECT_CLOSED_STATUSES:
        raise bad_request("已完成项目不能继续预约人力")
    if project.manager_id != user.id and not has_global_project_access(db, user):
        raise forbidden("只有该项目的项目负责人可以申请项目资源变更")
    return project


def assert_project_booking_access(
    db: Session,
    project_id: int,
    user: User,
    target_user_ids: list[int],
) -> Project:
    """Authorize a project booking for the exact people being scheduled."""
    project = db.scalar(
        select(Project)
        .where(Project.id == project_id, Project.is_deleted.is_(False))
        .with_for_update()
    )
    if not project:
        raise not_found("project not found")
    if project.approval_status != "approved":
        raise bad_request("项目尚未通过审批，不能执行该操作")
    if project.status in PROJECT_CLOSED_STATUSES:
        raise bad_request("已完成项目不能继续预约人力")

    target_ids = set(target_user_ids)
    if not target_ids:
        raise bad_request("请选择至少一名被预约人")
    member_ids = set(
        db.scalars(
            select(ProjectMember.user_id).where(
                ProjectMember.project_id == project.id,
                ProjectMember.left_at.is_(None),
            )
        ).all()
    )
    if not target_ids <= member_ids:
        raise forbidden("项目经理只能预约本项目的有效成员")
    self_booking = target_ids == {user.id} and user.id in member_ids
    if (
        project.manager_id != user.id
        and not has_global_project_access(db, user)
        and not self_booking
    ):
        raise forbidden("项目负责人可预约项目成员；普通任务成员只能预约自己的任务时间")
    return project


def _validate_project_manager(db: Session, manager_id: int, department_id: int) -> User:
    department = db.get(Department, department_id)
    if not department or department.status != "active":
        raise bad_request("项目必须属于有效部门")
    manager = db.get(User, manager_id)
    if not manager or manager.is_deleted or manager.status != "active":
        raise not_found("project manager not found")
    if not (PROJECT_CREATOR_ROLES & get_role_codes(db, manager.id)):
        raise bad_request("项目负责人必须具有项目经理、职能主管、部门主管或超级管理员角色")
    if manager.department_id != department_id:
        raise bad_request("项目经理必须属于项目所属部门")
    return manager


def _validate_initial_project_members(
    db: Session,
    member_ids: list[int],
) -> list[User]:
    unique_ids = list(dict.fromkeys(member_ids))
    members = db.scalars(select(User).where(User.id.in_(unique_ids))).all()
    members_by_id = {member.id: member for member in members}
    missing_ids = [member_id for member_id in unique_ids if member_id not in members_by_id]
    if missing_ids:
        raise bad_request(f"项目成员不存在：{', '.join(map(str, missing_ids))}")
    ordered_members = [members_by_id[member_id] for member_id in unique_ids]
    for member in ordered_members:
        if member.is_deleted or member.status != "active":
            raise bad_request(f"项目成员 {member.name} 已删除或已停用")
        if not member.department_id:
            raise bad_request(f"项目成员 {member.name} 必须设置部门")
        if member.organization_id:
            organization = db.get(Organization, member.organization_id)
            if (
                not organization
                or organization.status != "active"
                or organization.department_id != member.department_id
            ):
                raise bad_request(f"项目成员 {member.name} 的部门和组织关系无效")
    return ordered_members


def _add_initial_project_members(
    db: Session,
    project: Project,
    manager: User,
    members: list[User],
) -> None:
    joined_at = beijing_now()
    db.add(
        ProjectMember(
            project_id=project.id,
            user_id=manager.id,
            project_role="manager",
            joined_at=joined_at,
        )
    )
    for member in members:
        db.add(
            ProjectMember(
                project_id=project.id,
                user_id=member.id,
                project_role="member",
                joined_at=joined_at,
            )
        )
        create_notification(
            db,
            member.id,
            "project_member_added",
            "你已加入项目",
            f"你已在项目创建时被加入项目“{project.name}”。",
            related_type="project",
            related_id=project.id,
        )


def get_department_manager(db: Session, department_id: int) -> User:
    department = db.get(Department, department_id)
    if not department or department.status != "active":
        raise not_found("department not found")
    if not department.manager_id:
        raise bad_request("请先为项目所属部门设置部门主管")
    approver = db.get(User, department.manager_id)
    if not approver or approver.is_deleted or approver.status != "active":
        raise bad_request("项目所属部门的部门主管不存在或已停用，请先重新设置")
    if "department_manager" not in get_role_codes(db, approver.id):
        raise bad_request("部门负责人必须具有部门主管角色")
    if approver.department_id != department_id:
        raise bad_request("部门主管必须属于项目所属部门，请先修正用户部门或部门负责人")
    return approver


def _assert_department_manager(db: Session, project: Project, user: User) -> User:
    if "super_admin" in get_role_codes(db, user.id):
        return user
    if not project.department_id:
        raise bad_request("项目未设置所属部门，无法确定部门主管审批人")
    approver = get_department_manager(db, project.department_id)
    if approver.id != user.id:
        raise forbidden("只有项目所属部门当前设置的部门主管可以审批")
    return approver


def list_projects(
    db: Session,
    user: User,
    page: int,
    page_size: int,
    keyword: str | None,
    status: str | None,
    manager_id: int | None,
    department_id: int | None,
    organization_id: int | None,
    employee_no: str | None,
    manager_name: str | None,
    approval_status: str | None = None,
    approver_id: int | None = None,
    personnel_keyword: str | None = None,
    organization_keyword: str | None = None,
    personnel_scope: str | None = None,
    manageable_only: bool = False,
):
    if status and status not in PROJECT_FILTER_STATUSES:
        raise bad_request("invalid project status filter")
    items, total = project_repository.list(
        db,
        page,
        page_size,
        keyword,
        status,
        manager_id,
        department_id,
        organization_id,
        employee_no,
        manager_name,
        approval_status,
        approver_id,
        manageable_project_ids(db, user) if manageable_only else visible_project_ids(db, user),
        personnel_keyword=personnel_keyword,
        organization_keyword=organization_keyword,
        personnel_scope_user_ids=resolve_personnel_scope_user_ids(db, personnel_scope),
    )
    global_access = has_global_project_access(db, user)
    for item in items:
        item["can_manage"] = global_access or item["manager_id"] == user.id
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def list_pending_project_approvals(db: Session, user: User) -> list[dict]:
    if "department_manager" not in get_role_codes(db, user.id):
        return []
    managed_department_ids = set(
        db.scalars(
            select(Department.id).where(
                Department.manager_id == user.id,
                Department.status == "active",
            )
        ).all()
    )
    pending_project_ids = set(
        db.scalars(
            select(Project.id).where(
                Project.department_id.in_(managed_department_ids or {-1}),
                Project.approval_status == "pending",
                Project.is_deleted.is_(False),
            )
        ).all()
    )
    items, _ = project_repository.list(
        db,
        1,
        200,
        approval_status="pending",
        visible_project_ids=pending_project_ids,
    )
    return items


def project_detail(db: Session, project_id: int, user: User) -> dict:
    project = assert_project_visible(db, project_id, user)
    items, _ = project_repository.list(db, 1, 1, visible_project_ids={project.id})
    item = items[0]
    item["can_manage"] = project.manager_id == user.id or has_global_project_access(db, user)
    return item


def create_project(db: Session, payload: ProjectCreate, user: User) -> Project:
    roles = get_role_codes(db, user.id)
    if not (roles & PROJECT_CREATOR_ROLES):
        raise forbidden("只有项目经理、职能主管、部门主管或超级管理员可以创建项目")
    if payload.manager_id != user.id and not has_global_project_access(db, user):
        raise forbidden("项目负责人必须选择当前创建人本人")
    manager = _validate_project_manager(db, payload.manager_id, payload.department_id)
    get_department_manager(db, payload.department_id)
    members = _validate_initial_project_members(db, payload.member_ids)
    values = payload.model_dump(exclude={"member_ids"})
    project = Project(
        **values,
        code=_generate_project_code(db),
        priority="medium",
        status="not_started",
        approval_status="draft",
        created_by=user.id,
    )
    db.add(project)
    db.flush()
    _add_initial_project_members(db, project, manager, members)
    db.flush()
    log_operation(
        db,
        operator_id=user.id,
        module="project",
        action="create_draft",
        object_type="project",
        object_id=project.id,
        after_data={
            **model_to_dict(project),
            "member_ids": payload.member_ids,
        },
    )
    db.commit()
    db.refresh(project)
    return project


def _generate_project_code(db: Session) -> str:
    for _ in range(20):
        code = f"P-{beijing_now():%Y%m%d}-{uuid4().hex[:6].upper()}"
        if not db.scalar(select(Project.id).where(Project.code == code)):
            return code
    raise conflict("无法生成唯一项目编号，请重试", 40921)


def submit_project(db: Session, project_id: int, user: User) -> Project:
    project = db.scalar(
        select(Project)
        .where(Project.id == project_id, Project.is_deleted.is_(False))
        .with_for_update()
    )
    if not project:
        raise not_found("project not found")
    if project.manager_id != user.id and not has_global_project_access(db, user):
        raise forbidden("只有项目负责人、部门主管或超级管理员可以提交审批")
    if project.approval_status not in {"draft", "rejected"}:
        raise bad_request("只有草稿或已驳回项目可以提交审批")
    roles = get_role_codes(db, user.id)
    if not (roles & PROJECT_CREATOR_ROLES):
        raise forbidden("当前用户不再具有项目创建权限")
    if not project.department_id:
        raise bad_request("项目必须设置所属部门")
    _validate_project_manager(db, project.manager_id, project.department_id)
    before = model_to_dict(project)
    project.approval_note = None
    project.approved_by = None
    project.approved_at = None
    approver = get_department_manager(db, project.department_id)
    submitter = db.get(User, project.created_by) or user
    project.approval_status = "pending"
    project.status = "not_started"
    project.approver_id = approver.id
    create_notification(
        db,
        approver.id,
        "project_approval_required",
        "项目等待部门主管审批",
        f"{submitter.name} 提交了项目 {project.code} - {project.name}，"
        f"请审核项目与 {project.budget_hours} 小时工时额度。",
        level="warning",
        related_type="project",
        related_id=project.id,
    )
    action = "submit_for_department_approval"
    db.flush()
    log_operation(
        db,
        operator_id=user.id,
        module="project",
        action=action,
        object_type="project",
        object_id=project.id,
        before_data=before,
        after_data=model_to_dict(project),
    )
    db.commit()
    db.refresh(project)
    return project


def update_project(db: Session, project_id: int, payload: ProjectUpdate, user: User) -> Project:
    project = assert_project_manageable(db, project_id, user)
    if project.status in PROJECT_CLOSED_STATUSES:
        raise bad_request("已完成项目不能再修改")
    before = model_to_dict(project)
    values = payload.model_dump(exclude_unset=True)
    required_fields = {
        "name",
        "manager_id",
        "department_id",
        "budget_hours",
        "planned_start",
        "planned_end",
    }
    if any(values.get(key) is None for key in required_fields if key in values):
        raise bad_request("项目名称、负责人、部门、工时和计划日期不能为空")
    # Actual project dates are derived from execution records by status_sync_service.
    # Never let a project edit overwrite those linked values.
    if "manager_id" in values and values["manager_id"] != project.manager_id:
        raise bad_request("项目提交后不能更换项目经理，请删除草稿后由新项目经理重新创建")
    if project.approval_status == "approved" and {"manager_id", "department_id", "budget_hours"} & values.keys():
        raise bad_request("已审批项目不能直接修改负责人、部门或工时额度；工时请发起追加申请")
    department_id = values.get("department_id", project.department_id)
    manager_id = values.get("manager_id", project.manager_id)
    if not department_id:
        raise bad_request("project department is required")
    _validate_project_manager(db, manager_id, department_id)
    if project.approval_status != "approved":
        get_department_manager(db, department_id)
    planned_start = values.get("planned_start", project.planned_start)
    planned_end = values.get("planned_end", project.planned_end)
    if planned_end < planned_start:
        raise bad_request("planned_end must be on or after planned_start")
    if {"planned_start", "planned_end"} & values.keys():
        if db.scalar(
            select(Task.id).where(
                Task.project_id == project.id,
                Task.is_deleted.is_(False),
                or_(Task.planned_start < planned_start, Task.planned_end > planned_end),
            ).limit(1)
        ):
            raise bad_request("项目计划日期不能排除已有任务的计划时间")
        range_start = datetime.combine(planned_start, time.min)
        range_end = datetime.combine(planned_end + timedelta(days=1), time.min)
        if db.scalar(
            select(ScheduleBooking.id).where(
                ScheduleBooking.project_id == project.id,
                booked_schedule_predicate(),
                or_(
                    ScheduleBooking.start_time < range_start,
                    ScheduleBooking.end_time > range_end,
                ),
            ).limit(1)
        ):
            raise bad_request("项目计划日期不能排除已有预约时间")
    if project.approval_status != "approved":
        if project.manager_id != user.id and not has_global_project_access(db, user):
            raise forbidden("未审批项目只能由项目创建人修改")
        if project.approval_status == "pending":
            raise bad_request("待审批项目不能修改，请先由部门主管审批")
    for key, value in values.items():
        setattr(project, key, value)
    if project.approval_status == "rejected":
        project.approval_status = "draft"
        project.approver_id = None
        project.approved_by = None
        project.approved_at = None
        project.approval_note = None
    db.flush()
    log_operation(
        db,
        operator_id=user.id,
        module="project",
        action="update",
        object_type="project",
        object_id=project.id,
        before_data=before,
        after_data=model_to_dict(project),
    )
    db.commit()
    db.refresh(project)
    return project


def decide_project(
    db: Session,
    project_id: int,
    payload: ProjectDecision,
    user: User,
    approved: bool,
) -> Project:
    project = db.scalar(
        select(Project)
        .where(Project.id == project_id, Project.is_deleted.is_(False))
        .with_for_update()
    )
    if not project:
        raise not_found("project not found")
    if project.approval_status != "pending":
        raise bad_request("only pending projects can be reviewed")
    if not project.department_id:
        raise bad_request("项目必须设置所属部门")
    approver = get_department_manager(db, project.department_id)
    if user.id != approver.id:
        raise forbidden("只有项目所属部门当前设置的部门主管可以审批")
    if not approved and not payload.note:
        raise bad_request("驳回项目时必须填写原因")
    if approved:
        if not project.department_id:
            raise bad_request("项目必须设置所属部门")
        _validate_project_manager(db, project.manager_id, project.department_id)
    before = model_to_dict(project)
    project.approver_id = approver.id
    project.approval_status = "approved" if approved else "rejected"
    project.status = "not_started"
    project.approved_by = user.id
    project.approved_at = beijing_now()
    project.approval_note = payload.note
    recipient_ids = {project.manager_id}
    if project.created_by:
        recipient_ids.add(project.created_by)
    for recipient_id in recipient_ids:
        create_notification(
            db,
            recipient_id,
            "project_approved" if approved else "project_rejected",
            "项目审批已通过" if approved else "项目审批已驳回",
            f"项目 {project.code} - {project.name} {'已获批' if approved else '未通过审批'}。"
            + (f" 审批意见：{payload.note}" if payload.note else ""),
            level="info" if approved else "warning",
            related_type="project",
            related_id=project.id,
        )
    db.flush()
    log_operation(
        db,
        operator_id=user.id,
        module="project",
        action="approve" if approved else "reject",
        object_type="project",
        object_id=project.id,
        before_data=before,
        after_data=model_to_dict(project),
        reason=payload.note,
    )
    db.commit()
    db.refresh(project)
    return project


def complete_project(db: Session, project_id: int, user: User) -> Project:
    project = db.scalar(select(Project).where(
        Project.id == project_id, Project.is_deleted.is_(False)
    ).with_for_update())
    if not project:
        raise not_found("project not found")
    assert_project_manageable(db, project_id, user)
    if project.status == "completed":
        raise bad_request("项目已确认完成，请勿重复操作")
    assert_project_approved(db, project_id)
    tasks = list(db.scalars(select(Task).where(
        Task.project_id == project_id, Task.is_deleted.is_(False),
    ).with_for_update()).all())
    if not tasks or any(task.status != "completed" for task in tasks):
        raise bad_request("项目至少需要一项任务，且所有任务均已完成才能确认完成")
    if db.scalar(select(ProjectResourceRequest.id).where(
        ProjectResourceRequest.project_id == project_id,
        ProjectResourceRequest.status == "pending",
    ).limit(1)):
        raise bad_request("请先处理待审批的项目资源申请，再确认项目完成")
    synchronize_schedule_statuses(db)
    if db.scalar(select(ScheduleBooking.id).where(
        ScheduleBooking.project_id == project_id,
        or_(ScheduleBooking.status.in_({"pending", "changed"}),
            ScheduleBooking.status.in_({"confirmed", "running"}) & (ScheduleBooking.end_time > beijing_now())),
    ).limit(1)):
        raise bad_request("请先处理待确认或尚未结束的预约，再确认项目完成")
    before = model_to_dict(project)
    actual_start, actual_end = db.execute(select(
        func.min(ExecutionRecord.actual_start), func.max(ExecutionRecord.actual_end)
    ).join(Task, Task.id == ExecutionRecord.task_id).where(
        Task.project_id == project_id, Task.is_deleted.is_(False),
        ExecutionRecord.is_deleted.is_(False),
    )).one()
    project.status = "completed"
    project.actual_start = actual_start
    project.actual_end = actual_end or beijing_now().date()
    log_operation(db, operator_id=user.id, module="project", action="complete",
                  object_type="project", object_id=project.id,
                  before_data=before, after_data=model_to_dict(project))
    if project.manager_id != user.id:
        create_notification(db, project.manager_id, "project_completed", "项目已确认完成",
                            f"项目“{project.name}”已由 {user.name} 确认完成。",
                            related_type="project", related_id=project.id)
    db.commit()
    db.refresh(project)
    return project


def delete_draft_project(db: Session, project_id: int, user: User) -> None:
    project = assert_project_manageable(db, project_id, user)
    if project.approval_status not in {"draft", "rejected"}:
        raise bad_request("只有草稿或已驳回项目可以删除")
    before = model_to_dict(project)
    project.is_deleted = True
    log_operation(
        db,
        operator_id=user.id,
        module="project",
        action="delete",
        object_type="project",
        object_id=project.id,
        before_data=before,
    )
    db.commit()


def list_members(db: Session, project_id: int, user: User):
    assert_project_visible(db, project_id, user)
    return project_repository.list_members(db, project_id)


def _assert_member_can_be_removed(
    db: Session,
    project: Project,
    member_user_id: int,
) -> ProjectMember:
    if member_user_id == project.manager_id:
        raise bad_request("项目经理属于固定项目成员，不能移除")
    member = db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == member_user_id,
            ProjectMember.left_at.is_(None),
        )
    )
    if not member:
        raise not_found("active project member not found")
    synchronize_schedule_statuses(db)
    dependencies: list[str] = []
    if db.scalar(
        select(TaskAssignee.id)
        .join(Task, Task.id == TaskAssignee.task_id)
        .where(
            TaskAssignee.user_id == member_user_id,
            Task.project_id == project.id,
            Task.is_deleted.is_(False),
            Task.status != "completed",
        )
        .limit(1)
    ):
        dependencies.append("未结束任务")
    if db.scalar(
        select(ScheduleBooking.id).where(
            ScheduleBooking.project_id == project.id,
            ScheduleBooking.user_id == member_user_id,
            or_(
                ScheduleBooking.status.in_({"pending", "changed"}),
                (
                    ScheduleBooking.status.in_({"confirmed", "running"})
                    & (ScheduleBooking.end_time > beijing_now())
                ),
            ),
        ).limit(1)
    ):
        dependencies.append("待确认或未结束预约")
    if dependencies:
        raise conflict(
            f"移除成员前请先处理：{', '.join(dependencies)}",
            40925,
            {"dependencies": dependencies},
        )
    return member


def _resource_request_summary(item: ProjectResourceRequest) -> str:
    changes: list[str] = []
    if item.requested_hours > 0:
        changes.append(f"追加 {item.requested_hours} 小时")
    if item.add_member_ids:
        changes.append(f"新增 {len(item.add_member_ids)} 名成员")
    if item.remove_member_ids:
        changes.append(f"移除 {len(item.remove_member_ids)} 名成员")
    return "、".join(changes)


def create_resource_request(
    db: Session,
    project_id: int,
    payload: ProjectResourceRequestCreate,
    user: User,
) -> ProjectResourceRequest:
    project = assert_project_owner_for_resource_request(db, project_id, user)
    if not project.department_id:
        raise bad_request("项目未设置所属部门，无法申请资源变更")
    if db.scalar(
        select(ProjectResourceRequest.id).where(
            ProjectResourceRequest.project_id == project.id,
            ProjectResourceRequest.status == "pending",
        )
    ):
        raise conflict("该项目已有待审批的项目资源申请", 40923)
    active_member_ids = set(
        db.scalars(
            select(ProjectMember.user_id).where(
                ProjectMember.project_id == project.id,
                ProjectMember.left_at.is_(None),
            )
        ).all()
    )
    if set(payload.add_member_ids) & active_member_ids:
        raise bad_request("申请新增的人员中包含当前项目已有成员")
    _validate_initial_project_members(db, payload.add_member_ids)
    for member_id in payload.remove_member_ids:
        _assert_member_can_be_removed(db, project, member_id)
    approver = get_department_manager(db, project.department_id)
    item = ProjectResourceRequest(
        project_id=project.id,
        requested_hours=payload.requested_hours,
        add_member_ids=payload.add_member_ids,
        remove_member_ids=payload.remove_member_ids,
        reason=payload.reason,
        requested_by=user.id,
        status="pending",
    )
    db.add(item)
    db.flush()
    create_notification(
        db,
        approver.id,
        "project_resources_approval_required",
        "项目资源申请待部门主管审批",
        f"项目 {project.code} 申请{_resource_request_summary(item)}。原因：{item.reason}",
        level="warning",
        related_type="project_resource_request",
        related_id=item.id,
    )
    log_operation(
        db,
        operator_id=user.id,
        module="project",
        action="request_resources",
        object_type="project_resource_request",
        object_id=item.id,
        after_data=model_to_dict(item),
    )
    db.commit()
    db.refresh(item)
    return item


def list_pending_resource_requests(db: Session, user: User) -> list[dict]:
    """Return the department manager's actionable resource requests."""
    roles = get_role_codes(db, user.id)
    if not roles & {"department_manager", "super_admin"}:
        return []
    requester = aliased(User)
    statement = (
        select(
            ProjectResourceRequest,
            Project.code.label("project_code"),
            Project.name.label("project_name"),
            requester.name.label("requester_name"),
        )
        .join(Project, Project.id == ProjectResourceRequest.project_id)
        .join(Department, Department.id == Project.department_id)
        .join(requester, requester.id == ProjectResourceRequest.requested_by)
        .where(
            ProjectResourceRequest.status == "pending",
            Project.is_deleted.is_(False),
        )
        .order_by(ProjectResourceRequest.created_at.asc())
    )
    if "super_admin" not in roles:
        statement = statement.where(Department.manager_id == user.id)
    rows = db.execute(statement).all()
    return [
        {
            **model_to_dict(item),
            "project_code": project_code,
            "project_name": project_name,
            "requester_name": requester_name,
        }
        for item, project_code, project_name, requester_name in rows
    ]


def list_resource_requests(db: Session, project_id: int, user: User) -> list[dict]:
    assert_project_manageable(db, project_id, user)
    requester = aliased(User)
    reviewer = aliased(User)
    rows = db.execute(
        select(
            ProjectResourceRequest,
            requester.name.label("requester_name"),
            reviewer.name.label("reviewer_name"),
        )
        .join(requester, requester.id == ProjectResourceRequest.requested_by)
        .outerjoin(reviewer, reviewer.id == ProjectResourceRequest.reviewed_by)
        .where(ProjectResourceRequest.project_id == project_id)
        .order_by(ProjectResourceRequest.created_at.desc())
    ).all()
    return [
        {
            **model_to_dict(item),
            "requester_name": requester_name,
            "reviewer_name": reviewer_name,
        }
        for item, requester_name, reviewer_name in rows
    ]


def decide_resource_request(
    db: Session,
    project_id: int,
    request_id: int,
    payload: ProjectDecision,
    user: User,
    approved: bool,
) -> ProjectResourceRequest:
    project = db.scalar(
        select(Project)
        .where(Project.id == project_id, Project.is_deleted.is_(False))
        .with_for_update()
    )
    if not project:
        raise not_found("project not found")
    _assert_department_manager(db, project, user)
    item = db.scalar(
        select(ProjectResourceRequest)
        .where(
            ProjectResourceRequest.id == request_id,
            ProjectResourceRequest.project_id == project_id,
        )
        .with_for_update()
    )
    if not item:
        raise not_found("resource request not found")
    if item.status != "pending":
        raise bad_request("only pending resource requests can be reviewed")
    if not approved and not payload.note:
        raise bad_request("驳回项目资源申请时必须填写原因")
    before = model_to_dict(item)
    item.status = "approved" if approved else "rejected"
    item.reviewed_by = user.id
    item.reviewed_at = beijing_now()
    item.review_note = payload.note
    if approved:
        project.budget_hours += item.requested_hours
        added_users = _validate_initial_project_members(db, item.add_member_ids or [])
        active_member_ids = set(
            db.scalars(
                select(ProjectMember.user_id).where(
                    ProjectMember.project_id == project.id,
                    ProjectMember.left_at.is_(None),
                )
            ).all()
        )
        if set(item.add_member_ids or []) & active_member_ids:
            raise bad_request("申请新增的人员中包含当前项目已有成员，请驳回后重新申请")
        for member_id in item.remove_member_ids or []:
            member = _assert_member_can_be_removed(db, project, member_id)
            member.left_at = beijing_now()
            create_notification(
                db,
                member_id,
                "project_member_removed",
                "你已退出项目",
                f"项目资源申请获批后，你已从项目“{project.name}”移除。",
                level="warning",
                related_type="project",
                related_id=project.id,
            )
        for member_user in added_users:
            member = db.scalar(
                select(ProjectMember).where(
                    ProjectMember.project_id == project.id,
                    ProjectMember.user_id == member_user.id,
                )
            )
            if member:
                member.left_at = None
                member.project_role = "member"
                member.joined_at = beijing_now()
            else:
                db.add(ProjectMember(
                    project_id=project.id,
                    user_id=member_user.id,
                    project_role="member",
                    joined_at=beijing_now(),
                ))
            create_notification(
                db,
                member_user.id,
                "project_member_added",
                "你已加入项目",
                f"项目资源申请获批后，你已加入项目“{project.name}”。",
                related_type="project",
                related_id=project.id,
            )
    create_notification(
        db,
        item.requested_by,
        "project_resources_approved" if approved else "project_resources_rejected",
        "项目资源申请已获批" if approved else "项目资源申请被驳回",
        f"项目 {project.code} 的资源申请（{_resource_request_summary(item)}）"
        f"{'已通过' if approved else '未通过'}。"
        + (f" 审批意见：{payload.note}" if payload.note else ""),
        level="info" if approved else "warning",
        related_type="project_resource_request",
        related_id=item.id,
    )
    db.flush()
    log_operation(
        db,
        operator_id=user.id,
        module="project",
        action="approve_resources" if approved else "reject_resources",
        object_type="project_resource_request",
        object_id=item.id,
        before_data=before,
        after_data=model_to_dict(item),
        reason=payload.note,
    )
    db.commit()
    db.refresh(item)
    return item
