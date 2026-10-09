import uuid
from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.sql import func
from app.db.base_class import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(150), nullable=False)
    # Deactivating a company locks out its members and its API keys at once.
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

