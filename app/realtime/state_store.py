
from datetime import datetime

class StateStore:
    def __init__(self):
        self.state = {}
        self.last_end_ts = {}  # 👈 NUEVO

    def preload_last_end_ts(self, lagoon_id: str, data: dict):
        self.last_end_ts[lagoon_id] = data

    def update(self, lagoon_id: str, tags: dict):
        now = datetime.now().isoformat()
        lagoon_state = self.state.setdefault(lagoon_id, {})

        for tag, value in tags.items():
            if isinstance(value, bool):
                prev = lagoon_state.get(tag)

                if not prev or prev["value"] != value:
                    lagoon_state[tag] = {
                        "value": value,
                        "updated_at": now,
                        "last_end_ts": (
                            self.last_end_ts
                            .get(lagoon_id, {})
                            .get(tag)
                        ),
                    }
            else:
                lagoon_state[tag] = value

    def snapshot(self, lagoon_id: str):
        return {
            "tags": self.state.get(lagoon_id, {})
        }
