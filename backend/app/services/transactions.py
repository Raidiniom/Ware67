from sqlalchemy.orm import Session

from app.models.api_key import ApiKey
from app.models.product import Product
from app.models.transaction import Transaction
from app.models.user import User


def transaction_rows(db: Session, company_id: str):
    """One company's transactions as (Transaction, product name, sku, user name, key name).

    Shared by the transaction history and the inbound dashboard feed, so joins
    and company scoping stay the same in both.
    """
    # Outer joins: a row is made either by a user or by a partner API key.
    return (db.query(Transaction, Product.name, Product.sku, User.name, ApiKey.name)
            .join(Product, Product.id == Transaction.product_id)
            .outerjoin(User, User.id == Transaction.user_id)
            .outerjoin(ApiKey, ApiKey.id == Transaction.api_key_id)
            .filter(Transaction.company_id == company_id))
