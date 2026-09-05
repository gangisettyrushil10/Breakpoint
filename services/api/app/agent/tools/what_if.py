"""The `what_if` tool: price a permanent change without committing to it.

The product has two different notions of harm, and until this existed only one of
them was reachable in conversation:

* a **one-off shock** — a layoff, a repair — moves the *breaking point*. That is
  `simulate` with scenarios, and the agent could already do it.
* a **permanent change** — fuel up $40 a month, rent up $200, a subscription
  cancelled — moves the *resilience score and the runway*, because
  `compute_resilience_score` reads the profile and nothing else. There was no way
  to ask that question: `simulate` takes no profile, and the only tool that could
  change one was `patch_profile`, which *saves*. Asking "what if petrol went up?"
  would have overwritten the user's real budget to answer a hypothetical.

So this runs the same engine twice — once as things are, once over a modified
copy — and reports both plus the difference. Nothing is written anywhere.

**Every delta is computed here.** The model subtracting two scores is exactly the
arithmetic ARCHITECTURE.md forbids, and "that costs you two points" is precisely
the sentence a user will act on, so it has to come back as a tool result the
grounding ledger can vouch for.
"""

from pydantic import BaseModel, Field, ValidationError

from app.agent.tools.errors import validation_detail
from app.agent.tools.patch_profile import PatchProfileInput, apply_patch
from app.agent.tools.simulate import run_simulate
from app.domain.financial_profile import FinancialProfile
from app.scenarios.schema import ScenarioInput, scenario_last_month

TOOL_NAME = "what_if"

TOOL_DESCRIPTION = """\
Try a permanent change to the user's budget and report what it would do, without
saving it.

Use this whenever the question is about an ongoing change rather than a one-off
emergency: "what if petrol goes up 50 cents a gallon", "what if my rent rises
$200", "what if I cancel my subscriptions", "what if I earned $300 more". The
server runs the engine twice and returns both results and the difference.

**Almost always use `changeBy`, not `change`.** People describe these as a
movement — "rent goes up $200" — not as a new total, and working out the new
total means adding $200 to a figure you would have to remember correctly. Send
the movement (`{"expenses": {"rentCents": 20000}}`) and the server does the sum.
Reach for `change` only when someone states an actual new figure ("if rent were
$1,900").

Use `simulate` with scenarios instead for one-off events — a layoff, a car
repair. Those move the breaking point rather than the score.

This tool changes nothing. The user's saved budget is untouched, so you can try
several ideas in a row and compare them. If they decide they want to keep one,
call `patch_profile` with it.

Do not work out the difference between two numbers yourself — this returns every
delta already calculated."""


class _Relative(BaseModel):
    """Amounts to add to what is already there. Negatives are the point.

    Deliberately not `PatchProfileInput`: every money field there is `ge=0`,
    because a rent of minus four hundred is nonsense. A *change* of minus four
    hundred is not — it is someone moving somewhere cheaper.
    """

    model_config = {"extra": "forbid"}


class RelativeHousehold(_Relative):
    dependents: int | None = None


class RelativeIncome(_Relative):
    monthlyTakeHomeCents: int | None = None


class RelativeExpenses(_Relative):
    rentCents: int | None = None
    utilitiesCents: int | None = None
    groceriesCents: int | None = None
    transportationCents: int | None = None
    insuranceCents: int | None = None
    subscriptionsCents: int | None = None
    discretionaryCents: int | None = None
    otherEssentialCents: int | None = None


class RelativeDebt(_Relative):
    minimumPaymentsCents: int | None = None
    creditCardBalanceCents: int | None = None
    availableCreditCents: int | None = None
    creditAprBps: int | None = None


class RelativeSavings(_Relative):
    liquidCents: int | None = None


class RelativeChange(_Relative):
    """Every group optional; within a group, every field optional."""

    household: RelativeHousehold | None = None
    income: RelativeIncome | None = None
    expenses: RelativeExpenses | None = None
    debt: RelativeDebt | None = None
    savings: RelativeSavings | None = None


