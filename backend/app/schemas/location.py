from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.schemas.common import blank_to_none


class LocationBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    warehouse: str | None = Field(default=None, max_length=100)
    aisle: str | None = Field(default=None, max_length=50)
    shelf: str | None = Field(default=None, max_length=50)
    bin: str | None = Field(default=None, max_length=50)

    @field_validator("name", "description", "warehouse", "aisle", "shelf", "bin", mode="before")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator("description", "warehouse", "aisle", "shelf", "bin", mode="before")
    @classmethod
    def _blank(cls, v):
        return blank_to_none(v)


class LocationCreate(LocationBase):
    pass


class LocationUpdate(LocationBase):
    pass


class LocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str | None
    warehouse: str | None
    aisle: str | None
    shelf: str | None
    bin: str | None
    product_count: int = 0
    created_at: datetime | None
    updated_at: datetime | None


class LocationList(BaseModel):
    items: list[LocationRead]
    total: int