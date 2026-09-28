from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.schemas.simulator import ScenarioInfo, SimulateIncidentRequest, SimulateIncidentResponse
from backend.app.simulator.engine import IncidentSimulatorEngine
from backend.app.simulator.historical_seeds import get_historical_seeds
from backend.app.simulator.scenarios import get_all_scenarios

router = APIRouter()


@router.post(
    "/simulate",
    response_model=SimulateIncidentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Simulate a production incident scenario",
)
async def simulate_incident(
    request: SimulateIncidentRequest,
    db: AsyncSession = Depends(get_db),
) -> SimulateIncidentResponse:
    """Generates a realistic production incident scenario without requiring Azure, Kubernetes, or PagerDuty.
    
    The generated incident feeds directly into the same operational pipeline as real alerts.
    """
    engine = IncidentSimulatorEngine(db)
    try:
        response = await engine.simulate(request)
        return response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/simulate/scenarios",
    response_model=List[ScenarioInfo],
    summary="List available incident simulation scenarios",
)
async def list_simulation_scenarios() -> List[ScenarioInfo]:
    """Returns the catalog of all available deterministic incident simulation scenarios."""
    return get_all_scenarios()


@router.get(
    "/simulate/historical-seeds",
    response_model=List[Dict[str, Any]],
    summary="List historical incident seeds for Hindsight memory",
)
async def list_historical_seeds() -> List[Dict[str, Any]]:
    """Returns organizational incident experiences formatted for Hindsight retention."""
    return get_historical_seeds()
