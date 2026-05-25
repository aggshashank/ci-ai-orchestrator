"""
aggregator.py
-------------
Combines correctness, format, latency, and cost dimension scores
into a weighted agent score, then a weighted pipeline score.
Compares against saved baseline and flags regressions.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from eval_config import DIMENSION_WEIGHTS, AGENT_THRESHOLDS, REGRESSION_THRESHOLD


@dataclass
class AgentEvalResult:
    agent: str
    test_case_id: str
    correctness: float
    format: float
    latency: float
    cost: float
    weighted_score: float
    passed: bool
    issues: list = field(default_factory=list)


@dataclass
class PipelineEvalResult:
    run_id: str
    total_cases: int
    passed_cases: int
    agent_scores: dict          # agent_name -> avg scores across test cases
    dimension_scores: dict      # dimension -> avg across all agents + cases
    pipeline_score: float       # single 0-1 number for the whole pipeline
    regressions: list           # list of regression dicts
    per_case_results: list      # flat list of AgentEvalResult


def compute_agent_weighted_score(correctness: float, fmt: float,
                                 latency: float, cost: float) -> float:
    """Weighted combination of four dimension scores."""
    w = DIMENSION_WEIGHTS
    return round(
        correctness * w["correctness"] +
        fmt         * w["format"]      +
        latency     * w["latency"]     +
        cost        * w["cost"],
        3
    )


def aggregate_run(per_case_results: list[AgentEvalResult],
                  run_id: str) -> PipelineEvalResult:
    """
    Aggregate all per-case, per-agent results into a single pipeline result.
    """
    total = len(per_case_results)
    passed = sum(1 for r in per_case_results if r.passed)

    # Group by agent
    agent_buckets: dict[str, list[AgentEvalResult]] = {}
    for r in per_case_results:
        agent_buckets.setdefault(r.agent, []).append(r)

    agent_scores = {}
    for agent, results in agent_buckets.items():
        n = len(results)
        agent_scores[agent] = {
            "correctness": round(sum(r.correctness for r in results) / n, 3),
            "format":      round(sum(r.format      for r in results) / n, 3),
            "latency":     round(sum(r.latency     for r in results) / n, 3),
            "cost":        round(sum(r.cost        for r in results) / n, 3),
            "weighted":    round(sum(r.weighted_score for r in results) / n, 3),
            "pass_rate":   round(sum(1 for r in results if r.passed) / n, 3),
        }

    # Pipeline-level dimension averages (across all agents)
    all_correct  = [r.correctness     for r in per_case_results]
    all_fmt      = [r.format          for r in per_case_results]
    all_latency  = [r.latency         for r in per_case_results]
    all_cost     = [r.cost            for r in per_case_results]

    def avg(lst): return round(sum(lst) / len(lst), 3) if lst else 0.0

    dimension_scores = {
        "correctness": avg(all_correct),
        "format":      avg(all_fmt),
        "latency":     avg(all_latency),
        "cost":        avg(all_cost),
    }

    # Agent weights for pipeline score
    pipeline_weighted_scores = []
    for agent, scores in agent_scores.items():
        w = AGENT_THRESHOLDS.get(agent, type("T", (), {"weight": 1.0})()).weight
        pipeline_weighted_scores.append(scores["weighted"] * w)

    total_weight = sum(
        AGENT_THRESHOLDS.get(a, type("T", (), {"weight": 1.0})()).weight
        for a in agent_scores
    )
    pipeline_score = round(
        sum(pipeline_weighted_scores) / total_weight if total_weight > 0 else 0.0, 3
    )

    return PipelineEvalResult(
        run_id=run_id,
        total_cases=total,
        passed_cases=passed,
        agent_scores=agent_scores,
        dimension_scores=dimension_scores,
        pipeline_score=pipeline_score,
        regressions=[],
        per_case_results=per_case_results,
    )


def compare_to_baseline(current: PipelineEvalResult,
                         baseline_path: Path) -> list[dict]:
    """
    Load saved baseline and return list of regressions
    where score dropped more than REGRESSION_THRESHOLD.
    """
    if not baseline_path.exists():
        return []

    baseline = json.loads(baseline_path.read_text())
    regressions = []

    for agent, curr_scores in current.agent_scores.items():
        base_scores = baseline.get("agent_scores", {}).get(agent, {})
        for dim in ("correctness", "format", "latency", "cost", "weighted"):
            curr_val = curr_scores.get(dim, 0.0)
            base_val = base_scores.get(dim, 0.0)
            drop = base_val - curr_val
            if drop > REGRESSION_THRESHOLD:
                regressions.append({
                    "agent": agent,
                    "dimension": dim,
                    "baseline": base_val,
                    "current": curr_val,
                    "drop": round(drop, 3),
                    "severity": "HIGH" if drop > 0.15 else "MEDIUM",
                })

    return regressions


def save_as_baseline(result: PipelineEvalResult, path: Path):
    """Save current run as the new baseline."""
    data = {
        "run_id": result.run_id,
        "pipeline_score": result.pipeline_score,
        "agent_scores": result.agent_scores,
        "dimension_scores": result.dimension_scores,
    }
    path.write_text(json.dumps(data, indent=2))
