from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.responses import success
from app.models.organization import Department
from app.models.project import Project, ProjectMember
from app.models.rbac import Role, UserRole
from app.models.schedule import ScheduleBooking
from app.models.user import User
from app.services.visibility_service import visible_schedule_user_ids

router = APIRouter(prefix="/lookups", tags=["通用选项"])


@router.get("/users")
def user_options(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(
            User.id,
            User.employee_no,
            User.name,
            User.department_id,
            User.organization_id,
            User.supervisor_id,
        )
        .where(User.status == "active", User.is_deleted.is_(False))
        .order_by(User.name)
    ).all()
    return success([dict(row._mapping) for row in rows])


@router.get("/schedule-users")
def schedule_user_options(
    project_id: int | None = None,
    keyword: str | None = None,
    name: str | None = None,
    employee_no: str | None = None,
    department_id: int | None = None,
    organization_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    visible_ids = visible_schedule_user_ids(db, current_user)
    statement = select(
        User.id,
        User.employee_no,
        User.name,
        User.department_id,
        User.organization_id,
        User.supervisor_id,
    ).where(User.status == "active", User.is_deleted.is_(False))
    if visible_ids is not None:
        statement = statement.where(User.id.in_(visible_ids or {-1}))
    if project_id:
        statement = statement.where(User.id.in_(select(ProjectMember.user_id).where(ProjectMember.project_id == project_id, ProjectMember.left_at.is_(None))))
    if keyword:
        statement = statement.where(
            or_(
                User.name.like(f"%{keyword}%"),
                User.employee_no.like(f"%{keyword}%"),
            )
        )
    if name:
        statement = statement.where(User.name.like(f"%{name}%"))
    if employee_no:
        statement = statement.where(User.employee_no.like(f"%{employee_no}%"))
    if department_id:
        statement = statement.where(User.department_id == department_id)
    if organization_id:
        statement = statement.where(User.organization_id == organization_id)
    rows = db.execute(statement.order_by(User.name)).all()
    items = [dict(row._mapping) for row in rows]
    items.sort(key=lambda item: (item["id"] != current_user.id, item["name"]))
    return success(items)


@router.get("/schedule-projects")
def schedule_project_options(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Projects represented in the viewer's person-based schedule scope."""
    visible_ids = visible_schedule_user_ids(db, current_user)
    statement = select(Project.id, Project.code, Project.name).where(
        Project.is_deleted.is_(False)
    )
    if visible_ids is not None:
        scheduled_project_ids = select(ScheduleBooking.project_id).where(
            ScheduleBooking.user_id.in_(visible_ids or {-1})
        )
        member_project_ids = select(ProjectMember.project_id).where(
            ProjectMember.user_id.in_(visible_ids or {-1}),
            ProjectMember.left_at.is_(None),
        )
        statement = statement.where(
            (Project.id.in_(scheduled_project_ids))
            | (Project.id.in_(member_project_ids))
            | (Project.manager_id == current_user.id)
        )
    rows = db.execute(statement.order_by(Project.code, Project.name)).all()
    return success([dict(row._mapping) for row in rows])


@router.get("/l3-users")
def l3_user_options(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(
            User.id,
            User.employee_no,
            User.name,
            User.department_id,
            User.organization_id,
            User.supervisor_id,
        )
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            Role.code == "department_manager",
            User.status == "active",
            User.is_deleted.is_(False),
        )
        .order_by(User.name)
    ).all()
    return success([dict(row._mapping) for row in rows])


@router.get("/departments")
def department_options(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Department.id, Department.code, Department.name, Department.manager_id)
        .where(Department.status == "active")
        .order_by(Department.code)
    ).all()
    return success([dict(row._mapping) for row in rows])
