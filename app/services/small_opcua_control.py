from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

import yaml


DEFAULT_COLLECTORS_CONFIG = (
    Path(__file__).resolve().parents[3]
    / "collector_python"
    / "collectors.yml"
)
SUPPORTED_PUMP_ACTIONS = {"partir", "parar"}
SUPPORTED_WRITE_TYPES = {
    "bool",
    "int16",
    "int32",
    "uint16",
    "uint32",
    "float",
    "double",
}
_PULSE_LOCKS: dict[str, Lock] = {}
_PULSE_LOCKS_GUARD = Lock()


class SmallPumpControlError(RuntimeError):
    pass


class UnsupportedPumpActionError(SmallPumpControlError):
    pass


class PumpControlConfigurationError(SmallPumpControlError):
    pass


class PumpControlWriteError(SmallPumpControlError):
    pass


class ValueWriteValidationError(SmallPumpControlError):
    pass


@dataclass(frozen=True)
class PumpControlTarget:
    lagoon_id: str
    module_id: str
    logical_tag: str
    endpoint: str
    node_id: str
    pulse_seconds: float
    timeout_sec: float
    username: str | None = None
    password: str | None = None


@dataclass(frozen=True)
class ValueWriteTarget:
    lagoon_id: str
    module_id: str
    command_id: str
    logical_tag: str
    endpoint: str
    node_id: str
    data_type: str
    min_value: float | None
    max_value: float | None
    timeout_sec: float
    username: str | None = None
    password: str | None = None


def _config_path() -> Path:
    configured_path = os.getenv("SMALL_CONTROL_CONFIG_PATH", "").strip()
    return Path(configured_path) if configured_path else DEFAULT_COLLECTORS_CONFIG


def _normalized_action(action: str) -> str:
    normalized = str(action or "").strip().lower()
    if normalized not in SUPPORTED_PUMP_ACTIONS:
        raise UnsupportedPumpActionError(
            f"Unsupported pump action: {action!r}"
        )
    return normalized


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as config_file:
            payload = yaml.safe_load(config_file) or {}
    except OSError as exc:
        raise PumpControlConfigurationError(
            f"Unable to read Small Lagoons control config: {path}"
        ) from exc

    if not isinstance(payload, dict):
        raise PumpControlConfigurationError(
            f"Control config must contain a YAML object: {path}"
        )
    return payload


def _load_lagoon_configs(path: Path) -> list[dict[str, Any]]:
    root = _load_yaml(path)
    entries = root.get("plcs")
    if not isinstance(entries, list):
        return [root]

    configs: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue

        include = str(entry.get("include") or "").strip()
        if not include:
            configs.append(entry)
            continue

        include_path = Path(include)
        if not include_path.is_absolute():
            include_path = path.parent / include_path
        included_config = _load_yaml(include_path.resolve())
        overrides = {
            key: value
            for key, value in entry.items()
            if key != "include"
        }
        configs.append({**included_config, **overrides})

    return configs


def _find_lagoon_config(
    configs: list[dict[str, Any]],
    lagoon_id: str,
) -> dict[str, Any]:
    normalized_lagoon_id = str(lagoon_id or "").strip().lower()
    for config in configs:
        candidate_id = str(config.get("lagoon_id") or "").strip().lower()
        if candidate_id == normalized_lagoon_id:
            return config

    raise PumpControlConfigurationError(
        f"No collector config was found for lagoon {lagoon_id!r}"
    )


def _select_module(
    config: dict[str, Any],
    action: str,
    module_id: str | None,
) -> dict[str, Any]:
    modules = config.get("opcua_modules") or []
    if not isinstance(modules, list):
        raise PumpControlConfigurationError("opcua_modules must be a list")

    normalized_module_id = str(module_id or "").strip().lower()
    candidates: list[dict[str, Any]] = []
    for module in modules:
        if not isinstance(module, dict):
            continue

        actions = module.get("actions") or {}
        if not isinstance(actions, dict) or not actions.get(action):
            continue

        candidate_id = str(module.get("id") or "").strip().lower()
        if normalized_module_id and candidate_id != normalized_module_id:
            continue
        candidates.append(module)

    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        module_label = f" module {module_id!r}" if module_id else ""
        raise PumpControlConfigurationError(
            f"Action {action!r} is not configured for{module_label}"
        )

    raise PumpControlConfigurationError(
        f"Multiple modules support action {action!r}; module_id is required"
    )


