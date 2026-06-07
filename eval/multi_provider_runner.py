"""
multi_provider_runner.py
------------------------
Runs the full eval pipeline against multiple LLM providers sequentially
and generates an HTML comparison report.

Usage:
    python multi_provider_runner.py --providers ollama,groq,openai
    python multi_provider_runner.py --providers ollama --dry-run
    python multi_provider_runner.py --providers groq,openai --save-db
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure eval/ and ai-orchestrator/ are importable
_EVAL_DIR = Path(__file__).resolve().parent
_AI_ORCH = _EVAL_DIR.parent / "ai-orchestrator"
sys.path.insert(0, str(_EVAL_DIR))
sys.path.insert(0, str(_AI_ORCH))


def _run_for_provider(provider: str, args: argparse.Namespace):
    """
    Set LLM_PROVIDER, clear the lru_cache on get_llm/get_settings,
    then run the eval. Returns a PipelineEvalResult.
    """
    os.environ["LLM_PROVIDER"] = provider

    # Clear caches so the new provider is picked up without a process restart
    try:
        from config import get_settings
        get_settings.cache_clear()
    except Exception:
        pass
    try:
        from llm.factory import get_llm
        get_llm.cache_clear()
    except Exception:
        pass

    # Import runner fresh each iteration to avoid stale module state
    import importlib
    import runner as runner_mod
    importlib.reload(runner_mod)

    return runner_mod.run_eval(args)


def generate_comparison_report(
    results: dict[str, object],
    output_path: Path,
) -> None:
    """Write a self-contained HTML report comparing scores across providers."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    providers = list(results.keys())

    def _color(score: float) -> str:
        if score >= 0.85: return "#1a7a6e"
        if score >= 0.70: return "#c07000"
        return "#c00000"

    def _bar(score: float, w: int = 100) -> str:
        fill = int(score * w)
        c = _color(score)
        return (
            f'<div style="display:inline-flex;align-items:center;gap:6px">'
            f'<div style="width:{w}px;height:8px;background:#eee;border-radius:4px;overflow:hidden">'
            f'<div style="width:{fill}px;height:100%;background:{c};border-radius:4px"></div></div>'
            f'<span style="font-size:12px;color:{c};font-weight:500">{int(score*100)}%</span>'
            f'</div>'
        )

    # Header row
    header_cells = "".join(f"<th>{p}</th>" for p in providers)

    # Pipeline score row
    pipe_cells = "".join(
        f"<td>{_bar(results[p].pipeline_score)}</td>" for p in providers
    )

    # Per-agent rows
    all_agents = list(results[providers[0]].agent_scores.keys()) if providers else []
    agent_rows = ""
    for agent in all_agents:
        cells = ""
        for p in providers:
            s = results[p].agent_scores.get(agent, {})
            w = s.get("weighted", 0)
            cells += f"<td>{_bar(w)}</td>"
        agent_rows += f"<tr><td style='font-weight:500'>{agent}</td>{cells}</tr>"

    # Dimension rows
    all_dims = ["correctness", "format", "latency", "cost"]
    dim_rows = ""
    for dim in all_dims:
        cells = ""
        for p in providers:
            v = results[p].dimension_scores.get(dim, 0)
            cells += f"<td>{_bar(v)}</td>"
        dim_rows += f"<tr><td style='font-weight:500'>{dim.title()}</td>{cells}</tr>"

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Multi-Provider Eval Comparison — {now}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
     max-width:1100px;margin:40px auto;padding:0 24px;color:#1a1a1a;line-height:1.6}}
h1{{font-size:22px;font-weight:600;margin:0 0 4px}}
h2{{font-size:17px;font-weight:600;margin:32px 0 12px;
    border-bottom:1px solid #e4e4e4;padding-bottom:8px}}
.meta{{color:#666;font-size:13px;margin-bottom:32px}}
table{{width:100%;border-collapse:collapse;font-size:14px;margin:16px 0}}
th{{background:#f0f0f0;padding:10px 14px;text-align:left;font-weight:600;font-size:13px;
    border-bottom:2px solid #ddd}}
td{{padding:10px 14px;border-bottom:1px solid #eeeeee;vertical-align:middle}}
</style></head><body>
<h1>Multi-Provider Evaluation Comparison</h1>
<p class="meta">Generated: {now} &nbsp;·&nbsp; Providers: {', '.join(providers)}</p>

<h2>Pipeline Score</h2>
<table>
  <thead><tr><th>Metric</th>{header_cells}</tr></thead>
  <tbody>
    <tr><td style='font-weight:500'>Pipeline Score</td>{pipe_cells}</tr>
  </tbody>
</table>

<h2>Per-Agent Weighted Scores</h2>
<table>
  <thead><tr><th>Agent</th>{header_cells}</tr></thead>
  <tbody>{agent_rows}</tbody>
</table>

<h2>Dimension Averages</h2>
<table>
  <thead><tr><th>Dimension</th>{header_cells}</tr></thead>
  <tbody>{dim_rows}</tbody>
</table>

</body></html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"[multi_provider] Comparison report: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-provider eval comparison")
    parser.add_argument(
        "--providers", default="ollama",
        help="Comma-separated provider names (e.g. ollama,groq,openai)",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Run agents in mock mode — no LLM calls")
    parser.add_argument("--save-baseline", action="store_true")
    parser.add_argument("--save-db", action="store_true",
                        help="Persist results to PostgreSQL via db_results.py")
    parser.add_argument("--judge", action="store_true")
    parser.add_argument("--case", help="Evaluate a single test case by ID")
    args = parser.parse_args()

    providers = [p.strip() for p in args.providers.split(",") if p.strip()]
    results: dict[str, object] = {}

    for provider in providers:
        print(f"\n{'='*55}")
        print(f"  Provider: {provider.upper()}")
        print(f"{'='*55}")
        try:
            pipeline = _run_for_provider(provider, args)
            results[provider] = pipeline

            if args.save_db:
                from db_results import save_eval_run
                save_eval_run(pipeline, pipeline.per_case_results,
                              provider=provider, dataset_ver="v2")
        except Exception as exc:
            print(f"[ERROR] Provider {provider} failed: {exc}")

    if len(results) > 1:
        report_path = _EVAL_DIR / "reports" / "provider_comparison.html"
        generate_comparison_report(results, report_path)

    # Print summary table
    print(f"\n{'='*55}")
    print(f"  {'Provider':<12} {'Pipeline':>10} {'Passed':>8} {'Regressions':>13}")
    print(f"  {'-'*50}")
    for p, r in results.items():
        print(
            f"  {p:<12} {r.pipeline_score:>10.3f} "
            f"{r.passed_cases:>4}/{r.total_cases:<3} "
            f"{len(r.regressions):>12}"
        )
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
