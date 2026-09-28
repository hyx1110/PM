"""Regression source only; uses no live database, service or mail server."""
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.core.exceptions import BusinessException
from app.models.overtime import OvertimeRequest
from app.schemas.overtime import OvertimeCreate, OvertimeDecision
from app.services import overtime_service as service


def dt(hour, minute=0):
    return datetime(2026, 9, 28, hour, minute)


@pytest.mark.parametrize(("start", "end", "workday", "expected"), [
    (dt(18), dt(20), True, Decimal("2")),
    (dt(12), dt(13), True, Decimal("1")),
    (dt(8), dt(8, 30), True, Decimal("0.5")),
    (dt(17, 30), dt(18), True, Decimal("0.5")),
    (dt(9), dt(12), False, Decimal("3")),
    (dt(23, 30), dt(0) + timedelta(days=1), True, Decimal("0.5")),
])
def test_only_nonworking_capacity(monkeypatch, start, end, workday, expected):
    monkeypatch.setattr(service, "is_workday", lambda db, day: workday)
    assert service.calculate_overtime_hours(object(), start, end) == expected


@pytest.mark.parametrize(("start", "end"), [
    (dt(8), dt(9)), (dt(11, 30), dt(12, 30)), (dt(12, 30), dt(13, 30)),
    (dt(17), dt(18)), (dt(18), dt(17)), (dt(18, 10), dt(19)),
    (dt(23), dt(1) + timedelta(days=1)),
])
def test_invalid_time_windows(monkeypatch, start, end):
    monkeypatch.setattr(service, "is_workday", lambda db, day: True)
    with pytest.raises(BusinessException):
        service.calculate_overtime_hours(object(), start, end)


def test_payload_normalizes_beijing_and_trims_reason():
    payload = OvertimeCreate(task_id=1, start_time="2026-09-28T10:00:00Z",
        end_time="2026-09-28T12:00:00Z", reason="  发布支持  ")
    assert payload.start_time == dt(18)
    assert payload.end_time == dt(20)
    assert payload.reason == "发布支持"


def test_midnight_is_an_exclusive_day_boundary():
    payload = OvertimeCreate(task_id=1, start_time=dt(23, 30),
        end_time=dt(0)+timedelta(days=1), reason="夜间支持")
    assert payload.end_time.date() > payload.start_time.date()


def test_blank_reason_rejected():
    with pytest.raises(ValidationError):
        OvertimeCreate(task_id=1, start_time=dt(18), end_time=dt(20), reason="  ")


@pytest.mark.parametrize(("approver_id", "actor_id"), [(2, 3), (1, 1)])
def test_cannot_approve_as_stranger_or_self(monkeypatch, approver_id, actor_id):
    item = SimpleNamespace(user_id=1, approver_id=approver_id, status="pending")
    monkeypatch.setattr(service, "_locked_request", lambda *args: (object(), object(), item))
    with pytest.raises(BusinessException) as error:
        service.decide_request(MagicMock(), 1, OvertimeDecision(), SimpleNamespace(id=actor_id), True)
    assert error.value.status_code == 403


@pytest.mark.parametrize(("applicant_id", "expected_approver"), [(1, 2), (2, 3)])
def test_member_and_manager_follow_different_approvers(monkeypatch, applicant_id, expected_approver):
    from app.services import project_service
    db = MagicMock()
    project = SimpleNamespace(id=10, name="项目", manager_id=2, department_id=5)
    task = SimpleNamespace(id=20, name="任务", planned_start=dt(0).date(), planned_end=dt(0).date())
    monkeypatch.setattr(service, "_lock_context", lambda *args: (project, task))
    monkeypatch.setattr(service, "_validate_context", lambda *args: None)
    monkeypatch.setattr(service, "_check_conflicts", lambda *args: None)
    monkeypatch.setattr(service, "calculate_overtime_hours", lambda *args: Decimal("2"))
    monkeypatch.setattr(service, "beijing_now", lambda: dt(12))
    monkeypatch.setattr(project_service, "get_department_manager", lambda *args: SimpleNamespace(id=3))
    monkeypatch.setattr(service, "create_notification", MagicMock())
    monkeypatch.setattr(service, "log_operation", MagicMock())
    monkeypatch.setattr(service, "request_detail", lambda *args: {})
    db.get.return_value = SimpleNamespace(is_deleted=False, status="active")
    payload = OvertimeCreate(task_id=20, start_time=dt(18), end_time=dt(20), reason="交付")
    service.create_request(db, payload, SimpleNamespace(id=applicant_id, name="申请人"))
    created = db.add.call_args.args[0]
    assert created.approver_id == expected_approver
    assert created.status == "pending"
    db.commit.assert_called_once()


def approved_item():
    return OvertimeRequest(id=1, project_id=10, task_id=20, user_id=1, approver_id=2,
        start_time=dt(18), end_time=dt(20), hours=Decimal("2"), reason="交付", status="approved")


@pytest.mark.parametrize("hours", [Decimal("2.5"), Decimal("0.3"), Decimal("0"), Decimal("-1")])
def test_execution_cannot_exceed_approved_hours_or_use_fraction(monkeypatch, hours):
    db = MagicMock()
    db.scalar.side_effect = [approved_item(), None]
    monkeypatch.setattr(service, "beijing_now", lambda: dt(21))
    with pytest.raises(BusinessException):
        service.resolve_execution_hours(db, 1, 20, 1, dt(0).date(), dt(0).date(), hours)


def test_one_request_cannot_be_recorded_twice(monkeypatch):
    db = MagicMock()
    db.scalar.side_effect = [approved_item(), 99]
    monkeypatch.setattr(service, "beijing_now", lambda: dt(21))
    with pytest.raises(BusinessException) as error:
        service.resolve_execution_hours(db, 1, 20, 1, dt(0).date(), dt(0).date(), Decimal("1"))
    assert error.value.status_code == 409


def test_actual_hours_resolve_only_after_overtime_ends(monkeypatch):
    db = MagicMock()
    db.scalar.side_effect = [approved_item(), None]
    monkeypatch.setattr(service, "beijing_now", lambda: dt(21))
    assert service.resolve_execution_hours(db, 1, 20, 1, dt(0).date(), dt(0).date(), None) == Decimal("2")
    db.scalar.side_effect = [approved_item()]
    monkeypatch.setattr(service, "beijing_now", lambda: dt(19))
    with pytest.raises(BusinessException):
        service.resolve_execution_hours(db, 1, 20, 1, dt(0).date(), dt(0).date(), Decimal("1"))


def test_other_person_or_withdrawn_request_not_usable(monkeypatch):
    db = MagicMock()
    item = approved_item()
    db.scalar.return_value = item
    with pytest.raises(BusinessException):
        service.resolve_execution_hours(db, 1, 20, 9, dt(0).date(), dt(0).date(), Decimal("1"))
    item.status = "withdrawn"
    with pytest.raises(BusinessException):
        service.resolve_execution_hours(db, 1, 20, 1, dt(0).date(), dt(0).date(), Decimal("1"))
