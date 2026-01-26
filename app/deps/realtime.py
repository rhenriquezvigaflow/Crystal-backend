from app.realtime.state_store import StateStore
from app.realtime.ws_manager import WebSocketManager

state_store = StateStore()
ws_manager = WebSocketManager()


def get_state_store():
    return state_store


def get_ws_manager():
    return ws_manager
