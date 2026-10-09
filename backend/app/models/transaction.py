import uuid
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.db.base_class import Base
from app.models.tenant import company_id_column


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = company_id_column()
    product_id = Column(String(36), ForeignKey("products.id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False)
    # Exactly one of user_id / api_key_id is set: a person in the app, or a
    # partner integration acting through an API key.
    user_id = Column(String(36), ForeignKey("users.id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=True)
    api_key_id = Column(String(36), ForeignKey("api_keys.id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=True)
    type = Column(String(20), nullable=False)  # STOCK_IN | STOCK_OUT
    quantity = Column(Integer, nullable=False)
    reference_type = Column(String(50))
    reference_id = Column(String(100))
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
