from app.db.base_class import Base

# Import models so Alembic's autogenerate can see them
from app.models.role import Role
from app.models.user import User