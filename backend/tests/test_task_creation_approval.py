"""Parent-task approval regressions. Sources only; not executed by the coding agent."""
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import BusinessException
from app.models.project import Project
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskDecision
from app.services import execution_service, overtime_service, project_service, schedule_service, task_service
from app.services.task_approval_policy import assert_task_approved


def task(state="pending", parent_id=None, task_id=10):
    return Task(id=task_id, project_id=1, parent_id=parent_id, name="接口开发", owner_id=3,
                status="not_started", approval_status=state, is_deleted=False,
                planned_start=date(2026, 10, 9), planned_end=date(2026, 10, 20),
                estimated_hours=Decimal("8"), created_by=2)


def project():
    return Project(id=1, name="研发项目", manager_id=2, department_id=7,
                   approval_status="approved", status="running", is_deleted=False)


@pytest.mark.parametrize("parent_id,expected", [(None, "pending"), (9, "not_required")])
def test_creation_requires_approval_only_at_top_level(monkeypatch, parent_id, expected):
    db = MagicMock()
    monkeypatch.setattr(task_service, "assert_project_manageable", lambda *args: None)
    monkeypatch.setattr(task_service, "assert_project_approved", lambda *args: project())
    monkeypatch.setattr(task_service, "_validate_owners", lambda *args: [3])
    monkeypatch.setattr(task_service, "_validate_parent", lambda *args: task("approved", task_id=9) if parent_id else None)
    for name in ("_validate_assignees_with_parent", "_validate_estimated_hours", "_validate_task_window", "log_operation"):
        monkeypatch.setattr(task_service, name, lambda *args, **kwargs: None)
    approver = MagicMock(return_value=SimpleNamespace(id=8))
    notify = MagicMock()
    monkeypatch.setattr(task_service, "_root_task_approver", approver)
    monkeypatch.setattr(task_service, "_notify_task_approval", notify)
    assigned = MagicMock()
    monkeypatch.setattr(task_service, "create_notification", assigned)
    payload = TaskCreate(project_id=1, parent_id=parent_id, name="接口开发", owner_ids=[3],
                         planned_start=date(2026, 10, 9), planned_end=date(2026, 10, 20), estimated_hours=8)
    item = task_service.create_task(db, payload, SimpleNamespace(id=2, name="项目经理"))
    assert item.approval_status == expected
    assert item.status == "not_started"
    assert item.created_by == 2
    assert approver.call_count == notify.call_count == (0 if parent_id else 1)
    assert assigned.call_count == (1 if parent_id else 0)
    db.commit.assert_called_once()


@pytest.mark.parametrize("state", ["pending", "rejected", "not_required", None])
def test_unapproved_roots_fail_closed(state):
    with pytest.raises(BusinessException):
        assert_task_approved(MagicMock(), task(state))


def test_children_inherit_approved_root_and_invalid_hierarchies_are_rejected():
    db = MagicMock()
    child = task("not_required", parent_id=9)
    root = task("approved", task_id=9)
    db.get.return_value = root
    assert_task_approved(db, child)
    for state in ("pending", "rejected"):
        root.approval_status = state
        with pytest.raises(BusinessException):
            assert_task_approved(db, child)
    root.approval_status = "approved"
    root.parent_id = child.id
    db.get.side_effect = [root, child]
    with pytest.raises(BusinessException, match="层级无效"):
        assert_task_approved(db, child)


@pytest.mark.parametrize("roles,assigned,allowed", [
    ({"super_admin"}, True, False),
    ({"project_manager"}, True, False),
    ({"department_manager"}, False, False),
    ({"department_manager"}, True, True),
    ({"super_admin", "department_manager"}, True, True),
])
def test_only_current_project_department_manager_can_approve(monkeypatch, roles, assigned, allowed):
    db = MagicMock()
    item = task()
    actor = SimpleNamespace(id=8, name="审批人")
    monkeypatch.setattr(task_service, "_lock_task_approval", lambda *args: (item, project()))
    monkeypatch.setattr(project_service, "get_role_codes", lambda *args: roles)
    monkeypatch.setattr(project_service, "get_department_manager", lambda *args: SimpleNamespace(id=8 if assigned else 9))
    monkeypatch.setattr(task_service, "_validate_root_task_submission", lambda *args: [3])
    monkeypatch.setattr(task_service, "create_notification", MagicMock())
    monkeypatch.setattr(task_service, "log_operation", MagicMock())
    if not allowed:
        with pytest.raises(BusinessException) as error:
            task_service.decide_task(db, item.id, TaskDecision(), actor, approve=True)
        assert error.value.status_code == 403
        assert item.approval_status == "pending"
        db.commit.assert_not_called()
    else:
        task_service.decide_task(db, item.id, TaskDecision(), actor, approve=True)
        assert item.approval_status == "approved" and item.approved_by == actor.id
        assert isinstance(item.approved_at, datetime)
        db.commit.assert_called_once()
        with pytest.raises(BusinessException, match="重复审批"):
            task_service.decide_task(db, item.id, TaskDecision(), actor, approve=True)


