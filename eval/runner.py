"""
runner.py
---------
Main eval entry point. Loads golden dataset, invokes each agent,
collects dimension scores, aggregates, compares to baseline.

Usage:
    python runner.py                     # run all agents, all test cases
    python runner.py --agent credit_agent        # single agent
    python runner.py --case GD-001               # single test case
    python runner.py --save-baseline             # save run as new baseline
    python runner.py --judge                     # enable LLM-as-judge scoring
    python runner.py --dry-run                   # validate dataset only, no LLM calls
"""
import sys, os
from pathlib import Path

# Add project root to path so we can import ai-orchestrator modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent
AI_ORCH = PROJECT_ROOT / "ai-orchestrator"
sys.path.insert(0, str(PROJECT_ROOT / "eval"))
sys.path.insert(0, str(AI_ORCH))

import json, time, argparse, uuid
from datetime import datetime, timezone

from eval_config import AGENT_THRESHOLDS, ACTIVE_PROVIDER
from aggregator import (AgentEvalResult, aggregate_run,
                         compare_to_baseline, save_as_baseline)
from scorers.format_scorer import score_format
from scorers.correctness_scorer import score_correctness
from scorers.latency_scorer import score_latency, compute_percentiles
from scorers.cost_scorer import score_cost, project_cost_per_1000_apps
from report_generator import generate_report

try:
    from agents.credit_agent import credit_agent
    from agents.fraud_agent import fraud_agent
    from agents.policy_rag_agent import policy_rag_agent
    from agents.risk_decision_agent import risk_decision_agent
    from agents.explainability_agent import explainability_agent
    from agents.state import GraphState
    from models.events import ApplicationRequest
    AGENTS_AVAILABLE = True
except ImportError as e:
    print(f"[WARN] Could not import agents: {e}")
    print("[WARN] Running in mock mode — agents return stub outputs")
    AGENTS_AVAILABLE = False


# ── Mock agent outputs (used when real agents unavailable) ────────────────────

MOCK_OUTPUTS = {
    "credit_agent": {
        "riskLevel": "MEDIUM", "reason": "Mock credit assessment",
        "score": 0.5, "keyFactors": ["mock"]
    },
    "fraud_agent": {
        "fraudRisk": "LOW", "reason": "Mock fraud assessment",
        "indicators": [], "recommendAction": "PROCEED"
    },
    "policy_rag_agent": {
        "policy_applicable": False, "rules": [], "action": "APPROVE", "citations": []
    },
    "risk_decision_agent": {
        "recommendation": "MANUAL_REVIEW", "confidence": 0.5,
        "reasons": ["Mock decision"], "composite_score": 0.5,
        "signal_weights": {}
    },
    "explainability_agent": {
        "plain_language_summary": "Mock summary.",
        "audit_narrative": "Mock audit narrative for compliance review.",
        "recommended_next_steps": "Contact customer service.",
        "adverse_action_codes": [],
        "policy_citations": [],
        "signal_weights": {},
    },
}


def invoke_agent(agent_name: str, state: dict, dry_run: bool = False) -> tuple[dict, float, int, int]:
    """
    Invoke a single agent. Returns (output_dict, latency_s, prompt_tokens, completion_tokens).
    In dry_run mode returns mock output instantly.
    """
    if dry_run or not AGENTS_AVAILABLE:
        return MOCK_OUTPUTS.get(agent_name, {}), 0.01, 0, 0

    agent_fns = {
        "credit_agent":         credit_agent,
        "fraud_agent":          fraud_agent,
        "policy_rag_agent":     policy_rag_agent,
        "risk_decision_agent":  risk_decision_agent,
        "explainability_agent": explainability_agent,
    }

    fn = agent_fns.get(agent_name)
    if not fn:
        return {}, 0.0, 0, 0

    start = time.time()
    timed_out = False
    try:
        result_state = fn(state)
        # Extract the agent's output key from state update
        output_key = {
            "credit_agent":         "credit_result",
            "fraud_agent":          "fraud_result",
            "policy_rag_agent":     "policy_context",
            "risk_decision_agent":  "risk_decision",
            "explainability_agent": "explanation",
        }.get(agent_name, agent_name)

        output = result_state.get(output_key, {})
    except Exception as e:
        output = {"_error": str(e)}
        timed_out = True

    latency_s = round(time.time() - start, 3)

    # Ollama token counts (available in response metadata if using langchain-ollama)
    # For now we estimate from output size — replace with actual metadata if available
    output_str = json.dumps(output)
    prompt_tokens = 400     # approximate — replace with actual from LLM response metadata
    completion_tokens = len(output_str.split()) * 2   # rough estimate

    return output, latency_s, prompt_tokens, completion_tokens


def build_state(case: dict) -> dict:
    """Build a GraphState from a golden dataset test case."""
    app_data = case["application"]
    try:
        app = ApplicationRequest(**app_data)
    except Exception:
        # Fallback if ApplicationRequest not available
        app = type("App", (), app_data)()

    return {
        "correlation_id": f"EVAL-{case['id']}",
        "application": app,
        "credit_result": {},
        "fraud_result": {},
        "policy_context": {},
        "risk_decision": {},
        "explanation": {},
    }


