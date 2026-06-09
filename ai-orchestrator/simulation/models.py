from __future__ import annotations

from pydantic import BaseModel, Field


class SimulationRequest(BaseModel):
    strategy_version: str
    sample_size: int = Field(default=500, ge=1, le=5000)
    date_range: str = Field(
        default="last_90_days",
        description="all | last_7_days | last_30_days | last_90_days",
    )


class RecommendationDistribution(BaseModel):
    APPROVE: int = 0
    DECLINE: int = 0
    MANUAL_REVIEW: int = 0
    total: int = 0

    @classmethod
    def from_counter(cls, counter: dict[str, int]) -> "RecommendationDistribution":
        a = counter.get("APPROVE", 0)
        d = counter.get("DECLINE", 0)
        m = counter.get("MANUAL_REVIEW", 0)
        return cls(APPROVE=a, DECLINE=d, MANUAL_REVIEW=m, total=a + d + m)


class ChangedDecision(BaseModel):
    correlation_id: str
    original: str
    simulated: str


class SimulationResult(BaseModel):
    simulation_id: str
    strategy_version: str
    sample_size: int
    date_range: str
    status: str                                        # pending | running | complete | failed
    baseline_distribution: RecommendationDistribution | None = None
    simulated_distribution: RecommendationDistribution | None = None
    changed_decisions: list[ChangedDecision] | None = None
    change_rate: float | None = None                   # % of decisions with different outcome
    p_value: float | None = None                       # chi-squared p-value vs baseline
    error_message: str | None = None
    created_at: str
    completed_at: str | None = None
