from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ── Origination ───────────────────────────────────────────────────────────────

class ApplicationRequest(BaseModel):
    name: str
    customerId: Optional[str] = None    # links to existing customer relationship
    creditScore: int
    utilization: float
    addressMismatch: Optional[bool] = False
    delinquencies: Optional[int] = 0
    annualIncome: Optional[float] = None
    channel: Optional[str] = "WEB"


class ApplicationReceivedEvent(BaseModel):
    correlationId: str
    receivedAt: datetime
    channel: str
    application: ApplicationRequest
    decisionType: str = "ORIGINATION"
    eventVersion: str = "1.0"


# ── Limit Review ──────────────────────────────────────────────────────────────

class LimitReviewRequest(BaseModel):
    customerId: str
    currentCreditLimit: float
    accountAgeMonths: int
    recentUtilizationAvg: float             # average over last 3 months
    paymentsMadeOnTime: int                  # out of paymentsCounted
    paymentsCounted: int = 12               # window evaluated
    missedPayments: int = 0
    currentBalance: float = 0.0


class LimitReviewTriggeredEvent(BaseModel):
    correlationId: str
    triggeredAt: datetime
    customerId: str
    request: LimitReviewRequest
    decisionType: str = "LIMIT_REVIEW"
    eventVersion: str = "1.0"


# ── Delinquency Treatment ─────────────────────────────────────────────────────

class DelinquencyTreatmentRequest(BaseModel):
    customerId: str
    daysPastDue: int
    amountPastDue: float
    currentBalance: float
    currentCreditLimit: float
    previousTreatments: list[str] = Field(default_factory=list)  # ["REMINDER", ...]
    contactAttempts: int = 0


class DelinquencyTreatmentEvent(BaseModel):
    correlationId: str
    triggeredAt: datetime
    customerId: str
    request: DelinquencyTreatmentRequest
    decisionType: str = "DELINQUENCY_TREATMENT"
    eventVersion: str = "1.0"


# ── Cross-Sell ────────────────────────────────────────────────────────────────

class CrossSellRequest(BaseModel):
    customerId: str
    monthsOnBook: int
    averageMonthlyBalance: float
    currentProduct: str                     # BASIC_CARD | REWARDS_CARD | SECURED_CARD
    triggerReason: str                      # TENURE | SPEND_PATTERN | LIMIT_INCREASE | BUREAU_REFRESH
    rewardPointsBalance: int = 0
    annualSpend: float = 0.0


class CrossSellEvent(BaseModel):
    correlationId: str
    triggeredAt: datetime
    customerId: str
    request: CrossSellRequest
    decisionType: str = "CROSS_SELL"
    eventVersion: str = "1.0"


# ── Outcome Events (Task 3.3) ─────────────────────────────────────────────────

class OutcomeEvent(BaseModel):
    """
    Published by downstream systems when an account outcome is observed.

    Topics:
      outcome.account_default  → outcomeType="ACCOUNT_DEFAULT"
      outcome.fraud_confirmed  → outcomeType="FRAUD_CONFIRMED"
      outcome.early_payoff     → outcomeType="EARLY_PAYOFF"
    """
    correlationId: str                          # original decision correlationId
    outcomeType: str                            # ACCOUNT_DEFAULT | FRAUD_CONFIRMED | EARLY_PAYOFF
    outcomeDate: str                            # ISO date string YYYY-MM-DD
    monthsOnBooks: int = 0
    originalRecommendation: str = ""
    originalConfidence: float = 0.0
    eventVersion: str = "1.0"
