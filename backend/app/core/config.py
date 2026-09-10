from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "项目任务与人力协同管理系统"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    database_url: str = "mysql+pymysql://project_user:change_me@127.0.0.1:3306/project_management?charset=utf8mb4"
    secret_key: str = Field(default="replace_me", min_length=8)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    cors_origins: str = "http://localhost:5173"
    timezone: str = "Asia/Shanghai"
    standard_work_hours: float = 8.0
    initial_admin_username: str = "admin"
    initial_admin_password: str = "ChangeMe123!"
    initial_admin_name: str = "系统管理员"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
