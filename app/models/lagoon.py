from sqlalchemy import Column, String, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime



from app.models.base import Base

class Lagoon(Base):
    __tablename__ = "lagoons"

    id = Column(String, primary_key=True)
    name = Column(String)
    plc_type = Column(String)
    timezone = Column(String)