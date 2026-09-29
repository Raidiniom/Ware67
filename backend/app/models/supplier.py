import uuid
from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.sql import func
from app.db.base_class import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(150), nullable=False)
    contact_person = Column(String(150))
    contact_number = Column(String(50))
    email = Column(String(150))
    address = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())