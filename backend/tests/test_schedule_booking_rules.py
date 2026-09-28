"""Regression source for booking quota/withdrawal; no live database or services.

These tests are supplied for the operator to run, not executed during delivery.
"""
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import BusinessException
from app.models.schedule import ScheduleBooking
from app.repositories.project_repository import booked_schedule_predicate
from app.schemas.schedule import ScheduleBatchCreate, ScheduleCreate, ScheduleDecision
from app.services import schedule_service as service


NOW = datetime(2026, 9, 28, 8)
START = datetime(2026, 9, 28, 9)
END = datetime(2026, 9, 28, 10)


def booking(status="confirmed"):
    return ScheduleBooking(id=1, project_id=10, task_id=20, user_id=2,
        created_by=3, start_time=START, end_time=END, status=status,
        planned_hours=Decimal("1"), version=1)


def configure_context(monkeypatch, db):
    project = SimpleNamespace(id=10, budget_hours=Decimal("10"), manager_id=3,
        status="running", is_deleted=False)
    monkeypatch.setattr(service, "beijing_now", lambda: NOW)
    monkeypatch.setattr(service, "assert_project_booking_access", lambda *args: project)
    monkeypatch.setattr(service, "_validate_relations", MagicMock())
    monkeypatch.setattr(service, "calculate_work_hours", lambda *args: Decimal("1"))
    monkeypatch.setattr(service, "_lock_users", MagicMock())
    monkeypatch.setattr(service, "_raise_conflicts", MagicMock())
    monkeypatch.setattr(service, "_collect_conflicts", lambda *args: [])
    monkeypatch.setattr(service, "create_notification", MagicMock())
    monkeypatch.setattr(service, "log_operation", MagicMock())
    db.get.return_value = project
    return project


def test_quota_predicate_includes_unexpired_proposals_but_not_failed_bookings(monkeypatch):
    from app.repositories import project_repository
    monkeypatch.setattr(project_repository, "beijing_now", lambda: NOW)
    params = booked_schedule_predicate().compile().params.values()
    status_groups = [set(value) for value in params if isinstance(value, (list, tuple, set))]
    assert {"pending", "changed"} in status_groups
    assert {"confirmed", "running", "completed"} in status_groups
    assert NOW in params
    assert not {"draft", "rejected", "withdrawn", "cancelled"} & set.union(*status_groups)


def test_pending_hours_block_second_submission_before_insert(monkeypatch):
    db = MagicMock()
    configure_context(monkeypatch, db)
    monkeypatch.setattr(service, "_assert_project_capacity", MagicMock())
    db.get.return_value = SimpleNamespace(id=20, is_deleted=False, estimated_hours=Decimal("1"))
    # Existing pending 1h is returned by the reserved-quota predicate.
    db.scalars.return_value.all.return_value = [Decimal("1")]
    payload = ScheduleCreate(project_id=10, task_id=20, user_id=2,
        start_time=START, end_time=END)
    with pytest.raises(BusinessException, match="待确认预约也占用额度"):
        service.create_schedule(db, payload, SimpleNamespace(id=3))
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_batch_checks_total_people_hours_not_per_person(monkeypatch):
    db = MagicMock()
    project = configure_context(monkeypatch, db)
    project_check = MagicMock()
    monkeypatch.setattr(service, "_assert_project_capacity", project_check)
    db.get.return_value = SimpleNamespace(id=20, is_deleted=False, estimated_hours=Decimal("1"))
    db.scalars.return_value.all.return_value = []
    payload = ScheduleBatchCreate(project_id=10, task_id=20, user_ids=[2, 4],
        start_time=START, end_time=END)
    with pytest.raises(BusinessException, match="本次需要 2 小时"):
        service.batch_create_schedules(db, payload, SimpleNamespace(id=3))
    project_check.assert_called_once_with(db, project, Decimal("2"))
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_two_half_hour_bookings_fit_shared_one_hour_task(monkeypatch):
    db = MagicMock()
    configure_context(monkeypatch, db)
    monkeypatch.setattr(service, "calculate_work_hours", lambda *args: Decimal("0.5"))
    db.get.return_value = SimpleNamespace(id=20, is_deleted=False, estimated_hours=Decimal("1"))
    db.scalars.return_value.all.return_value = []
    payload = ScheduleBatchCreate(project_id=10, task_id=20, user_ids=[2, 4],
        start_time=START, end_time=datetime(2026, 9, 28, 9, 30))
    result = service.batch_create_schedules(db, payload, SimpleNamespace(id=3))
    assert result["created"] == 2
    rows = [call.args[0] for call in db.add.call_args_list]
    assert sum(row.planned_hours for row in rows) == Decimal("1")
    assert all(row.status == "pending" for row in rows)
    db.commit.assert_called_once()


def test_task_capacity_reads_current_rows_and_excludes_edited_booking():
    db = MagicMock()
    db.get.return_value = SimpleNamespace(is_deleted=False, estimated_hours=Decimal("1"))
    db.scalars.return_value.all.return_value = []
    service._assert_task_capacity(db, 20, Decimal("1"), 7)
    statement = db.scalars.call_args.args[0]
    sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert "FOR UPDATE" in sql
    assert "schedule_bookings.id != 7" in sql
    assert "'pending'" in sql and "'changed'" in sql


