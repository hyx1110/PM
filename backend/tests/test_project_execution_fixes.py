"""2026-09-29 regression cases. Source only; no real database or server required."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.core.exceptions import BusinessException
from app.models.project import Project, ProjectResourceRequest
from app.schemas.execution import ExecutionCreate, ExecutionUpdate
from app.schemas.project import ProjectDecision, ProjectResourceRequestCreate, ProjectUpdate
from app.services import execution_service, project_service, work_calendar_service
from app.repositories.execution_repository import execution_repository


TODAY = date(2026, 9, 29)


@pytest.mark.parametrize("schema", [ExecutionCreate, ExecutionUpdate])
@pytest.mark.parametrize("hours", ["0", "-0.5", "0.3", "4.3", "4.25", "NaN", "Infinity"])
def test_execution_hours_reject_invalid_units(schema, hours):
    base = {"task_id": 1, "actual_start": TODAY} if schema is ExecutionCreate else {}
    with pytest.raises(ValidationError):
        schema(**base, actual_hours=hours)


def test_completed_execution_requires_explicit_hours_but_running_can_default():
    base = {"task_id": 1, "actual_start": TODAY, "actual_end": TODAY}
    with pytest.raises(ValidationError):
        ExecutionCreate(**base, status="completed")
    assert ExecutionCreate(**base).actual_hours is None
    assert ExecutionCreate(**base, status="completed", actual_hours="4.5").actual_hours == Decimal("4.5")


def test_normal_execution_service_also_enforces_units(monkeypatch):
    monkeypatch.setattr(execution_service, "beijing_today", lambda: TODAY)
    monkeypatch.setattr(execution_service, "calculate_workday_hours", lambda *args: Decimal("8"))
    with pytest.raises(BusinessException):
        execution_service._resolve_actual_hours(None, TODAY, TODAY, Decimal("4.3"))
    assert execution_service._resolve_actual_hours(None, TODAY, TODAY, Decimal("4.5")) == Decimal("4.5")
    assert execution_service._resolve_actual_hours(None, TODAY, TODAY, None) == Decimal("8")


def test_execution_list_scope_is_own_or_managed_project():
    db = MagicMock()
    db.scalar.return_value = 0
    db.execute.return_value.all.return_value = []
    execution_repository.list(db, 1, 20, own_user_id=7, managed_by_user_id=7, user_id=8)
    count_query = str(db.scalar.call_args.args[0].compile(compile_kwargs={"literal_binds": True}))
    assert "execution_records.user_id = 7 OR projects.manager_id = 7" in count_query
    assert "execution_records.user_id = 8" in count_query  # search intersects, never replaces scope


@pytest.mark.parametrize("mine", [False, True])
def test_execution_service_passes_manager_scope_and_honors_mine(monkeypatch, mine):
    monkeypatch.setattr(execution_service, "_has_global_execution_access", lambda *args: False)
    monkeypatch.setattr(execution_service, "resolve_personnel_scope_user_ids", lambda *args: None)
    listing = MagicMock(return_value=([], 0))
    monkeypatch.setattr(execution_service.execution_repository, "list", listing)
    execution_service.list_executions(MagicMock(), SimpleNamespace(id=7), 1, 20, mine=mine)
    kwargs = listing.call_args.kwargs
    assert kwargs["own_user_id"] == kwargs["managed_by_user_id"] == 7
    assert kwargs.get("user_id") == (7 if mine else None)


@pytest.mark.parametrize("managed", [False, True])
def test_execution_detail_allows_exact_project_owner_only(monkeypatch, managed):
    db = MagicMock()
    db.scalar.return_value = 10 if managed else None
    monkeypatch.setattr(execution_service.execution_repository, "get", lambda *args: SimpleNamespace(task_id=3, user_id=8))
    monkeypatch.setattr(execution_service.execution_repository, "detail", lambda *args: {"id": 2})
    monkeypatch.setattr(execution_service, "_has_global_execution_access", lambda *args: False)
    if managed:
        assert execution_service.execution_detail(db, 2, SimpleNamespace(id=7)) == {"id": 2}
    else:
        with pytest.raises(BusinessException) as error:
            execution_service.execution_detail(db, 2, SimpleNamespace(id=7))
        assert error.value.status_code == 403


@pytest.mark.parametrize("action", ["update", "delete"])
def test_manager_read_permission_does_not_allow_other_peoples_writes(monkeypatch, action):
    monkeypatch.setattr(execution_service.execution_repository, "get", lambda *args: SimpleNamespace(task_id=3, user_id=8, is_deleted=False))
    monkeypatch.setattr(execution_service, "_lock_executable_task", lambda *args: SimpleNamespace(project_id=10))
    monkeypatch.setattr(execution_service, "_assert_project_not_evaluated", lambda *args: None)
    monkeypatch.setattr(execution_service, "_has_global_execution_access", lambda *args: False)
    with pytest.raises(BusinessException) as error:
        if action == "update":
            execution_service.update_execution(MagicMock(), 2, ExecutionUpdate(description="改他人记录"), SimpleNamespace(id=7))
        else:
            execution_service.delete_execution(MagicMock(), 2, SimpleNamespace(id=7))
    assert error.value.status_code == 403


def make_project():
    return Project(id=10, code="P-10", name="项目", manager_id=7, department_id=1,
                   approval_status="approved", status="running", is_deleted=False, budget_hours=Decimal("8"),
                   planned_start=date(2026, 9, 1), planned_end=date(2026, 9, 28))


def test_extension_only_request_is_valid_and_blank_reason_is_not():
    payload = ProjectResourceRequestCreate(requested_planned_end="2026-10-09", reason="  延期交付  ")
    assert payload.requested_hours == 0
    assert payload.reason == "延期交付"
    with pytest.raises(ValidationError):
        ProjectResourceRequestCreate(requested_planned_end="2026-10-09", reason="  ")
    with pytest.raises(ValidationError):
        ProjectResourceRequestCreate(reason="没有任何变更")


def test_submitting_extension_keeps_original_project_date(monkeypatch):
    project = make_project()
    db = MagicMock()
    db.scalar.return_value = None  # no pending resource request
    db.scalars.return_value.all.return_value = []
    monkeypatch.setattr(project_service, "beijing_today", lambda: TODAY)
    monkeypatch.setattr(project_service, "assert_project_owner_for_resource_request", lambda *args: project)
    monkeypatch.setattr(project_service, "get_department_manager", lambda *args: SimpleNamespace(id=9))
    monkeypatch.setattr(project_service, "_validate_initial_project_members", lambda *args: [])
    monkeypatch.setattr(project_service, "create_notification", MagicMock())
    monkeypatch.setattr(project_service, "log_operation", MagicMock())
    request = project_service.create_resource_request(db, 10,
        ProjectResourceRequestCreate(requested_planned_end="2026-10-09", reason="延期"), SimpleNamespace(id=7))
    assert request.status == "pending"
    assert request.original_planned_end == project.planned_end == date(2026, 9, 28)
    assert request.requested_planned_end == date(2026, 10, 9)
    assert project.budget_hours == Decimal("8")


@pytest.mark.parametrize("new_end", [date(2026, 9, 27), date(2026, 9, 28)])
def test_extension_rejects_invalid_or_elapsed_dates(monkeypatch, new_end):
    monkeypatch.setattr(project_service, "beijing_today", lambda: TODAY)
    with pytest.raises(BusinessException):
        project_service._validate_project_extension(make_project(), new_end)


def test_only_overdue_open_approved_projects_can_extend(monkeypatch):
    monkeypatch.setattr(project_service, "beijing_today", lambda: TODAY)
    project = make_project()
    project_service._validate_project_extension(project, date(2026, 10, 9))
    project.planned_end = TODAY
    with pytest.raises(BusinessException):
        project_service._validate_project_extension(project, date(2026, 10, 9))
    project.planned_end = date(2026, 9, 28)
    project.status = "completed"
    with pytest.raises(BusinessException):
        project_service._validate_project_extension(project, date(2026, 10, 9))


def test_direct_project_edit_cannot_bypass_extension_approval(monkeypatch):
    project = make_project()
    db = MagicMock()
    db.scalar.return_value = project
    monkeypatch.setattr(project_service, "assert_project_manageable", lambda *args: project)
    monkeypatch.setattr(project_service, "_validate_project_manager", lambda *args: None)
    with pytest.raises(BusinessException):
        project_service.update_project(db, 10, ProjectUpdate(planned_end=date(2026, 10, 9)), SimpleNamespace(id=7))
    assert project.planned_end == date(2026, 9, 28)


def test_ordinary_project_owner_cannot_approve_resource_change(monkeypatch):
    monkeypatch.setattr(project_service, "get_role_codes", lambda *args: {"project_manager"})
    monkeypatch.setattr(project_service, "get_department_manager", lambda *args: SimpleNamespace(id=9))
    with pytest.raises(BusinessException) as error:
        project_service._assert_department_manager(MagicMock(), make_project(), SimpleNamespace(id=7))
    assert error.value.status_code == 403


@pytest.mark.parametrize("approved", [False, True])
def test_resource_decision_only_changes_dates_when_approved(monkeypatch, approved):
    project = make_project()
    request = ProjectResourceRequest(id=2, project_id=10, status="pending", requested_by=7,
        requested_hours=Decimal("8"), original_planned_end=project.planned_end,
        requested_planned_end=date(2026, 10, 9), reason="延期", add_member_ids=[], remove_member_ids=[])
    db = MagicMock()
    db.scalar.side_effect = [project, request]
    db.scalars.return_value.all.return_value = []
    monkeypatch.setattr(project_service, "beijing_today", lambda: TODAY)
    monkeypatch.setattr(project_service, "_assert_department_manager", lambda *args: None)
    monkeypatch.setattr(project_service, "_validate_initial_project_members", lambda *args: [])
    monkeypatch.setattr(project_service, "create_notification", MagicMock())
    monkeypatch.setattr(project_service, "log_operation", MagicMock())
    project_service.decide_resource_request(db, 10, 2, ProjectDecision(note="审批意见"), SimpleNamespace(id=9), approved)
    assert request.status == ("approved" if approved else "rejected")
    assert project.planned_end == (date(2026, 10, 9) if approved else date(2026, 9, 28))
    assert project.budget_hours == Decimal("16" if approved else "8")
    db.commit.assert_called_once()


def test_workday_count_respects_inclusive_bounds_holidays_and_makeup_days():
    db = MagicMock()
    # Mon 9/28 is a holiday override; Sat 10/3 is a makeup workday.
    db.execute.return_value.all.return_value = [(date(2026, 9, 28), "holiday"), (date(2026, 10, 3), "workday")]
    assert work_calendar_service.count_workdays(db, date(2026, 9, 28), date(2026, 10, 4)) == 5
    with pytest.raises(BusinessException):
        work_calendar_service.count_workdays(db, date(2026, 10, 4), date(2026, 9, 28))


def test_planned_hours_endpoint_uses_eight_hours_per_person(monkeypatch):
    from app.api.v1.work_calendar import estimate_planned_hours
    monkeypatch.setattr(work_calendar_service, "count_workdays", lambda *args: 5)
    result = estimate_planned_hours(TODAY, date(2026, 10, 4), 3, SimpleNamespace(id=7), MagicMock())
    assert result["data"]["planned_hours"] == 120
