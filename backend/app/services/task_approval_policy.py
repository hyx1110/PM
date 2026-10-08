"""Shared approval gate for scheduling, execution, overtime and task hierarchy."""
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request
from app.models.task import Task

EXECUTABLE_TASK_APPROVALS = ("approved", "not_required")


def assert_task_approved(db: Session, task: Task) -> None:
    visited: set[int] = set()
    cursor = task
    while cursor:
        if cursor.id in visited or cursor.is_deleted or cursor.project_id != task.project_id:
            raise bad_request("任务层级无效，请联系项目负责人处理")
        visited.add(cursor.id)
        if cursor.approval_status not in EXECUTABLE_TASK_APPROVALS:
            raise bad_request("父任务尚未通过部门主管审批，不能创建子任务、预约工时、填报执行记录或申请加班")
        if not cursor.parent_id:
            if cursor.approval_status != "approved":
                raise bad_request("顶层任务必须经过部门主管审批")
            return
        cursor = db.get(Task, cursor.parent_id)
        if cursor is None:
            raise bad_request("上级任务不存在，请联系项目负责人处理")
