from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Request, Response, status
from sqlalchemy import text

from app.db.session import SessionLocal
from app.services.ingest_service import get_runtime_metrics

router = APIRouter(tags=["health"])


def _to_iso(value: object) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return None


def _database_ready() -> bool:
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        db.close()


def _runtime_payload() -> dict[str, object]:
    runtime = get_runtime_metrics()
    last_ingest_utc = runtime.get("last_ingest_utc")

    last_ingest_age_sec: float | None = None
    if isinstance(last_ingest_utc, datetime):
        last_ingest_age_sec = round(
            (datetime.now(timezone.utc) - last_ingest_utc).total_seconds(),
            1,
        )

    return {
        "last_ingest_utc": _to_iso(last_ingest_utc),
        "last_ingest_age_sec": last_ingest_age_sec,
        "last_lagoon": runtime.get("last_lagoon"),
        "last_minute_rows": runtime.get("last_minute_rows"),
        "last_event_count": runtime.get("last_event_count"),
    }


@router.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok"}


@router.get("/health/live")
def health_live() -> dict[str, object]:
    return {"status": "ok"}


@router.get("/health/ready")
def health_ready(request: Request, response: Response) -> dict[str, object]:
    database_ready = _database_ready()
    if not database_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    ws_manager = getattr(request.app.state, "ws_manager", None)
    ws_stats = (
        ws_manager.stats()
        if ws_manager and hasattr(ws_manager, "stats")
        else {
            "lagoon_count": 0,
            "total_connections": 0,
            "connections_by_lagoon": {},
        }
    )

    watchdog = getattr(request.app.state, "scada_watchdog", None)
    signal_monitor = getattr(
        request.app.state,
        "alarm_lagoon_signal_monitor",
        None,
    )

    return {
        "status": "ready" if database_ready else "degraded",
        "checks": {
            "database": "ok" if database_ready else "down",
            "watchdog": "running" if watchdog is not None else "not_loaded",
            "signal_monitor": (
                "running" if signal_monitor is not None else "not_loaded"
            ),
        },
        "runtime": _runtime_payload(),
        "websocket": ws_stats,
    }
