from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from app.models.employee_profile import EmployeeProfile
from app.models.organization import Department, Organization
from app.models.rbac import Role, UserRole
from app.models.user import User


class UserRepository:
    def get(self, db: Session, user_id: int) -> User | None:
        return db.scalar(select(User).where(User.id == user_id, User.is_deleted.is_(False)))

    def get_by_username(self, db: Session, username: str) -> User | None:
        # Deleted usernames remain reserved so historical records cannot be
        # confused with a newly created identity using the same login name.
        return db.scalar(select(User).where(User.username == username))

    def get_by_employee_no(self, db: Session, employee_no: str) -> User | None:
        return db.scalar(select(User).where(User.employee_no == employee_no))

    @staticmethod
    def _profile_data(profile: EmployeeProfile | None) -> dict | None:
        if not profile:
            return None
        return {
            column.name: getattr(profile, column.name)
            for column in EmployeeProfile.__table__.columns
        }

    def detail(self, db: Session, user_id: int) -> dict | None:
        supervisor = aliased(User)
        row = db.execute(
            select(
                User,
                Department.name.label("department_name"),
                Organization.name.label("organization_name"),
                supervisor.name.label("supervisor_name"),
                EmployeeProfile,
            )
            .outerjoin(Department, Department.id == User.department_id)
            .outerjoin(Organization, Organization.id == User.organization_id)
            .outerjoin(supervisor, supervisor.id == User.supervisor_id)
            .outerjoin(EmployeeProfile, EmployeeProfile.user_id == User.id)
            .where(User.id == user_id, User.is_deleted.is_(False))
        ).first()
        if not row:
            return None
        user, department_name, organization_name, supervisor_name, profile = row
        role_rows = db.execute(
            select(Role.id, Role.code, UserRole.is_manual, UserRole.is_hr_auto)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user.id)
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
            manual_role_ids=[item.id for item in role_rows if item.is_manual],
            hr_role_ids=[item.id for item in role_rows if item.is_hr_auto],
            manual_roles=[item.code for item in role_rows if item.is_manual],
            hr_roles=[item.code for item in role_rows if item.is_hr_auto],
            employee_profile=self._profile_data(profile),
        )
        return data

    def list(
        self,
        db: Session,
        page: int,
        page_size: int,
        keyword: str | None = None,
        department_id: int | None = None,
        status: str | None = None,
    ) -> tuple[list[dict], int]:
        supervisor = aliased(User)
        filters = [User.is_deleted.is_(False)]
        if keyword:
            filters.append(
                or_(
                    User.name.like(f"%{keyword}%"),
                    User.username.like(f"%{keyword}%"),
                    User.employee_no.like(f"%{keyword}%"),
                )
            )
        if department_id:
            filters.append(User.department_id == department_id)
        if status:
            filters.append(User.status == status)
        count = db.scalar(select(func.count(User.id)).where(*filters)) or 0
        statement = (
            select(
                User,
                Department.name.label("department_name"),
                Organization.name.label("organization_name"),
                supervisor.name.label("supervisor_name"),
                EmployeeProfile,
            )
            .outerjoin(Department, Department.id == User.department_id)
            .outerjoin(Organization, Organization.id == User.organization_id)
            .outerjoin(supervisor, supervisor.id == User.supervisor_id)
            .outerjoin(EmployeeProfile, EmployeeProfile.user_id == User.id)
            .where(*filters)
            .order_by(User.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = []
        for user, department_name, organization_name, supervisor_name, profile in db.execute(statement):
            role_rows = db.execute(
                select(Role.id, Role.code, UserRole.is_manual, UserRole.is_hr_auto)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(UserRole.user_id == user.id)
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
                manual_role_ids=[row.id for row in role_rows if row.is_manual],
                hr_role_ids=[row.id for row in role_rows if row.is_hr_auto],
                manual_roles=[row.code for row in role_rows if row.is_manual],
                hr_roles=[row.code for row in role_rows if row.is_hr_auto],
                employee_profile=self._profile_data(profile),
            )
            items.append(data)
        return items, count


user_repository = UserRepository()
