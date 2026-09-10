from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.models.organization import Department, Organization
from app.models.user import User


class OrganizationRepository:
    def list_departments(self, db: Session) -> list[dict]:
        manager = aliased(User)
        rows = db.execute(
            select(Department, manager.name.label("manager_name"))
            .outerjoin(manager, manager.id == Department.manager_id)
            .order_by(Department.code)
        ).all()
        return [
            {**{col.name: getattr(item, col.name) for col in Department.__table__.columns}, "manager_name": manager_name}
            for item, manager_name in rows
        ]

    def list_organizations(self, db: Session, department_id: int | None = None) -> list[dict]:
        manager = aliased(User)
        statement = (
            select(Organization, manager.name.label("manager_name"))
            .outerjoin(manager, manager.id == Organization.manager_id)
            .order_by(Organization.level, Organization.code)
        )
        if department_id:
            statement = statement.where(Organization.department_id == department_id)
        rows = db.execute(statement).all()
        return [
            {**{col.name: getattr(item, col.name) for col in Organization.__table__.columns}, "manager_name": manager_name}
            for item, manager_name in rows
        ]

    def has_children(self, db: Session, organization_id: int) -> bool:
        return bool(db.scalar(select(func.count()).select_from(Organization).where(Organization.parent_id == organization_id)))


organization_repository = OrganizationRepository()

