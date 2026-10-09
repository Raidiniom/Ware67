import uuid
from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.sql import func
from app.db.base_class import Base
from app.models.tenant import company_id_column


class Location(Base):
    __tablename__ = "locations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = company_id_column()
    name = Column(String(150), nullable=False)
    description = Column(Text)
    warehouse = Column(String(100))
    aisle = Column(String(50))
    shelf = Column(String(50))
    bin = Column(String(50))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())