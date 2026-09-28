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


def stub_pending_sources(monkeypatch, *, projects=(), resources=(), bookings=()):
    # Replace all data providers: these tests do not connect to a database.
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
