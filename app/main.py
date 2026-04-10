import app.models
import app.alarms.models

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core.logging import get_logger
from app.ws.routes import router as ws_router
from app.auth.auth import router as auth_router
from app.auth.routers.lagoons_router import router as rbac_lagoons_router
from app.routers.health import router as health_router
from app.routers.ingest import router as ingest_router
from app.routers.alarm_thresholds import router as alarm_thresholds_router
from app.routers.scada_layouts import router as scada_layouts_router
from app.routers.scada_read import router as scada_read_router
from app.routers.scada_event import router as scada_event_router
from app.scada.history.router import router as scada_history_router
from app.routers.crystal.lagoons import router as crystal_lagoons_router
from app.routers.small.lagoons import router as small_lagoons_router
from app.routers.small.control import router as small_control_router
from app.routers.small.chemicals import router as small_chemicals_router

from app.state.store import RealtimeStateStore
from app.ws.manager import WebSocketManager
from app.db.session import SessionLocal
from app.alarms.silence_monitor import AlarmLagoonSignalMonitor
from app.monitor.scada_watchdog import ScadaStallWatchdog
from app.repositories.scada_event_repository import ScadaEventRepository
from app.models.lagoon import Lagoon
from app.models.scada_event import ScadaEvent

logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):

    app.state.state_store = RealtimeStateStore()
    app.state.ws_manager = WebSocketManager()

    db = SessionLocal()

    try:
        # =====================================================
        # Cargar metadata de lagunas desde tabla lagoons
        # =====================================================
        lagoons = db.query(Lagoon).filter(Lagoon.enable.is_(True)).all()

        for lagoon in lagoons:
            app.state.state_store.set_lagoon_timezone(
                lagoon_id=lagoon.id,
                timezone_str=lagoon.timezone,
            )
            app.state.state_store.set_lagoon_layout(
                lagoon_id=lagoon.id,
                layout_name=lagoon.scada_layout,
            )

        logger.info("[BOOT] lagoon_runtime_metadata_loaded count=%s", len(lagoons))

        # =====================================================
        #  Detectar lagunas con eventos
        # =====================================================
        lagoon_ids = (
            db.query(ScadaEvent.lagoon_id)
            .distinct()
            .all()
        )

        lagoon_ids = [row[0] for row in lagoon_ids]

        logger.info("[BOOT] event_lagoons_detected lagoon_ids=%s", lagoon_ids)

        # =====================================================
        #  Precargar ultimo start_ts por bomba
        # =====================================================
        for lagoon_id in lagoon_ids:

            last_times = (
                ScadaEventRepository.get_last_event_time_by_lagoon(db, lagoon_id)
            )

            if last_times:
                for tag_id, ts in last_times.items():
                    app.state.state_store.set_pump_last_on(
                        lagoon_id=lagoon_id,
                        tag_id=tag_id,
                        ts=ts
                    )

                logger.info(
                    "[BOOT] pump_last_on_initialized lagoon_id=%s tags=%s",
                    lagoon_id,
                    len(last_times),
                )
            else:
                logger.info(
                    "[BOOT] pump_last_on_skipped lagoon_id=%s reason=no_previous_state",
                    lagoon_id,
                )

    finally:
        db.close()

    app.state.scada_watchdog = ScadaStallWatchdog()
    await app.state.scada_watchdog.start()
    app.state.alarm_lagoon_signal_monitor = AlarmLagoonSignalMonitor()
    await app.state.alarm_lagoon_signal_monitor.start()

    try:
        yield
    finally:
        await app.state.alarm_lagoon_signal_monitor.stop()
        await app.state.scada_watchdog.stop()




app = FastAPI(lifespan=lifespan)

proxy_trusted_hosts = [
    host.strip()
    for host in os.getenv(
        "PROXY_TRUSTED_HOSTS",
        "127.0.0.1,::1,localhost",
    ).split(",")
    if host.strip()
]

app.add_middleware(
    ProxyHeadersMiddleware,
    trusted_hosts=proxy_trusted_hosts,
)

origins = [
    "https://localhost",
    "http://localhost",
    "http://localhost:5173",
    "https://localhost:5173",
    "http://192.168.1.22",
    "http://localhost:3000",
    "http://localhost:5174",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(rbac_lagoons_router)
app.include_router(ingest_router)
app.include_router(alarm_thresholds_router)
app.include_router(alarm_thresholds_router, prefix="/crystal")
app.include_router(alarm_thresholds_router, prefix="/small")
app.include_router(alarm_thresholds_router, prefix="/api")
app.include_router(alarm_thresholds_router, prefix="/api/crystal")
app.include_router(alarm_thresholds_router, prefix="/api/small")
app.include_router(ws_router)
app.include_router(scada_layouts_router)
app.include_router(scada_layouts_router, prefix="/api")
app.include_router(scada_read_router)
app.include_router(scada_event_router)
app.include_router(scada_history_router)
app.include_router(crystal_lagoons_router)
app.include_router(small_lagoons_router)
app.include_router(small_control_router)
app.include_router(small_chemicals_router)
