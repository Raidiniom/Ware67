import enum
import uuid

from sqlalchemy import Column, DateTime, Enum as SAEnum, ForeignKey, JSON, String, Text
from sqlalchemy.sql import func

from app.db.base_class import Base
from app.models.tenant import company_id_column


class ApiKeyStatus(str, enum.Enum):
    """Lifecycle of a partner API key:

    PENDING  -> a company asked for a key; nothing to use yet
    APPROVED -> the platform team approved; the company may reveal it once
    REJECTED -> the platform team said no
    ACTIVE   -> revealed: the secret exists and authenticates
    REVOKED  -> withdrawn or revoked by the company or the platform team
    LAPSED   -> approved but not revealed in time

    "Expired" is not stored: it's an ACTIVE key whose expires_at has passed.
    """
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    LAPSED = "LAPSED"


def _user_fk(nullable: bool = True) -> Column:
    return Column(String(36), ForeignKey("users.id", onupdate="CASCADE", ondelete="RESTRICT"),
                  nullable=nullable)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # The company whose data this key can read and change.
    company_id = company_id_column()
    name = Column(String(150), nullable=False)
    purpose = Column(Text, nullable=True)
    status = Column(SAEnum(ApiKeyStatus), nullable=False, default=ApiKeyStatus.PENDING)

    # What the company asked for, and what the platform team granted.
    requested_scopes = Column(JSON, nullable=False)
    scopes = Column(JSON, nullable=True)

    # Only set at reveal: until then there is no secret anywhere.
    key_prefix = Column(String(32), nullable=True, unique=True, index=True)
    key_hash = Column(String(64), nullable=True, unique=True)

    requested_by = _user_fk(nullable=False)
    reviewed_by = _user_fk()
    reviewed_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    reveal_deadline = Column(DateTime, nullable=True)
    revealed_by = _user_fk()
    revealed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    revoked_by = _user_fk()
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
