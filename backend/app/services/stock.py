from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.product import Product


def apply_stock_change(db: Session, product_id: str, delta: int) -> tuple[Product, int, int]:
    """Locks the product row, applies delta, and refuses to go negative.
    The caller commits, so stock update, history row, and audit row land together."""
    product = (
        db.query(Product)
        .filter(Product.id == product_id)
        .with_for_update()
        .one_or_none()
    )
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")

    before = product.current_stock
    after = before + delta
    if after < 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Insufficient stock: {before} on hand, this change would leave {after}",
        )
    product.current_stock = after
    return product, before, after