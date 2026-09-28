from functools import lru_cache

from pydantic import Field, model_validator
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
    standard_work_hours: float = Field(default=8.0, gt=0)
    risk_stale_days: int = Field(default=7, ge=1)
    import_max_mb: int = Field(default=10, ge=1, le=100)
    import_default_password: str = Field(default="ChangeMe123!", min_length=8)
    redis_url: str = "redis://127.0.0.1:6379/0"
    smtp_enabled: bool = False
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    smtp_ca_file: str | None = None
    smtp_timeout_seconds: int = Field(default=10, ge=1, le=60)
    smtp_max_attempts: int = Field(default=5, ge=1, le=10)
    smtp_subject_prefix: str = "[项目协同] "
    public_app_url: str | None = None
    wecom_webhook_url: str | None = None
    dingtalk_webhook_url: str | None = None
    notification_upcoming_hours: int = Field(default=24, ge=1, le=168)
    initial_admin_username: str = "admin"
    initial_admin_password: str = "ChangeMe123!"
    initial_admin_name: str = "系统管理员"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True)

    @model_validator(mode="after")
    def validate_mail(self):
        if self.smtp_enabled:
            if not self.smtp_host or not self.smtp_from:
                raise ValueError("启用邮件须配置 SMTP_HOST 和 SMTP_FROM")
            if self.smtp_use_tls and self.smtp_use_ssl:
                raise ValueError("SMTP_USE_TLS 与 SMTP_USE_SSL 不能同时开启")
        if self.public_app_url and not self.public_app_url.startswith(("https://", "http://")):
            raise ValueError("PUBLIC_APP_URL 必须为 http(s) 地址")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
