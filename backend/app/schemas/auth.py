from datetime import datetime
from pydantic import BaseModel, EmailStr, ConfigDict, Field, field_validator


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: EmailStr
    role: str
    role_id: str | None = None
    company_id: str | None = None
    is_platform_admin: bool = False
    is_active: bool
    created_at: datetime


class RegisterRequest(BaseModel):
    """Signing up creates a new company with this account as its owner."""
    name: str = Field(min_length=1, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    company_name: str = Field(min_length=1, max_length=150)

    @field_validator("name", "company_name")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class OnboardRequest(BaseModel):
    user_id: str
    role: str
    is_active: bool = True


class UpdateRoleRequest(BaseModel):
    user_id: str
    role: str


class UpdateStatusRequest(BaseModel):
    user_id: str
    is_active: bool


class MessageResponse(BaseModel):
    message: str


class UserListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime
