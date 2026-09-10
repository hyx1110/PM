from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class UserProfile(BaseModel):
    id: int
    username: str
    name: str
    email: str | None = None
    department_id: int | None = None
    organization_id: int | None = None
    status: str
    roles: list[str] = []
    permissions: list[str] = []


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile

