from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_LOCAL_ORIGINS = [
    "http://127.0.0.1",
    "http://localhost",
    "https://127.0.0.1",
    "https://localhost",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:8085",
    "https://localhost:5173",
    "https://localhost:5174",
]

_WEAK_JWT_SECRETS = {
    "",
    "changeme",
    "change-me",
    "change-this-in-prod-please",
    "replace-me",
    "secret",
}
_WEAK_COLLECTOR_KEYS = {
    "",
    "changeme",
    "change-me",
    "crystal-secret-123",
    "replace-me",
}


def _parse_csv_list(value: Any) -> list[str]:
    if value is None:
        return []

    raw_items: list[Any]
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        raw_items = raw.split(",")
    elif isinstance(value, list):
        raw_items = value
    else:
        raw_items = [value]

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        if not isinstance(item, str):
            continue
        candidate = item.strip().rstrip("/")
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return normalized


class Settings(BaseSettings):
    APP_ENV: str = Field(
        default="development",
        description="Application runtime environment",
    )
    DATABASE_URL: str
    LOG_LEVEL: str = "INFO"
    PROXY_HEADERS_ENABLED: bool = Field(
        default=True,
        description="Honor X-Forwarded-* headers from trusted reverse proxies",
    )
    PROXY_TRUSTED_HOSTS: str = Field(
        default="127.0.0.1,::1,localhost",
        description="Trusted reverse proxy hosts",
    )
    CORS_ALLOWED_ORIGINS: str = Field(
        default=",".join(DEFAULT_LOCAL_ORIGINS),
        description="Allowed browser origins for REST requests",
    )
    WS_ALLOWED_ORIGINS: str = Field(
        default="",
        description="Allowed browser origins for WebSocket connections",
    )
    WS_ALLOW_QUERY_TOKEN: bool = Field(
        default=False,
        description="Allow legacy WebSocket auth token in query string",
    )
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
    JWT_ISSUER: str = Field(
        default="crystal-scada",
        description="JWT issuer claim",
    )
    JWT_AUDIENCE: str | None = Field(
        default=None,
        description="Optional JWT audience claim",
    )
    SECURITY_ENFORCE_STRONG_SECRETS: bool = Field(
        default=False,
        description="Fail startup when weak shared secrets are configured",
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
    ALARM_LAGOON_SIGNAL_MONITOR_ENABLED: bool = Field(
        default=True,
        description="Enable background monitor for lagoon no-signal alarms",
    )
    ALARM_LAGOON_SIGNAL_CHECK_INTERVAL_SEC: float = Field(
        default=30,
        description="Background monitor interval in seconds",
    )
    MAIL_USERNAME: str = Field(
        default="",
        description="SMTP username for notification emails",
    )
    MAIL_PASSWORD: str = Field(
        default="",
        description="SMTP password for notification emails",
    )
    MAIL_FROM: str = Field(
        default="",
        description="From email address for notification emails",
    )
    MAIL_PORT: int = Field(
        default=587,
        description="SMTP port for notification emails",
    )
    MAIL_SERVER: str = Field(
        default="smtp-mail.outlook.com",
        description="SMTP server hostname for notification emails",
    )
    MAIL_STARTTLS: bool = Field(
        default=True,
        description="Use STARTTLS for SMTP connections",
    )
    MAIL_SSL_TLS: bool = Field(
        default=False,
        description="Use SSL/TLS for SMTP connections",
    )
    MAIL_FROM_NAME: str = Field(
        default="Crystal SCADA",
        description="Optional sender display name for notification emails",
    )
    MAIL_TIMEOUT_SEC: int = Field(
        default=15,
        description="SMTP timeout for notification delivery in seconds",
    )
    MAIL_DISPATCH_MAX_WORKERS: int = Field(
        default=2,
        description="Maximum background workers used for notification delivery",
    )

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.strip().lower() in {"prod", "production"}

    @property
    def proxy_trusted_hosts(self) -> list[str]:
        return _parse_csv_list(self.PROXY_TRUSTED_HOSTS)

    @property
    def cors_allowed_origins(self) -> list[str]:
        return _parse_csv_list(self.CORS_ALLOWED_ORIGINS)

    @property
    def ws_allowed_origins(self) -> list[str]:
        return _parse_csv_list(self.WS_ALLOWED_ORIGINS)

    @property
    def effective_ws_allowed_origins(self) -> list[str]:
        if self.ws_allowed_origins:
            return self.ws_allowed_origins
        return self.cors_allowed_origins

    @property
    def email_templates_dir(self) -> Path:
        return Path(__file__).resolve().parents[1] / "templates" / "email"

    @property
    def is_mail_configured(self) -> bool:
        return all(
            [
                self.MAIL_USERNAME.strip(),
                self.MAIL_PASSWORD.strip(),
                self.MAIL_FROM.strip(),
                self.MAIL_SERVER.strip(),
                self.MAIL_PORT > 0,
            ]
        )

    def _is_weak_jwt_secret(self) -> bool:
        secret = self.JWT_SECRET_KEY.strip()
        return secret.lower() in _WEAK_JWT_SECRETS or len(secret) < 32

    def _is_weak_collector_api_key(self) -> bool:
        api_key = self.COLLECTOR_API_KEY.strip()
        return api_key.lower() in _WEAK_COLLECTOR_KEYS or len(api_key) < 24

    def security_warnings(self) -> list[str]:
        warnings: list[str] = []
        if self._is_weak_jwt_secret():
            warnings.append(
                "JWT_SECRET_KEY is weak; rotate it to a random value with at least 32 characters."
            )
        if self._is_weak_collector_api_key():
            warnings.append(
                "COLLECTOR_API_KEY is weak; rotate it to a random value with at least 24 characters."
            )
        return warnings

    def validate_runtime_security(self) -> None:
        if not (self.SECURITY_ENFORCE_STRONG_SECRETS or self.is_production):
            return

        issues = self.security_warnings()
        if issues:
            raise ValueError(" ; ".join(issues))

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="forbid",
    )


settings = Settings()
