from enum import Enum


class JobStability(str, Enum):
    STABLE = "stable"
    CONTRACT = "contract"
    UNSTABLE = "unstable"


class PayFrequency(str, Enum):
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    SEMIMONTHLY = "semimonthly"
    MONTHLY = "monthly"
