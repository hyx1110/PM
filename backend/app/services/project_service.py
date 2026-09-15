from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.core.dependencies import get_role_codes
from app.core.exceptions import bad_request, conflict, forbidden, not_found
from app.models.organization import Department, Organization
from app.models.project import Project, ProjectHourRequest, ProjectMember
from app.models.user import User
from app.repositories.project_repository import project_repository
from app.schemas.project import (
    PROJECT_STATUSES,
    ProjectCreate,
    ProjectDecision,
    ProjectHourRequestCreate,
    ProjectMemberCreate,
    ProjectUpdate,
)
from app.services.notification_service import create_notification
from app.services.operation_log_service import log_operation
from app.utils.model import model_to_dict

PROJECT_CREATOR_ROLES = {"project_manager", "department_manager", "super_admin"}
PROJECT_CLOSED_STATUSES = {"Completed", "Cancelled"}
PROJECT_STATUS_TRANSITIONS = {
    "Draft": {"Planned", "Running", "Cancelled"},
    "Planned": {"Running", "Suspended", "Completed", "Cancelled"},
    "Running": {"Suspended", "Completed", "Cancelled"},
    "Suspended": {"Running", "Completed", "Cancelled"},
    "Completed": set(),
    "Cancelled": set(),
}


def visible_project_ids(db: Session, user: User) -> set[int] | None:
    roles = get_role_codes(db, user.id)
    if "super_admin" in roles:
        return None
    visible = project_repository.visible_ids_for_user(db, user.id)
    visible.update(
        db.scalars(
            select(Project.id).where(
                Project.approver_id == user.id,
                Project.is_deleted.is_(False),
            )
        ).all()
    )
    if roles & {"department_manager", "functional_manager"} and user.department_id:
        visible.update(
            db.scalars(
                select(Project.id).where(
                    Project.department_id == user.department_id,
                    Project.is_deleted.is_(False),
                )
            ).all()
        )
    return visible


def manageable_project_ids(db: Session, user: User) -> set[int] | None:
    """Projects whose team-level data the current user may manage."""
    roles = get_role_codes(db, user.id)
    if "super_admin" in roles:
        return None
    manageable: set[int] = set()
    if roles & PROJECT_CREATOR_ROLES:
        manageable.update(
            db.scalars(
                select(Project.id).where(
                    Project.manager_id == user.id,
                    Project.is_deleted.is_(False),
                )
            ).all()
        )
    if roles & {"department_manager", "functional_manager"} and user.department_id:
        manageable.update(
            db.scalars(
                select(Project.id).where(
                    Project.department_id == user.department_id,
                    Project.is_deleted.is_(False),
                )
            ).all()
        )
    return manageable


def assert_project_visible(db: Session, project_id: int, user: User) -> Project:
    project = project_repository.get(db, project_id)
    if not project:
        raise not_found("project not found")
    scope = visible_project_ids(db, user)
    if scope is not None and project_id not in scope:
        raise forbidden("project is outside your data scope")
    return project


def assert_project_manageable(db: Session, project_id: int, user: User) -> Project:
    project = project_repository.get(db, project_id)
    if not project:
        raise not_found("project not found")
    roles = get_role_codes(db, user.id)
    allowed = "super_admin" in roles or (
        project.manager_id == user.id and bool(roles & PROJECT_CREATOR_ROLES)
    )
    if roles & {"department_manager", "functional_manager"}:
        allowed = allowed or (
            user.department_id is not None and project.department_id == user.department_id
        )
    if not allowed:
        raise forbidden("you cannot manage this project")
    return project


def assert_project_approved(db: Session, project_id: int) -> Project:
    project = project_repository.get(db, project_id)
    if not project:
        raise not_found("project not found")
    if project.approval_status != "approved":
        raise bad_request("项目尚未通过审批，不能执行该操作")
    if project.status in PROJECT_CLOSED_STATUSES:
        raise bad_request("已完成或已取消的项目不能继续增加业务数据")
    return project


