import uuid
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.db.base_class import Base
from app.models.tenant import company_id_column


class InventoryAdjustment(Base):
    __tablename__ = "inventory_adjustments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = company_id_column()
    product_id = Column(String(36), ForeignKey("products.id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False)
    quantity_change = Column(Integer, nullable=False)
    reason = Column(String(150))
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())