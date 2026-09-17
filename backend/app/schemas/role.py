from datetime import datetime

from pydantic import Field

from app.schemas.common import ORMModel


class PermissionResponse(ORMModel):
    id: int
    code: str
    name: str
    module: str
    created_at: datetime
    updated_at: datetime


class RoleResponse(ORMModel):
    id: int
    code: str
    name: str
    description: str | None
    is_system: bool
    permission_ids: list[int] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class RolePermissionsUpdate(ORMModel):
    permission_ids: list[int] = Field(default_factory=list)
