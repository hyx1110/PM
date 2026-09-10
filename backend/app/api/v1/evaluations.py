from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.responses import success
from app.models.user import User
from app.schemas.evaluation import EvaluationUpsert
from app.services import evaluation_service

router = APIRouter(prefix="/tasks", tags=["任务评价"])


@router.get("/{task_id}/evaluation")
def get_evaluation(
    task_id: int,
    current_user: User = Depends(require_permission("process_report:view")),
    db: Session = Depends(get_db),
):
    return success(evaluation_service.get_evaluation(db, task_id, current_user))


@router.put("/{task_id}/evaluation")
def upsert_evaluation(
    task_id: int,
    payload: EvaluationUpsert,
    current_user: User = Depends(require_permission("evaluation:edit")),
    db: Session = Depends(get_db),
):
    evaluation_service.upsert_evaluation(db, task_id, payload, current_user)
    return success(evaluation_service.get_evaluation(db, task_id, current_user))

