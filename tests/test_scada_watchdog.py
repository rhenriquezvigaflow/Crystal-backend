import unittest
from datetime import datetime, timezone

from app.monitor.scada_watchdog import (
    ScadaStallWatchdog,
    WatchdogSnapshot,
)


class TestScadaWatchdog(unittest.TestCase):
    def setUp(self):
        self.watchdog = ScadaStallWatchdog()
        self.watchdog.timeout_sec = 120
        self.now = datetime.now(timezone.utc)

    def test_no_history_is_not_stalled(self):
        snapshot = WatchdogSnapshot(
            minute_bucket_last=None,
            minute_write_last=None,
            event_write_last=None,
            minute_bucket_age_sec=None,
            minute_write_age_sec=None,
            event_write_age_sec=None,
        )
        self.assertFalse(self.watchdog._is_stalled(snapshot))

    def test_recent_minute_write_is_not_stalled_even_if_events_old(self):
        snapshot = WatchdogSnapshot(
            minute_bucket_last=self.now,
            minute_write_last=self.now,
            event_write_last=self.now,
            minute_bucket_age_sec=95.0,
            minute_write_age_sec=30.0,
            event_write_age_sec=1200.0,
        )
        self.assertFalse(self.watchdog._is_stalled(snapshot))

    def test_stale_minute_write_is_stalled(self):
        snapshot = WatchdogSnapshot(
            minute_bucket_last=self.now,
            minute_write_last=self.now,
            event_write_last=self.now,
            minute_bucket_age_sec=180.0,
            minute_write_age_sec=121.0,
            event_write_age_sec=10.0,
        )
        self.assertTrue(self.watchdog._is_stalled(snapshot))

    def test_event_fallback_when_minute_table_empty(self):
        recent_event = WatchdogSnapshot(
            minute_bucket_last=None,
            minute_write_last=None,
            event_write_last=self.now,
            minute_bucket_age_sec=None,
            minute_write_age_sec=None,
            event_write_age_sec=10.0,
        )
        self.assertFalse(self.watchdog._is_stalled(recent_event))

        stale_event = WatchdogSnapshot(
            minute_bucket_last=None,
            minute_write_last=None,
            event_write_last=self.now,
            minute_bucket_age_sec=None,
            minute_write_age_sec=None,
            event_write_age_sec=121.0,
        )
        self.assertTrue(self.watchdog._is_stalled(stale_event))


if __name__ == "__main__":
    unittest.main()
