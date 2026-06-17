"""
Customer 360 profile — assembled from prior decisions, payment events, and bureau data.
Stored in Redis with a 24h TTL; a profile_version timestamp on each decision row
ensures audit reproducibility even after the cache evicts a stale profile.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PaymentHistory(BaseModel):
    month: str          # YYYY-MM
    on_time: bool
    amount: float
    days_past_due: int = 0


class ExposureSummary(BaseModel):
    product_type: str   # CREDIT_CARD | PERSONAL_LOAN | MORTGAGE | AUTO
    current_balance: float
    credit_limit: float
    utilization: float
    account_age_months: int
    status: str         # CURRENT | DELINQUENT | CLOSED


class CustomerProfile(BaseModel):
    customer_id: str
    profile_version: str        # ISO timestamp of build — stored on decision for audit replay

    existing_accounts: int = 0
    total_exposure: float = 0.0

    # Trend data — most recent month last
    utilization_trend_3m: list[float] = Field(default_factory=list)

    # 0.0 = all late / 1.0 = always on time
    payment_consistency_score: float = 0.5

    prior_applications: list[dict] = Field(default_factory=list)
    channel_interactions: list[dict] = Field(default_factory=list)

    # Lifetime value estimate in USD
    estimated_clv: float = 0.0

    last_bureau_refresh: Optional[datetime] = None
    exposure_summary: list[ExposureSummary] = Field(default_factory=list)
    payment_history: list[PaymentHistory] = Field(default_factory=list)

    is_new_customer: bool = True


def empty_profile(customer_id: str = "unknown") -> CustomerProfile:
    """Return a safe empty profile for customers with no history."""
    return CustomerProfile(
        customer_id=customer_id,
        profile_version="none",
        is_new_customer=True,
    )
