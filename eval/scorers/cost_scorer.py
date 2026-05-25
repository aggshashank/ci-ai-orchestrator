"""
cost_scorer.py — scores token consumption against configured ceiling.
"""
from dataclasses import dataclass, field


COST_PER_1M = {
    "ollama_local":      0.00,
    "groq_llama3_8b":    0.05,
    "openai_gpt4o":      5.00,
    "openai_gpt4o_mini": 0.15,
}


@dataclass
class CostScore:
    agent: str
    score: float
    passed: bool
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    token_ceiling: int
    cost_usd: float
    provider: str
    issues: list = field(default_factory=list)


def score_cost(agent_name: str, prompt_tokens: int, completion_tokens: int,
               token_ceiling: int, provider: str = "ollama_local") -> CostScore:
    """
    Score = 1.0 if total_tokens <= ceiling.
    Decays linearly to 0.0 at 3× ceiling.
    token_ceiling = 0 means agent has no LLM call (deterministic) → always 1.0.
    """
    total = prompt_tokens + completion_tokens
    cost_per_1m = COST_PER_1M.get(provider, 0.0)
    cost_usd = round((total / 1_000_000) * cost_per_1m, 6)
    issues = []

    if token_ceiling == 0:
        # Deterministic agent — no LLM cost
        return CostScore(agent_name, 1.0, True, 0, 0, 0, 0, 0.0, provider)

    if total <= token_ceiling:
        score = 1.0
    else:
        overage = (total - token_ceiling) / (2 * token_ceiling)
        score = max(0.0, round(1.0 - overage, 3))
        issues.append(f"Token usage {total} exceeds ceiling {token_ceiling}")

    return CostScore(agent_name, score, score >= 0.70,
                     prompt_tokens, completion_tokens, total,
                     token_ceiling, cost_usd, provider, issues)


def project_cost_per_1000_apps(agent_scores: list[CostScore]) -> float:
    """Compute estimated cost to process 1000 applications at current token usage."""
    total_per_app = sum(s.cost_usd for s in agent_scores)
    return round(total_per_app * 1000, 4)
