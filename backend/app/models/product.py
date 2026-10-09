import uuid
from sqlalchemy import Column, String, Text, Integer, Numeric, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.db.base_class import Base
from app.models.tenant import company_id_column


class Product(Base):
    __tablename__ = "products"
    # Two companies may both sell an "SKU-001".
    __table_args__ = (UniqueConstraint("company_id", "sku", name="uq_products_company_sku"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = company_id_column()
    sku = Column(String(100), nullable=False)
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
