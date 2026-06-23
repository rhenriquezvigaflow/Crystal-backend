from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.services.small_opcua_control import (
    UnsupportedPumpActionError,
    ValueWriteValidationError,
    pulse_pump_action,
    resolve_value_write_target,
    write_configured_value,
    write_boolean_without_timestamps,
)


CONFIG = """
lagoon_id: small_sim
product_type: small
opcua_modules:
  - id: recirculation_pump
    driver: siemens
    ip: 192.168.100.10
    pulse_seconds: 0.25
    actions:
      partir: TAGS_01_BOOL
      parar: TAGS_02_BOOL
    state_tag: TAGS_03_BOOL
    tags:
      TAGS_01_BOOL: ns=4;i=23
      TAGS_02_BOOL: ns=4;i=24
      TAGS_03_BOOL: ns=4;i=25
      TAGS_02_INT: ns=4;i=14
    write_commands:
      set_tags_02_int:
        tag: TAGS_02_INT
        data_type: int16
        min: -100
        max: 100
"""


class FakeNode:
    def __init__(self, initial_value=0) -> None:
        self.current_value = initial_value
        self.attribute_writes: list[tuple[object, object]] = []

    def get_value(self):
        return self.current_value

    def set_attribute(self, attribute_id, data_value) -> None:
        self.attribute_writes.append((attribute_id, data_value))
        self.current_value = data_value.Value.Value

    @property
    def values(self) -> list[bool]:
        return [
            data_value.Value.Value
            for _, data_value in self.attribute_writes
        ]


class FakeClient:
    def __init__(self, endpoint: str, timeout: float) -> None:
        self.endpoint = endpoint
        self.timeout = timeout
        self.node = FakeNode()
        self.node_id: str | None = None
        self.connected = False

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def get_node(self, node_id: str) -> FakeNode:
        self.node_id = node_id
        return self.node