def _get_pulse_lock(target: PumpControlTarget) -> Lock:
    key = f"{target.lagoon_id}:{target.module_id}:{target.endpoint}"
    with _PULSE_LOCKS_GUARD:
        return _PULSE_LOCKS.setdefault(key, Lock())


def _get_write_lock(target: ValueWriteTarget) -> Lock:
    key = f"{target.lagoon_id}:{target.module_id}:{target.endpoint}"
    with _PULSE_LOCKS_GUARD:
        return _PULSE_LOCKS.setdefault(key, Lock())


def resolve_pump_control_target(
    lagoon_id: str,
    action: str,
    *,
    module_id: str | None = None,
    config_path: Path | None = None,
) -> PumpControlTarget:
    normalized_action = _normalized_action(action)
    path = config_path or _config_path()
    config = _find_lagoon_config(_load_lagoon_configs(path), lagoon_id)
    product_type = str(config.get("product_type") or "").strip().lower()
    if product_type and product_type != "small":
        raise PumpControlConfigurationError(
            f"Lagoon {lagoon_id!r} is not configured as product_type small"
        )

    module = _select_module(config, normalized_action, module_id)
    actions = module.get("actions") or {}
    logical_tag = actions.get(normalized_action)
    if logical_tag == module.get("state_tag"):
        raise PumpControlConfigurationError(
            "Pump state tag cannot be configured as a writable action"
        )

    tags = module.get("tags") or {}
    node_id = tags.get(logical_tag)
    if not node_id:
        raise PumpControlConfigurationError(
            f"Action {normalized_action!r} references missing tag {logical_tag!r}"
        )

    endpoint = str(module.get("opc_server_url") or "").strip()
    if not endpoint:
        ip = str(module.get("ip") or "").strip()
        endpoint = f"opc.tcp://{ip}:4840" if ip else ""
    if not endpoint:
        raise PumpControlConfigurationError(
            f"OPC UA endpoint is missing for action {normalized_action!r}"
        )

    pulse_seconds = float(module.get("pulse_seconds", 0.25))
    if pulse_seconds <= 0 or pulse_seconds > 5:
        raise PumpControlConfigurationError(
            "pulse_seconds must be greater than 0 and at most 5 seconds"
        )

    return PumpControlTarget(
        lagoon_id=str(config.get("lagoon_id") or lagoon_id),
        module_id=str(module.get("id") or ""),
        logical_tag=str(logical_tag),
        endpoint=endpoint,
        node_id=str(node_id),
        pulse_seconds=pulse_seconds,
        timeout_sec=float(module.get("timeout_sec", 4)),
        username=module.get("username"),
        password=module.get("password"),
    )


