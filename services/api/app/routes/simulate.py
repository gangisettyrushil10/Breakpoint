from pydantic import BaseModel, Field, field_validator

from fastapi import APIRouter

from app.domain.financial_profile import FinancialProfile
from app.scenarios.library import SCENARIO_PRESETS, merge_schedules
from app.simulation.baseline import BaselineResult, compute_baseline
from app.simulation.monthly import MonthState
from app.simulation.runner import SimulationResult, run_months
from app.simulation.scoring import (
    BreakingPoint,
    ResilienceScore,
    compute_resilience_score,
    find_breaking_point,
)

router = APIRouter(tags=["simulate"])


class SimulateRequest(BaseModel):
    profile: FinancialProfile
    months: int = Field(default=6, ge=1, le=12)
    scenarios: list[str] = Field(default_factory=list)

    @field_validator("scenarios")
    @classmethod
    def scenarios_must_be_known(cls, value: list[str]) -> list[str]:
        unknown = [name for name in value if name not in SCENARIO_PRESETS]
        if unknown:
            known = sorted(SCENARIO_PRESETS)
            raise ValueError(f"unknown scenario(s) {unknown}; choose from {known}")
        return value


class SimulateResponse(BaseModel):
    baseline: BaselineResult
    resilience: ResilienceScore
    simulation: SimulationResult
    breakingPoint: BreakingPoint


@router.post("/simulate", response_model=SimulateResponse)
def simulate(request: SimulateRequest) -> SimulateResponse:
    profile = request.profile
    months = request.months

    baseline = compute_baseline(profile)
    resilience = compute_resilience_score(profile)

    named_schedules = [(name, SCENARIO_PRESETS[name](months)) for name in request.scenarios]
    combined_schedule = merge_schedules(*(schedule for _, schedule in named_schedules))

    start = MonthState(
        cashCents=profile.savings.liquidCents,
        creditCardBalanceCents=profile.debt.creditCardBalanceCents,
    )
    simulation = run_months(profile, start, months, combined_schedule)

    breaking_point_candidates = named_schedules or [
        (name, preset(months)) for name, preset in SCENARIO_PRESETS.items()
    ]
    breaking_point = find_breaking_point(profile, months, breaking_point_candidates)

    return SimulateResponse(
        baseline=baseline,
        resilience=resilience,
        simulation=simulation,
        breakingPoint=breaking_point,
    )
