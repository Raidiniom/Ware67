from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    categories,
    suppliers,
    locations,
    products,
    transactions,
    inventory_adjustments,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(categories.router)
api_router.include_router(suppliers.router)
api_router.include_router(locations.router)
api_router.include_router(products.router)
api_router.include_router(transactions.router)
api_router.include_router(inventory_adjustments.router)