def assert_project_owner_for_hour_request(
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
        raise bad_request("已完成或已取消的项目不能继续预约人力")
    if (
        project.manager_id != user.id
        or not (get_role_codes(db, user.id) & PROJECT_CREATOR_ROLES)
    ):
        raise forbidden("只有该项目的项目负责人可以申请追加工时")
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
        raise bad_request("已完成或已取消的项目不能继续预约人力")

    target_ids = set(target_user_ids)
    if not target_ids:
        raise bad_request("请选择至少一名被预约人")
    roles = get_role_codes(db, user.id)
    if "super_admin" in roles:
        return project
    if project.manager_id == user.id and roles & PROJECT_CREATOR_ROLES:
        return project
    if roles & {"department_manager", "functional_manager"}:
        direct_report_ids = set(
            db.scalars(
                select(User.id).where(
                    User.id.in_(target_ids),
                    User.supervisor_id == user.id,
                    User.status == "active",
                    User.is_deleted.is_(False),
                )
            ).all()
        )
        if target_ids <= direct_report_ids:
            return project
    raise forbidden("项目经理只能预约本项目成员；L3/L4 只能预约自己的直属下属")


def _validate_project_manager(db: Session, manager_id: int, department_id: int) -> User:
    manager = db.get(User, manager_id)
    if not manager or manager.is_deleted or manager.status != "active":
        raise not_found("project manager not found")
    if not (get_role_codes(db, manager.id) & PROJECT_CREATOR_ROLES):
        raise bad_request("项目负责人必须具有项目经理、L3 或超级管理员角色")
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
        if not member.department_id or not member.organization_id:
            raise bad_request(f"项目成员 {member.name} 必须设置部门和组织")
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
    joined_at = datetime.now()
    db.add(
        ProjectMember(
            project_id=project.id,
            user_id=manager.id,
            project_role="manager",
            allocation_percent=100,
            joined_at=joined_at,
        )
    )
    for member in members:
        db.add(
            ProjectMember(
                project_id=project.id,
                user_id=member.id,
                project_role="member",
                allocation_percent=100,
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


def get_department_l3(db: Session, department_id: int) -> User:
    department = db.get(Department, department_id)
    if not department or department.status != "active":
        raise not_found("department not found")
    if not department.manager_id:
        raise bad_request("请先为项目所属部门设置 L3（部门主管）")
    approver = db.get(User, department.manager_id)
    if not approver or approver.is_deleted or approver.status != "active":
        raise bad_request("项目所属部门的 L3 用户不存在或已停用，请先重新设置")
    if "department_manager" not in get_role_codes(db, approver.id):
        raise bad_request("部门负责人必须具有 L3（部门主管）角色")
    if approver.department_id != department_id:
        raise bad_request("L3 必须属于项目所属部门，请先修正用户部门或部门负责人")
    return approver


def _assert_department_l3(db: Session, project: Project, user: User) -> User:
    if not project.department_id:
        raise bad_request("项目未设置所属部门，无法确定 L3 审批人")
    approver = get_department_l3(db, project.department_id)
    if approver.id != user.id:
        raise forbidden("只有项目所属部门当前设置的 L3 可以审批")
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
    approval_status: str | None = None,
):
    items, total = project_repository.list(
        db,
        page,
        page_size,
        keyword,
        status,
        manager_id,
        department_id,
        approval_status,
        visible_project_ids(db, user),
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def project_detail(db: Session, project_id: int, user: User) -> dict:
    project = assert_project_visible(db, project_id, user)
    items, _ = project_repository.list(db, 1, 1, visible_project_ids={project.id})
    return items[0]


def create_project(db: Session, payload: ProjectCreate, user: User) -> Project:
    if db.scalar(select(Project.id).where(Project.code == payload.code)):
        raise conflict("project code already exists", 40921)
    roles = get_role_codes(db, user.id)
    if not (roles & PROJECT_CREATOR_ROLES):
        raise forbidden("只有项目经理、L3 或超级管理员可以创建项目")
    if payload.manager_id != user.id:
        raise forbidden("项目负责人必须选择当前创建人本人")
    manager = _validate_project_manager(db, payload.manager_id, payload.department_id)
    members = _validate_initial_project_members(db, payload.member_ids)
    values = payload.model_dump(exclude={"status", "member_ids"})
    auto_approved = bool(roles & {"department_manager", "super_admin"})
    project = Project(
        **values,
        status="Planned" if auto_approved else "Draft",
        approval_status="approved" if auto_approved else "draft",
        created_by=user.id,
        approved_at=datetime.now() if auto_approved else None,
        approval_note=(
            "创建人属于 L3 或超级管理员，系统自动通过"
            if auto_approved
            else None
        ),
    )
    db.add(project)
    db.flush()
    _add_initial_project_members(db, project, manager, members)
    db.flush()
    log_operation(
        db,
        operator_id=user.id,
        module="project",
        action="create_auto_approved" if auto_approved else "create_draft",
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


def _get_active_supervisor(db: Session, creator: User) -> User:
    supervisor = db.get(User, creator.supervisor_id) if creator.supervisor_id else None
    if not supervisor or supervisor.is_deleted or supervisor.status != "active":
        raise bad_request("当前用户未设置有效直属主管，无法提交项目审批")
    return supervisor


def submit_project(db: Session, project_id: int, user: User) -> Project:
    project = db.scalar(
        select(Project)
        .where(Project.id == project_id, Project.is_deleted.is_(False))
        .with_for_update()
    )
    if not project:
        raise not_found("project not found")
    if project.created_by != user.id or project.manager_id != user.id:
        raise forbidden("只有项目创建人可以提交审批")
    if project.approval_status not in {"draft", "rejected"}:
        raise bad_request("只有草稿或已驳回项目可以提交审批")
    roles = get_role_codes(db, user.id)
    if not (roles & PROJECT_CREATOR_ROLES):
        raise forbidden("当前用户不再具有项目创建权限")
    before = model_to_dict(project)
    project.approval_note = None
    project.approved_by = None
    project.approved_at = None
    if roles & {"department_manager", "super_admin"}:
        project.approval_status = "approved"
        project.status = "Planned"
        project.approver_id = None
        project.approved_at = datetime.now()
        project.approval_note = "创建人属于 L3 或超级管理员，系统自动通过"
        action = "auto_approve"
    else:
        creator = db.get(User, project.created_by)
        if not creator:
            raise not_found("project creator not found")
        approver = _get_active_supervisor(db, creator)
        project.approval_status = "pending"
        project.status = "Draft"
        project.approver_id = approver.id
        create_notification(
            db,
            approver.id,
            "project_approval_required",
            "项目等待直属主管审批",
            f"{creator.name} 提交了项目 {project.code} - {project.name}，"
            f"请审核项目与 {project.budget_hours} 小时工时额度。",
            level="warning",
            related_type="project",
            related_id=project.id,
        )
        action = "submit_for_approval"
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
    before = model_to_dict(project)
    values = payload.model_dump(exclude_unset=True)
    if "manager_id" in values and values["manager_id"] != project.manager_id:
        raise bad_request("项目提交后不能更换项目经理，请删除草稿后由新项目经理重新创建")
    if project.approval_status == "approved" and {"manager_id", "department_id", "budget_hours"} & values.keys():
        raise bad_request("已审批项目不能直接修改负责人、部门或工时额度；工时请发起追加申请")
    department_id = values.get("department_id", project.department_id)
    manager_id = values.get("manager_id", project.manager_id)
    if not department_id:
        raise bad_request("project department is required")
    _validate_project_manager(db, manager_id, department_id)
    planned_start = values.get("planned_start", project.planned_start)
    planned_end = values.get("planned_end", project.planned_end)
    actual_start = values.get("actual_start", project.actual_start)
    actual_end = values.get("actual_end", project.actual_end)
    if planned_end < planned_start:
        raise bad_request("planned_end must be on or after planned_start")
    if actual_start and actual_end and actual_end < actual_start:
        raise bad_request("actual_end must be on or after actual_start")
    if values.get("status") and values["status"] not in PROJECT_STATUSES:
        raise bad_request("invalid project status")
    if project.approval_status != "approved":
        if project.manager_id != user.id:
            raise forbidden("未审批项目只能由项目创建人修改")
        if project.approval_status == "pending":
            raise bad_request("待审批项目不能修改，请先由直属主管审批")
        values["status"] = "Draft"
    elif "status" in values and values["status"] != project.status:
        allowed_statuses = PROJECT_STATUS_TRANSITIONS.get(project.status, set())
        if values["status"] not in allowed_statuses:
            raise bad_request(
                f"项目状态不能从 {project.status} 变更为 {values['status']}"
            )
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
    if project.approver_id != user.id:
        raise forbidden("只有项目创建人的直属主管可以审批")
    if project.created_by == user.id:
        raise forbidden("项目创建人不能审批自己的项目")
    if not approved and not payload.note:
        raise bad_request("驳回项目时必须填写原因")
    before = model_to_dict(project)
    project.approval_status = "approved" if approved else "rejected"
    project.status = "Planned" if approved else "Draft"
    project.approved_by = user.id
    project.approved_at = datetime.now()
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


def add_member(db: Session, project_id: int, payload: ProjectMemberCreate, user: User) -> ProjectMember:
    project = assert_project_manageable(db, project_id, user)
    assert_project_approved(db, project_id)
    member_user = db.get(User, payload.user_id)
    if (
        not member_user
        or member_user.is_deleted
        or member_user.status != "active"
    ):
        raise not_found("user not found")
    if not member_user.department_id or not member_user.organization_id:
        raise bad_request("项目成员必须来自完整的部门和组织架构")
    organization = db.get(Organization, member_user.organization_id)
    if (
        not organization
        or organization.status != "active"
        or organization.department_id != member_user.department_id
    ):
        raise bad_request("项目成员的部门和组织关系无效")
    member = db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == payload.user_id,
        )
    )
    if member and member.left_at is None:
        raise conflict("user is already an active project member", 40922)
    if member:
        member.left_at = None
        member.project_role = payload.project_role
        member.allocation_percent = payload.allocation_percent
        member.joined_at = payload.joined_at
    else:
        member = ProjectMember(project_id=project_id, **payload.model_dump())
        db.add(member)
    db.flush()
    if member_user.id != user.id:
        create_notification(
            db,
            member_user.id,
            "project_member_added",
            "你已加入项目",
            f"你已被加入项目“{project.name}”。",
            related_type="project",
            related_id=project.id,
        )
    log_operation(
        db,
        operator_id=user.id,
        module="project",
        action="add_member",
        object_type="project_member",
        object_id=member.id,
        after_data=model_to_dict(member),
    )
    db.commit()
    db.refresh(member)
    return member


def remove_member(db: Session, project_id: int, member_user_id: int, user: User) -> None:
    project = assert_project_manageable(db, project_id, user)
    assert_project_approved(db, project_id)
    if member_user_id == project.manager_id:
        raise bad_request("项目经理属于固定项目成员，不能移除")
    member = db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == member_user_id,
            ProjectMember.left_at.is_(None),
        )
    )
    if not member:
        raise not_found("active project member not found")
    before = model_to_dict(member)
    member.left_at = datetime.now()
    log_operation(
        db,
        operator_id=user.id,
        module="project",
        action="remove_member",
        object_type="project_member",
        object_id=member.id,
        before_data=before,
        after_data=model_to_dict(member),
    )
    db.commit()


