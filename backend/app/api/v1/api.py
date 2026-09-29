from fastapi import APIRouter
from app.api.v1.endpoints import auth, management, products, categories

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(products.router)
api_router.include_router(management.router)
api_router.include_router(categories.router)
