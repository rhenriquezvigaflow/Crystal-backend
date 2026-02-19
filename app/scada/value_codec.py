from __future__ import annotations

from typing import Any, Optional


def is_state_value(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value in (0, 1, 2, 3)


def is_bool_value(value: Any) -> bool:
    return isinstance(value, bool)


def is_numeric_value(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_state_or_bool_value(value: Any) -> bool:
    return is_state_value(value) or is_bool_value(value)


def to_storage_fields(value: Any) -> tuple[Optional[int], Optional[float], Optional[bool]]:
    if is_state_value(value):
        return int(value), None, None
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
