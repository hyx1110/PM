"""Project plan-change regression sources. Not executed during this delivery."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import BusinessException
from app.models.project import Project, ProjectResourceRequest
from app.schemas.project import ProjectDecision, ProjectResourceRequestCreate
from app.services import project_service


@pytest.fixture
def context(monkeypatch):
    project = Project(id=10, name="计划调整项目", manager_id=7, department_id=1,
                      approval_status="approved", status="running", is_deleted=False,
                      planned_start=date(2099, 9, 1), planned_end=date(2099, 9, 30),
                      budget_hours=Decimal("80"))
    db = MagicMock()
    db.scalar.return_value = None
    db.scalars.return_value.all.return_value = []
    monkeypatch.setattr(project_service, "assert_project_owner_for_resource_request", lambda *args: project)
    monkeypatch.setattr(project_service, "get_department_manager", lambda *args: SimpleNamespace(id=9))
    monkeypatch.setattr(project_service, "_assert_department_manager", lambda *args: None)
    monkeypatch.setattr(project_service, "_validate_initial_project_members", lambda *args: [])
    monkeypatch.setattr(project_service, "create_notification", MagicMock())
    monkeypatch.setattr(project_service, "log_operation", MagicMock())
    return db, project


@pytest.mark.parametrize("dates", [
    {"requested_planned_start": "2099-08-31"},
    {"requested_planned_start": "2099-09-02"},
    {"requested_planned_end": "2099-09-29"},
    {"requested_planned_start": "2099-09-02", "requested_planned_end": "2099-09-29"},
])
def test_date_only_application_preserves_live_plan_until_approval(context, dates):
    db, project = context
    request = project_service.create_resource_request(
        db, project.id, ProjectResourceRequestCreate(**dates, reason="调整项目周期"), SimpleNamespace(id=7))
    assert request.status == "pending"
    assert request.requested_hours == 0
    assert request.original_planned_start == project.planned_start == date(2099, 9, 1)
    assert request.original_planned_end == project.planned_end == date(2099, 9, 30)
    assert project.budget_hours == Decimal("80")
    db.commit.assert_called_once()


def test_extension_still_requires_positive_additional_hours(context):
    db, project = context
    with pytest.raises(BusinessException) as error:
        project_service.create_resource_request(db, project.id,
            ProjectResourceRequestCreate(requested_planned_end="2099-10-02", reason="提前申请延期"), SimpleNamespace(id=7))
    assert "正数追加工时" in error.value.message
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_unchanged_dates_are_not_a_resource_change(context):
    db, project = context
    with pytest.raises(BusinessException) as error:
        project_service.create_resource_request(db, project.id,
            ProjectResourceRequestCreate(requested_planned_start=project.planned_start,
                                         requested_planned_end=project.planned_end, reason="没有变化"), SimpleNamespace(id=7))
    assert "相同" in error.value.message
    db.add.assert_not_called()


@pytest.mark.parametrize("approved", [True, False])
def test_decision_applies_both_dates_only_when_approved(context, approved):
    db, project = context
    request = ProjectResourceRequest(id=2, project_id=10, requested_by=7, status="pending",
        original_planned_start=project.planned_start, original_planned_end=project.planned_end,
        requested_planned_start=date(2099, 9, 2), requested_planned_end=date(2099, 9, 29),
        requested_hours=Decimal("0"), add_member_ids=[], remove_member_ids=[], reason="调整周期")
    db.scalar.side_effect = [project, request, None, None]
    project_service.decide_resource_request(db, 10, 2, ProjectDecision(note="审核结果"), SimpleNamespace(id=9), approved)
    assert project.planned_start == date(2099, 9, 2 if approved else 1)
    assert project.planned_end == date(2099, 9, 29 if approved else 30)
    assert project.budget_hours == Decimal("80")
    assert request.status == ("approved" if approved else "rejected")
    db.commit.assert_called_once()


@pytest.mark.parametrize("field", ["planned_start", "planned_end"])
def test_approval_rejects_stale_date_snapshot(context, field):
    db, project = context
    request = ProjectResourceRequest(id=2, project_id=10, requested_by=7, status="pending",
        original_planned_start=project.planned_start, original_planned_end=project.planned_end,
        requested_planned_start=date(2099, 8, 30), requested_hours=Decimal("0"),
        add_member_ids=[], remove_member_ids=[], reason="调整周期")
    setattr(project, field, date(2099, 9, 5))
    db.scalar.side_effect = [project, request]
    with pytest.raises(BusinessException) as error:
        project_service.decide_resource_request(db, 10, 2, ProjectDecision(), SimpleNamespace(id=9), True)
    assert "计划日期已变化" in error.value.message
    assert request.status == "pending"
    db.commit.assert_not_called()


@pytest.mark.parametrize("stage", ["submit", "approve"])
@pytest.mark.parametrize("blocking,description", [([123], "任务"), ([None, 456], "预约")])
def test_plan_bounds_rechecked_at_submission_and_approval(context, stage, blocking, description):
    db, project = context
    request = ProjectResourceRequest(id=2, project_id=10, requested_by=7, status="pending",
        original_planned_start=project.planned_start, original_planned_end=project.planned_end,
        requested_planned_start=date(2099, 9, 5), requested_hours=Decimal("0"),
        add_member_ids=[], remove_member_ids=[], reason="缩短周期")
    db.scalar.side_effect = ([project, request] if stage == "approve" else []) + blocking
    with pytest.raises(BusinessException) as error:
        if stage == "submit":
            project_service.create_resource_request(db, 10,
                ProjectResourceRequestCreate(requested_planned_start="2099-09-05", reason="缩短周期"), SimpleNamespace(id=7))
        else:
            project_service.decide_resource_request(db, 10, 2, ProjectDecision(), SimpleNamespace(id=9), True)
    assert description in error.value.message
    assert project.planned_start == date(2099, 9, 1)
    assert project.budget_hours == Decimal("80")
    assert request.status == "pending"
    db.commit.assert_not_called()


def test_resource_summary_names_both_date_changes():
    request = ProjectResourceRequest(requested_hours=Decimal("0"), add_member_ids=[], remove_member_ids=[],
        original_planned_start=date(2099, 9, 1), requested_planned_start=date(2099, 9, 2),
        original_planned_end=date(2099, 9, 30), requested_planned_end=date(2099, 9, 29))
    summary = project_service._resource_request_summary(request)
    assert "计划开始日期从 2099-09-01 调整为 2099-09-02" in summary
    assert "计划结束日期从 2099-09-30 调整为 2099-09-29" in summary
