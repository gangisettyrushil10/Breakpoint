from app.domain.financial_profile import FinancialProfile
from app.scenarios.library import layoff, merge_schedules, rent_hike
from app.simulation.monthly import MonthState
from app.simulation.prevention import build_prevention_plan
from app.simulation.runner import MonthlyAdjustments, run_months
from app.simulation.scoring import find_breaking_point


def base_payload() -> dict:
    return {
        "schemaVersion": 1,
        "currency": "USD",
        "location": {"city": "Dallas", "state": "TX", "postalCode": "75201"},
        "household": {"dependents": 0, "jobStability": "stable"},
        "income": {"monthlyTakeHomeCents": 435000, "payFrequency": "biweekly"},
        "expenses": {
            "rentCents": 155000,
            "utilitiesCents": 22000,
            "groceriesCents": 45000,
            "transportationCents": 20000,
            "insuranceCents": 18000,
            "subscriptionsCents": 5000,
            "discretionaryCents": 30000,
            "otherEssentialCents": 0,
        },
        "debt": {
            "minimumPaymentsCents": 30000,
            "creditCardBalanceCents": 0,
            "availableCreditCents": 200000,
            "creditAprBps": 2299,
        },
        "savings": {"liquidCents": 200000},
    }


def moderate_profile_payload() -> dict:
    """Under the credit limit, but a full layoff overwhelms it with a large overage."""
    return base_payload()


def already_over_limit_profile_payload() -> dict:
    """Existing credit card debt already exceeds available credit before any shock."""
    payload = base_payload()
    payload["income"]["monthlyTakeHomeCents"] = 330_000
    payload["savings"]["liquidCents"] = 50_000
    payload["debt"]["availableCreditCents"] = 20_000
    payload["debt"]["creditCardBalanceCents"] = 180_000
    return payload


def comfortable_profile_payload() -> dict:
    payload = base_payload()
    payload["savings"]["liquidCents"] = 3_000_000
    return payload


def feasible_profile_payload() -> dict:
    """Thin buffer + a mild rent hike -> small overage a realistic cut can cover."""
    return {
        "schemaVersion": 1,
        "currency": "USD",
        "location": {"city": "Dallas", "state": "TX", "postalCode": "75201"},
        "household": {"dependents": 0, "jobStability": "stable"},
        "income": {"monthlyTakeHomeCents": 300_000, "payFrequency": "biweekly"},
        "expenses": {
            "rentCents": 150_000,
            "utilitiesCents": 15_000,
            "groceriesCents": 40_000,
            "transportationCents": 20_000,
            "insuranceCents": 15_000,
            "subscriptionsCents": 2_000,
            "discretionaryCents": 5_000,
            "otherEssentialCents": 0,
        },
        "debt": {
            "minimumPaymentsCents": 48_000,
            "creditCardBalanceCents": 0,
            "availableCreditCents": 20_000,
            "creditAprBps": 1999,
        },
        "savings": {"liquidCents": 10_000},
    }


def test_no_plan_when_breaking_point_not_triggered() -> None:
    profile = FinancialProfile.model_validate(comfortable_profile_payload())
    candidates = [("layoff", layoff(start_month=0, duration_months=3, replacement_income_cents=0))]
    breaking_point = find_breaking_point(profile, months=3, candidate_scenarios=candidates)

    assert breaking_point.triggered is False
    assert build_prevention_plan(profile, breaking_point) is None


def test_already_over_credit_limit_yields_no_achievable_levers() -> None:
    profile = FinancialProfile.model_validate(already_over_limit_profile_payload())
    candidates = [("layoff", layoff(start_month=0, duration_months=3, replacement_income_cents=0))]
    breaking_point = find_breaking_point(profile, months=3, candidate_scenarios=candidates)
    assert breaking_point.triggered is True  # sanity check on the fixture

    plan = build_prevention_plan(profile, breaking_point)

    assert plan is not None
    assert plan.alreadyOverCreditLimit is True
    assert plan.extraSavingsCentsNeeded is None
    assert plan.monthlyCutCentsNeeded is None
    assert plan.monthlyCutFeasible is None
    assert plan.cuttableMonthlyCents == 35_000  # discretionary 30_000 + subscriptions 5_000


