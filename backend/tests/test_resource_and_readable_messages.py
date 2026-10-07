"""0930 regression sources; do not execute without the maintainer's approval."""
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.core.exceptions import BusinessException
from app.models.notification import Notification
from app.models.project import Project, ProjectResourceRequest
from app.schemas.project import ProjectResourceRequestCreate, ProjectDecision
from app.services import project_service, notification_service, operation_log_service
from app.services.business_text_service import booking_contexts, readable_booking_notification


@pytest.mark.parametrize("hours", [None, "0", "-0.5", "0.3", "NaN", "Infinity"])
def test_extension_rejects_missing_or_invalid_hours(hours):
    values = {} if hours is None else {"requested_hours": hours}
    with pytest.raises(ValidationError):
        ProjectResourceRequestCreate(requested_planned_end="2026-10-09", reason="项目延期", **values)


def test_extension_positive_half_hours_and_member_only_request_are_valid():
    assert ProjectResourceRequestCreate(requested_planned_end="2026-10-09", requested_hours="4.5", reason="项目延期").requested_hours == Decimal("4.5")
    assert ProjectResourceRequestCreate(add_member_ids=[2], reason="添加成员").requested_hours == 0


def resource_fixture(status="pending", requester=7):
    project = Project(id=10, name="交付项目", manager_id=7, department_id=1,
                      planned_start=date(2026, 9, 1), planned_end=date(2026, 9, 28),
                      budget_hours=Decimal("80"), status="running", approval_status="approved")
    request = ProjectResourceRequest(id=5, project_id=10, requested_by=requester, status=status,
                                     requested_hours=Decimal("16"), requested_planned_end=date(2026, 10, 9),
                                     add_member_ids=[], remove_member_ids=[], reason="延期交付")
    db = MagicMock()
    db.scalar.side_effect = [project, request]
    db.get.return_value = SimpleNamespace(manager_id=9)
    return db, project, request


def test_withdraw_only_updates_request_and_notifies_reviewer(monkeypatch):
    db, project, request = resource_fixture()
    notify, audit = MagicMock(), MagicMock()
    monkeypatch.setattr(project_service, "create_notification", notify)
    monkeypatch.setattr(project_service, "log_operation", audit)
    user = SimpleNamespace(id=7, name="项目经理")
    result = project_service.withdraw_resource_request(db, 10, 5, user)
    assert result.status == "withdrawn"
    assert result.reviewed_by is None  # Withdrawal is not an approval decision.
    assert project.budget_hours == Decimal("80")
    assert project.planned_end == date(2026, 9, 28)
    assert notify.call_args.args[1:3] == (9, "project_resources_withdrawn")
    assert audit.call_args.kwargs["action"] == "withdraw_resources"
    for call in db.scalar.call_args_list:
        assert "FOR UPDATE" in str(call.args[0])
    db.add.assert_not_called()
    db.commit.assert_called_once()


@pytest.mark.parametrize("status,requester,code", [("approved",7,400), ("rejected",7,400), ("withdrawn",7,400), ("pending",8,403)])
def test_withdraw_rejects_reviewed_or_other_users_requests(status, requester, code):
    db, project, request = resource_fixture(status, requester)
    with pytest.raises(BusinessException) as error:
        project_service.withdraw_resource_request(db, 10, 5, SimpleNamespace(id=7, name="经理"))
    assert error.value.status_code == code
    assert request.status == status
    db.commit.assert_not_called()


@pytest.mark.parametrize("approved", [True, False])
def test_reviewer_cannot_act_on_withdrawn_request(monkeypatch, approved):
    db, project, request = resource_fixture("withdrawn")
    monkeypatch.setattr(project_service, "_assert_department_manager", lambda *args: None)
    with pytest.raises(BusinessException):
        project_service.decide_resource_request(db, 10, 5, ProjectDecision(note="意见"), SimpleNamespace(id=9), approved)
    assert request.status == "withdrawn"
    assert project.budget_hours == Decimal("80")
    db.commit.assert_not_called()


def test_resource_names_are_batched_and_missing_members_are_explicit():
    request = ProjectResourceRequest(id=5, requested_hours=Decimal("8"), add_member_ids=[2, 3], remove_member_ids=[4])
    db = MagicMock()
    db.execute.return_value.all.return_value = [(2,"张三","001"), (4,"李四","003")]
    details = project_service._resource_member_details(db, [request])[5]
    assert details["add_members"][0]["name"] == "张三"
    assert details["add_members"][1]["name"] == "原成员资料已不存在"
    summary = project_service._resource_request_summary(request, details)
    assert "新增 2 名成员" in summary and "张三（001）" in summary
    assert "移除 1 名成员：李四（003）" in summary
    db.execute.assert_called_once()


