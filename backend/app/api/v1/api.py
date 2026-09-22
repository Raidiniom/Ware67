from fastapi import APIRouter
from app.api.v1.endpoints import auth, products

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(products.router)
