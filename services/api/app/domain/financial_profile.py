from pydantic import BaseModel, Field, field_validator

from app.domain.enums import JobStability, PayFrequency

SCHEMA_VERSION = 1


class Location(BaseModel):
    city: str = Field(min_length=1)
    state: str = Field(min_length=2, max_length=2)
    postalCode: str = Field(min_length=1)


class Household(BaseModel):
    dependents: int = Field(ge=0)
    jobStability: JobStability


class Income(BaseModel):
    monthlyTakeHomeCents: int = Field(gt=0)
    payFrequency: PayFrequency


class Expenses(BaseModel):
    rentCents: int = Field(ge=0)
    utilitiesCents: int = Field(ge=0)
    groceriesCents: int = Field(ge=0)
    transportationCents: int = Field(ge=0)
    insuranceCents: int = Field(ge=0)
    subscriptionsCents: int = Field(ge=0)
    discretionaryCents: int = Field(ge=0)
    otherEssentialCents: int = Field(ge=0)


class Debt(BaseModel):
    minimumPaymentsCents: int = Field(ge=0)
    creditCardBalanceCents: int = Field(ge=0)
    availableCreditCents: int = Field(ge=0)
    creditAprBps: int = Field(ge=0, le=10000)


class Savings(BaseModel):
    liquidCents: int = Field(ge=0)


class FinancialProfile(BaseModel):
    """Canonical Phase 1 money contract. Money is integer cents; APR is basis points."""

    schemaVersion: int
    currency: str
    location: Location
    household: Household
    income: Income
    expenses: Expenses
    debt: Debt
    savings: Savings

    @field_validator("schemaVersion")
    @classmethod
    def schema_version_must_be_supported(cls, value: int) -> int:
        if value != SCHEMA_VERSION:
            raise ValueError(f"schemaVersion must be {SCHEMA_VERSION}")
        return value

    @field_validator("currency")
    @classmethod
    def currency_must_be_usd(cls, value: str) -> str:
        if value != "USD":
            raise ValueError('currency must be "USD" for Phase 1')
        return value
