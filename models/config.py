from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint, func
from services.db import Base

class Config(Base):
    __tablename__ = "config"
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), nullable=False)
    value = Column(String, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("key", name="uq_config_key"),)
