from fastapi import Request, WebSocket


# ===== HTTP (REST) =====
def get_state_store_http(request: Request):
    return request.app.state.state_store


def get_ws_manager_http(request: Request):
    return request.app.state.ws_manager


# ===== WEBSOCKET =====
def get_state_store_ws(websocket: WebSocket):
    return websocket.app.state.state_store


def get_ws_manager_ws(websocket: WebSocket):
    return websocket.app.state.ws_manager