def create_hour_request(
    db: Session,
    project_id: int,
    payload: ProjectHourRequestCreate,
    user: User,
) -> ProjectHourRequest:
    project = assert_project_owner_for_hour_request(db, project_id, user)
    if not project.department_id:
        raise bad_request("项目未设置所属部门，无法申请追加工时")
    if db.scalar(
        select(ProjectHourRequest.id).where(
            ProjectHourRequest.project_id == project.id,
            ProjectHourRequest.status == "pending",
        )
    ):
        raise conflict("该项目已有待审批的追加工时申请", 40923)
    approver = get_department_l3(db, project.department_id)
    item = ProjectHourRequest(
        project_id=project.id,
        requested_hours=payload.requested_hours,
        reason=payload.reason,
        requested_by=user.id,
        status="pending",
    )
    db.add(item)
    db.flush()
    create_notification(
        db,
        approver.id,
        "project_hours_approval_required",
        "追加项目工时待 L3 审批",
        f"项目 {project.code} 申请追加 {item.requested_hours} 小时。原因：{item.reason}",
        level="warning",
        related_type="project_hour_request",
        related_id=item.id,
    )
    log_operation(
        db,
        operator_id=user.id,
        module="project",
        action="request_hours",
        object_type="project_hour_request",
        object_id=item.id,
        after_data=model_to_dict(item),
    )
    db.commit()
    db.refresh(item)
    return item


