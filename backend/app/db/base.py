from app.db.base_class import Base  # noqa: F401

# Import every model so Base.metadata knows about all tables.
# Alembic autogenerate (alembic/env.py) relies on this file.
from app.models.role import Role  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.category import Category  # noqa: F401
from app.models.supplier import Supplier  # noqa: F401
from app.models.location import Location  # noqa: F401
from app.models.product import Product  # noqa: F401
from app.models.transaction import Transaction  # noqa: F401
from app.models.inventory_adjustment import InventoryAdjustment  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.api_key import ApiKey  # noqa: F401
