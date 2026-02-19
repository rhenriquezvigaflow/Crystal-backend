from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    DATABASE_URL: str
    LOG_LEVEL: str = "INFO"
    COLLECTOR_API_KEY: str = Field(
        ...,
        description="API Key used by PLC collectors to ingest data"
    )

    class Config:
        env_file = ".env"
        extra = "forbid"   


settings = Settings()