def list_hour_requests(db: Session, project_id: int, user: User) -> list[dict]:
    assert_project_manageable(db, project_id, user)
    requester = aliased(User)
    reviewer = aliased(User)
    rows = db.execute(
        select(
            ProjectHourRequest,
            requester.name.label("requester_name"),
            reviewer.name.label("reviewer_name"),
        )
        .join(requester, requester.id == ProjectHourRequest.requested_by)
        .outerjoin(reviewer, reviewer.id == ProjectHourRequest.reviewed_by)
        .where(ProjectHourRequest.project_id == project_id)
        .order_by(ProjectHourRequest.created_at.desc())
    ).all()
    return [
        {
            **model_to_dict(item),
            "requester_name": requester_name,
            "reviewer_name": reviewer_name,
        }
        for item, requester_name, reviewer_name in rows
    ]


def decide_hour_request(
    db: Session,
    project_id: int,
    request_id: int,
    payload: ProjectDecision,
    user: User,
    approved: bool,
) -> ProjectHourRequest:
    project = db.scalar(
        select(Project)
        .where(Project.id == project_id, Project.is_deleted.is_(False))
        .with_for_update()
    )
    if not project:
        raise not_found("project not found")
    _assert_department_l3(db, project, user)
    item = db.scalar(
        select(ProjectHourRequest)
        .where(
            ProjectHourRequest.id == request_id,
            ProjectHourRequest.project_id == project_id,
        )
        .with_for_update()
    )
    if not item:
        raise not_found("hour request not found")
    if item.status != "pending":
        raise bad_request("only pending hour requests can be reviewed")
    if not approved and not payload.note:
        raise bad_request("驳回追加工时申请时必须填写原因")
    before = model_to_dict(item)
    item.status = "approved" if approved else "rejected"
    item.reviewed_by = user.id
    item.reviewed_at = datetime.now()
    item.review_note = payload.note
    if approved:
        project.budget_hours += item.requested_hours
    create_notification(
        db,
        item.requested_by,
        "project_hours_approved" if approved else "project_hours_rejected",
        "追加项目工时已获批" if approved else "追加项目工时被驳回",
        f"项目 {project.code} 的 {item.requested_hours} 小时追加申请"
        f"{'已通过' if approved else '未通过'}。"
        + (f" 审批意见：{payload.note}" if payload.note else ""),
        level="info" if approved else "warning",
        related_type="project_hour_request",
        related_id=item.id,
    )
    db.flush()
    log_operation(
        db,
        operator_id=user.id,
        module="project",
        action="approve_hours" if approved else "reject_hours",
        object_type="project_hour_request",
        object_id=item.id,
        before_data=before,
        after_data=model_to_dict(item),
        reason=payload.note,
    )
    db.commit()
    db.refresh(item)
    return item
