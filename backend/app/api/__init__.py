"""FastAPI routers."""

from fastapi import APIRouter

from app.api import compare, health, optimize, scenarios, simulate

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(scenarios.router)
api_router.include_router(optimize.router)
api_router.include_router(simulate.router)
api_router.include_router(compare.router)
