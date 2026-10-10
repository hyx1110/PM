"""2026-10-08/09 permission regressions. Source only; not run by the coding agent."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import BusinessException
from app.models.project import Project
from app.schemas.project import ProjectDecision
from app.services import project_service, rbac_service, schedule_service, user_service, visibility_service


def result(values):
    return SimpleNamespace(all=lambda: values)


def sql(statement):
    return str(statement.compile(compile_kwargs={"literal_binds": True}))


def test_manager_sees_system_members_without_any_project_relationship(monkeypatch):
    monkeypatch.setattr(visibility_service, "get_role_codes", lambda *args: {"project_manager"})
    db = MagicMock()
    db.scalars.return_value = result([2, 3, 4])
    assert visibility_service.visible_schedule_user_ids(db, SimpleNamespace(id=1)) == {1, 2, 3, 4}
    db.scalars.assert_called_once()
    query = sql(db.scalars.call_args.args[0])
    assert "roles.code = 'project_member'" in query
    assert "user_roles.user_id = users.id" in query
    assert "roles.id = user_roles.role_id" in query
    assert "users.status = 'active'" in query
    assert "users.is_deleted IS false" in query
    assert "project_members" not in query and "projects" not in query
    # No department restriction or single-role requirement: mixed-role users
    # qualify by having a project_member assignment, regardless of other roles.
    assert "GROUP BY" not in query and "HAVING" not in query
    assert "users.department_id" not in query


def test_manager_does_not_fall_back_to_project_members_or_owners_without_member_role(monkeypatch):
    monkeypatch.setattr(visibility_service, "get_role_codes", lambda *args: {"project_manager"})
    db = MagicMock()
    db.scalars.return_value.all.return_value = []
    assert visibility_service.visible_schedule_user_ids(db, SimpleNamespace(id=1)) == {1}
    db.scalars.assert_called_once()


def test_combined_manager_roles_union_system_members_and_subordinates(monkeypatch):
    monkeypatch.setattr(visibility_service, "get_role_codes", lambda *args: {"project_manager", "functional_manager", "project_member"})
    monkeypatch.setattr(visibility_service, "descendant_user_ids", lambda *args: {8})
    db = MagicMock()
    db.scalars.return_value = result([2, 3])
    assert visibility_service.visible_schedule_user_ids(db, SimpleNamespace(id=1)) == {1, 2, 3, 8}


def test_member_role_changes_are_read_on_each_calendar_request(monkeypatch):
    monkeypatch.setattr(visibility_service, "get_role_codes", lambda *args: {"project_manager"})
    db = MagicMock()
    db.scalars.side_effect = [result([2]), result([2, 3]), result([3])]
    user = SimpleNamespace(id=1)
    assert visibility_service.visible_schedule_user_ids(db, user) == {1, 2}
    assert visibility_service.visible_schedule_user_ids(db, user) == {1, 2, 3}
    assert visibility_service.visible_schedule_user_ids(db, user) == {1, 3}


@pytest.mark.parametrize("role", ["super_admin", "department_manager"])
def test_global_calendar_roles_keep_full_scope(monkeypatch, role):
    monkeypatch.setattr(visibility_service, "get_role_codes", lambda *args: {role, "project_manager"})
    db = MagicMock()
    assert visibility_service.visible_schedule_user_ids(db, SimpleNamespace(id=1)) is None
    db.scalars.assert_not_called()


def test_plain_member_still_only_sees_self(monkeypatch):
    monkeypatch.setattr(visibility_service, "get_role_codes", lambda *args: {"project_member"})
    assert visibility_service.visible_schedule_user_ids(MagicMock(), SimpleNamespace(id=1)) == {1}


def test_functional_manager_without_project_manager_keeps_existing_scope(monkeypatch):
    monkeypatch.setattr(visibility_service, "get_role_codes", lambda *args: {"functional_manager"})
    monkeypatch.setattr(visibility_service, "descendant_user_ids", lambda *args: {8})
    db = MagicMock()
    db.scalars.return_value = result([9])
    assert visibility_service.visible_schedule_user_ids(db, SimpleNamespace(id=1)) == {1, 8, 9}
    query = sql(db.scalars.call_args.args[0])
    assert "project_members" in query and "projects.manager_id = 1" in query
    assert "roles.code" not in query


def test_wider_calendar_scope_does_not_allow_booking_for_other_project(monkeypatch):
    db = MagicMock()
    db.scalar.return_value = Project(id=10, manager_id=9, approval_status="approved", status="running")
    db.scalars.return_value.all.return_value = [1, 2, 9]
    monkeypatch.setattr(project_service, "has_global_project_access", lambda *args: False)
    with pytest.raises(BusinessException) as error:
        project_service.assert_project_booking_access(db, 10, SimpleNamespace(id=1), [2])
    assert error.value.status_code == 403


@pytest.mark.parametrize("state,allowed", [
    ("pending", False), ("changed", False),
    ("confirmed", True), ("running", True), ("completed", True),
])
def test_other_managers_unconfirmed_bookings_remain_private(monkeypatch, state, allowed):
    monkeypatch.setattr(schedule_service, "synchronize_schedule_statuses", lambda *args: {})
    monkeypatch.setattr(schedule_service, "visible_schedule_user_ids", lambda *args: {1, 2})
    monkeypatch.setattr(schedule_service.schedule_repository, "get", lambda *args: SimpleNamespace(user_id=2, created_by=9, status=state))
    monkeypatch.setattr(schedule_service.schedule_repository, "detail", lambda *args: {"id": 3})
    if allowed:
        assert schedule_service.schedule_detail(MagicMock(), 3, SimpleNamespace(id=1)) == {"id": 3}
    else:
        with pytest.raises(BusinessException) as error:
            schedule_service.schedule_detail(MagicMock(), 3, SimpleNamespace(id=1))
        assert error.value.status_code == 403


def test_confirmed_booking_outside_role_scope_is_not_public(monkeypatch):
    monkeypatch.setattr(schedule_service, "synchronize_schedule_statuses", lambda *args: {})
    monkeypatch.setattr(schedule_service, "visible_schedule_user_ids", lambda *args: {1})
    monkeypatch.setattr(schedule_service.schedule_repository, "get", lambda *args: SimpleNamespace(user_id=2, created_by=9, status="confirmed"))
    with pytest.raises(BusinessException) as error:
        schedule_service.schedule_detail(MagicMock(), 3, SimpleNamespace(id=1))
    assert error.value.status_code == 403


@pytest.mark.parametrize("roles,assigned,allowed", [
    ({"super_admin"}, True, False),
    ({"super_admin", "project_manager"}, True, False),
    ({"department_manager"}, True, True),
    ({"super_admin", "department_manager", "project_manager"}, True, True),
    ({"super_admin", "department_manager"}, False, False),
])
def test_department_approval_is_not_overridden_by_super_admin(monkeypatch, roles, assigned, allowed):
    actor = SimpleNamespace(id=1)
    monkeypatch.setattr(project_service, "get_role_codes", lambda *args: roles)
    monkeypatch.setattr(project_service, "get_department_manager", lambda *args: actor if assigned else SimpleNamespace(id=9))
    if allowed:
        assert project_service._assert_department_manager(MagicMock(), SimpleNamespace(department_id=3), actor) is actor
    else:
        with pytest.raises(BusinessException) as error:
            project_service._assert_department_manager(MagicMock(), SimpleNamespace(department_id=3), actor)
        assert error.value.status_code == 403


@pytest.mark.parametrize("approved", [True, False])
def test_project_creation_approval_and_rejection_deny_pure_super_admin(monkeypatch, approved):
    db = MagicMock()
    db.scalar.return_value = Project(id=10, department_id=3, approval_status="pending")
    monkeypatch.setattr(project_service, "get_role_codes", lambda *args: {"super_admin"})
    with pytest.raises(BusinessException) as error:
        project_service.decide_project(db, 10, ProjectDecision(note="审批意见"), SimpleNamespace(id=1), approved)
    assert error.value.status_code == 403
    db.commit.assert_not_called()


def test_super_admin_has_no_department_approval_todos(monkeypatch):
    monkeypatch.setattr(project_service, "get_role_codes", lambda *args: {"super_admin"})
    db = MagicMock()
    user = SimpleNamespace(id=1, department_id=3)
    assert project_service.list_pending_project_approvals(db, user) == []
    assert project_service.list_pending_resource_requests(db, user) == []
    db.execute.assert_not_called()
    db.scalars.assert_not_called()


@pytest.mark.parametrize("approved", [True, False])
def test_resource_approval_and_rejection_deny_pure_super_admin(monkeypatch, approved):
    db = MagicMock()
    db.scalar.return_value = Project(id=10, department_id=3, approval_status="approved")
    monkeypatch.setattr(project_service, "get_role_codes", lambda *args: {"super_admin"})
    with pytest.raises(BusinessException) as error:
        project_service.decide_resource_request(db, 10, 20, ProjectDecision(note="审批意见"), SimpleNamespace(id=1), approved)
    assert error.value.status_code == 403
    db.commit.assert_not_called()


def test_super_admin_with_department_role_only_gets_own_department_resource_todos(monkeypatch):
    monkeypatch.setattr(project_service, "get_role_codes", lambda *args: {"super_admin", "department_manager"})
    monkeypatch.setattr(project_service, "_resource_member_details", lambda *args: {})
    db = MagicMock()
    db.execute.return_value.all.return_value = []
    assert project_service.list_pending_resource_requests(db, SimpleNamespace(id=1, department_id=3)) == []
    query = sql(db.execute.call_args.args[0])
    assert "departments.manager_id = 1" in query and "departments.id = 3" in query


@pytest.mark.parametrize("role_ids", [[1], [1, 2, 3, 4, 5, 1]])
def test_existing_admin_can_create_super_admin_with_multiple_roles(role_ids):
    db = MagicMock()
    db.scalars.return_value.all.return_value = list(set(role_ids))
    db.scalar.side_effect = [SimpleNamespace(id=1), 50]  # role, operator's active super assignment
    assert rbac_service.validate_user_role_ids(db, role_ids, operator_id=7) == list(dict.fromkeys(role_ids))


def test_non_admin_cannot_escalate_through_user_or_role_endpoints():
    assert user_service._validate_role_ids is rbac_service.validate_user_role_ids
    db = MagicMock()
    db.scalars.return_value.all.return_value = [1, 2]
    db.scalar.side_effect = [SimpleNamespace(id=1), None]
    with pytest.raises(BusinessException) as error:
        user_service._validate_role_ids(db, [1, 2], operator_id=7)
    assert error.value.status_code == 403


def test_existing_super_admin_can_keep_super_role_and_add_department_role():
    db = MagicMock()
    db.scalars.return_value.all.return_value = [1, 2, 3]
    db.scalar.side_effect = [SimpleNamespace(id=1), 50]
    assert rbac_service.validate_user_role_ids(db, [1, 2, 3], operator_id=7, existing_user_id=7) == [1, 2, 3]


@pytest.mark.parametrize("operation", [{"new_role_ids": []}, {"new_status": "disabled"}, {"deleting": True}])
def test_last_active_super_admin_remains_protected(operation):
    db = MagicMock()
    db.scalar.side_effect = [SimpleNamespace(id=1), 50, None]
    with pytest.raises(BusinessException) as error:
        rbac_service.assert_super_admin_continuity(db, SimpleNamespace(id=7, status="active", is_deleted=False), **operation)
    assert "最后一个" in error.value.message
