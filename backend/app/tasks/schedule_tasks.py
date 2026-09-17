from app.core.database import SessionLocal
from app.services.schedule_lifecycle_service import synchronize_schedule_statuses
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.schedule_tasks.synchronize_schedule_statuses")
def synchronize_schedule_statuses_task() -> dict[str, int]:
    with SessionLocal() as db:
        result = synchronize_schedule_statuses(db)
        db.commit()
        return result
