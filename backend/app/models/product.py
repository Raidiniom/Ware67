import uuid
from sqlalchemy import Column, String, Text, Integer, Numeric, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.db.base_class import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sku = Column(String(100), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    category_id = Column(String(36), ForeignKey("categories.id", onupdate="CASCADE", ondelete="SET NULL"))
    supplier_id = Column(String(36), ForeignKey("suppliers.id", onupdate="CASCADE", ondelete="SET NULL"))
    location_id = Column(String(36), ForeignKey("locations.id", onupdate="CASCADE", ondelete="SET NULL"))
    unit = Column(String(50))
    price = Column(Numeric(12, 2), nullable=False, default=0)
    reorder_level = Column(Integer, nullable=False, default=0)
    current_stock = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())