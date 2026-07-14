import asyncio
from threading import Lock
from time import monotonic
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB

from app.alarms.notifier import dispatch_notifications
from app.alarms.service import evaluate_alarms, log_persisted_alarm_transitions
from app.core.config import settings
from app.core.lagoon_aliases import normalize_lagoon_id
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models.lagoon import Lagoon
from app.models.role import ProductType
from app.services.ingest_service import ingest, log_persisted_ingest
from app.security.api_key import verify_collector_key

router = APIRouter()
logger = get_logger("api.ingest")
INGEST_TIMEOUT_SEC = settings.INGEST_REQUEST_TIMEOUT_SEC
INGEST_DB_TIMEOUTS_SQL = text(
    """
    SELECT
        set_config('statement_timeout', :statement_timeout, true),
        set_config('lock_timeout', :lock_timeout, true)
    """
)
SYNC_COLLECTOR_TAGS_SQL = text(
    """
    SELECT public.sp_sync_collector_tags_and_alarms_v2(
        :lagoon_id,
        :source_ts,
        :tags_payload
    ) AS sync_result
    """
).bindparams(bindparam("tags_payload", type_=JSONB))
_collector_sync_lock = Lock()
_collector_sync_last_attempt: dict[str, float] = {}


class IngestPayload(BaseModel):
    lagoon_id: str
    product_type: Optional[ProductType] = None
    timestamp: Optional[datetime] = None
    tags: dict


def _product_value(value) -> str:
    if isinstance(value, ProductType):
        return value.value
    return str(value)


def _ensure_ingest_product(
    *,
    db,
    lagoon_id: str,
    requested_product_type: str | None,
) -> str:
    lagoon = (
        db.query(Lagoon)
        .filter(
            Lagoon.id == lagoon_id,
            Lagoon.enable.is_(True),
        )
        .first()
    )
    if lagoon is None:
        raise HTTPException(status_code=404, detail="Lagoon not found")

    lagoon_product_type = _product_value(lagoon.product_type)
    if requested_product_type and requested_product_type != lagoon_product_type:
        raise HTTPException(
            status_code=409,
            detail="Lagoon product_type mismatch",
        )

    return lagoon_product_type


def _configure_ingest_transaction(*, db) -> None:
    statement_timeout_ms = max(0, int(settings.INGEST_DB_STATEMENT_TIMEOUT_MS))
    lock_timeout_ms = max(0, int(settings.INGEST_DB_LOCK_TIMEOUT_MS))
    db.execute(
        INGEST_DB_TIMEOUTS_SQL,
        {
            "statement_timeout": f"{statement_timeout_ms}ms",
            "lock_timeout": f"{lock_timeout_ms}ms",
        },
    )


def _should_sync_collector_metadata(lagoon_id: str) -> bool:
    interval_sec = max(
        0.0,
        float(settings.INGEST_COLLECTOR_SYNC_INTERVAL_SEC),
    )
    if interval_sec == 0:
        return True

    now_monotonic = monotonic()
    with _collector_sync_lock:
        last_attempt = _collector_sync_last_attempt.get(lagoon_id)
        if (
            last_attempt is not None
            and now_monotonic - last_attempt < interval_sec
        ):
            return False
        _collector_sync_last_attempt[lagoon_id] = now_monotonic
    return True


def _reset_collector_sync_throttle() -> None:
    with _collector_sync_lock:
        _collector_sync_last_attempt.clear()


def _sync_collector_tags_and_alarms(
    *,
    db,
    lagoon_id: str,
    source_ts: datetime,
    tags: dict,
) -> tuple[int, int]:
    if not tags:
        return 0, 0

    try:
        # Collector metadata is optional for the realtime path. A savepoint
        # keeps a lock/statement failure from poisoning the ingest transaction.
        with db.begin_nested():
            result = db.execute(
                SYNC_COLLECTOR_TAGS_SQL,
                {
                    "lagoon_id": lagoon_id,
                    "source_ts": source_ts,
                    "tags_payload": tags,
                },
            ).scalar_one_or_none()

        if isinstance(result, dict):
            return (
                int(result.get("registered_tags") or 0),
                int(result.get("new_alarm_definitions") or 0),
            )
    except Exception:
        logger.exception(
            "[INGEST SYNC ERROR] lagoon=%s",
            lagoon_id,
        )
    return 0, 0


