"""Optimization endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.services import run_optimization
from app.core.limits import simulation_slot
from app.schemas import OptimizeRequest, OptimizeResponse

router = APIRouter()


@router.post("/optimize", response_model=OptimizeResponse)
def post_optimize(request: OptimizeRequest) -> OptimizeResponse:
    try:
        with simulation_slot():
            return run_optimization(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
