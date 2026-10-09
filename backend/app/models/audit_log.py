import uuid
from sqlalchemy import Column, String, JSON, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.db.base_class import Base
from app.models.tenant import company_id_column


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # NULL for platform-level events (e.g. a platform admin deactivating a company).
    company_id = company_id_column(nullable=True)
    user_id = Column(String(36), ForeignKey("users.id", onupdate="CASCADE", ondelete="SET NULL"))
    action = Column(String(100), nullable=False)
    entity = Column(String(100), nullable=False)
    entity_id = Column(String(36))
    details = Column(JSON)
    ip_address = Column(String(45))
    created_at = Column(DateTime, server_default=func.now())
