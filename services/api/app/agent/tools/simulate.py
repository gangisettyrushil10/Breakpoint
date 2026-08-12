"""The `simulate` tool: the agent's only source of truth for numbers.

This wraps the exact same deterministic pipeline that `POST /simulate` runs.
The engine itself (`app.simulation.*`, `app.scenarios.*`) stays LLM-free — this
module only orchestrates it and hands back JSON the model can quote verbatim.

`tests/test_agent_tools.py` asserts this tool and the HTTP route produce
byte-identical output for the same inputs. If you change one, change both.
"""

from pydantic import BaseModel, Field, ValidationError, model_validator

from app.agent.tools.errors import validation_detail
from app.domain.financial_profile import FinancialProfile
from app.routes.simulate import SimulateResponse
from app.scenarios.library import SCENARIO_PRESETS, merge_schedules
from app.scenarios.schema import ScenarioInput, resolve_scenario, scenario_last_month
from app.simulation.baseline import compute_baseline
from app.simulation.monthly import MonthState
from app.simulation.prevention import build_prevention_plan
from app.simulation.runner import run_months
from app.simulation.scoring import compute_resilience_score, find_breaking_point

TOOL_NAME = "simulate"

TOOL_DESCRIPTION = """\
Run the deterministic BreakPoint stress-test engine on the user's saved financial
profile and return every number the conversation is allowed to use: baseline
cash flow, the 0-100 resilience score and its three subscores, the month-by-month
cash and credit trajectory, the breaking point, and the prevention plan.

Call this before stating any score, runway, breaking point, or dollar figure about
this user. You do not have access to their budget except through this tool, and
you may not estimate these numbers yourself.

You do not pass the profile — the server supplies it. You choose the horizon and
which hardship scenarios to stack. Pass an empty `scenarios` list to see the
no-shock baseline; pass one or more scenarios to stress-test specific events.
When `scenarios` is empty the engine searches its own preset shocks (car repair,
medical bill, rent hike, layoff) to find the smallest stack that breaks the
budget, so an empty call is the right way to answer "what would break me?"."""


class SimulateToolInput(BaseModel):
    """What the model is allowed to choose. The profile is server-supplied."""

    months: int = Field(
        default=6,
        ge=1,
        le=12,
        description=(
            "How many months to project, 1-12. Omit this unless the user asked "
            "about a specific window — the server fills in the horizon they are "
            "currently looking at, so sending a value overrides their view."
        ),
    )
    scenarios: list[ScenarioInput] = Field(
        default_factory=list,
        description=(
            "Hardship scenarios to apply. Every month index must be less than "
            "`months`. Leave empty for the baseline projection."
        ),
    )

    @model_validator(mode="after")
    def scenarios_must_fit_within_months(self) -> "SimulateToolInput":
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


def input_schema() -> dict:
    """JSON Schema handed to the model as the tool's `input_schema`.

    `months` has its advertised default stripped. `_run_tools` layers the
    model's arguments *over* the server's (`{**tool_defaults, **call.arguments}`),
    so a schema default is actively harmful here: the model reads `"default": 6`,
    helpfully echoes it, and silently overrides the horizon the user is actually
    looking at. Observed in practice — the dashboard showed 12 months while the
    reply described 6, and both were grounded, so no guardrail could catch it.

    The pydantic default stays for the in-process call path, where nothing else
    supplies one.
    """
    schema = SimulateToolInput.model_json_schema()
    schema.get("properties", {}).get("months", {}).pop("default", None)
    return schema


def run_simulate(
    profile: FinancialProfile,
    months: int = 6,
    scenarios: list[ScenarioInput] | None = None,
) -> SimulateResponse:
    """Same orchestration as `POST /simulate`, callable in-process."""
    scenarios = scenarios or []

    baseline = compute_baseline(profile)
    resilience = compute_resilience_score(profile)

    named_schedules = [
        (f"{scenario.type}#{i}", resolve_scenario(scenario))
        for i, scenario in enumerate(scenarios)
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


def handle(profile: FinancialProfile, arguments: dict) -> dict:
    """Registry entry point. Returns the tool_result payload for the model.

    Validation failures come back as data, not exceptions — the model should get
    a chance to correct a bad month index rather than crashing the request.
    """
    try:
        parsed = SimulateToolInput.model_validate(arguments or {})
    except ValidationError as error:
        return {
            "ok": False,
            "error": "invalid_arguments",
            "detail": validation_detail(error),
        }

    result = run_simulate(profile, parsed.months, parsed.scenarios)

    return {
        "ok": True,
        "months": parsed.months,
        "scenarios": [scenario.model_dump() for scenario in parsed.scenarios],
        "result": result.model_dump(),
    }
