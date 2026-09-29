"""Homepage relationship-scope regression sources; do not require a live database."""
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services import dashboard_service, visibility_service


@pytest.mark.parametrize("roles", [
    {"project_member"}, {"project_manager"}, {"functional_manager"},
    {"department_manager"}, {"super_admin"},
    {"super_admin", "department_manager", "project_manager", "project_member"},
])
def test_every_homepage_role_uses_self_and_all_descendants(monkeypatch, roles):
    monkeypatch.setattr(visibility_service, "get_role_codes", lambda *args: roles)
    monkeypatch.setattr(visibility_service, "descendant_user_ids", lambda *args: {2, 3, 4})
    project_lookup = MagicMock(return_value={11, 12, 13})
    monkeypatch.setattr(visibility_service, "related_project_ids", project_lookup)
    db = MagicMock()
    result = visibility_service.dashboard_visibility_scopes(db, SimpleNamespace(id=1))
    assert result == (roles, {11, 12, 13}, {1, 2, 3, 4})
    project_lookup.assert_called_once_with(db, {1, 2, 3, 4})


def test_administrator_without_relationships_gets_empty_scope_not_global(monkeypatch):
    monkeypatch.setattr(visibility_service, "get_role_codes", lambda *args: {"super_admin"})
    monkeypatch.setattr(visibility_service, "descendant_user_ids", lambda *args: set())
    monkeypatch.setattr(visibility_service, "related_project_ids", lambda *args: set())
    assert visibility_service.dashboard_visibility_scopes(MagicMock(), SimpleNamespace(id=1)) == ({"super_admin"}, set(), {1})
    # The homepage restriction must not remove global administration privileges.
    assert visibility_service.has_global_project_access(MagicMock(), SimpleNamespace(id=1)) is True


def test_all_reporting_levels_and_cycles_are_handled():
    db = MagicMock()
    batches = [{2, 3}, {4}, {5, 1}, {2}]
    db.scalars.side_effect = [SimpleNamespace(all=lambda batch=batch: batch) for batch in batches]
    assert visibility_service.descendant_user_ids(db, 1) == {2, 3, 4, 5}
    assert db.scalars.call_count == 4
    for call in db.scalars.call_args_list:
        sql = str(call.args[0])
        assert "users.supervisor_id IN" in sql
        assert "users.is_deleted IS false" in sql


def test_related_projects_union_owner_active_membership_and_task_assignments():
    db = MagicMock()
    db.scalars.side_effect = [
        SimpleNamespace(all=lambda: [10, 11]),
        SimpleNamespace(all=lambda: [11, 12]),
        SimpleNamespace(all=lambda: [13]),
    ]
    assert visibility_service.related_project_ids(db, {1, 2}) == {10, 11, 12, 13}
    statements = [str(call.args[0]) for call in db.scalars.call_args_list]
    assert "projects.manager_id IN" in statements[0]
    assert "project_members.left_at IS NULL" in statements[1]
    assert "task_assignees.user_id IN" in statements[2]
    assert all("projects.is_deleted IS false" in sql for sql in statements)


def result_rows(rows=(), one=None):
    result = MagicMock()
    result.all.return_value = list(rows)
    result.one.return_value = one
    return result


@pytest.mark.parametrize("project_count", [0, 7, 12])
def test_workbench_does_not_truncate_projects_at_five(monkeypatch, project_count):
    now = datetime(2026, 9, 29, 12)
    project_ids = set(range(1, project_count + 1))
    projects = [
        (SimpleNamespace(id=id, code=f"P-{id}", name=f"项目 {id}",
                         planned_start=date(2026, 9, 1), planned_end=date(2026, 10, 30),
                         actual_start=None, actual_end=None, status="not_started"), "经理")
        for id in sorted(project_ids)
    ]
    monkeypatch.setattr(dashboard_service, "beijing_now", lambda: now)
    monkeypatch.setattr(dashboard_service, "dashboard_visibility_scopes", lambda *args: ({"super_admin"}, project_ids, {1}))
    monkeypatch.setattr(dashboard_service, "_pending_items", lambda *args: [])
    monkeypatch.setattr(dashboard_service, "_my_day", lambda *args: {"date": now.date(), "items": []})
    db = MagicMock()
    db.scalar.return_value = 0
    db.scalars.return_value.all.return_value = []
    db.execute.side_effect = [
        result_rows(projects),  # all scoped projects
        result_rows(),         # timeline tasks
        result_rows(),         # my tasks
        result_rows(),         # execution comparisons
        result_rows(),         # risks
        result_rows(),         # planned-hours trend
        result_rows(),         # actual-hours trend
        result_rows(one=(0, 0)),  # total/completed tasks
        result_rows(),         # overrun tasks
        result_rows(one=(0, 0)),  # pending bookings
        result_rows(one=(0, 0)),  # personal pending tasks
    ]
    data = dashboard_service.dashboard_workbench(db, SimpleNamespace(id=1))
    assert len(data["timeline"]) == len(data["project_health"]) == project_count
    assert {project["id"] for project in data["timeline"]} == project_ids
    assert data["scope_label"] == "本人负责、参与或执行的项目"
    project_query = str(db.execute.call_args_list[0].args[0].compile(compile_kwargs={"literal_binds": True}))
    assert "LIMIT" not in project_query.upper()
    assert "projects.id IN" in project_query
    assert "projects.approval_status = 'approved'" in project_query
    if not project_count:
        assert "projects.id IN (-1)" in project_query
