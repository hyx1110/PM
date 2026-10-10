from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services import dashboard_service


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (datetime(2026, 9, 26, 8, 30), datetime(2026, 9, 26, 8, 30)),
        ("2026-09-26T08:30:00", datetime(2026, 9, 26, 8, 30)),
        (" 2026-09-26 08:30:00 ", datetime(2026, 9, 26, 8, 30)),
        ("2026-09-26T08:30:00+08:00", datetime(2026, 9, 26, 8, 30)),
        ("2026-09-26T00:30:00Z", datetime(2026, 9, 26, 8, 30)),
        ("2026-09-25T20:30:00-04:00", datetime(2026, 9, 26, 8, 30)),
        (
            datetime(2026, 9, 26, 0, 30, tzinfo=timezone.utc),
            datetime(2026, 9, 26, 8, 30),
        ),
        (None, None),
        ("", None),
        ("invalid-timestamp", None),
    ],
)
def test_pending_datetime_normalizes_to_beijing(value, expected):
    assert dashboard_service._pending_datetime(value) == expected


def stub_pending_sources(monkeypatch, *, projects=(), resources=(), bookings=(), tasks=()):
    # Replace all data providers: these tests do not connect to a database.
    monkeypatch.setattr(dashboard_service.task_service, "list_pending_task_approvals", lambda *args: list(tasks))
    monkeypatch.setattr(dashboard_service.overtime_service, "list_requests", lambda *args, **kwargs: {"items": []})
    monkeypatch.setattr(
        dashboard_service.project_service,
        "list_pending_project_approvals",
        lambda db, user: list(projects),
    )
    monkeypatch.setattr(
        dashboard_service.project_service,
        "list_pending_resource_requests",
        lambda db, user: list(resources),
    )
    monkeypatch.setattr(
        dashboard_service.schedule_repository,
        "list_pending_for_user",
        lambda db, user_id, limit: list(bookings),
    )


def test_pending_items_merge_mixed_timestamps_and_keep_overdue_dates(monkeypatch):
    now = datetime(2026, 9, 28, 12)
    project = {
        "id": 1,
        "name": "项目审批",
        "planned_start": "2026-09-28",
        "planned_end": "2026-10-30",
        "created_at": datetime(2026, 9, 28, 9),
    }
    resource = {
        "id": 2,
        "project_id": 1,
        "created_at": "2026-09-26T00:30:00Z",
        "requested_hours": 8,
    }
    booking = {
        "id": 3,
        "project_id": 1,
        "task_id": 4,
        "start_time": datetime(2026, 9, 29, 8, 30),
        "end_time": datetime(2026, 9, 29, 12),
        "planned_hours": 3.5,
        "created_at": datetime(2026, 9, 27, 10),
        "status": "pending",
    }
    expired_booking = {
        **booking,
        "id": 5,
        "start_time": datetime(2026, 9, 27, 8, 30),
        "end_time": datetime(2026, 9, 27, 12),
    }
    stub_pending_sources(
        monkeypatch,
        projects=[project],
        resources=[resource],
        bookings=[booking, expired_booking],
    )

    items = dashboard_service._pending_items(object(), SimpleNamespace(id=9), now)

    assert [item["id"] for item in items] == ["resource-2", "booking-3", "project-1"]
    assert items[0]["created_at"] == datetime(2026, 9, 26, 8, 30)
    assert all(isinstance(item["created_at"], datetime) for item in items)
    assert all(item["created_at"].tzinfo is None for item in items)
    assert [
        item["id"] for item in items
        if item["created_at"] < now - timedelta(hours=24)
    ] == ["resource-2", "booking-3"]
    # Normalization must not change the source service's serialized payload.
    assert resource["created_at"] == "2026-09-26T00:30:00Z"


@pytest.mark.parametrize("created_at", [None, "", "invalid-timestamp"])
def test_missing_or_invalid_pending_time_keeps_item_without_fabricating_date(
    monkeypatch, created_at
):
    now = datetime(2026, 9, 28, 12)
    stub_pending_sources(
        monkeypatch,
        resources=[
            {"id": 1, "project_id": 1, "created_at": created_at},
            {"id": 2, "project_id": 1, "created_at": "2026-09-26T08:30:00"},
        ],
    )

    items = dashboard_service._pending_items(object(), SimpleNamespace(id=9), now)

    assert [item["id"] for item in items] == ["resource-2", "resource-1"]
    assert items[1]["created_at"] is None


def test_empty_pending_items(monkeypatch):
    stub_pending_sources(monkeypatch)
    assert dashboard_service._pending_items(
        object(), SimpleNamespace(id=9), datetime(2026, 9, 28, 12)
    ) == []


