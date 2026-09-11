from fastapi import APIRouter

from app.api.v1 import (
    auth,
    data_exchange,
    dashboard,
    evaluations,
    executions,
    lookups,
    notifications,
    operation_logs,
    organizations,
    projects,
    reports,
    risks,
    roles,
    schedules,
    tasks,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(notifications.router)
api_router.include_router(lookups.router)
api_router.include_router(users.router)
api_router.include_router(organizations.router)
api_router.include_router(roles.router)
api_router.include_router(projects.router)
api_router.include_router(tasks.router)
api_router.include_router(schedules.router)
api_router.include_router(executions.router)
api_router.include_router(evaluations.router)
api_router.include_router(reports.router)
api_router.include_router(risks.router)
api_router.include_router(data_exchange.router)
api_router.include_router(operation_logs.router)
