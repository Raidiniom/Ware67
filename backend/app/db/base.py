from app.db.base_class import Base

# Import models so Alembic's autogenerate can see them
from app.models.role import Role
from app.models.user import User
from app.models.category import Category
from app.models.supplier import Supplier
from app.models.location import Location
from app.models.product import Product
from app.models.transaction import Transaction
from app.models.inventory_adjustment import InventoryAdjustment
