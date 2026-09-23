from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.user import User


def _parse_scope(value: str | None) -> tuple[set[int], set[int], set[int]]:
    department_ids: set[int] = set()
    organization_ids: set[int] = set()
    user_ids: set[int] = set()
    targets = {
        "department": department_ids,
        "organization": organization_ids,
        "user": user_ids,
    }
    for token in (value or "").split(","):
        kind, separator, raw_id = token.strip().partition(":")
        if not separator or kind not in targets:
            continue
        try:
            item_id = int(raw_id)
        except ValueError:
            continue
        if item_id > 0:
            targets[kind].add(item_id)
    return department_ids, organization_ids, user_ids


def _descendant_organization_ids(
    db: Session,
    organization_ids: set[int],
) -> set[int]:
    if not organization_ids:
        return set()
    rows = db.execute(select(Organization.id, Organization.parent_id)).all()
    children: dict[int, set[int]] = {}
    for organization_id, parent_id in rows:
        if parent_id is not None:
            children.setdefault(parent_id, set()).add(organization_id)
    expanded = set(organization_ids)
    pending = list(organization_ids)
    while pending:
        parent_id = pending.pop()
        for child_id in children.get(parent_id, set()):
            if child_id not in expanded:
                expanded.add(child_id)
                pending.append(child_id)
    return expanded


def resolve_personnel_scope_user_ids(
    db: Session,
    value: str | None,
) -> set[int] | None:
    """Resolve a department/organization/user multi-selection to a user-id union.

    ``None`` means no scope filter was supplied. An invalid or now-empty supplied
    scope resolves to an empty set so it can never accidentally broaden a query.
    Selecting an organization includes users in all descendant organizations.
    """

    if value is None or not value.strip():
        return None
    department_ids, organization_ids, user_ids = _parse_scope(value)
    organization_ids = _descendant_organization_ids(db, organization_ids)
    clauses = []
    if department_ids:
        clauses.append(User.department_id.in_(department_ids))
    if organization_ids:
        clauses.append(User.organization_id.in_(organization_ids))
    if user_ids:
        clauses.append(User.id.in_(user_ids))
    if not clauses:
        return set()
    return set(
        db.scalars(
            select(User.id).where(
                User.is_deleted.is_(False),
                or_(*clauses),
            )
        ).all()
    )
