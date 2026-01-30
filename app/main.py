# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.ws.routes import router as ws_router
from app.routers.ingest import router as ingest_router

from app.state.store import RealtimeStateStore
from app.ws.manager import WebSocketManager

from app.db.session import SessionLocal
from app.repositories.scada_event_repository import ScadaEventRepository
from app.persist.worker import PersistWorker
from fastapi.middleware.cors import CORSMiddleware


# SCADA History Router
from app.scada.history.router import router as scada_history_router



@asynccontextmanager
async def lifespan(app: FastAPI):
    # ==========================
    # Singletons
    # ==========================
    app.state.state_store = RealtimeStateStore()
    app.state.ws_manager = WebSocketManager()

 
    db = SessionLocal()
    try:
        lagoon_id = "costa_del_lago"  # 👈 luego lo puedes generalizar

        last_start_by_pump = (
            ScadaEventRepository.get_last_start_ts_by_lagoon(
                db, lagoon_id
            )
        )

        if last_start_by_pump:
            app.state.state_store.pump_last_on[lagoon_id] = last_start_by_pump

        print("[BOOT] pump_last_on precargado:", last_start_by_pump)

    finally:
        db.close()

    # ==========================
    # Worker de persistencia
    # ==========================
    app.state.persist_worker = PersistWorker()
    await app.state.persist_worker.start()
    print("[BOOT] PersistWorker iniciado")

    yield

    await app.state.persist_worker.stop()


api = FastAPI(lifespan=lifespan)

api.include_router(ingest_router)
api.include_router(ws_router)

api.include_router(scada_history_router)

api.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)