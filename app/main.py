import app.models
import app.auth.model

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ws.routes import router as ws_router
from app.routers.ingest import router as ingest_router
from app.routers.scada_event import router as scada_event_router
from app.scada.history.router import router as scada_history_router

from app.state.store import RealtimeStateStore
from app.ws.manager import WebSocketManager
from app.persist.worker import PersistWorker
from app.db.session import SessionLocal
from app.monitor.scada_watchdog import ScadaStallWatchdog
from app.repositories.scada_event_repository import ScadaEventRepository
from app.models.scada_event import ScadaEvent
from app.services.ingest_service import initialize_last_state

from app.auth.auth import router as auth_router

from app.models.lagoon import Lagoon

@asynccontextmanager
async def lifespan(app: FastAPI):

    app.state.state_store = RealtimeStateStore()
    app.state.ws_manager = WebSocketManager()

    db = SessionLocal()

    try:
        # =====================================================
        # Cargar timezones desde tabla lagoons
        # =====================================================
        lagoons = db.query(Lagoon).all()

        for lagoon in lagoons:
            app.state.state_store.set_lagoon_timezone(
                lagoon_id=lagoon.id,
                timezone_str=lagoon.timezone,
            )

        print(f"[BOOT] Timezones cargadas: {len(lagoons)}")

        # =====================================================
        #  Detectar lagunas con eventos
        # =====================================================
        lagoon_ids = (
            db.query(ScadaEvent.lagoon_id)
            .distinct()
            .all()
        )

        lagoon_ids = [row[0] for row in lagoon_ids]

        print(f"[BOOT] Lagunas detectadas en eventos: {lagoon_ids}")

        # =====================================================
        #  Precargar último start_ts por bomba
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

                print(
                    f"[BOOT] pump_last_on inicializado → "
                    f"{lagoon_id} ({len(last_times)} tags)"
                )
            else:
                print(f"[BOOT] sin estados previos → {lagoon_id}")

    finally:
        db.close()

    app.state.scada_watchdog = ScadaStallWatchdog()
    await app.state.scada_watchdog.start()

    try:
        yield
    finally:
        await app.state.scada_watchdog.stop()




app = FastAPI(lifespan=lifespan)


app.include_router(ingest_router)
app.include_router(ws_router)
app.include_router(scada_event_router)
app.include_router(scada_history_router)
app.include_router(auth_router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://192.168.1.22",
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:5174",
        "http://localhost:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