def run_eval(args) -> "PipelineEvalResult":
    dataset_path = Path(__file__).parent / "golden_dataset.json"
    cases = json.loads(dataset_path.read_text())

    # Filter by case or agent if requested
    if args.case:
        cases = [c for c in cases if c["id"] == args.case]
    if not cases:
        print(f"[ERROR] No test cases found (filter: {args.case})")
        sys.exit(1)

    target_agents = list(AGENT_THRESHOLDS.keys())
    if args.agent:
        target_agents = [args.agent]

    run_id = f"eval-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:8]}"
    print(f"\n{'='*60}")
    print(f"  Eval Run: {run_id}")
    print(f"  Cases:    {len(cases)}")
    print(f"  Agents:   {', '.join(target_agents)}")
    print(f"  Mode:     {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"{'='*60}\n")

    all_results: list[AgentEvalResult] = []
    latencies_by_agent: dict[str, list[float]] = {a: [] for a in target_agents}

    for case in cases:
        print(f"  [{case['id']}] {case['scenario']}")
        state = build_state(case)

        # Run agents sequentially (matching actual pipeline order)
        for agent_name in target_agents:
            expected = case.get("expected", {}).get(agent_name, {})

            # Invoke
            output, latency_s, prompt_tok, compl_tok = invoke_agent(
                agent_name, state, dry_run=args.dry_run
            )

            # Update state for downstream agents
            key_map = {
                "credit_agent":        "credit_result",
                "fraud_agent":         "fraud_result",
                "policy_rag_agent":    "policy_context",
                "risk_decision_agent": "risk_decision",
                "explainability_agent":"explanation",
            }
            if key_map.get(agent_name):
                state[key_map[agent_name]] = output

            # Score dimensions
            output_str = json.dumps(output) if output else "{}"
            fmt_score   = score_format(agent_name, output_str)
            corr_score  = score_correctness(agent_name, output, expected,
                                             use_judge=args.judge)
            thresholds  = AGENT_THRESHOLDS.get(agent_name)
            lat_score   = score_latency(agent_name, latency_s,
                                         thresholds.latency_ceiling_s,
                                         timed_out="_error" in output)
            cost_score  = score_cost(agent_name, prompt_tok, compl_tok,
                                      thresholds.token_ceiling, ACTIVE_PROVIDER)

            from aggregator import compute_agent_weighted_score
            weighted = compute_agent_weighted_score(
                corr_score.score, fmt_score.score,
                lat_score.score, cost_score.score
            )

            # Determine pass
            passed = (
                corr_score.score  >= thresholds.correctness_floor and
                fmt_score.score   >= thresholds.format_floor       and
                lat_score.passed                                    and
                not "_error" in output
            )

            issues = fmt_score.issues + [c["detail"] for c in corr_score.checks if not c["passed"]]

            result = AgentEvalResult(
                agent=agent_name,
                test_case_id=case["id"],
                correctness=corr_score.score,
                format=fmt_score.score,
                latency=lat_score.score,
                cost=cost_score.score,
                weighted_score=weighted,
                passed=passed,
                issues=issues,
            )
            all_results.append(result)
            latencies_by_agent[agent_name].append(latency_s)

            status = "✓" if passed else "✗"
            print(f"    {status} {agent_name:<28} "
                  f"corr={corr_score.score:.2f} fmt={fmt_score.score:.2f} "
                  f"lat={latency_s:.1f}s  weighted={weighted:.2f}")

        print()

    # Aggregate
    pipeline = aggregate_run(all_results, run_id)

    # Latency percentiles
    pipeline.latency_percentiles = {
        agent: compute_percentiles(lats)
        for agent, lats in latencies_by_agent.items()
    }

    # Baseline comparison
    baseline_path = Path(__file__).parent / "baselines" / "baseline.json"
    regressions = compare_to_baseline(pipeline, baseline_path)
    pipeline.regressions = regressions

    # Save baseline if requested
    if args.save_baseline:
        save_as_baseline(pipeline, baseline_path)
        print(f"[INFO] Baseline saved to {baseline_path}")

    return pipeline


def print_summary(pipeline):
    print(f"\n{'='*60}")
    print(f"  EVAL SUMMARY — {pipeline.run_id}")
    print(f"{'='*60}")
    print(f"  Pipeline score : {pipeline.pipeline_score:.3f}")
    print(f"  Cases passed   : {pipeline.passed_cases}/{pipeline.total_cases}")
    print()
    print(f"  {'Agent':<30} {'Correctness':>11} {'Format':>7} {'Latency':>8} {'Weighted':>9}")
    print(f"  {'-'*69}")
    for agent, scores in pipeline.agent_scores.items():
        print(f"  {agent:<30} "
              f"{scores['correctness']:>11.3f} "
              f"{scores['format']:>7.3f} "
              f"{scores['latency']:>8.3f} "
              f"{scores['weighted']:>9.3f}")

    if pipeline.regressions:
        print(f"\n  ⚠  REGRESSIONS DETECTED ({len(pipeline.regressions)})")
        for r in pipeline.regressions:
            print(f"     [{r['severity']}] {r['agent']}.{r['dimension']}: "
                  f"{r['baseline']:.3f} → {r['current']:.3f} (drop={r['drop']:.3f})")
    else:
        print("\n  ✓  No regressions vs baseline")

    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="AI Agent Eval Framework")
    parser.add_argument("--agent",         help="Evaluate a single agent only")
    parser.add_argument("--case",          help="Evaluate a single test case by ID")
    parser.add_argument("--save-baseline", action="store_true",
                        help="Save this run as the new baseline")
    parser.add_argument("--judge",         action="store_true",
                        help="Enable LLM-as-judge for explainability scoring")
    parser.add_argument("--dry-run",       action="store_true",
                        help="Validate config and dataset without calling agents")
    parser.add_argument("--report",        action="store_true",
                        help="Generate HTML report after eval")
    args = parser.parse_args()

    pipeline = run_eval(args)
    print_summary(pipeline)

    if args.report:
        report_path = Path(__file__).parent / "reports" / "latest.html"
        generate_report(pipeline, report_path)
        print(f"[INFO] Report written to {report_path}")

    # Exit 1 if regressions detected (useful for CI)
    sys.exit(1 if pipeline.regressions else 0)


if __name__ == "__main__":
    main()
