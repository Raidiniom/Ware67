import uuid

from sqlalchemy import Column, DateTime, Integer, Numeric, String, Text
from sqlalchemy.sql import func

from app.db.base_class import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sku = Column(String(100), nullable=False, unique=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    # The existing MySQL table enforces these three foreign keys. They are
    # intentionally mapped as scalar IDs until the Category, Supplier, and
    # Location ORM models are added by their respective feature modules.
    category_id = Column(String(36), nullable=True)
    supplier_id = Column(String(36), nullable=True)
    location_id = Column(String(36), nullable=True)
    unit = Column(String(50), nullable=True)
    price = Column(Numeric(12, 2), nullable=False, default=0)
    reorder_level = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
