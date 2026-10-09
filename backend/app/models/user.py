import uuid
import enum
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from app.models.tenant import company_id_column


class UserRole(str, enum.Enum):
    """Roles inside a company, lowest to highest."""
    GUEST = "GUEST"
    STAFF = "STAFF"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"
    OWNER = "OWNER"


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(150), nullable=False)
    email = Column(String(150), nullable=False, unique=True, index=True)
    password = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole), nullable=False, default=UserRole.GUEST)
    role_id = Column(String(36), ForeignKey("roles.id", onupdate="CASCADE", ondelete="SET NULL"), nullable=True)
    # NULL only for platform admins, who belong to no company.
    company_id = company_id_column(nullable=True)
    # The WARE67 team: manages companies and API keys, never sees inventory.
    is_platform_admin = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    role_obj = relationship("Role", back_populates="users")
