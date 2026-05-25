"""
eval_config.py
--------------
All thresholds, weights, and tunable parameters in one place.
Edit here to change eval behaviour — never scatter magic numbers in scorers.
"""
from dataclasses import dataclass, field


@dataclass
class AgentThreshold:
    correctness_floor: float      # minimum acceptable correctness score (0-1)
    format_floor: float           # minimum acceptable format score (0-1)
    latency_ceiling_s: float      # max acceptable p95 latency in seconds
    token_ceiling: int            # max acceptable prompt+completion tokens per call
    weight: float                 # relative weight in overall pipeline score


# Per-agent thresholds — edit to match your SLA and budget
AGENT_THRESHOLDS: dict[str, AgentThreshold] = {
    "credit_agent": AgentThreshold(
        correctness_floor=0.80,
        format_floor=1.00,
        latency_ceiling_s=120.0,
        token_ceiling=600,
        weight=1.0,
    ),
    "fraud_agent": AgentThreshold(
        correctness_floor=0.75,
        format_floor=1.00,
        latency_ceiling_s=90.0,
        token_ceiling=500,
        weight=1.0,
    ),
    "policy_rag_agent": AgentThreshold(
        correctness_floor=0.70,
        format_floor=1.00,
        latency_ceiling_s=180.0,
        token_ceiling=1200,
        weight=1.0,
    ),
    "risk_decision_agent": AgentThreshold(
        correctness_floor=0.90,   # deterministic — any miss is a code bug
        format_floor=1.00,
        latency_ceiling_s=1.0,
        token_ceiling=0,          # no LLM call — token cost is 0
        weight=1.5,               # higher weight: final decision matters most
    ),
    "explainability_agent": AgentThreshold(
        correctness_floor=0.65,   # LLM-as-judge scoring — inherently fuzzier
        format_floor=0.90,
        latency_ceiling_s=120.0,
        token_ceiling=800,
        weight=0.8,
    ),
}

# Dimension weights — how much each dimension contributes to agent total score
DIMENSION_WEIGHTS = {
    "correctness": 0.50,
    "format":      0.25,
    "latency":     0.15,
    "cost":        0.10,
}

# Regression alert threshold — flag if score drops more than this vs baseline
REGRESSION_THRESHOLD = 0.05   # 5 percentage points

# Number of times to run each test case (median is used to handle flakiness)
EVAL_RUNS_PER_CASE = 1        # increase to 3 for production stability testing

# LLM-as-judge model (can be different from the agent model)
JUDGE_MODEL = "llama3:latest"

# Cost per 1M tokens (update when switching LLM providers)
COST_PER_1M_TOKENS = {
    "ollama_local": 0.00,         # free
    "groq_llama3_8b": 0.05,       # $0.05 per 1M tokens
    "openai_gpt4o": 5.00,         # $5.00 per 1M tokens
    "openai_gpt4o_mini": 0.15,
}
ACTIVE_PROVIDER = "ollama_local"