def test_rejection_requires_reason_then_allows_resubmission(monkeypatch):
    db = MagicMock()
    item = task()
    monkeypatch.setattr(task_service, "_lock_task_approval", lambda *args: (item, project()))
    for name in ("_assert_department_manager", "assert_project_manageable", "log_operation", "_notify_task_approval"):
        monkeypatch.setattr(task_service, name, MagicMock())
    monkeypatch.setattr(task_service, "_root_task_approver", lambda *args: SimpleNamespace(id=8))
    monkeypatch.setattr(task_service, "_validate_root_task_submission", lambda *args: [3])
    notification = MagicMock()
    monkeypatch.setattr(task_service, "create_notification", notification)
    with pytest.raises(BusinessException, match="驳回原因"):
        task_service.decide_task(db, item.id, TaskDecision(note=" "), SimpleNamespace(id=8), approve=False)
    task_service.decide_task(db, item.id, TaskDecision(note="调整计划"), SimpleNamespace(id=8), approve=False)
    assert item.approval_status == "rejected" and item.approval_note == "调整计划"
    assert {call.args[1] for call in notification.call_args_list} == {2}
    task_service.submit_task(db, item.id, SimpleNamespace(id=2))
    assert item.approval_status == "pending" and item.approver_id == 8
    assert item.approved_by is None and item.approved_at is None and item.approval_note is None
    with pytest.raises(BusinessException, match="只有被驳回"):
        task_service.submit_task(db, item.id, SimpleNamespace(id=2))


def test_missing_department_cannot_silently_approve():
    missing = project()
    missing.department_id = None
    with pytest.raises(BusinessException, match="部门主管"):
        task_service._root_task_approver(MagicMock(), missing)


def test_revalidates_capacity_before_approval(monkeypatch):
    db = MagicMock()
    item = task()
    monkeypatch.setattr(task_service, "_lock_task_approval", lambda *args: (item, project()))
    monkeypatch.setattr(task_service, "_assert_department_manager", lambda *args: None)
    from app.core.exceptions import bad_request
    monkeypatch.setattr(task_service, "_validate_root_task_submission", MagicMock(side_effect=bad_request("工时不足")))
    with pytest.raises(BusinessException, match="工时不足"):
        task_service.decide_task(db, item.id, TaskDecision(), SimpleNamespace(id=8), approve=True)
    assert item.approval_status == "pending"
    db.commit.assert_not_called()


def test_unapproved_task_is_blocked_by_booking_execution_and_overtime():
    item = task()
    db = MagicMock()
    db.get.side_effect = [SimpleNamespace(is_deleted=False, status="active"), project()]
    db.scalar.return_value = item
    with pytest.raises(BusinessException, match="尚未通过部门主管审批"):
        schedule_service._validate_relations(db, 3, 1, item.id)
    db = MagicMock()
    db.scalar.side_effect = [1, project(), item]
    with pytest.raises(BusinessException, match="尚未通过部门主管审批"):
        execution_service._lock_executable_task(db, item.id)
    with pytest.raises(BusinessException, match="尚未通过部门主管审批"):
        overtime_service._validate_context(MagicMock(), project(), item, 3)


def test_pending_permissions_do_not_grant_administrator_review():
    item = {"project_id": 1, "project_manager_id": 2, "owner_ids": [3], "approval_status": "pending"}
    task_service._add_permissions(item, SimpleNamespace(id=2), True, set())
    assert item["can_manage"] is True and item["can_delete"] is True
    assert item["can_edit"] is False and item["can_review"] is False
    assert item["effective_status"] == "not_started"
    task_service._add_permissions(item, SimpleNamespace(id=8), True, {1})
    assert item["can_review"] is True
