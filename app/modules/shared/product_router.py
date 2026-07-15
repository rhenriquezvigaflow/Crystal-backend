from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Literal, Mapping

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.jwt import get_current_user
from app.auth.services.lagoon_service import (
    PERMISSION_CONTROL,
    PERMISSION_VIEW,
    ensure_lagoon_access,
    get_lagoon_permissions,
    get_product_lagoons_for_user,
    resolve_permitted_product_types,
    user_has_permission,
)
from app.core.lagoon_aliases import normalize_lagoon_id
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.lagoon import Lagoon
from app.models.role import ProductType
from app.repositories.scada_event_repository import ScadaEventRepository
from app.schemas.scada import ScadaCurrent, ScadaSnapshot
from app.schemas.scada_event import LastPumpEventsResponse
from app.security.rbac import extract_user_roles, require_roles
from app.services.scada_query_service import get_history_payload
from app.services.scada_read_service import get_current, get_last_minute
from app.services.xlsx_export import XLSX_MEDIA_TYPE, build_xlsx_workbook

from .command_service import CommandService, TagWriteCommand


@dataclass(frozen=True, slots=True)
class ProductRouterConfig:
    product_type: ProductType
    read_roles: list[str]
    write_roles: list[str]
    tags: list[str]
    include_tag_write_endpoint: bool = False


class TagWriteRequest(BaseModel):
    lagoon_id: str
    tag_id: str
    value: Any
    reason: str | None = Field(default=None, max_length=500)


def _extract_user_id(user: dict) -> str:
    user_id = user.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return user_id


def _role_set(user_roles: list[str]) -> set[str]:
    return {role.strip().lower() for role in user_roles if role and role.strip()}


def _has_write_role(user_roles: list[str], write_roles: list[str]) -> bool:
    roles = _role_set(user_roles)
    allowed = {role.strip().lower() for role in write_roles if role and role.strip()}
    return bool(roles.intersection(allowed))


def _slugify_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "laguna"


def _map_lagoon_access(
    *,
    lagoon: Lagoon,
    user_id: str,
    user_roles: list[str],
    write_roles: list[str],
    lagoon_permissions: Mapping[str, Mapping[str, bool]],
) -> dict[str, Any]:
    product_write = _has_write_role(user_roles, write_roles)
    specific_permissions = lagoon_permissions.get(lagoon.id, {})
    can_edit = product_write or bool(specific_permissions.get("can_edit"))
    can_control = product_write or bool(specific_permissions.get("can_control"))

    product_value = (
        lagoon.product_type.value
        if isinstance(lagoon.product_type, ProductType)
        else str(lagoon.product_type)
    )
    return {
        "id": lagoon.id,
        "name": lagoon.name,
        "lagoon_id": lagoon.id,
        "lagoon_name": lagoon.name,
        "plc_type": lagoon.plc_type,
        "country_id": lagoon.country_id,
        "country_name": lagoon.country.name if lagoon.country else None,
        "timezone": lagoon.timezone,
        "ip": lagoon.ip,
        "enable": bool(lagoon.enable),
        "can_view": True,
        "can_edit": can_edit,
        "can_control": can_control,
        "product_type": product_value,
    }


