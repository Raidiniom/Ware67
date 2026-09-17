import uuid
import enum
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class TransactionType(str, enum.Enum):
    STOCK_IN = "STOCK_IN"
    STOCK_OUT = "STOCK_OUT"


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id = Column(String(36), ForeignKey("products.id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False)
    type = Column(SAEnum(TransactionType), nullable=False)
    quantity = Column(Integer, nullable=False)
    reference_type = Column(String(50), nullable=True)
    reference_id = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    product = relationship("Product")
    user = relationship("User")
