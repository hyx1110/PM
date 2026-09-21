from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_role_codes
from app.core.exceptions import bad_request, forbidden, not_found
from app.models.evaluation import TaskEvaluation
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.schemas.evaluation import EvaluationUpsert
from app.services.operation_log_service import log_operation
from app.services.project_service import assert_project_visible
from app.utils.model import model_to_dict
from app.utils.time import beijing_now


def get_evaluation(db: Session, task_id: int, user: User) -> dict | None:
    task = db.get(Task, task_id)
    if not task or task.is_deleted:
        raise not_found("task not found")
    assert_project_visible(db, task.project_id, user)
    row = db.execute(
        select(TaskEvaluation, User.name.label("evaluator_name"))
        .join(User, User.id == TaskEvaluation.evaluator_id)
        .where(TaskEvaluation.task_id == task_id)
    ).first()
    if not row:
        return None
    item, evaluator_name = row
    return {
        **{col.name: getattr(item, col.name) for col in TaskEvaluation.__table__.columns},
        "evaluator_name": evaluator_name,
    }


def upsert_evaluation(db: Session, task_id: int, payload: EvaluationUpsert, user: User) -> TaskEvaluation:
    task = db.scalar(
        select(Task)
        .where(Task.id == task_id, Task.is_deleted.is_(False))
        .with_for_update()
    )
    if not task or task.is_deleted:
        raise not_found("task not found")
    project = db.get(Project, task.project_id)
    if not project or project.is_deleted:
        raise not_found("project not found")
    roles = get_role_codes(db, user.id)
    if not roles & {"super_admin", "department_manager"} and project.manager_id != user.id:
        raise forbidden("只有超级管理员、部门主管或本项目负责人可以进行评价")
    if not project or project.status != "Completed":
        raise bad_request("项目执行完成后才能进行评价")
    if task.status != "completed":
        raise bad_request("任务完成后才能进行评价")
    evaluation = db.scalar(select(TaskEvaluation).where(TaskEvaluation.task_id == task_id))
    if evaluation:
        raise bad_request("该任务已完成评价，不能重复评价")
    evaluation = TaskEvaluation(
        task_id=task_id,
        evaluator_id=user.id,
        evaluated_at=beijing_now(),
        **payload.model_dump(),
    )
    db.add(evaluation)
    db.flush()
    log_operation(
        db,
        operator_id=user.id,
        module="evaluation",
        action="create",
        object_type="task_evaluation",
        object_id=evaluation.id,
        after_data=model_to_dict(evaluation),
    )
    db.commit()
    db.refresh(evaluation)
    return evaluation
