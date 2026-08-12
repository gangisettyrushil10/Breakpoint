"""The `patch_profile` tool: let the user correct their budget mid-conversation.

Merges a partial profile into the working profile and revalidates the whole
thing. Nothing here decides anything — it only edits the inputs that
`simulate` will later run on.
"""

from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.agent.tools.errors import validation_detail
from app.domain.enums import JobStability, PayFrequency
from app.domain.financial_profile import FinancialProfile

TOOL_NAME = "patch_profile"

TOOL_DESCRIPTION = """\
Update one or more fields on the user's saved financial profile, then use
`simulate` again to see what changed.

Only send the fields the user actually told you about — everything you omit is
left exactly as it was. All money is in integer cents ($1,250.00 is 125000).

Use this when the user corrects a number or describes a change to their
situation ("rent is going up to $1,800", "I've got about $3k saved now").
Never guess at a value to fill a gap: if you don't know a number, ask."""


class _Partial(BaseModel):
    """Base for patch fragments: unknown keys are an error, not a silent no-op."""

    model_config = {"extra": "forbid"}


class PartialLocation(_Partial):
    city: str | None = None
    state: str | None = None
    postalCode: str | None = None


class PartialHousehold(_Partial):
    dependents: int | None = Field(default=None, ge=0)
    jobStability: JobStability | None = None


class PartialIncome(_Partial):
    monthlyTakeHomeCents: int | None = Field(default=None, gt=0)
    payFrequency: PayFrequency | None = None


class PartialExpenses(_Partial):
    rentCents: int | None = Field(default=None, ge=0)
    utilitiesCents: int | None = Field(default=None, ge=0)
    groceriesCents: int | None = Field(default=None, ge=0)
    transportationCents: int | None = Field(default=None, ge=0)
    insuranceCents: int | None = Field(default=None, ge=0)
    subscriptionsCents: int | None = Field(default=None, ge=0)
    discretionaryCents: int | None = Field(default=None, ge=0)
    otherEssentialCents: int | None = Field(default=None, ge=0)


class PartialDebt(_Partial):
    minimumPaymentsCents: int | None = Field(default=None, ge=0)
    creditCardBalanceCents: int | None = Field(default=None, ge=0)
    availableCreditCents: int | None = Field(default=None, ge=0)
    creditAprBps: int | None = Field(default=None, ge=0, le=10000)


class PartialSavings(_Partial):
    liquidCents: int | None = Field(default=None, ge=0)


class PatchProfileInput(_Partial):
    """Every group is optional; within a group, every field is optional."""

    location: PartialLocation | None = None
    household: PartialHousehold | None = None
    income: PartialIncome | None = None
    expenses: PartialExpenses | None = None
    debt: PartialDebt | None = None
    savings: PartialSavings | None = None


def input_schema() -> dict:
    return PatchProfileInput.model_json_schema()


def _changed_paths(patch: PatchProfileInput) -> list[str]:
    """Dotted paths the model explicitly set — `None` means 'not mentioned'."""
    paths: list[str] = []
    for group_name, group in patch.model_dump(exclude_none=True).items():
        for field_name in group:
            paths.append(f"{group_name}.{field_name}")
    return sorted(paths)


def apply_patch(
    profile: FinancialProfile, patch: PatchProfileInput
) -> FinancialProfile:
    """Shallow-merge each group, then revalidate the whole profile."""
    merged: dict[str, Any] = profile.model_dump()

    for group_name, group in patch.model_dump(exclude_none=True).items():
        merged[group_name] = {**merged[group_name], **group}

    return FinancialProfile.model_validate(merged)


def handle(profile: FinancialProfile, arguments: dict) -> dict:
    try:
        patch = PatchProfileInput.model_validate(arguments or {})
    except ValidationError as error:
        return {
            "ok": False,
            "error": "invalid_arguments",
            "detail": validation_detail(error),
        }

    changed = _changed_paths(patch)
    if not changed:
        return {
            "ok": False,
            "error": "empty_patch",
            "detail": "No fields were provided. Send at least one field to update.",
        }

    try:
        updated = apply_patch(profile, patch)
    except ValidationError as error:
        return {
            "ok": False,
            "error": "invalid_profile",
            "detail": validation_detail(error),
        }

    return {"ok": True, "changed": changed, "profile": updated.model_dump()}
