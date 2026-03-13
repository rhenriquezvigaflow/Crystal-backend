from app.routers.small.chemicals import router as chemicals_router
from app.routers.small.control import router as control_router
from app.routers.small.lagoons import router as lagoons_router

__all__ = ["lagoons_router", "control_router", "chemicals_router"]
