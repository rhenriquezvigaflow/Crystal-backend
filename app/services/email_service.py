from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.notifications import AlarmNotificationPayload

logger = get_logger("alarms.email.service")


class EmailConfigurationError(RuntimeError):
    """Raised when SMTP settings are incomplete."""


class EmailService:
    def __init__(
        self,
        *,
        settings_obj: Any = settings,
        mail_client: FastMail | None = None,
        template_env: Environment | None = None,
    ) -> None:
        self._settings = settings_obj
        self._mail_client = mail_client
        self._template_env = template_env or Environment(
            loader=FileSystemLoader(str(self._settings.email_templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            enable_async=False,
        )

    @property
    def is_configured(self) -> bool:
        return bool(self._settings.is_mail_configured)

    def render_template(
        self,
        template_name: str,
        context: Mapping[str, Any],
    ) -> str:
        template = self._template_env.get_template(template_name)
        return template.render(**context)

    async def send_email(
        self,
        *,
        recipients: Sequence[str],
        subject: str,
        template_name: str,
        context: Mapping[str, Any],
    ) -> None:
        normalized_recipients = [
            str(recipient).strip()
            for recipient in recipients
            if str(recipient).strip()
        ]
        if not normalized_recipients:
            raise ValueError("Email recipients are required")
        if not self.is_configured:
            raise EmailConfigurationError(
                "SMTP email settings are incomplete. Configure MAIL_* variables in .env."
            )

        html_body = self.render_template(
            template_name=template_name,
            context=context,
        )
        message = MessageSchema(
            subject=subject,
            recipients=normalized_recipients,
            body=html_body,
            subtype="html",
        )

        try:
            await self._get_mail_client().send_message(message)
        except Exception:
            logger.exception(
                "[EMAIL SMTP ERROR] recipients=%s subject=%s template=%s",
                normalized_recipients,
                subject,
                template_name,
            )
            raise

        logger.info(
            "[EMAIL SMTP OK] recipients=%s subject=%s template=%s",
            len(normalized_recipients),
            subject,
            template_name,
        )

    async def send_alarm_notification(
        self,
        payload: AlarmNotificationPayload,
    ) -> None:
        subject = payload.subject
        await self.send_email(
            recipients=[str(item) for item in payload.recipients],
            subject=subject,
            template_name="alarm_notification.html",
            context={
                "payload": payload,
                "notification": payload.model_dump(mode="json"),
                "subject": subject,
            },
        )

    def send_alarm_notification_sync(
        self,
        payload: AlarmNotificationPayload,
    ) -> None:
        asyncio.run(self.send_alarm_notification(payload))

    async def send_auth_2fa_code(
        self,
        *,
        recipient: str,
        code: str,
        expires_minutes: int,
    ) -> None:
        await self.send_email(
            recipients=[recipient],
            subject="Small Lagoons authentication code",
            template_name="auth_2fa_code.html",
            context={
                "code": code,
                "expires_minutes": expires_minutes,
            },
        )

    def send_auth_2fa_code_sync(
        self,
        *,
        recipient: str,
        code: str,
        expires_minutes: int,
    ) -> None:
        asyncio.run(
            self.send_auth_2fa_code(
                recipient=recipient,
                code=code,
                expires_minutes=expires_minutes,
            )
        )

    def _get_mail_client(self) -> FastMail:
        if self._mail_client is None:
            self._mail_client = FastMail(self._build_connection_config())
        return self._mail_client

    def _build_connection_config(self) -> ConnectionConfig:
        return ConnectionConfig(
            MAIL_USERNAME=self._settings.MAIL_USERNAME,
            MAIL_PASSWORD=self._settings.MAIL_PASSWORD,
            MAIL_FROM=self._settings.MAIL_FROM,
            MAIL_PORT=self._settings.MAIL_PORT,
            MAIL_SERVER=self._settings.MAIL_SERVER,
            MAIL_STARTTLS=self._settings.MAIL_STARTTLS,
            MAIL_SSL_TLS=self._settings.MAIL_SSL_TLS,
            MAIL_FROM_NAME=self._settings.MAIL_FROM_NAME,
            TEMPLATE_FOLDER=self._settings.email_templates_dir,
            USE_CREDENTIALS=True,
            VALIDATE_CERTS=True,
            TIMEOUT=self._settings.MAIL_TIMEOUT_SEC,
        )
