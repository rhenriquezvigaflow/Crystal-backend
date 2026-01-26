# app/main.py
from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.db.session import engine
from app.models.base import Base
import app.models

from app.routers.ingest import router as ingest_router, get_state_store, get_ws_manager
from app.routers.health import router as health_router
from app.ws.routes import router as ws_router
from app.routers import scada_read
from app.routers import scada_ws


from app.state.store import RealtimeStateStore
from app.ws.manager import WebSocketManager
from app.persist.worker import PersistWorker


state_store = RealtimeStateStore()
ws_manager = WebSocketManager()
persist_worker = PersistWorker()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await persist_worker.start()
    yield
    await persist_worker.stop()

app = FastAPI(
    title="Crystal Lagoons SCADA Backend",
    lifespan=lifespan,
)

app.dependency_overrides[get_state_store] = lambda: state_store
app.dependency_overrides[get_ws_manager] = lambda: ws_manager

# =========================
# DB INIT
# =========================

Base.metadata.create_all(bind=engine)

# =========================
# ROUTERS
# =========================

app.include_router(health_router)
app.include_router(ingest_router)
app.include_router(ws_router)
app.include_router(scada_read.router)
app.include_router(scada_ws.router)

