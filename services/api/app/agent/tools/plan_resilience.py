"""Find minimum deterministic changes that reach a requested resilience score."""

from collections.abc import Callable

from pydantic import BaseModel, Field, ValidationError

from app.agent.tools.errors import validation_detail
from app.domain.financial_profile import FinancialProfile
from app.simulation.baseline import compute_baseline
from app.simulation.scoring import compute_resilience_score

TOOL_NAME = "plan_resilience_target"

TOOL_DESCRIPTION = """\
Find the smallest verified changes that would raise the user's resilience score
to a target without modifying their saved profile. The engine independently searches three
paths: extra liquid savings, additional monthly take-home income, and a monthly
cut limited to subscriptions plus discretionary spending. Use this for "how do
I get to 70?" or "what single change helps most?". Quote the returned values;
never calculate a target or delta yourself."""


class PlanResilienceInput(BaseModel):
    targetScore: int = Field(default=70, ge=0, le=100)
    maxAdditionalSavingsCents: int = Field(default=10_000_000, ge=0)
    maxMonthlyChangeCents: int = Field(default=1_000_000, ge=0)


def input_schema() -> dict:
    return PlanResilienceInput.model_json_schema()


def _profile_with(profile: FinancialProfile, path: str, delta_cents: int) -> FinancialProfile:
    payload = profile.model_dump()
    if path == "savings":
        payload["savings"]["liquidCents"] += delta_cents
    elif path == "income":
        payload["income"]["monthlyTakeHomeCents"] += delta_cents
    elif path == "flexible_cut":
        remaining = delta_cents
        for field in ("subscriptionsCents", "discretionaryCents"):
            reduction = min(payload["expenses"][field], remaining)
            payload["expenses"][field] -= reduction
            remaining -= reduction
    return FinancialProfile.model_validate(payload)


def _minimum_change(
    score_for: Callable[[int], int], target: int, maximum: int
) -> int | None:
    """Return the minimum whole-dollar change that reaches target."""
    if score_for(0) >= target:
        return 0
    maximum_units = maximum // 100
    if score_for(maximum_units * 100) < target:
        return None

    low, high = 0, maximum_units
    while low < high:
        midpoint = (low + high) // 2
        if score_for(midpoint * 100) >= target:
            high = midpoint
        else:
            low = midpoint + 1
    return low * 100


def _result_for(
    profile: FinancialProfile,
    path: str,
    label: str,
    target: int,
    maximum: int,
) -> dict:
    def score_for(delta_cents: int) -> int:
        changed = _profile_with(profile, path, delta_cents)
        return compute_resilience_score(changed).score

    required = _minimum_change(score_for, target, maximum)
    if required is None:
        return {
            "id": path,
            "label": label,
            "feasible": False,
            "maximumTestedCents": maximum,
        }

    changed = _profile_with(profile, path, required)
    baseline = compute_baseline(changed)
    allocation = None
    if path == "flexible_cut":
        allocation = {
            "subscriptionsCutCents": min(
                profile.expenses.subscriptionsCents, required
            ),
            "discretionaryCutCents": max(
                0, required - profile.expenses.subscriptionsCents
            ),
        }

    return {
        "id": path,
        "label": label,
        "feasible": True,
        "requiredCents": required,
        "resultingScore": compute_resilience_score(changed).score,
        "resultingRunwayMonths": baseline.runwayMonths,
        "resultingMonthlyBufferCents": baseline.monthlyBufferCents,
        "allocation": allocation,
    }


def handle(profile: FinancialProfile, arguments: dict) -> dict:
    try:
        parsed = PlanResilienceInput.model_validate(arguments or {})
    except ValidationError as error:
        return {
            "ok": False,
            "error": "invalid_arguments",
            "detail": validation_detail(error),
        }

    current = compute_resilience_score(profile)
    flexible = (
        profile.expenses.subscriptionsCents + profile.expenses.discretionaryCents
    )
    pathways = [
        _result_for(
            profile,
            "savings",
            "Add liquid savings",
            parsed.targetScore,
            parsed.maxAdditionalSavingsCents,
        ),
        _result_for(
            profile,
            "income",
            "Increase monthly take-home",
            parsed.targetScore,
            parsed.maxMonthlyChangeCents,
        ),
        _result_for(
            profile,
            "flexible_cut",
            "Reduce flexible monthly spending",
            parsed.targetScore,
            min(parsed.maxMonthlyChangeCents, flexible),
        ),
    ]

    return {
        "ok": True,
        "currentScore": current.score,
        "targetScore": parsed.targetScore,
        "alreadyAtTarget": current.score >= parsed.targetScore,
        "pathways": pathways,
        "writesProfile": False,
        "note": "Monthly cuts are limited to subscriptions and discretionary spending.",
    }