class WhatIfInput(BaseModel):
    """A hypothetical change, plus optionally the shocks to test it against."""

    change: PatchProfileInput | None = Field(
        default=None,
        description=(
            "Set a field to a NEW TOTAL. Use for 'what if rent were $1,900'. "
            "Same shape `patch_profile` takes."
        ),
    )
    changeBy: RelativeChange | None = Field(
        default=None,
        description=(
            "Add an amount to what is already there — the usual case. Use for "
            "'rent goes up $200' (send 20000), 'petrol costs me $30 more' "
            "(30000), 'I cancel my $65 subscriptions' (send -6500). Negative "
            "means less. Do NOT work out the new total yourself; send the "
            "change and the server adds it."
        ),
    )
    scenarios: list[ScenarioInput] = Field(
        default_factory=list,
        description=(
            "Optional hardship scenarios to run against BOTH versions, so the "
            "comparison is like for like. Leave empty to compare the ordinary "
            "month, which is what moves the score."
        ),
    )
    months: int = Field(default=12, ge=1, le=12)


def input_schema() -> dict:
    return WhatIfInput.model_json_schema()


def _apply_relative(
    profile: FinancialProfile, change_by: RelativeChange
) -> FinancialProfile:
    """Add each amount to what is already there, then revalidate the whole thing.

    Revalidation is what catches a change that lands somewhere impossible —
    cancelling $200 of a $65 subscription bill leaves minus $135, and the
    profile model rejects it, which becomes a correctable error rather than a
    budget quietly containing a negative.
    """
    merged: dict = profile.model_dump()

    for group_name, group in change_by.model_dump(exclude_none=True).items():
        for field, delta in group.items():
            merged[group_name][field] = merged[group_name][field] + delta

    return FinancialProfile.model_validate(merged)


def _breaking_point_summary(result) -> dict:
    point = result.breakingPoint
    return {
        "triggered": point.triggered,
        "monthIndex": point.monthIndex,
        "shockCombination": point.shockCombination,
        "overageCents": point.overageCents,
    }


def handle(profile: FinancialProfile, arguments: dict) -> dict:
    try:
        parsed = WhatIfInput.model_validate(arguments or {})
    except ValidationError as error:
        return {
            "ok": False,
            "error": "invalid_arguments",
            "detail": validation_detail(error),
        }

    out_of_range = [
        scenario
        for scenario in parsed.scenarios
        if scenario_last_month(scenario) >= parsed.months
    ]
    if out_of_range:
        return {
            "ok": False,
            "error": "invalid_arguments",
            "detail": (
                f"{len(out_of_range)} scenario(s) extend past months={parsed.months}"
            ),
        }

    if parsed.change is None and parsed.changeBy is None:
        return {
            "ok": False,
            "error": "invalid_arguments",
            "detail": "Send either `change` (new totals) or `changeBy` (amounts to add).",
        }

    try:
        modified = profile
        if parsed.change is not None:
            modified = apply_patch(modified, parsed.change)
        if parsed.changeBy is not None:
            modified = _apply_relative(modified, parsed.changeBy)
    except ValidationError as error:
        # A change that produces an impossible budget — rent below zero, income
        # cut to nothing — is data the model can correct, not a crash.
        return {
            "ok": False,
            "error": "invalid_change",
            "detail": validation_detail(error),
        }

    before = run_simulate(profile, parsed.months, parsed.scenarios)
    after = run_simulate(modified, parsed.months, parsed.scenarios)

    # Runway is None when essentials are zero — nothing to run out of. Treating
    # that as 0.0 would report a wild delta against a real number.
    before_runway = before.baseline.runwayMonths
    after_runway = after.baseline.runwayMonths
    runway_delta = (
        None
        if before_runway is None or after_runway is None
        else round(after_runway - before_runway, 2)
    )

    changed = sorted(
        set(parsed.change.model_dump(exclude_none=True) if parsed.change else {})
        | set(parsed.changeBy.model_dump(exclude_none=True) if parsed.changeBy else {})
    )

    return {
        "ok": True,
        "changed": changed,
        "writesProfile": False,
        "score": {
            "before": before.resilience.score,
            "after": after.resilience.score,
            "delta": after.resilience.score - before.resilience.score,
        },
        "runwayMonths": {
            "before": before_runway,
            "after": after_runway,
            "delta": runway_delta,
        },
        "monthlyBufferCents": {
            "before": before.baseline.monthlyBufferCents,
            "after": after.baseline.monthlyBufferCents,
            "delta": (
                after.baseline.monthlyBufferCents - before.baseline.monthlyBufferCents
            ),
        },
        "breakingPoint": {
            "before": _breaking_point_summary(before),
            "after": _breaking_point_summary(after),
        },
        "preventionPlanAfter": (
            after.preventionPlan.model_dump() if after.preventionPlan else None
        ),
    }