def _persist_ingest(
    lagoon_id: str,
    requested_product_type: str | None,
    ts_dt: datetime,
    tags: dict,
):
    notification_jobs = []
    transition_count = 0
    minute_row_count = 0
    event_count = 0

    db = SessionLocal()
    try:
        _configure_ingest_transaction(db=db)
        _ensure_ingest_product(
            db=db,
            lagoon_id=lagoon_id,
            requested_product_type=requested_product_type,
        )
        sync_registered_tags = 0
        sync_new_alarm_definitions = 0
        if tags and _should_sync_collector_metadata(lagoon_id):
            (
                sync_registered_tags,
                sync_new_alarm_definitions,
            ) = _sync_collector_tags_and_alarms(
                db=db,
                lagoon_id=lagoon_id,
                source_ts=ts_dt,
                tags=tags,
            )

        pump_last_on_updates, ingest_summary = ingest(
            lagoon_id=lagoon_id,
            ts=ts_dt,
            tags=tags,
            db=db,
        )
        minute_row_count = ingest_summary.minute_rows
        event_count = ingest_summary.detected_event_count

        transitions, notification_jobs = evaluate_alarms(
            payload={
                "lagoon_id": lagoon_id,
                "timestamp": ts_dt,
                "tags": tags,
            },
            db=db,
        )
        transition_count = len(transitions)

        db.commit()
        if sync_registered_tags or sync_new_alarm_definitions:
            logger.info(
                "[INGEST SYNC] lagoon=%s tags=%s alarms=%s",
                lagoon_id,
                sync_registered_tags,
                sync_new_alarm_definitions,
            )
        log_persisted_ingest(ingest_summary)
        log_persisted_alarm_transitions(transitions)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    if notification_jobs:
        try:
            dispatch_notifications(notification_jobs)
        except Exception:
            logger.exception(
                "[NOTIFY ERROR] lagoon=%s reason=dispatch_failed",
                lagoon_id,
            )

    return pump_last_on_updates, transition_count, minute_row_count, event_count


@router.post("/ingest/scada")
async def ingest_scada(
    payload: IngestPayload,
    request: Request,
    _: None = Depends(verify_collector_key),
):
    state = request.app.state.state_store
    ws = request.app.state.ws_manager

    lagoon_id = normalize_lagoon_id(payload.lagoon_id)
    if not lagoon_id:
        raise HTTPException(status_code=422, detail="lagoon_id is required")

    product_type = payload.product_type.value if payload.product_type else None
    tags = payload.tags or {}

    # ===== UTC timestamp =====
    if payload.timestamp:
        ts_dt = payload.timestamp
        if ts_dt.tzinfo is None:
            ts_dt = ts_dt.replace(tzinfo=timezone.utc)
    else:
        ts_dt = datetime.now(timezone.utc)

    ts_iso = ts_dt.isoformat()
    client_ip = request.client.host if request.client else "-"

    if not state.accepts_update_ts(lagoon_id, ts_iso):
        return {"ok": True}

    try:
        (
            pump_last_on_updates,
            alarm_transition_count,
            minute_row_count,
            scada_event_count,
        ) = await asyncio.wait_for(
            asyncio.to_thread(
                _persist_ingest,
                lagoon_id,
                product_type,
                ts_dt,
                tags,
            ),
            timeout=INGEST_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "[INGEST TIMEOUT] lagoon=%s product=%s ip=%s timeout_sec=%s",
            lagoon_id,
            product_type or "-",
            client_ip,
            INGEST_TIMEOUT_SEC,
        )
        raise HTTPException(
            status_code=504,
            detail="Ingest timeout",
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "[INGEST ERROR] lagoon=%s product=%s ip=%s",
            lagoon_id,
            product_type or "-",
            client_ip,
        )
        raise

    if alarm_transition_count:
        logger.info(
            "[INGEST ALARMS] lagoon=%s product=%s count=%s",
            lagoon_id,
            product_type or "-",
            alarm_transition_count,
        )

    logger.debug(
        "[INGEST OK] lagoon=%s product=%s ip=%s rows=%s events=%s alarms=%s at=%s",
        lagoon_id,
        product_type or "-",
        client_ip,
        minute_row_count,
        scada_event_count,
        alarm_transition_count,
        ts_iso,
    )

    # ===== REALTIME =====
    state_updated = await state.update(
        lagoon_id=lagoon_id,
        tags=tags,
        ts=ts_iso,
        pump_last_on_updates=pump_last_on_updates,
    )
    if not state_updated:
        return {"ok": True}

    # ===== WS =====
    await ws.broadcast(
        lagoon_id,
        await state.tick_payload(lagoon_id),
    )

    return {"ok": True}
