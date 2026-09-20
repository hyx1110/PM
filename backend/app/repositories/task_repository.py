from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from app.models.project import Project
from app.models.organization import Department, Organization
from app.models.schedule import ScheduleBooking
from app.models.task import Task, TaskAssignee
from app.models.user import User
from app.repositories.project_repository import booked_schedule_predicate
from app.utils.time import beijing_today


class TaskRepository:
    def get(self, db: Session, task_id: int) -> Task | None:
        return db.scalar(select(Task).where(Task.id == task_id, Task.is_deleted.is_(False)))

    @staticmethod
    def _booked_hours_expression():
        return (
            select(func.coalesce(func.sum(ScheduleBooking.planned_hours), 0))
            .where(
                ScheduleBooking.task_id == Task.id,
                booked_schedule_predicate(),
            )
            .correlate(Task)
            .scalar_subquery()
        )

    @staticmethod
    def _assignee_map(db: Session, task_ids: list[int]) -> dict[int, list[dict]]:
        if not task_ids:
            return {}
        rows = db.execute(
            select(TaskAssignee.task_id, User.id, User.name, User.employee_no)
            .join(User, User.id == TaskAssignee.user_id)
            .where(TaskAssignee.task_id.in_(task_ids))
            .order_by(TaskAssignee.id)
        ).all()
        result: dict[int, list[dict]] = {}
        for task_id, user_id, name, employee_no in rows:
            result.setdefault(task_id, []).append({"id": user_id, "name": name, "employee_no": employee_no})
        return result

    def _serialize_rows(self, db: Session, rows) -> list[dict]:
        assignees = self._assignee_map(db, [row[0].id for row in rows])
        items: list[dict] = []
        for task, project_name, project_manager_name, project_manager_id, booked_hours in rows:
            owners = assignees.get(task.id, [])
            items.append({
                **{col.name: getattr(task, col.name) for col in Task.__table__.columns},
                "project_name": project_name,
                "owner_ids": [owner["id"] for owner in owners],
                "owner_names": [owner["name"] for owner in owners],
                "owner_name": "、".join(owner["name"] for owner in owners),
                "project_manager_name": project_manager_name,
                "project_manager_id": project_manager_id,
                "booked_hours": booked_hours or 0,
            })
        return items

    def detail(self, db: Session, task_id: int) -> dict | None:
        manager = aliased(User)
        rows = db.execute(
            select(Task, Project.name, manager.name, Project.manager_id, self._booked_hours_expression())
            .join(Project, Project.id == Task.project_id)
            .join(manager, manager.id == Project.manager_id)
            .where(Task.id == task_id, Task.is_deleted.is_(False), Project.is_deleted.is_(False))
        ).all()
        return self._serialize_rows(db, rows)[0] if rows else None

    def list(
        self,
        db: Session,
        page: int,
        page_size: int,
        project_id: int | None = None,
        owner_id: int | None = None,
        status: str | None = None,
        department_id: int | None = None,
        organization_id: int | None = None,
        employee_no: str | None = None,
        owner_name: str | None = None,
        visible_project_ids: set[int] | None = None,
        own_user_id: int | None = None,
        personnel_keyword: str | None = None,
        organization_keyword: str | None = None,
    ) -> tuple[list[dict], int]:
        filters = [
            Task.is_deleted.is_(False),
            Task.project_id.in_(select(Project.id).where(Project.is_deleted.is_(False))),
        ]
        if project_id:
            filters.append(Task.project_id == project_id)
        if owner_id:
            filters.append(Task.id.in_(select(TaskAssignee.task_id).where(TaskAssignee.user_id == owner_id)))
        if status == "delayed":
            filters.extend([Task.planned_end < beijing_today(), Task.status.notin_({"completed", "cancelled"})])
        elif status:
            filters.append(Task.status == status)
        if department_id or organization_id or employee_no or owner_name or personnel_keyword or organization_keyword:
            people = select(User.id).where(User.is_deleted.is_(False))
            if department_id:
                people = people.where(User.department_id == department_id)
            if organization_id:
                people = people.where(User.organization_id == organization_id)
            if employee_no:
                people = people.where(User.employee_no.like(f"%{employee_no}%"))
            if owner_name:
                people = people.where(User.name.like(f"%{owner_name}%"))
            if personnel_keyword:
                people = people.where(or_(User.name.like(f"%{personnel_keyword}%"), User.employee_no.like(f"%{personnel_keyword}%")))
            if organization_keyword:
                people = people.where(or_(
                    User.department_id.in_(select(Department.id).where(Department.name.like(f"%{organization_keyword}%"))),
                    User.organization_id.in_(select(Organization.id).where(Organization.name.like(f"%{organization_keyword}%"))),
                ))
            filters.append(Task.id.in_(select(TaskAssignee.task_id).where(TaskAssignee.user_id.in_(people))))
        if visible_project_ids is not None:
            filters.append(Task.project_id.in_(visible_project_ids or {-1}))
        if own_user_id is not None:
            filters.append(
                Task.id.in_(
                    select(TaskAssignee.task_id).where(
                        TaskAssignee.user_id == own_user_id
                    )
                )
            )
        total = db.scalar(select(func.count(Task.id)).where(*filters)) or 0
        manager = aliased(User)
        rows = db.execute(
            select(Task, Project.name, manager.name, Project.manager_id, self._booked_hours_expression())
            .join(Project, Project.id == Task.project_id)
            .join(manager, manager.id == Project.manager_id)
            .where(*filters)
            .order_by(
                Task.planned_start.desc(),
                Task.planned_end.desc(),
                Task.created_at.desc(),
                Task.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return self._serialize_rows(db, rows), total


task_repository = TaskRepository()
