from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.services.lagoon_service import (
    PERMISSION_CONTROL,
    ensure_lagoon_access,
)
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.role import ProductType
from app.security.rbac import SMALL_WRITE_ROLES, extract_user_roles, require_roles
from app.services.small_control_audit import (
    begin_control_audit,
    complete_control_audit,
    fail_control_audit,
)
from app.services.small_opcua_control import (
    PumpControlConfigurationError,
    PumpControlWriteError,
    UnsupportedPumpActionError,
    ValueWriteValidationError,
    pulse_pump_action,
    write_configured_value,
)

router = APIRouter(prefix="/small", tags=["Small Control"])
logger = get_logger("api.small.control")


class ControlCommand(BaseModel):
    lagoon_id: str
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ValueControlCommand(BaseModel):
    lagoon_id: str
    module_id: str
    command_id: str
    value: int | float | bool


def _extract_user_id(user: dict) -> str:
    user_id = user.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return user_id


def _execute_pump_control(
    lagoon_id: str,
    action: str,
    module_id: str | None,
):
    try:
        return pulse_pump_action(
            lagoon_id,
            action,
            module_id=module_id,
        )
    except UnsupportedPumpActionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PumpControlConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PumpControlWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _execute_value_control(cmd: ValueControlCommand):
    try:
        return write_configured_value(
            cmd.lagoon_id,
            cmd.command_id,
            cmd.value,
            module_id=cmd.module_id,
        )
    except PumpControlConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueWriteValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PumpControlWriteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _execute_audited_pump_control(
    *,
    db: Session,
    lagoon_id: str,
    action: str,
    module_id: str | None,
    user_id: str,
    user_email: str,
):
    action_label = {
        "partir": "start",
        "parar": "stop",
    }.get(action.strip().lower(), action.strip().lower())
    audit = begin_control_audit(
        db,
        lagoon_id=lagoon_id,
        module_id=module_id or "auto",
        control_type="pump_action",
        action=action_label,
        change_summary=f"Pump {action_label} command requested",
        user_id=user_id,
        user_email=user_email,
        new_value={"action": action_label},
    )
    try:
        target = _execute_pump_control(lagoon_id, action, module_id)
    except HTTPException as exc:
        fail_control_audit(db, audit, exc)
        raise

    complete_control_audit(
        db,
        audit,
        module_id=target.module_id,
        tag_id=target.logical_tag,
        node_id=target.node_id,
        new_value={"action": action_label},
        change_summary=(
            f"Pump {action_label} command executed on {target.logical_tag}"
        ),
    )
    return target


def _execute_audited_value_control(
    *,
    db: Session,
    cmd: ValueControlCommand,
    user_id: str,
    user_email: str,
):
    audit = begin_control_audit(
        db,
        lagoon_id=cmd.lagoon_id,
        module_id=cmd.module_id,
        control_type="value_write",
        action="change_value",
        command_id=cmd.command_id,
        new_value=cmd.value,
        change_summary=f"Value change requested for {cmd.command_id}",
        user_id=user_id,
        user_email=user_email,
    )
    try:
        target, previous_value, normalized_value = _execute_value_control(cmd)
    except HTTPException as exc:
        fail_control_audit(db, audit, exc)
        raise

    complete_control_audit(
        db,
        audit,
        module_id=target.module_id,
        tag_id=target.logical_tag,
        node_id=target.node_id,
        previous_value=previous_value,
        new_value=normalized_value,
        change_summary=(
            f"{target.logical_tag} changed from "
            f"{previous_value!r} to {normalized_value!r}"
        ),
    )
    return target, previous_value, normalized_value


@router.post("/control")
def send_control_command(
    cmd: ControlCommand,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles(SMALL_WRITE_ROLES)),
):
    user_id = _extract_user_id(user)
    email = str(user.get("email", "-"))
    roles = extract_user_roles(user)
    ensure_lagoon_access(
        db=db,
        user_id=user_id,
        user_email=email,
        user_roles=roles,
        lagoon_id=cmd.lagoon_id,
        permission=PERMISSION_CONTROL,
        expected_product_type=ProductType.SMALL,
    )
    target = _execute_audited_pump_control(
        db=db,
        lagoon_id=cmd.lagoon_id,
        action=cmd.action,
        module_id=str(cmd.payload.get("module_id") or "").strip() or None,
        user_id=user_id,
        user_email=email,
    )
    logger.info(
        "[API] endpoint_response_summary endpoint=/api/small/control method=POST user_id=%s lagoon_id=%s action=%s",
        user_id,
        cmd.lagoon_id,
        cmd.action,
    )
    return {
        "ok": True,
        "product_type": "small",
        "lagoon_id": cmd.lagoon_id,
        "action": cmd.action,
        "module_id": target.module_id,
        "pulse_seconds": target.pulse_seconds,
        "requested_by": user_id,
    }


@router.put("/control")
def update_control_command(
    cmd: ControlCommand,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles(SMALL_WRITE_ROLES)),
):
    user_id = _extract_user_id(user)
    email = str(user.get("email", "-"))
    roles = extract_user_roles(user)
    ensure_lagoon_access(
        db=db,
        user_id=user_id,
        user_email=email,
        user_roles=roles,
        lagoon_id=cmd.lagoon_id,
        permission=PERMISSION_CONTROL,
        expected_product_type=ProductType.SMALL,
    )
    target = _execute_audited_pump_control(
        db=db,
        lagoon_id=cmd.lagoon_id,
        action=cmd.action,
        module_id=str(cmd.payload.get("module_id") or "").strip() or None,
        user_id=user_id,
        user_email=email,
    )
    logger.info(
        "[API] endpoint_response_summary endpoint=/api/small/control method=PUT user_id=%s lagoon_id=%s action=%s",
        user_id,
        cmd.lagoon_id,
        cmd.action,
    )
    return {
        "ok": True,
        "product_type": "small",
        "lagoon_id": cmd.lagoon_id,
        "action": cmd.action,
        "module_id": target.module_id,
        "pulse_seconds": target.pulse_seconds,
        "updated_by": user_id,
    }


@router.put("/control/value")
def write_control_value(
    cmd: ValueControlCommand,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles(SMALL_WRITE_ROLES)),
):
    user_id = _extract_user_id(user)
    email = str(user.get("email", "-"))
    roles = extract_user_roles(user)
    ensure_lagoon_access(
        db=db,
        user_id=user_id,
        user_email=email,
        user_roles=roles,
        lagoon_id=cmd.lagoon_id,
        permission=PERMISSION_CONTROL,
        expected_product_type=ProductType.SMALL,
    )
    target, previous_value, normalized_value = _execute_audited_value_control(
        db=db,
        cmd=cmd,
        user_id=user_id,
        user_email=email,
    )
    logger.info(
        "[API] endpoint_response_summary endpoint=/api/small/control/value method=PUT "
        "user_id=%s lagoon_id=%s module_id=%s command_id=%s value=%s data_type=%s",
        user_id,
        cmd.lagoon_id,
        target.module_id,
        target.command_id,
        normalized_value,
        target.data_type,
    )
    return {
        "ok": True,
        "product_type": "small",
        "lagoon_id": cmd.lagoon_id,
        "module_id": target.module_id,
        "command_id": target.command_id,
        "previous_value": previous_value,
        "value": normalized_value,
        "data_type": target.data_type,
        "updated_by": user_id,
    }
