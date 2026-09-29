from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth, management, products, 
    categories, suppliers, locations, 
    transactions, adjustments, audit_logs)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(products.router)
api_router.include_router(management.router)
api_router.include_router(categories.router)
api_router.include_router(suppliers.router)
api_router.include_router(locations.router)
api_router.include_router(transactions.router)
api_router.include_router(adjustments.router)
api_router.include_router(audit_logs.router)
