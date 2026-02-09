import app.models 
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ws.routes import router as ws_router
from app.routers.ingest import router as ingest_router
from app.scada.history.router import router as scada_history_router

from app.state.store import RealtimeStateStore
from app.ws.manager import WebSocketManager
from app.persist.worker import PersistWorker
from app.db.session import SessionLocal
from app.repositories.scada_event_repository import ScadaEventRepository


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ==========================
    # Singletons
    # ==========================
    app.state.state_store = RealtimeStateStore()
    app.state.ws_manager = WebSocketManager()  # ← CORREGIDO

    # ==========================
    # Preload desde BD
    # ==========================
    db = SessionLocal()
    try:
        lagoon_id = "costa_del_lago"
        last_start_by_pump = (
            ScadaEventRepository.get_last_start_ts_by_lagoon(db, lagoon_id)
        )
        if last_start_by_pump:
            app.state.state_store.pump_last_on[lagoon_id] = last_start_by_pump
        print("[BOOT] pump_last_on precargado:", last_start_by_pump)
    finally:
        db.close()

    # ==========================
    # Persist worker
    # ==========================
    app.state.persist_worker = PersistWorker()
    await app.state.persist_worker.start()
    print("[BOOT] PersistWorker iniciado")

    yield

    await app.state.persist_worker.stop()
    print("[BOOT] PersistWorker detenido")


app = FastAPI(lifespan=lifespan)

# ======================================================
# Routers
# ======================================================
app.include_router(ingest_router)
app.include_router(ws_router)
app.include_router(scada_history_router)

# ======================================================
# CORS
# ======================================================
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
