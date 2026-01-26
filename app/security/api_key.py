from fastapi import Depends, Header, HTTPException
from app.core.config import settings


def verify_collector_key(x_api_key: str = Header(...)):
    if x_api_key != settings.COLLECTOR_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid collector key")
