"""Today's personal feed: query/serialization regression sources (not executed)."""
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.dashboard_service import _my_day


def test_my_day_queries_only_authenticated_user_and_beijing_calendar_window():
    db = MagicMock()
    db.execute.return_value.all.return_value = []
    db.scalars.return_value.all.return_value = []
    now = datetime(2026, 9, 30, 10, 15)
    assert _my_day(db, 7, now) == {"date": date(2026, 9, 30), "items": []}

    booking_sql = str(db.execute.call_args.args[0].compile(compile_kwargs={"literal_binds": True}))
    personal_sql = str(db.scalars.call_args.args[0].compile(compile_kwargs={"literal_binds": True}))
    assert "schedule_bookings.user_id = 7" in booking_sql
    assert "personal_time_blocks.user_id = 7" in personal_sql
    for sql in (booking_sql, personal_sql):
        # Half-open overlap: exclude arrangements ending exactly at midnight,
        # and those starting at the next day's midnight. Include cross-day ones.
        assert "start_time < '2026-10-01 00:00:00'" in sql
        assert "end_time > '2026-09-30 00:00:00'" in sql
        assert "LIMIT" not in sql.upper()
    for status in ("confirmed", "running", "completed", "pending", "changed"):
        assert f"'{status}'" in booking_sql
    for excluded in ("cancelled", "rejected", "draft"):
        assert f"'{excluded}'" not in booking_sql
    assert "end_time > '2026-09-30 10:15:00'" in booking_sql
    assert "projects.is_deleted IS false" in booking_sql
    assert "tasks.is_deleted IS false" in booking_sql
    assert "personal_time_blocks.status = 'active'" in personal_sql
    assert "'withdrawn'" not in personal_sql
    db.commit.assert_not_called()
    db.flush.assert_not_called()
    db.add.assert_not_called()


def test_all_overlapping_invitations_and_personal_time_remain_separate():
    db = MagicMock()
    now = datetime(2026, 9, 30, 10)
    start, end = datetime(2026, 9, 30, 13), datetime(2026, 9, 30, 14)
    pending = SimpleNamespace(id=1, start_time=start, end_time=end, status="pending", remark="项目一邀请")
    changed = SimpleNamespace(id=2, start_time=start, end_time=end, status="changed", remark=None)
    completed = SimpleNamespace(id=3, start_time=datetime(2026, 9, 30, 8, 30), end_time=datetime(2026, 9, 30, 9), status="completed", remark=None)
    block = SimpleNamespace(id=1, start_time=datetime(2026, 9, 29, 22), end_time=datetime(2026, 9, 30, 8), status="active", time_type="leave", remark="跨天休假")
    db.execute.return_value.all.return_value = [(changed, "项目二", "任务二"), (pending, "项目一", "任务一"), (completed, "项目三", "任务三")]
    db.scalars.return_value.all.return_value = [block]

    data = _my_day(db, 7, now)
    assert [item["id"] for item in data["items"]] == ["personal-1", "booking-3", "booking-1", "booking-2"]
    assert [item["status"] for item in data["items"]] == ["active", "completed", "pending", "changed"]
    assert data["items"][0]["title"] == "休假"
    # Keep raw dates for the detail drawer; clipping to today's 00:00/24:00 is
    # presentation only and must not overwrite stored or returned intervals.
    assert data["items"][0]["start_time"] == block.start_time
    assert data["items"][2]["project_name"] == "项目一"
    assert all("planned_hours" not in item for item in data["items"])
    assert db.execute.call_count == db.scalars.call_count == 1
