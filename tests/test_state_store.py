import asyncio
import unittest
from datetime import datetime, timezone

from app.state.store import (
    LAYOUT2_VALVE_TAG_SOURCES,
    RealtimeStateStore,
)


class TestRealtimeStateStore(unittest.TestCase):
    def test_snapshot_includes_layout2_valves_with_default_zero(self):
        store = RealtimeStateStore()

        payload = store.snapshot("ava-lagoons")

        self.assertEqual(payload["type"], "snapshot")
        self.assertEqual(payload["lagoon_id"], "ava-lagoons")
        self.assertEqual(payload["pump_last_on"], {})

        for tag_id in LAYOUT2_VALVE_TAG_SOURCES:
            self.assertEqual(payload["tags"][tag_id], 0)

    def test_tick_payload_normalizes_layout2_valves(self):
        store = RealtimeStateStore()
        ts = datetime.now(timezone.utc).isoformat()

        asyncio.run(
            store.update(
                lagoon_id="ava-lagoons",
                tags={
                    "VE237_ST": None,
                    "VE238_ST": 1,
                    "VE239_ST": "2",
                    "VE240_ST": 3.0,
                    "VE244_ST": 9,
                    "VE401_ST": "foo",
                    "other_sensor": 12.5,
                },
                ts=ts,
            )
        )

        payload = asyncio.run(store.tick_payload("ava-lagoons"))

        self.assertEqual(payload["type"], "tick")
        self.assertEqual(payload["ts"], ts)
        self.assertIn("plc_status", payload)
        self.assertIn("local_time", payload)
        self.assertIn("timezone", payload)
        self.assertEqual(payload["tags"]["ve237"], 0)
        self.assertEqual(payload["tags"]["ve238"], 1)
        self.assertEqual(payload["tags"]["ve239"], 2)
        self.assertEqual(payload["tags"]["ve240"], 3)
        self.assertEqual(payload["tags"]["ve244"], 0)
        self.assertEqual(payload["tags"]["ve401"], 0)
        self.assertEqual(payload["tags"]["ve402"], 0)
        self.assertEqual(payload["tags"]["other_sensor"], 12.5)
        self.assertNotIn("VE237_ST", payload["tags"])
        self.assertNotIn("VE238_ST", payload["tags"])

    def test_tick_payload_exposes_only_canonical_valve_tags(self):
        store = RealtimeStateStore()
        ts = datetime.now(timezone.utc).isoformat()

        asyncio.run(
            store.update(
                lagoon_id="ava-lagoons",
                tags={
                    "VE237_ST": 1,
                    "VE238_ST": "2",
                    "VE239_ST": 3,
                    "VE240_ST": 0,
                },
                ts=ts,
            )
        )

        payload = asyncio.run(store.tick_payload("ava-lagoons"))

        self.assertEqual(payload["tags"]["ve237"], 1)
        self.assertEqual(payload["tags"]["ve238"], 2)
        self.assertEqual(payload["tags"]["ve239"], 3)
        self.assertEqual(payload["tags"]["ve240"], 0)
        self.assertNotIn("VE237_ST", payload["tags"])
        self.assertNotIn("VE238_ST", payload["tags"])
        self.assertNotIn("VE239_ST", payload["tags"])
        self.assertNotIn("VE240_ST", payload["tags"])


if __name__ == "__main__":
    unittest.main()
