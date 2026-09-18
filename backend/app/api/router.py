from fastapi import APIRouter

from app.api.endpoints import auth
from app.api.endpoints import applications
from app.api.endpoints import sync
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(applications.router, prefix="/applications", tags=["applications"])
api_router.include_router(sync.router, prefix="/sync", tags=["sync"])