"""
latency_scorer.py — scores agent response time against configured ceiling.
"""
import statistics
from dataclasses import dataclass, field


@dataclass
class LatencyScore:
    agent: str
    score: float          # 0.0 – 1.0
    passed: bool
    latency_s: float      # actual wall-clock seconds
    ceiling_s: float      # configured ceiling
    timed_out: bool
    fallback_used: bool
    issues: list = field(default_factory=list)


def score_latency(agent_name: str, latency_s: float, ceiling_s: float,
                  timed_out: bool = False, fallback_used: bool = False) -> LatencyScore:
    """
    Score = 1.0 if latency <= ceiling.
    Score degrades linearly to 0.0 at 3× the ceiling.
    Timeout or fallback usage applies additional -0.30 deduction.
    """
    issues = []

    if timed_out:
        issues.append(f"Agent timed out (>{ceiling_s}s)")
        return LatencyScore(agent_name, 0.0, False, latency_s, ceiling_s, True, fallback_used, issues)

    if latency_s <= ceiling_s:
        score = 1.0
    else:
        # Linear decay from 1.0 at ceiling to 0.0 at 3× ceiling
        overage = (latency_s - ceiling_s) / (2 * ceiling_s)
        score = max(0.0, round(1.0 - overage, 3))
        issues.append(f"Latency {latency_s:.1f}s exceeds ceiling {ceiling_s}s")

    if fallback_used:
        score = max(0.0, round(score - 0.30, 3))
        issues.append("Fallback result used due to agent error")

    passed = score >= 0.60 and not timed_out
    return LatencyScore(agent_name, score, passed, latency_s, ceiling_s,
                        timed_out, fallback_used, issues)


def compute_percentiles(latencies: list[float]) -> dict:
    """Compute p50, p95, p99 from a list of latency measurements."""
    if not latencies:
        return {"p50": 0, "p95": 0, "p99": 0, "mean": 0}
    s = sorted(latencies)
    n = len(s)
    def pct(p): return s[min(int(n * p / 100), n - 1)]
    return {
        "p50": round(pct(50), 2),
        "p95": round(pct(95), 2),
        "p99": round(pct(99), 2),
        "mean": round(statistics.mean(s), 2),
    }
