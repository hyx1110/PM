from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import not_found
from app.models.evaluation import TaskEvaluation
from app.models.task import Task
from app.models.user import User
from app.schemas.evaluation import EvaluationUpsert
from app.services.operation_log_service import log_operation
from app.services.project_service import assert_project_manageable, assert_project_visible
from app.utils.model import model_to_dict


def get_evaluation(db: Session, task_id: int, user: User) -> dict | None:
    task = db.get(Task, task_id)
    if not task:
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
    task = db.get(Task, task_id)
    if not task:
        raise not_found("task not found")
    assert_project_manageable(db, task.project_id, user)
    evaluation = db.scalar(select(TaskEvaluation).where(TaskEvaluation.task_id == task_id))
    before = model_to_dict(evaluation) if evaluation else None
    if evaluation:
        for key, value in payload.model_dump().items():
            setattr(evaluation, key, value)
        evaluation.evaluator_id = user.id
        evaluation.evaluated_at = datetime.now()
    else:
        evaluation = TaskEvaluation(
            task_id=task_id,
            evaluator_id=user.id,
            evaluated_at=datetime.now(),
            **payload.model_dump(),
        )
        db.add(evaluation)
    db.flush()
    log_operation(
        db,
        operator_id=user.id,
        module="evaluation",
        action="upsert",
        object_type="task_evaluation",
        object_id=evaluation.id,
        before_data=before,
        after_data=model_to_dict(evaluation),
    )
    db.commit()
    db.refresh(evaluation)
    return evaluation
