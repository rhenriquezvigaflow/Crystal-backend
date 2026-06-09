from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from app.core.lagoon_aliases import normalize_lagoon_id
from app.core.logging import get_logger
from app.models.role import ProductType

logger = get_logger("commands.tags")


@dataclass(frozen=True, slots=True)
class TagWriteCommand:
    product_type: ProductType
    lagoon_id: str
    tag_id: str
    value: Any
    requested_by: str
    reason: str | None = None


class CommandService:
    @staticmethod
    def validate_tag_write(command: TagWriteCommand) -> None:
        if not normalize_lagoon_id(command.lagoon_id):
            raise HTTPException(status_code=422, detail="lagoon_id is required")
        if not command.tag_id.strip():
            raise HTTPException(status_code=422, detail="tag_id is required")

    @staticmethod
    def prepare_tag_write(command: TagWriteCommand) -> dict[str, Any]:
        CommandService.validate_tag_write(command)
        command_id = str(uuid4())
        logger.info(
            "[COMMAND AUDIT] prepared command_id=%s product=%s lagoon_id=%s tag_id=%s requested_by=%s dispatched=false",
            command_id,
            command.product_type.value,
            normalize_lagoon_id(command.lagoon_id),
            command.tag_id,
            command.requested_by,
        )
        return {
            "ok": True,
            "command_id": command_id,
            "product_type": command.product_type.value,
            "lagoon_id": normalize_lagoon_id(command.lagoon_id),
            "tag_id": command.tag_id.strip(),
            "status": "validated_not_dispatched",
            "queued": False,
            "dispatched": False,
        }
