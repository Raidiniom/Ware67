"""Column shared by every company-owned table. Kept free of app imports so
any model can use it without import cycles."""
from sqlalchemy import Column, ForeignKey, String


def company_id_column(index: bool = True, nullable: bool = False) -> Column:
    """The company_id every company-owned table carries. RESTRICT: a company
    with data can be deactivated but never deleted out from under its rows."""
    return Column(
        String(36),
        ForeignKey("companies.id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=nullable,
        index=index,
    )
