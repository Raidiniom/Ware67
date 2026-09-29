from pydantic import BaseModel, ConfigDict


def blank_to_none(v):
    """Strip strings; turn '' into None (for optional fields)."""
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


class ProductBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    sku: str
    name: str
    current_stock: int