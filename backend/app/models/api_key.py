import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, JSON, String
from sqlalchemy.sql import func

from app.db.base_class import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(150), nullable=False)
    key_prefix = Column(String(32), nullable=False, unique=True, index=True)
    key_hash = Column(String(64), nullable=False, unique=True)
    scopes = Column(JSON, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(
        String(36),
        ForeignKey("users.id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )
    expires_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
