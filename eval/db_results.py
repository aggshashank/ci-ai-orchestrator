"""
db_results.py
-------------
Persists eval run results to PostgreSQL for trend analysis and
multi-provider comparison. Uses asyncpg directly (no ORM) so the eval
CLI tool stays independent of the app's async session machinery.

Tables are created on first use (CREATE TABLE IF NOT EXISTS).
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aggregator import AgentEvalResult, PipelineEvalResult

# Ensure ai-orchestrator is on the path for config
_AI_ORCH = Path(__file__).resolve().parent.parent / "ai-orchestrator"
if str(_AI_ORCH) not in sys.path:
    sys.path.insert(0, str(_AI_ORCH))

_DDL = """
CREATE TABLE IF NOT EXISTS eval_runs (
    id               SERIAL       PRIMARY KEY,
    run_id           VARCHAR(128) UNIQUE NOT NULL,
    provider         VARCHAR(64)  NOT NULL DEFAULT 'unknown',
    dataset_ver      VARCHAR(32)  NOT NULL DEFAULT 'v1',
    run_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    pipeline_score   FLOAT        NOT NULL,
    passed_cases     INT          NOT NULL,
    total_cases      INT          NOT NULL,
    regression_count INT          NOT NULL DEFAULT 0,
    agent_scores     JSONB,
    dimension_scores JSONB
);

CREATE TABLE IF NOT EXISTS eval_agent_results (
    id             SERIAL       PRIMARY KEY,
    run_id         VARCHAR(128) NOT NULL,
    agent          VARCHAR(64)  NOT NULL,
    test_case_id   VARCHAR(32)  NOT NULL,
    correctness    FLOAT,
    format_score   FLOAT,
    latency        FLOAT,
    cost           FLOAT,
    weighted_score FLOAT,
    passed         BOOLEAN,
    issues         JSONB
);
"""


def _sync_db_url() -> str:
    """Convert asyncpg URL to plain asyncpg-compatible URL."""
    try:
        from config import get_settings
        url = get_settings().database_url
        # asyncpg.connect() uses postgresql://... not postgresql+asyncpg://...
        return url.replace("postgresql+asyncpg://", "postgresql://")
    except Exception:
        return "postgresql://poc:poc@localhost:5432/decisions"


async def _persist(run_data: dict, per_case: list[dict]) -> None:
    import asyncpg
    conn = await asyncpg.connect(_sync_db_url(), timeout=10)
    try:
        await conn.execute(_DDL)
        await conn.execute(
            """
            INSERT INTO eval_runs
              (run_id, provider, dataset_ver, pipeline_score,
               passed_cases, total_cases, regression_count,
               agent_scores, dimension_scores)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9::jsonb)
            ON CONFLICT (run_id) DO NOTHING
            """,
            run_data["run_id"],
            run_data.get("provider", "unknown"),
            run_data.get("dataset_ver", "v1"),
            float(run_data["pipeline_score"]),
            int(run_data["passed_cases"]),
            int(run_data["total_cases"]),
            int(run_data.get("regression_count", 0)),
            json.dumps(run_data.get("agent_scores", {})),
            json.dumps(run_data.get("dimension_scores", {})),
        )
        for r in per_case:
            await conn.execute(
                """
                INSERT INTO eval_agent_results
                  (run_id, agent, test_case_id, correctness, format_score,
                   latency, cost, weighted_score, passed, issues)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb)
                """,
                run_data["run_id"],
                r["agent"],
                r["test_case_id"],
                float(r["correctness"]),
                float(r["format"]),
                float(r["latency"]),
                float(r["cost"]),
                float(r["weighted_score"]),
                bool(r["passed"]),
                json.dumps(r.get("issues", [])),
            )
    finally:
        await conn.close()


def save_eval_run(
    pipeline: "PipelineEvalResult",
    per_case_results: "list[AgentEvalResult]",
    provider: str = "unknown",
    dataset_ver: str = "v1",
) -> None:
    """Sync entry point — call from runner.py after a completed eval."""
    run_data = {
        "run_id": pipeline.run_id,
        "provider": provider,
        "dataset_ver": dataset_ver,
        "pipeline_score": pipeline.pipeline_score,
        "passed_cases": pipeline.passed_cases,
        "total_cases": pipeline.total_cases,
        "regression_count": len(pipeline.regressions),
        "agent_scores": pipeline.agent_scores,
        "dimension_scores": pipeline.dimension_scores,
    }
    per_case_dicts = [
        {
            "agent": r.agent,
            "test_case_id": r.test_case_id,
            "correctness": r.correctness,
            "format": r.format,
            "latency": r.latency,
            "cost": r.cost,
            "weighted_score": r.weighted_score,
            "passed": r.passed,
            "issues": r.issues,
        }
        for r in per_case_results
    ]
    try:
        asyncio.run(_persist(run_data, per_case_dicts))
        print(f"[db_results] Eval run {pipeline.run_id} saved to PostgreSQL.")
    except Exception as exc:
        print(f"[db_results] WARNING: could not persist eval results — {exc}")


async def _load_provider_runs(providers: list[str]) -> list[dict]:
    import asyncpg
    conn = await asyncpg.connect(_sync_db_url(), timeout=10)
    try:
        rows = await conn.fetch(
            """
            SELECT run_id, provider, dataset_ver, run_at,
                   pipeline_score, passed_cases, total_cases,
                   regression_count, agent_scores, dimension_scores
            FROM eval_runs
            WHERE provider = ANY($1::text[])
            ORDER BY run_at DESC
            LIMIT 5
            """,
            providers,
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()


def load_recent_runs(providers: list[str]) -> list[dict]:
    """Load the most recent eval run per provider for comparison."""
    try:
        return asyncio.run(_load_provider_runs(providers))
    except Exception as exc:
        print(f"[db_results] WARNING: could not load runs — {exc}")
        return []