def test_parent_task_approval_is_actionable_and_has_full_plan(monkeypatch):
    stub_pending_sources(monkeypatch, tasks=[{
        "id": 12, "project_id": 2, "name": "开发父任务", "project_name": "研发项目",
        "owner_names": ["张三", "李四"], "creator_name": "项目经理",
        "planned_start": "2026-10-09", "planned_end": "2026-10-20", "estimated_hours": 16,
        "description": "完成开发", "remark": "先评审", "submitted_at": "2026-10-08T09:00:00",
    }])
    item = dashboard_service._pending_items(object(), SimpleNamespace(id=8), datetime(2026, 10, 8, 12))[0]
    assert item["type"] == "task_approval" and item["actionable"] is True
    assert item["task_id"] == item["source_id"] == 12
    assert item["created_at"] == datetime(2026, 10, 8, 9)
    assert all(text in item["content"] for text in ("张三、李四", "2026-10-09", "2026-10-20", "16h", "完成开发", "先评审"))


def test_historical_zero_hour_extension_still_shows_old_new_dates_and_reason(monkeypatch):
    stub_pending_sources(monkeypatch, resources=[{
        "id": 12, "project_id": 2, "project_name": "延期项目", "requester_name": "经理",
        "requested_hours": 0, "add_member_ids": [], "remove_member_ids": [],
        "original_planned_end": "2026-09-28", "requested_planned_end": "2026-10-09",
        "reason": "延期交付", "created_at": "2026-09-29T09:00:00",
    }])
    item = dashboard_service._pending_items(object(), SimpleNamespace(id=9), datetime(2026, 9, 29, 12))[0]
    assert item["type"] == "resource_approval"
    assert item["actionable"] is True
    assert "2026-09-28 → 2026-10-09" in item["content"]
    assert "延期交付" in item["content"]


def test_resource_approval_shows_start_and_end_date_changes(monkeypatch):
    stub_pending_sources(monkeypatch, resources=[{
        "id": 12, "project_id": 2, "project_name": "项目", "requester_name": "经理",
        "requested_hours": 0, "add_member_ids": [], "remove_member_ids": [],
        "original_planned_start": "2026-09-01", "requested_planned_start": "2026-09-02",
        "original_planned_end": "2026-09-30", "requested_planned_end": "2026-09-29",
        "reason": "调整周期", "created_at": "2026-09-01T09:00:00",
    }])
    item = dashboard_service._pending_items(object(), SimpleNamespace(id=9), datetime(2026, 9, 1, 12))[0]
    assert "计划开始日期 2026-09-01 → 2026-09-02" in item["content"]
    assert "计划结束日期 2026-09-30 → 2026-09-29" in item["content"]


def test_resource_approval_content_includes_member_counts_names_and_employee_numbers(monkeypatch):
    stub_pending_sources(monkeypatch, resources=[{
        "id": 12, "project_id": 2, "project_name": "交付项目", "requester_name": "经理",
        "requested_hours": 8, "add_member_ids": [2, 3], "remove_member_ids": [4],
        "add_members": [{"id":2,"name":"张三","employee_no":"001"}, {"id":3,"name":"李四","employee_no":"002"}],
        "remove_members": [{"id":4,"name":"王五","employee_no":"003"}],
        "reason":"调整交付人员", "created_at":"2026-09-30T09:00:00",
    }])
    item = dashboard_service._pending_items(object(), SimpleNamespace(id=9), datetime(2026, 9, 30, 12))[0]
    assert all(value in item["content"] for value in ("新增 2 人", "移除 1 人", "张三（001）", "李四（002）", "王五（003）"))


def test_overtime_is_an_approval_with_normalized_time(monkeypatch):
    stub_pending_sources(monkeypatch)
    monkeypatch.setattr(dashboard_service.overtime_service, "list_requests", lambda *args, **kwargs: {"items": [{
        "id": 5, "task_id": 8, "task_name": "交付支持", "project_id": 2, "project_name": "项目",
        "user_name": "成员", "hours": 2, "reason": "夜间发布", "can_review": True,
        "start_time": "2026-09-28T18:00:00", "end_time": "2026-09-28T20:00:00",
        "created_at": "2026-09-28T09:00:00",
    }]})
    result = dashboard_service._pending_items(object(), SimpleNamespace(id=9), datetime(2026, 9, 28, 12))
    assert result[0]["type"] == "overtime_approval"
    assert result[0]["actionable"] is True
    assert result[0]["created_at"] == datetime(2026, 9, 28, 9)
