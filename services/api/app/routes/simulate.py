from pydantic import BaseModel, Field, model_validator

from fastapi import APIRouter

from app.domain.financial_profile import FinancialProfile
from app.scenarios.library import SCENARIO_PRESETS, merge_schedules
from app.scenarios.schema import ScenarioInput, resolve_scenario, scenario_last_month
from app.simulation.baseline import BaselineResult, compute_baseline
from app.simulation.monthly import MonthState
from app.simulation.prevention import PreventionPlan, build_prevention_plan
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
    scenarios: list[ScenarioInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def scenarios_must_fit_within_months(self) -> "SimulateRequest":
        out_of_range = [
            scenario
            for scenario in self.scenarios
            if scenario_last_month(scenario) >= self.months
        ]
        if out_of_range:
            raise ValueError(
                f"{len(out_of_range)} scenario(s) extend past months={self.months}; "
                "every scenario's month index must be < months"
            )
        return self


class SimulateResponse(BaseModel):
    baseline: BaselineResult
    resilience: ResilienceScore
    simulation: SimulationResult
    breakingPoint: BreakingPoint
    preventionPlan: PreventionPlan | None


@router.post("/simulate", response_model=SimulateResponse)
def simulate(request: SimulateRequest) -> SimulateResponse:
    profile = request.profile
    months = request.months

    baseline = compute_baseline(profile)
    resilience = compute_resilience_score(profile)

    named_schedules = [
        (f"{scenario.type}#{i}", resolve_scenario(scenario))
        for i, scenario in enumerate(request.scenarios)
    ]
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
    prevention_plan = build_prevention_plan(profile, breaking_point)

    return SimulateResponse(
        baseline=baseline,
        resilience=resilience,
        simulation=simulation,
        breakingPoint=breaking_point,
        preventionPlan=prevention_plan,
    )
