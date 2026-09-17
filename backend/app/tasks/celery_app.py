from celery import Celery
from celery.schedules import crontab
from celery.signals import after_setup_logger, after_setup_task_logger

from app.core.config import settings
from app.core.logging import configure_logging

celery_app = Celery(
    "project_workforce_management",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.risk_tasks",
        "app.tasks.notification_tasks",
        "app.tasks.schedule_tasks",
    ],
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
        "synchronize-schedule-statuses": {
            "task": "app.tasks.schedule_tasks.synchronize_schedule_statuses",
            "schedule": crontab(minute="*/5"),
        },
    },
)


@after_setup_logger.connect
def configure_celery_process_logging(logger=None, **_kwargs) -> None:
    names = (logger.name,) if logger is not None else ("celery",)
    configure_logging(names)


@after_setup_task_logger.connect
def configure_celery_task_logging(logger=None, **_kwargs) -> None:
    names = (logger.name,) if logger is not None else ("celery.task",)
    configure_logging(names)
