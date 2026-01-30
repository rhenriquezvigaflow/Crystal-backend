# app/deps/realtime.py
from fastapi import Request

def get_state_store(request: Request):
    return request.app.state.state_store

def get_ws_manager(request: Request):
    return request.app.state.ws_manager