@pytest.mark.parametrize("event,outcome", [("schedule_confirmed","已确认"), ("schedule_rejected","已拒绝"), ("schedule_withdrawn","已撤回预约"), ("schedule_rejected_due_to_conflict","因时段冲突自动关闭"), ("schedule_auto_cancelled","已自动取消")])
def test_booking_text_identifies_person_project_task_and_outcome(event, outcome):
    context = "被预约人：张三（工号 001）；项目：交付项目；任务：联调。"
    text = readable_booking_notification(event, "预约 #85 已处理，原因：会议占用。", context)
    assert all(part in text for part in ("张三", "交付项目", "联调", outcome, "会议占用"))
    assert "#85" not in text


def test_booking_context_and_legacy_display_do_not_invent_historical_dates():
    db = MagicMock()
    db.execute.return_value.all.return_value = [(85,"张三","001","交付项目","联调",datetime(2026,9,30,13),datetime(2026,9,30,14))]
    assert "2026-09-30 13:00" in booking_contexts(db, {85})[85]
    assert "2026-09-30" not in booking_contexts(db, {85}, include_time=False)[85]


def test_legacy_notifications_enrich_read_response_without_writes(monkeypatch):
    db = MagicMock()
    row = Notification(id=1, recipient_id=7, event_type="schedule_confirmed", title="人力预约已确认", content="预约 #85 已确认。", related_type="schedule", related_id="85")
    db.scalar.return_value = 1
    db.scalars.return_value.all.return_value = [row]
    monkeypatch.setattr(notification_service, "booking_contexts", lambda *args, **kwargs: {85: "被预约人：张三；项目：交付项目；任务：联调。"})
    result = notification_service.list_notifications(db, 7, 1, 20, None)
    assert "张三" in result["items"][0]["content"]
    assert "#85" not in result["items"][0]["content"]
    assert row.content == "预约 #85 已确认。"
    db.commit.assert_not_called()
    db.add.assert_not_called()


def test_audit_summaries_preserve_snapshot_names_and_translate_statuses():
    labels = {"user:7":"新姓名", "project:10":"交付项目", "task:3":"联调"}
    before = {"user_id":7,"project_id":10,"task_id":3,"status":"pending", "_display_labels":{"user:7":"张三（工号 001）"}}
    after = {**before,"status":"confirmed"}
    text = operation_log_service.describe_change("confirm", "schedule_booking", 85, before, after, labels)
    assert all(part in text for part in ("张三", "交付项目", "联调", "待本人确认 → 已确认"))
    assert "#85" not in text and "新姓名" not in text and "_display_labels" not in text
    resource = operation_log_service.describe_change("request_resources", "project_resource_request", 83, None,
        {"project_id":10,"add_member_ids":[7],"requested_hours":8}, labels)
    assert "新增成员=新姓名" in resource and "交付项目" in resource and "#83" not in resource


def test_missing_log_references_have_explicit_fallback_not_numeric_ids():
    text = operation_log_service.describe_change("delete", "project", 83, None, None)
    assert "资料已删除" in text and "#83" not in text


def test_new_log_persists_readable_names_in_existing_json_only(monkeypatch):
    db = MagicMock()
    labels = {"user:7":"张三（工号 001）", "project:10":"交付项目"}
    monkeypatch.setattr(operation_log_service, "load_reference_labels", lambda *args: labels)
    source = {"project_id":10,"add_member_ids":[7],"status":"pending"}
    operation_log_service.log_operation(db, operator_id=7, module="project", action="request_resources",
                                       object_type="project_resource_request", object_id=83, after_data=source)
    stored = db.add.call_args.args[0]
    assert stored.after_data["_display_labels"] == labels
    assert stored.object_id == "83"  # Technical audit identity is not destroyed.
    assert "_display_labels" not in source
    db.commit.assert_not_called()  # Audit joins the surrounding business transaction.


def test_new_notification_saves_event_context_and_ignores_later_lookup_changes(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(notification_service.settings, "smtp_enabled", False)
    monkeypatch.setattr(notification_service, "booking_contexts", lambda *args, **kwargs: {85: "被预约人：张三；项目：交付项目；任务：联调。预约时间：2026-09-30 13:00 至 14:00。"})
    row = notification_service.create_notification(db, 7, "schedule_confirmed", "人力预约已确认", "预约 #85 已确认。", related_type="schedule", related_id=85)
    snapshot = row.content
    assert "张三" in snapshot and "#85" not in snapshot
    db.scalar.return_value = 1
    db.scalars.return_value.all.return_value = [row]
    lookup = MagicMock(return_value={85:"被预约人：改名后的人员；项目：另一个名称；任务：已改期任务。"})
    monkeypatch.setattr(notification_service, "booking_contexts", lookup)
    assert notification_service.list_notifications(db, 7, 1, 20, None)["items"][0]["content"] == snapshot
    assert lookup.call_args.args[1] == set()
