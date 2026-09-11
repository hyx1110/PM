from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "project_workforce_management",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.risk_tasks", "app.tasks.notification_tasks"],
)
celery_app.conf.update(
    timezone=settings.timezone,
    enable_utc=False,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    beat_schedule={
        "scan-project-risks": {
            "task": "app.tasks.risk_tasks.scan_project_risks",
            "schedule": crontab(minute=5, hour="*/2"),
        },
        "create-upcoming-reminders": {
            "task": "app.tasks.notification_tasks.create_upcoming_reminders",
            "schedule": crontab(minute="*/30"),
        },
        "dispatch-external-notifications": {
            "task": "app.tasks.notification_tasks.dispatch_external_notifications",
            "schedule": crontab(minute="*/5"),
        },
    },
)