def test_extra_savings_and_infeasible_cut_for_large_shock() -> None:
    profile = FinancialProfile.model_validate(moderate_profile_payload())
    candidates = [("layoff", layoff(start_month=0, duration_months=3, replacement_income_cents=0))]
    breaking_point = find_breaking_point(profile, months=3, candidate_scenarios=candidates)
    assert breaking_point.triggered is True
    assert breaking_point.monthIndex == 1
    assert breaking_point.overageCents == 250_000

    plan = build_prevention_plan(profile, breaking_point)
    assert plan is not None
    assert plan.alreadyOverCreditLimit is False
    assert plan.extraSavingsCentsNeeded == 250_000
    assert plan.monthlyCutCentsNeeded == 125_000  # ceil(250_000 / 2 months)
    assert plan.cuttableMonthlyCents == 35_000
    assert plan.monthlyCutFeasible is False  # 125_000 > 35_000, can't cut your way out of a layoff

    # Prove extraSavingsCentsNeeded actually works: bump starting cash and rerun.
    boosted_profile = profile.model_copy(deep=True)
    boosted_profile.savings.liquidCents += plan.extraSavingsCentsNeeded
    boosted_start = MonthState(
        cashCents=boosted_profile.savings.liquidCents,
        creditCardBalanceCents=boosted_profile.debt.creditCardBalanceCents,
    )
    # Only the trigger month (and everything before it) is guaranteed fixed —
    # find_breaking_point stops at the *first* severe-risk month, and this
    # layoff keeps going for a 3rd month, which can trigger its own overage.
    schedule = layoff(start_month=0, duration_months=3, replacement_income_cents=0)
    result = run_months(boosted_profile, boosted_start, months=3, schedule=schedule)
    for month_result in result.months[: breaking_point.monthIndex + 1]:
        assert month_result.state.creditCardBalanceCents <= boosted_profile.debt.availableCreditCents


def test_extra_savings_and_feasible_cut_for_small_shock() -> None:
    profile = FinancialProfile.model_validate(feasible_profile_payload())
    candidates = [("rent_hike", rent_hike(start_month=0, duration_months=5, increase_cents=12_000))]
    breaking_point = find_breaking_point(profile, months=5, candidate_scenarios=candidates)
    assert breaking_point.triggered is True
    assert breaking_point.monthIndex == 4
    assert breaking_point.overageCents == 5_000

    plan = build_prevention_plan(profile, breaking_point)
    assert plan is not None
    assert plan.alreadyOverCreditLimit is False
    assert plan.extraSavingsCentsNeeded == 5_000
    assert plan.monthlyCutCentsNeeded == 1_000  # ceil(5_000 / 5 months)
    assert plan.cuttableMonthlyCents == 7_000  # discretionary 5_000 + subscriptions 2_000
    assert plan.monthlyCutFeasible is True

    # Prove extraSavingsCentsNeeded prevents the breaking point.
    boosted_profile = profile.model_copy(deep=True)
    boosted_profile.savings.liquidCents += plan.extraSavingsCentsNeeded
    boosted_start = MonthState(
        cashCents=boosted_profile.savings.liquidCents,
        creditCardBalanceCents=boosted_profile.debt.creditCardBalanceCents,
    )
    hike_schedule = rent_hike(start_month=0, duration_months=5, increase_cents=12_000)
    result = run_months(boosted_profile, boosted_start, months=5, schedule=hike_schedule)
    for month_result in result.months:
        assert month_result.state.creditCardBalanceCents <= boosted_profile.debt.availableCreditCents

    # Prove monthlyCutCentsNeeded prevents the breaking point when applied every month.
    cut_schedule = merge_schedules(
        hike_schedule,
        {m: MonthlyAdjustments(expenseDeltaCents=-plan.monthlyCutCentsNeeded) for m in range(5)},
    )
    start = MonthState(
        cashCents=profile.savings.liquidCents,
        creditCardBalanceCents=profile.debt.creditCardBalanceCents,
    )
    cut_result = run_months(profile, start, months=5, schedule=cut_schedule)
    for month_result in cut_result.months:
        assert month_result.state.creditCardBalanceCents <= profile.debt.availableCreditCents
