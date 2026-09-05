"""Explain the resilience score without asking the model to reverse-engineer it."""

from app.domain.financial_profile import FinancialProfile
from app.simulation.baseline import compute_baseline
from app.simulation.scoring import (
    BUFFER_MARGIN_FOR_FULL_SCORE,
    RUNWAY_MONTHS_FOR_FULL_SCORE,
    compute_resilience_score,
)

TOOL_NAME = "explain_resilience_score"

TOOL_DESCRIPTION = """\
Explain exactly how the user's current 0-100 resilience score was built. Returns
the three subscores, their weights and weighted points, the user's underlying
measurements, and the weakest component. Use this when someone asks why their
score is what it is or what is holding it back. The server performs every
calculation; do not recompute or combine these figures yourself."""


def input_schema() -> dict:
    return {"type": "object", "properties": {}, "additionalProperties": False}


def handle(profile: FinancialProfile, arguments: dict) -> dict:
    if arguments:
        return {
            "ok": False,
            "error": "invalid_arguments",
            "detail": "This tool takes no arguments.",
        }

    baseline = compute_baseline(profile)
    score = compute_resilience_score(profile)
    income = profile.income.monthlyTakeHomeCents
    total_credit = (
        profile.debt.creditCardBalanceCents + profile.debt.availableCreditCents
    )
    buffer_margin_percent = round(baseline.monthlyBufferCents / income * 100, 2)
    credit_available_percent = (
        100.0
        if total_credit == 0
        else round(profile.debt.availableCreditCents / total_credit * 100, 2)
    )

    components = [
        {
            "id": "runway",
            "label": "Emergency runway",
            "subscore": score.runwaySubscore,
            "weightPercent": 50,
            "weightedPoints": round(score.runwaySubscore * 0.5, 1),
            "runwayMonths": baseline.runwayMonths,
            "fullScoreAtMonths": RUNWAY_MONTHS_FOR_FULL_SCORE,
        },
        {
            "id": "buffer",
            "label": "Monthly buffer",
            "subscore": score.bufferSubscore,
            "weightPercent": 30,
            "weightedPoints": round(score.bufferSubscore * 0.3, 1),
            "monthlyBufferCents": baseline.monthlyBufferCents,
            "bufferMarginPercent": buffer_margin_percent,
            "fullScoreAtPercent": BUFFER_MARGIN_FOR_FULL_SCORE * 100,
        },
        {
            "id": "credit",
            "label": "Available credit",
            "subscore": score.creditSubscore,
            "weightPercent": 20,
            "weightedPoints": round(score.creditSubscore * 0.2, 1),
            "availableCreditCents": profile.debt.availableCreditCents,
            "totalCreditLimitCents": total_credit,
            "availableCreditPercent": credit_available_percent,
        },
    ]
    weakest = min(components, key=lambda component: component["subscore"])

    return {
        "ok": True,
        "score": score.score,
        "rating": (
            "resilient"
            if score.score >= 85
            else "stable"
            if score.score >= 70
            else "strained"
            if score.score >= 50
            else "critical"
        ),
        "formula": "50% runway + 30% monthly buffer + 20% available credit",
        "components": components,
        "weakestComponent": weakest["id"],
        "writesProfile": False,
    }