def test_project_capacity_includes_pending_and_reads_current_rows():
    db = MagicMock()
    db.scalars.return_value.all.return_value = [Decimal("1")]
    project = SimpleNamespace(id=10, budget_hours=Decimal("1"))
    with pytest.raises(BusinessException, match="项目剩余工时不足"):
        service._assert_project_capacity(db, project, Decimal("0.5"))
    assert "FOR UPDATE" in str(db.scalars.call_args.args[0])


def test_confirmation_does_not_count_its_own_reserved_quota_twice(monkeypatch):
    db = MagicMock()
    project = configure_context(monkeypatch, db)
    item = booking("pending")
    monkeypatch.setattr(service, "_get_schedule_for_ordered_update", lambda *args: item)
    project_check, task_check = MagicMock(), MagicMock()
    monkeypatch.setattr(service, "_assert_project_capacity", project_check)
    monkeypatch.setattr(service, "_assert_task_capacity", task_check)
    monkeypatch.setattr(service, "_reject_competing_proposals", MagicMock())
    service.confirm_schedule(db, 1, ScheduleDecision(), SimpleNamespace(id=2))
    project_check.assert_called_once_with(db, project, Decimal("1"), 1)
    task_check.assert_called_once_with(db, 20, Decimal("1"), 1)
    assert item.status == "confirmed"


def test_expired_pending_booking_cannot_reacquire_quota_by_confirming(monkeypatch):
    db = MagicMock()
    configure_context(monkeypatch, db)
    item = booking("pending")
    monkeypatch.setattr(service, "beijing_now", lambda: END)
    monkeypatch.setattr(service, "_get_schedule_for_ordered_update", lambda *args: item)
    with pytest.raises(BusinessException, match="预约时段已经结束"):
        service.confirm_schedule(db, 1, ScheduleDecision(), SimpleNamespace(id=2))
    db.commit.assert_not_called()


def test_assignee_can_withdraw_future_confirmed_booking_and_notify_creator(monkeypatch):
    db = MagicMock()
    configure_context(monkeypatch, db)
    item = booking()
    monkeypatch.setattr(service, "_get_schedule_for_ordered_update", lambda *args: item)
    db.scalar.return_value = None  # No related execution record.
    service.withdraw_schedule(db, 1, SimpleNamespace(id=2, name="被预约人"))
    assert item.status == "withdrawn"
    assert item.version == 2
    assert item.rejection_reason == "被预约人撤回已确认预约"
    assert service.create_notification.call_args.args[1] == 3
    db.commit.assert_called_once()


@pytest.mark.parametrize("actor_id", [3, 99])
def test_creator_or_other_user_cannot_withdraw_someone_elses_accepted_booking(monkeypatch, actor_id):
    db = MagicMock()
    configure_context(monkeypatch, db)
    monkeypatch.setattr(service, "_get_schedule_for_ordered_update", lambda *args: booking())
    with pytest.raises(BusinessException) as error:
        service.withdraw_schedule(db, 1, SimpleNamespace(id=actor_id))
    assert error.value.status_code == 403
    db.commit.assert_not_called()


@pytest.mark.parametrize("status", ["running", "completed", "withdrawn", "rejected", "cancelled"])
def test_terminal_or_running_bookings_cannot_be_withdrawn(monkeypatch, status):
    db = MagicMock()
    configure_context(monkeypatch, db)
    monkeypatch.setattr(service, "_get_schedule_for_ordered_update", lambda *args: booking(status))
    with pytest.raises(BusinessException):
        service.withdraw_schedule(db, 1, SimpleNamespace(id=2))
    db.commit.assert_not_called()


def test_started_confirmed_booking_is_protected_even_if_lifecycle_has_not_run(monkeypatch):
    db = MagicMock()
    configure_context(monkeypatch, db)
    monkeypatch.setattr(service, "beijing_now", lambda: START)
    monkeypatch.setattr(service, "_get_schedule_for_ordered_update", lambda *args: booking())
    with pytest.raises(BusinessException, match="已经开始"):
        service.withdraw_schedule(db, 1, SimpleNamespace(id=2))
    db.commit.assert_not_called()


def test_related_ordinary_execution_prevents_confirmed_withdrawal(monkeypatch):
    db = MagicMock()
    configure_context(monkeypatch, db)
    monkeypatch.setattr(service, "_get_schedule_for_ordered_update", lambda *args: booking())
    db.scalar.return_value = 50
    with pytest.raises(BusinessException, match="执行记录"):
        service.withdraw_schedule(db, 1, SimpleNamespace(id=2))
    statement = str(db.scalar.call_args.args[0])
    assert "overtime_request_id IS NULL" in statement
    db.commit.assert_not_called()


def test_creator_can_still_withdraw_pending_booking(monkeypatch):
    db = MagicMock()
    configure_context(monkeypatch, db)
    item = booking("pending")
    monkeypatch.setattr(service, "_get_schedule_for_ordered_update", lambda *args: item)
    service.withdraw_schedule(db, 1, SimpleNamespace(id=3, name="申请人"))
    assert item.status == "withdrawn"
    assert service.create_notification.call_args.args[1] == 2
    db.commit.assert_called_once()
