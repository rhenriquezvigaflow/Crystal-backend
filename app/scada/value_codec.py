from __future__ import annotations

from typing import Any, Optional


STATE_TAG_SUFFIXES = (
    ".ST",
    "_ST",
    "_STS",
    "_ST_SCADA",
    "_STS_SCADA",
)
DEFAULT_STATE_MAX_VALUE = 3
TAG_STATE_MAX_VALUE = 11


def is_state_tag_id(tag_id: str | None) -> bool:
    if not tag_id:
        return False

    normalized = str(tag_id).strip().upper()
    return any(normalized.endswith(suffix) for suffix in STATE_TAG_SUFFIXES)


def is_state_value(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value in (0, 1, 2, 3)


def is_bool_value(value: Any) -> bool:
    return isinstance(value, bool)


def is_numeric_value(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def coerce_state_value(
    value: Any,
    max_state: int = DEFAULT_STATE_MAX_VALUE,
) -> Optional[int]:
    if isinstance(value, bool):
        return int(value)

    if isinstance(value, int):
        normalized = value
    elif isinstance(value, float):
        if not value.is_integer():
            return None
        normalized = int(value)
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            parsed = float(stripped)
        except ValueError:
            return None
        if not parsed.is_integer():
            return None
        normalized = int(parsed)
    else:
        return None

    if 0 <= normalized <= max_state:
        return normalized
    return None


def is_state_or_bool_value(value: Any, tag_id: str | None = None) -> bool:
    if is_state_value(value) or is_bool_value(value):
        return True
    return is_state_tag_id(tag_id) and coerce_state_value(value, max_state=TAG_STATE_MAX_VALUE) is not None


def to_storage_fields(
    value: Any,
    tag_id: str | None = None,
) -> tuple[Optional[int], Optional[float], Optional[bool]]:
    if is_state_tag_id(tag_id):
        coerced_state = coerce_state_value(value, max_state=TAG_STATE_MAX_VALUE)
        if coerced_state is not None:
            return coerced_state, None, None

    if is_state_value(value):
        coerced_state = coerce_state_value(value)
        if coerced_state is not None:
            return coerced_state, None, None

    if is_bool_value(value):
        return None, None, bool(value)
    if is_numeric_value(value):
        return None, float(value), None
    return None, None, None


def from_storage_fields(
    state: Optional[int],
    value_bool: Optional[bool],
    value_num: Optional[float],
) -> Any:
    if state is not None:
        return state
    if value_bool is not None:
        return value_bool
    return value_num
