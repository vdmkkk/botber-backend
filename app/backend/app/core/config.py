from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ENV: str = "dev"
    SERVICE_PORT: int = 8080

    ADMIN_API_KEY: str

    PG_HOST: str
    PG_PORT: int
    PG_DB: str
    PG_USER: str
    PG_PASSWORD: str

    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int = 0

    JWT_SECRET: str
    JWT_ALG: str = "HS256"
    JWT_REFRESH_MINUTES: int = 15
    SESSION_TTL_DAYS: int = 30

    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_USER: str
    SMTP_PASSWORD: str
    SMTP_TLS: bool = True
    MAIL_FROM: str

    EMAIL_ENABLED: bool = True
    SMTP_TIMEOUT_SECONDS: int = 10

    VERIFY_CODE_TTL_MINUTES: int = 10
    VERIFY_RESEND_COOLDOWN_SECONDS: int = 60
    PASSWORD_RESET_TTL_MINUTES: int = 15

    FRONTEND_BASE_URL: str = "https://botberi.tech"

    LOGIN_ATTEMPT_WINDOW_SECONDS: int = 600
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_BLOCK_SECONDS: int = 900

    EXTERNAL_API_BASE_URL: str = "https://api.botberi.tech"         # instances API
    EXTERNAL_API_TOKEN: str | None = None

    KB_API_BASE_URL: str | None = "https://api.botberi.tech"  # knowledge API (can be same)
    KB_API_TOKEN: str | None = None

    HEALTH_POLL_INTERVAL_SECONDS: int = 3600                     # 60 min default
    HEALTH_CONCURRENCY: int = 10

    BILLING_TICK_SECONDS: int = 300           # run every 5 minutes; processes due items
    BILLING_LOCK_TTL_SECONDS: int = 240       # Redis lock TTL (shorter than tick)
    BILLING_TIMEZONE: str = "UTC"             # optional: for aligning to next midnight etc.

    # Which statuses are billable (external “active” only)
    BILLABLE_STATUSES: tuple[str, ...] = ("active",)

settings = Settings()
