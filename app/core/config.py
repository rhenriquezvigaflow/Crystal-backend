from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    DATABASE_URL: str
    LOG_LEVEL: str = "INFO"
    COLLECTOR_API_KEY: str = Field(
        ...,
        description="API Key used by PLC collectors to ingest data"
    )
    JWT_SECRET_KEY: str = Field(
        ...,
        description="Secret key used to sign JWT tokens",
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="JWT signing algorithm",
    )
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=60,
        description="Access token expiration in minutes",
    )
    SCADA_WATCHDOG_ENABLED: bool = Field(
        default=True,
        description="Enable watchdog recovery for stalled SCADA data",
    )
    SCADA_WATCHDOG_CHECK_INTERVAL_SEC: float = Field(
        default=20,
        description="Watchdog polling interval in seconds",
    )
    SCADA_WATCHDOG_TIMEOUT_SEC: float = Field(
        default=120,
        description="Stall timeout in seconds",
    )
    SCADA_WATCHDOG_STARTUP_GRACE_SEC: float = Field(
        default=60,
        description="Startup grace period before checks begin",
    )
    SCADA_WATCHDOG_RECOVERY_COOLDOWN_SEC: float = Field(
        default=90,
        description="Minimum seconds between recoveries",
    )
    SCADA_WATCHDOG_HARD_RESTART: bool = Field(
        default=False,
        description="Terminate process on stall after recovery",
    )

    class Config:
        env_file = ".env"
        extra = "forbid"   


settings = Settings()
