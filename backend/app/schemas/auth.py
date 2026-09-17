from pydantic import BaseModel, EmailStr, Field, model_validator


class LoginRequest(BaseModel):
    employee_no: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class UserProfile(BaseModel):
    id: int
    employee_no: str
    name: str
    email: str | None = None
    department_id: int | None = None
    organization_id: int | None = None
    supervisor_id: int | None = None
    status: str
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr | None = None


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_confirmation(self):
        if self.new_password != self.confirm_password:
            raise ValueError("新密码与确认密码不一致")
        if self.new_password == self.current_password:
            raise ValueError("新密码不能与当前密码相同")
        return self