def create_product_router(config: ProductRouterConfig) -> APIRouter:
    product = config.product_type
    product_value = product.value
    logger = get_logger(f"api.{product_value}")

    router = APIRouter(
        prefix=f"/{product_value}",
        tags=config.tags,
        dependencies=[Depends(require_roles(config.read_roles))],
    )

    @router.get("/lagoons")
    def list_lagoons(
        db: Session = Depends(get_db),
        user: dict = Depends(get_current_user),
    ):
        user_id = _extract_user_id(user)
        email = str(user.get("email", "-"))
        roles = extract_user_roles(user)
        permitted_products = sorted(resolve_permitted_product_types(roles))
        lagoons = get_product_lagoons_for_user(
            db=db,
            user_id=user_id,
            user_roles=roles,
            product_type=product,
        )
        product_write = _has_write_role(roles, config.write_roles)
        lagoon_permissions = (
            {}
            if product_write
            else get_lagoon_permissions(
                db=db,
                user_id=user_id,
                lagoon_ids=(lagoon.id for lagoon in lagoons),
            )
        )
        logger.info(
            "[LAGOONS] list_for_user endpoint=/api/%s/lagoons user_id=%s email=%s roles=%s permitted_products=%s lagoons_count=%s",
            product_value,
            user_id,
            email,
            roles,
            permitted_products,
            len(lagoons),
        )
        return [
            _map_lagoon_access(
                lagoon=lagoon,
                user_id=user_id,
                user_roles=roles,
                write_roles=config.write_roles,
                lagoon_permissions=lagoon_permissions,
            )
            for lagoon in lagoons
        ]

    @router.get("/dashboard")
    def product_dashboard(
        db: Session = Depends(get_db),
        user: dict = Depends(get_current_user),
    ):
        user_id = _extract_user_id(user)
        email = str(user.get("email", "-"))
        roles = extract_user_roles(user)
        lagoons = get_product_lagoons_for_user(
            db=db,
            user_id=user_id,
            user_roles=roles,
            product_type=product,
        )
        logger.info(
            "[API] endpoint_response_summary endpoint=/api/%s/dashboard user_id=%s email=%s roles=%s lagoons_total=%s",
            product_value,
            user_id,
            email,
            roles,
            len(lagoons),
        )
        return {
            "product_type": product_value,
            "lagoons_total": len(lagoons),
        }

    @router.get("/lagoons/{lagoon_id}/last-minute", response_model=ScadaSnapshot)
    def product_last_minute(
        lagoon_id: str,
        db: Session = Depends(get_db),
        user: dict = Depends(get_current_user),
    ):
        canonical_lagoon_id = normalize_lagoon_id(lagoon_id)
        user_id = _extract_user_id(user)
        roles = extract_user_roles(user)
        ensure_lagoon_access(
            db=db,
            user_id=user_id,
            user_email=str(user.get("email", "-")),
            user_roles=roles,
            lagoon_id=canonical_lagoon_id,
            permission=PERMISSION_VIEW,
            expected_product_type=product,
        )
        data = get_last_minute(canonical_lagoon_id, db)
        if not data:
            raise HTTPException(status_code=404, detail="No data")
        return data

    @router.get("/lagoons/{lagoon_id}/current", response_model=ScadaCurrent)
    def product_current(
        lagoon_id: str,
        request: Request,
        db: Session = Depends(get_db),
        user: dict = Depends(get_current_user),
    ):
        canonical_lagoon_id = normalize_lagoon_id(lagoon_id)
        user_id = _extract_user_id(user)
        roles = extract_user_roles(user)
        ensure_lagoon_access(
            db=db,
            user_id=user_id,
            user_email=str(user.get("email", "-")),
            user_roles=roles,
            lagoon_id=canonical_lagoon_id,
            permission=PERMISSION_VIEW,
            expected_product_type=product,
        )
        data = get_current(
            canonical_lagoon_id,
            db,
            state_store=getattr(request.app.state, "state_store", None),
        )
        if not data:
            raise HTTPException(status_code=404, detail="No data")
        return data

    @router.get(
        "/lagoons/{lagoon_id}/pump-events/last-3",
        response_model=LastPumpEventsResponse,
    )
    def product_last_3_pump_events(
        lagoon_id: str,
        db: Session = Depends(get_db),
        user: dict = Depends(get_current_user),
    ):
        canonical_lagoon_id = normalize_lagoon_id(lagoon_id)
        user_id = _extract_user_id(user)
        roles = extract_user_roles(user)
        ensure_lagoon_access(
            db=db,
            user_id=user_id,
            user_email=str(user.get("email", "-")),
            user_roles=roles,
            lagoon_id=canonical_lagoon_id,
            permission=PERMISSION_VIEW,
            expected_product_type=product,
        )
        events = ScadaEventRepository.get_last_3_events_by_lagoon(
            db=db,
            lagoon_id=canonical_lagoon_id,
        )
        if not events:
            raise HTTPException(status_code=404, detail="No pump events")
        return {
            "lagoon_id": canonical_lagoon_id,
            "events": events,
        }

    @router.get("/lagoons/{lagoon_id}/pump-events/report.xlsx")
    def download_pump_events_report(
        lagoon_id: str,
        db: Session = Depends(get_db),
        user: dict = Depends(get_current_user),
    ):
        canonical_lagoon_id = normalize_lagoon_id(lagoon_id)
        user_id = _extract_user_id(user)
        roles = extract_user_roles(user)
        lagoon = ensure_lagoon_access(
            db=db,
            user_id=user_id,
            user_email=str(user.get("email", "-")),
            user_roles=roles,
            lagoon_id=canonical_lagoon_id,
            permission=PERMISSION_VIEW,
            expected_product_type=product,
        )
        lagoon_name = lagoon.name if lagoon and lagoon.name else canonical_lagoon_id
        columns, rows = ScadaEventRepository.get_event_report_by_lagoon_name(
            db=db,
            lagoon_name=lagoon_name,
        )
        workbook = build_xlsx_workbook(
            columns=columns,
            rows=rows,
            sheet_name="Pump Report",
        )
        filename = (
            f"pump_report_{_slugify_filename(lagoon_name)}_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )
        return Response(
            content=workbook,
            media_type=XLSX_MEDIA_TYPE,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    @router.get("/history")
    def product_history(
        lagoon_id: str = Query(...),
        start_date: datetime = Query(...),
        end_date: datetime = Query(...),
        resolution: Literal["hourly", "daily", "weekly"] = Query("hourly"),
        tags: list[str] | None = Query(None),
        db: Session = Depends(get_db),
        user: dict = Depends(get_current_user),
    ):
        canonical_lagoon_id = normalize_lagoon_id(lagoon_id)
        user_id = _extract_user_id(user)
        roles = extract_user_roles(user)
        ensure_lagoon_access(
            db=db,
            user_id=user_id,
            user_email=str(user.get("email", "-")),
            user_roles=roles,
            lagoon_id=canonical_lagoon_id,
            permission=PERMISSION_VIEW,
            expected_product_type=product,
        )
        response = get_history_payload(
            db=db,
            lagoon_id=canonical_lagoon_id,
            start_date=start_date,
            end_date=end_date,
            resolution=resolution,
            tags=tags,
        )
        logger.info(
            "[API] endpoint_response_summary endpoint=/api/%s/history user_id=%s lagoon_id=%s resolution=%s tags_requested=%s series_count=%s source=%s",
            product_value,
            user_id,
            canonical_lagoon_id,
            response["resolution"],
            len(tags or []),
            len(response["series"]),
            response["source"],
        )
        return response

    if config.include_tag_write_endpoint:
        write_dependency = require_roles(config.write_roles)

        @router.post("/tags/write", status_code=status.HTTP_202_ACCEPTED)
        def prepare_tag_write(
            payload: TagWriteRequest,
            db: Session = Depends(get_db),
            user: dict = Depends(write_dependency),
        ):
            user_id = _extract_user_id(user)
            roles = extract_user_roles(user)
            ensure_lagoon_access(
                db=db,
                user_id=user_id,
                user_email=str(user.get("email", "-")),
                user_roles=roles,
                lagoon_id=payload.lagoon_id,
                permission=PERMISSION_CONTROL,
                expected_product_type=product,
            )
            return CommandService.prepare_tag_write(
                TagWriteCommand(
                    product_type=product,
                    lagoon_id=payload.lagoon_id,
                    tag_id=payload.tag_id,
                    value=payload.value,
                    requested_by=user_id,
                    reason=payload.reason,
                )
            )

    return router
