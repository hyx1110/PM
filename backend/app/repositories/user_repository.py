from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from app.models.organization import Department, Organization
from app.models.rbac import Role, UserRole
from app.models.user import User


class UserRepository:
    def get(self, db: Session, user_id: int) -> User | None:
        return db.scalar(select(User).where(User.id == user_id, User.is_deleted.is_(False)))

    def get_by_employee_no(self, db: Session, employee_no: str) -> User | None:
        # Deleted employee numbers remain reserved so historical records cannot
        # be confused with a newly created identity using the same login account.
        return db.scalar(select(User).where(User.employee_no == employee_no))

    def detail(self, db: Session, user_id: int) -> dict | None:
        supervisor = aliased(User)
        row = db.execute(
            select(
                User,
                Department.name.label("department_name"),
                Organization.name.label("organization_name"),
                supervisor.name.label("supervisor_name"),
            )
            .outerjoin(Department, Department.id == User.department_id)
            .outerjoin(Organization, Organization.id == User.organization_id)
            .outerjoin(supervisor, supervisor.id == User.supervisor_id)
            .where(User.id == user_id, User.is_deleted.is_(False))
        ).first()
        if not row:
            return None
        user, department_name, organization_name, supervisor_name = row
        role_rows = db.execute(
            select(Role.id, Role.code)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user.id)
            .order_by(Role.id)
        ).all()
        data = {
            column.name: getattr(user, column.name)
            for column in User.__table__.columns
            if column.name not in {"password_hash", "is_deleted"}
        }
        data.update(
            department_name=department_name,
            organization_name=organization_name,
            supervisor_name=supervisor_name,
            role_ids=[item.id for item in role_rows],
            roles=[item.code for item in role_rows],
        )
        return data

    def list(
        self,
        db: Session,
        page: int,
        page_size: int,
        keyword: str | None = None,
        department_id: int | None = None,
        organization_id: int | None = None,
        status: str | None = None,
        organization_keyword: str | None = None,
    ) -> tuple[list[dict], int]:
        supervisor = aliased(User)
        filters = [User.is_deleted.is_(False)]
        if keyword:
            filters.append(
                or_(
                    User.name.like(f"%{keyword}%"),
                    User.employee_no.like(f"%{keyword}%"),
                    User.email.like(f"%{keyword}%"),
                )
            )
        if department_id:
            filters.append(User.department_id == department_id)
        if organization_id:
            filters.append(User.organization_id == organization_id)
        if status:
            filters.append(User.status == status)
        if organization_keyword and organization_keyword.strip():
            term = f"%{organization_keyword.strip()}%"
            filters.append(or_(
                User.department_id.in_(select(Department.id).where(Department.name.like(term))),
                User.organization_id.in_(select(Organization.id).where(Organization.name.like(term))),
            ))
        count = db.scalar(select(func.count(User.id)).where(*filters)) or 0
        statement = (
            select(
                User,
                Department.name.label("department_name"),
                Organization.name.label("organization_name"),
                supervisor.name.label("supervisor_name"),
            )
            .outerjoin(Department, Department.id == User.department_id)
            .outerjoin(Organization, Organization.id == User.organization_id)
            .outerjoin(supervisor, supervisor.id == User.supervisor_id)
            .where(*filters)
            .order_by(User.employee_no.asc(), User.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = []
        for user, department_name, organization_name, supervisor_name in db.execute(statement):
            role_rows = db.execute(
                select(Role.id, Role.code)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(UserRole.user_id == user.id)
                .order_by(Role.id)
            ).all()
            data = {
                column.name: getattr(user, column.name)
                for column in User.__table__.columns
                if column.name not in {"password_hash", "is_deleted"}
            }
            data.update(
                department_name=department_name,
                organization_name=organization_name,
                supervisor_name=supervisor_name,
                role_ids=[row.id for row in role_rows],
                roles=[row.code for row in role_rows],
            )
            items.append(data)
        return items, count


user_repository = UserRepository()