def resolve_value_write_target(
    lagoon_id: str,
    command_id: str,
    *,
    module_id: str | None = None,
    config_path: Path | None = None,
) -> ValueWriteTarget:
    normalized_command_id = str(command_id or "").strip().lower()
    if not normalized_command_id:
        raise PumpControlConfigurationError("command_id is required")

    path = config_path or _config_path()
    config = _find_lagoon_config(_load_lagoon_configs(path), lagoon_id)
    product_type = str(config.get("product_type") or "").strip().lower()
    if product_type and product_type != "small":
        raise PumpControlConfigurationError(
            f"Lagoon {lagoon_id!r} is not configured as product_type small"
        )

    normalized_module_id = str(module_id or "").strip().lower()
    matches: list[tuple[dict[str, Any], dict[str, Any]]] = []
    modules = config.get("opcua_modules") or []
    if not isinstance(modules, list):
        raise PumpControlConfigurationError("opcua_modules must be a list")

    for module in modules:
        if not isinstance(module, dict):
            continue
        candidate_module_id = str(module.get("id") or "").strip().lower()
        if normalized_module_id and candidate_module_id != normalized_module_id:
            continue

        write_commands = module.get("write_commands") or {}
        if not isinstance(write_commands, dict):
            continue
        for configured_id, command in write_commands.items():
            if str(configured_id).strip().lower() != normalized_command_id:
                continue
            if isinstance(command, dict):
                matches.append((module, command))

    if not matches:
        raise PumpControlConfigurationError(
            f"Write command {command_id!r} is not configured for lagoon {lagoon_id!r}"
        )
    if len(matches) > 1:
        raise PumpControlConfigurationError(
            f"Multiple modules define write command {command_id!r}; module_id is required"
        )

    module, command = matches[0]
    logical_tag = str(command.get("tag") or "").strip()
    tags = module.get("tags") or {}
    node_id = tags.get(logical_tag)
    if not logical_tag or not node_id:
        raise PumpControlConfigurationError(
            f"Write command {command_id!r} references an unknown logical tag"
        )
    if logical_tag == module.get("state_tag"):
        raise PumpControlConfigurationError(
            "Pump state tag cannot be configured as a writable value"
        )

    data_type = str(command.get("data_type") or "").strip().lower()
    if data_type not in SUPPORTED_WRITE_TYPES:
        raise PumpControlConfigurationError(
            f"Unsupported write data_type {data_type!r}"
        )

    endpoint = str(module.get("opc_server_url") or "").strip()
    if not endpoint:
        ip = str(module.get("ip") or "").strip()
        endpoint = f"opc.tcp://{ip}:4840" if ip else ""
    if not endpoint:
        raise PumpControlConfigurationError(
            f"OPC UA endpoint is missing for write command {command_id!r}"
        )

    min_value = command.get("min")
    max_value = command.get("max")
    return ValueWriteTarget(
        lagoon_id=str(config.get("lagoon_id") or lagoon_id),
        module_id=str(module.get("id") or ""),
        command_id=normalized_command_id,
        logical_tag=logical_tag,
        endpoint=endpoint,
        node_id=str(node_id),
        data_type=data_type,
        min_value=float(min_value) if min_value is not None else None,
        max_value=float(max_value) if max_value is not None else None,
        timeout_sec=float(module.get("timeout_sec", 4)),
        username=module.get("username"),
        password=module.get("password"),
    )


def _default_client_factory(endpoint: str, timeout: float):
    from opcua import Client

    return Client(endpoint, timeout=timeout)


def write_boolean_without_timestamps(node: Any, value: bool) -> None:
    from opcua import ua

    data_value = ua.DataValue(
        ua.Variant(bool(value), ua.VariantType.Boolean)
    )
    data_value.StatusCode = None
    data_value.SourceTimestamp = None
    data_value.ServerTimestamp = None
    node.set_attribute(ua.AttributeIds.Value, data_value)


def _coerce_write_value(target: ValueWriteTarget, value: Any) -> bool | int | float:
    integer_ranges = {
        "int16": (-32768, 32767),
        "int32": (-2147483648, 2147483647),
        "uint16": (0, 65535),
        "uint32": (0, 4294967295),
    }

    if target.data_type == "bool":
        if isinstance(value, bool):
            normalized: bool | int | float = value
        elif isinstance(value, (int, float)) and value in (0, 1):
            normalized = bool(value)
        else:
            raise ValueWriteValidationError(
                "Boolean value must be true, false, 0 or 1"
            )
    elif target.data_type in integer_ranges:
        if isinstance(value, bool):
            raise ValueWriteValidationError("Integer value cannot be boolean")
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueWriteValidationError("Value must be numeric") from exc
        if not numeric.is_integer():
            raise ValueWriteValidationError(
                f"Value for {target.data_type} must be an integer"
            )
        normalized = int(numeric)
        type_min, type_max = integer_ranges[target.data_type]
        if not type_min <= normalized <= type_max:
            raise ValueWriteValidationError(
                f"Value is outside {target.data_type} range [{type_min}, {type_max}]"
            )
    else:
        if isinstance(value, bool):
            raise ValueWriteValidationError(
                "Floating-point value cannot be boolean"
            )
        try:
            normalized = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueWriteValidationError("Value must be numeric") from exc

    numeric_value = float(normalized)
    if target.min_value is not None and numeric_value < target.min_value:
        raise ValueWriteValidationError(
            f"Value must be at least {target.min_value:g}"
        )
    if target.max_value is not None and numeric_value > target.max_value:
        raise ValueWriteValidationError(
            f"Value must be at most {target.max_value:g}"
        )
    return normalized