class SmallPumpControlTests(unittest.TestCase):
    def test_partir_writes_true_then_false_to_configured_node(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "small_sim.yml"
            config_path.write_text(CONFIG, encoding="utf-8")
            clients: list[FakeClient] = []
            sleeps: list[float] = []

            def client_factory(endpoint: str, timeout: float) -> FakeClient:
                client = FakeClient(endpoint, timeout)
                clients.append(client)
                return client

            target = pulse_pump_action(
                "small_sim",
                "partir",
                config_path=config_path,
                client_factory=client_factory,
                sleep=sleeps.append,
            )

            self.assertEqual(target.node_id, "ns=4;i=23")
            self.assertEqual(target.module_id, "recirculation_pump")
            self.assertEqual(clients[0].node_id, "ns=4;i=23")
            self.assertEqual(clients[0].node.values, [True, False])
            for _, data_value in clients[0].node.attribute_writes:
                self.assertIsNone(data_value.SourceTimestamp)
                self.assertIsNone(data_value.ServerTimestamp)
            self.assertEqual(sleeps, [0.25])
            self.assertFalse(clients[0].connected)

    def test_state_tag_cannot_be_used_as_an_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "small_sim.yml"
            config_path.write_text(CONFIG, encoding="utf-8")

            with self.assertRaises(UnsupportedPumpActionError):
                pulse_pump_action(
                    "small_sim",
                    "TAGS_03_BOOL",
                    config_path=config_path,
                    client_factory=FakeClient,
                    sleep=lambda _: None,
                )

    def test_master_config_resolves_future_small_lagoon_by_id_and_module(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_dir = root / "config"
            config_dir.mkdir()
            (config_dir / "small_future.yml").write_text(
                """
lagoon_id: small_future
product_type: small
opcua_modules:
  - id: pump_a
    driver: siemens
    opc_server_url: opc.tcp://10.0.0.20:4840
    actions:
      partir: START_A
      parar: STOP_A
    state_tag: STATE_A
    tags:
      START_A: ns=4;i=101
      STOP_A: ns=4;i=102
      STATE_A: ns=4;i=103
  - id: pump_b
    driver: siemens
    opc_server_url: opc.tcp://10.0.0.21:4840
    actions:
      partir: START_B
      parar: STOP_B
    state_tag: STATE_B
    tags:
      START_B: ns=4;i=201
      STOP_B: ns=4;i=202
      STATE_B: ns=4;i=203
""",
                encoding="utf-8",
            )
            master_path = root / "collectors.yml"
            master_path.write_text(
                """
product_type: crystal
plcs:
  - include: config/small_future.yml
    product_type: small
""",
                encoding="utf-8",
            )
            clients: list[FakeClient] = []

            def client_factory(endpoint: str, timeout: float) -> FakeClient:
                client = FakeClient(endpoint, timeout)
                clients.append(client)
                return client

            target = pulse_pump_action(
                "small_future",
                "parar",
                module_id="pump_b",
                config_path=master_path,
                client_factory=client_factory,
                sleep=lambda _: None,
            )

            self.assertEqual(target.module_id, "pump_b")
            self.assertEqual(target.endpoint, "opc.tcp://10.0.0.21:4840")
            self.assertEqual(target.node_id, "ns=4;i=202")
            self.assertEqual(clients[0].node.values, [True, False])

    def test_boolean_writer_omits_status_and_timestamps(self) -> None:
        from opcua import ua

        node = FakeNode()

        write_boolean_without_timestamps(node, True)

        attribute_id, data_value = node.attribute_writes[0]
        self.assertEqual(attribute_id, ua.AttributeIds.Value)
        self.assertEqual(data_value.Value.VariantType, ua.VariantType.Boolean)
        self.assertIs(data_value.Value.Value, True)
        self.assertIsNone(data_value.StatusCode)
        self.assertIsNone(data_value.SourceTimestamp)
        self.assertIsNone(data_value.ServerTimestamp)

    def test_int16_write_uses_configured_command_and_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "small_sim.yml"
            config_path.write_text(CONFIG, encoding="utf-8")
            clients: list[FakeClient] = []

            def client_factory(endpoint: str, timeout: float) -> FakeClient:
                client = FakeClient(endpoint, timeout)
                clients.append(client)
                return client

            target, previous_value, value = write_configured_value(
                "small_sim",
                "set_tags_02_int",
                55,
                module_id="recirculation_pump",
                config_path=config_path,
                client_factory=client_factory,
            )

            self.assertEqual(target.node_id, "ns=4;i=14")
            self.assertEqual(target.logical_tag, "TAGS_02_INT")
            self.assertEqual(target.data_type, "int16")
            self.assertEqual(previous_value, 0)
            self.assertEqual(value, 55)
            data_value = clients[0].node.attribute_writes[0][1]
            self.assertEqual(data_value.Value.VariantType.name, "Int16")
            self.assertEqual(data_value.Value.Value, 55)
            self.assertIsNone(data_value.StatusCode)
            self.assertIsNone(data_value.SourceTimestamp)

    def test_int16_write_rejects_fraction_and_out_of_range(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "small_sim.yml"
            config_path.write_text(CONFIG, encoding="utf-8")

            with self.assertRaisesRegex(
                ValueWriteValidationError,
                "must be an integer",
            ):
                write_configured_value(
                    "small_sim",
                    "set_tags_02_int",
                    2.5,
                    config_path=config_path,
                    client_factory=FakeClient,
                )

            with self.assertRaisesRegex(
                ValueWriteValidationError,
                "at most 100",
            ):
                write_configured_value(
                    "small_sim",
                    "set_tags_02_int",
                    101,
                    config_path=config_path,
                    client_factory=FakeClient,
                )

    def test_write_target_is_resolved_without_node_id_in_caller(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "small_sim.yml"
            config_path.write_text(CONFIG, encoding="utf-8")

            target = resolve_value_write_target(
                "small_sim",
                "set_tags_02_int",
                module_id="recirculation_pump",
                config_path=config_path,
            )

            self.assertEqual(target.command_id, "set_tags_02_int")
            self.assertEqual(target.node_id, "ns=4;i=14")

    def test_future_small_value_command_is_loaded_from_master_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_dir = root / "config"
            config_dir.mkdir()
            (config_dir / "small_future.yml").write_text(
                """
lagoon_id: small_future
product_type: small
opcua_modules:
  - id: dosing_a
    opc_server_url: opc.tcp://10.0.0.30:4840
    tags:
      DOSING_SETPOINT: ns=4;i=301
    write_commands:
      set_dosing_setpoint:
        tag: DOSING_SETPOINT
        data_type: int16
        min: 0
        max: 500
""",
                encoding="utf-8",
            )
            master_path = root / "collectors.yml"
            master_path.write_text(
                """
plcs:
  - include: config/small_future.yml
""",
                encoding="utf-8",
            )

            target, previous_value, value = write_configured_value(
                "small_future",
                "SET_DOSING_SETPOINT",
                125,
                module_id="dosing_a",
                config_path=master_path,
                client_factory=FakeClient,
            )

            self.assertEqual(target.endpoint, "opc.tcp://10.0.0.30:4840")
            self.assertEqual(target.node_id, "ns=4;i=301")
            self.assertEqual(target.data_type, "int16")
            self.assertEqual(previous_value, 0)
            self.assertEqual(value, 125)


if __name__ == "__main__":
    unittest.main()
