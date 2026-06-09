"""
Simulation CLI — run a strategy simulation directly without the API.

Usage:
  python -m simulation.cli --strategy v1.1.0 --sample 500 --date-range last_90_days
  python -m simulation.cli --strategy v1.1.0 --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


async def _main(args: argparse.Namespace) -> None:
    # Bootstrap DB and settings
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from db.session import init_db
    from simulation.comparator import chi_squared_p_value, interpret_p_value
    from simulation.models import RecommendationDistribution, SimulationRequest
    from simulation.engine import _load_snapshot, _sample_decisions
    from strategy.manager import engine_from_snapshot, score_deterministically
    from simulation.report import generate_html_report

    if not args.dry_run:
        await init_db()

    request = SimulationRequest(
        strategy_version=args.strategy,
        sample_size=args.sample,
        date_range=args.date_range,
    )

    print(f"\nSimulation: strategy={args.strategy} sample={args.sample} "
          f"date_range={args.date_range}")

    if args.dry_run:
        print("[dry-run] Would simulate but DB is not initialised. Exiting.")
        return

    print("Loading strategy snapshot from DB…")
    snapshot, version = await _load_snapshot(request.strategy_version)
    engine = engine_from_snapshot(snapshot, version)

    print("Sampling historical decisions…")
    decisions = await _sample_decisions(request)
    if not decisions:
        print("No decisions found. Run some credit applications first.", file=sys.stderr)
        return

    print(f"Scoring {len(decisions)} decisions…")
    baseline_counter: dict[str, int] = {}
    simulated_counter: dict[str, int] = {}
    changed = []

    for d in decisions:
        orig = d["recommendation"]
        baseline_counter[orig] = baseline_counter.get(orig, 0) + 1

        credit = d["agent_outputs"].get("credit_agent", {})
        fraud  = d["agent_outputs"].get("fraud_agent", {})
        policy = d["agent_outputs"].get("policy_rag_agent", {})

        new_rec, _, _ = score_deterministically(engine, credit, fraud, policy)
        simulated_counter[new_rec] = simulated_counter.get(new_rec, 0) + 1
        if new_rec != orig:
            changed.append({"correlation_id": d["correlation_id"],
                            "original": orig, "simulated": new_rec})

    p_value = chi_squared_p_value(baseline_counter, simulated_counter)
    change_rate = len(changed) / max(len(decisions), 1) * 100

    print("\n── Results ─────────────────────────────────────")
    print(f"  Baseline:   {json.dumps(baseline_counter)}")
    print(f"  Simulated:  {json.dumps(simulated_counter)}")
    print(f"  Changed:    {len(changed)} ({change_rate:.1f}%)")
    print(f"  p-value:    {p_value:.4f}")
    print(f"  {interpret_p_value(p_value)}")

    if args.output:
        baseline_dist = RecommendationDistribution.from_counter(baseline_counter)
        simulated_dist = RecommendationDistribution.from_counter(simulated_counter)
        from simulation.models import ChangedDecision
        html = generate_html_report(
            simulation_id="cli",
            strategy_version=args.strategy,
            baseline=baseline_dist,
            simulated=simulated_dist,
            changed=[ChangedDecision(**c) for c in changed],
            p_value=p_value,
            sample_size=len(decisions),
            date_range=args.date_range,
        )
        Path(args.output).write_text(html, encoding="utf-8")
        print(f"\nHTML report written to {args.output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate strategy against historical decisions")
    parser.add_argument("--strategy", required=True, help="Strategy version (e.g. v1.1.0)")
    parser.add_argument("--sample", type=int, default=500, help="Number of decisions to sample")
    parser.add_argument("--date-range", default="last_90_days",
                        choices=["all", "last_7_days", "last_30_days", "last_90_days"])
    parser.add_argument("--output", default=None, help="Write HTML report to this file")
    parser.add_argument("--dry-run", action="store_true", help="Validate args without hitting DB")
    args = parser.parse_args()
    asyncio.run(_main(args))


if __name__ == "__main__":
    main()