def write_typed_value_without_metadata(
    node: Any,
    value: bool | int | float,
    data_type: str,
) -> None:
    from opcua import ua

    variant_types = {
        "bool": ua.VariantType.Boolean,
        "int16": ua.VariantType.Int16,
        "int32": ua.VariantType.Int32,
        "uint16": ua.VariantType.UInt16,
        "uint32": ua.VariantType.UInt32,
        "float": ua.VariantType.Float,
        "double": ua.VariantType.Double,
    }
    data_value = ua.DataValue(ua.Variant(value, variant_types[data_type]))
    data_value.StatusCode = None
    data_value.SourceTimestamp = None
    data_value.ServerTimestamp = None
    node.set_attribute(ua.AttributeIds.Value, data_value)


def pulse_pump_action(
    lagoon_id: str,
    action: str,
    *,
    module_id: str | None = None,
    config_path: Path | None = None,
    client_factory: Callable[..., Any] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> PumpControlTarget:
    target = resolve_pump_control_target(
        lagoon_id,
        action,
        module_id=module_id,
        config_path=config_path,
    )
    factory = client_factory or _default_client_factory

    with _get_pulse_lock(target):
        client = factory(target.endpoint, timeout=target.timeout_sec)
        if target.username and target.password:
            client.set_user(target.username)
            client.set_password(target.password)

        try:
            client.connect()
            node = client.get_node(target.node_id)
            write_boolean_without_timestamps(node, True)
            try:
                sleep(target.pulse_seconds)
            finally:
                write_boolean_without_timestamps(node, False)
        except Exception as exc:
            detail = str(exc).strip() or exc.__class__.__name__
            raise PumpControlWriteError(
                f"OPC UA endpoint {target.endpoint} is unavailable "
                f"for action {action!r}: {detail}"
            ) from exc
        finally:
            try:
                client.disconnect()
            except Exception:
                pass

    return target


def write_configured_value(
    lagoon_id: str,
    command_id: str,
    value: Any,
    *,
    module_id: str | None = None,
    config_path: Path | None = None,
    client_factory: Callable[..., Any] | None = None,
) -> tuple[ValueWriteTarget, Any, bool | int | float]:
    target = resolve_value_write_target(
        lagoon_id,
        command_id,
        module_id=module_id,
        config_path=config_path,
    )
    normalized_value = _coerce_write_value(target, value)
    factory = client_factory or _default_client_factory

    with _get_write_lock(target):
        client = factory(target.endpoint, timeout=target.timeout_sec)
        if target.username and target.password:
            client.set_user(target.username)
            client.set_password(target.password)

        try:
            client.connect()
            node = client.get_node(target.node_id)
            previous_value = node.get_value()
            write_typed_value_without_metadata(
                node,
                normalized_value,
                target.data_type,
            )
        except PumpControlWriteError:
            raise
        except Exception as exc:
            detail = str(exc).strip() or exc.__class__.__name__
            raise PumpControlWriteError(
                f"OPC UA write failed endpoint={target.endpoint} "
                f"command={target.command_id!r}: {detail}"
            ) from exc
        finally:
            try:
                client.disconnect()
            except Exception:
                pass

    return target, previous_value, normalized_value
