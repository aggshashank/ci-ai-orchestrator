"""
Quarterly model retrainer.

Reads signal accuracy features from the last N days of outcomes, derives
updated synthesis weights proportional to each signal's accuracy, writes
the updated synthesis_weights.yaml, and logs the run to MLflow.

CLI usage:
  python -m learning.model_trainer
  python -m learning.model_trainer --window-days 180 --dry-run

The "model" here is the synthesis_weights.yaml — a set of three floats that
credit/fraud/policy contributions are multiplied by in risk_decision_agent.
True ML retraining of a scoring model would be layered on top of this.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import structlog
import yaml

logger = structlog.get_logger()

_MIN_OUTCOMES = 50   # refuse to update weights on tiny samples


def _compute_new_weights(
    credit_accuracy: float,
    fraud_accuracy: float,
    current_weights: dict,
    min_weight: float = 0.15,
) -> dict:
    """
    Proportional weight update: each signal gets weight ∝ its accuracy.
    Policy weight is fixed as the residual after credit + fraud.
    Constrained so no weight falls below min_weight.
    """
    raw_credit = max(credit_accuracy, min_weight)
    raw_fraud  = max(fraud_accuracy, min_weight)
    total = raw_credit + raw_fraud

    credit_share = raw_credit / total
    fraud_share  = raw_fraud  / total

    # Reserve 25% for policy (unchanged — policy accuracy is hard to measure)
    policy_w = current_weights.get("policy", 0.25)
    remaining = 1.0 - policy_w

    credit_w = round(credit_share * remaining, 4)
    fraud_w  = round(1.0 - policy_w - credit_w, 4)

    return {"credit": credit_w, "fraud": fraud_w, "policy": policy_w}


def _load_current_weights(strategy_dir: Path) -> dict:
    weights_file = strategy_dir / "synthesis_weights.yaml"
    if not weights_file.exists():
        return {"credit": 0.45, "fraud": 0.30, "policy": 0.25}
    with weights_file.open() as f:
        data = yaml.safe_load(f)
    return data.get("weights", {"credit": 0.45, "fraud": 0.30, "policy": 0.25})


def _write_weights(strategy_dir: Path, weights: dict, source_window_days: int) -> Path:
    weights_file = strategy_dir / "synthesis_weights.yaml"
    payload = {
        "version": "auto-updated",
        "weights": weights,
        "source_window_days": source_window_days,
        "note": "Auto-updated by model_trainer.py — do not edit by hand",
    }
    with weights_file.open("w") as f:
        yaml.dump(payload, f, default_flow_style=False)
    return weights_file


async def run_training(window_days: int = 180, dry_run: bool = False) -> dict:
    from config import get_settings
    from learning.feature_store import compute_signal_accuracy
    from learning.mlflow_tracking import log_training_run

    settings = get_settings()
    features = await compute_signal_accuracy(window_days=window_days)

    if features.total_outcomes < _MIN_OUTCOMES:
        logger.warning(
            "insufficient_outcomes_for_retraining",
            total=features.total_outcomes,
            required=_MIN_OUTCOMES,
        )
        return {"status": "skipped", "reason": "insufficient_outcomes", "total": features.total_outcomes}

    strategies_dir = Path(__file__).parent.parent / settings.strategies_dir
    strategy_dir   = strategies_dir / settings.strategy_version
    current_weights = _load_current_weights(strategy_dir)

    new_weights = _compute_new_weights(
        credit_accuracy=features.credit_accuracy,
        fraud_accuracy=features.fraud_accuracy,
        current_weights=current_weights,
    )

    logger.info(
        "weight_update_computed",
        old=current_weights,
        new=new_weights,
        credit_accuracy=round(features.credit_accuracy, 4),
        fraud_accuracy=round(features.fraud_accuracy, 4),
        dry_run=dry_run,
    )

    if dry_run:
        return {"status": "dry_run", "old_weights": current_weights, "new_weights": new_weights}

    weights_path = _write_weights(strategy_dir, new_weights, window_days)

    run_id = log_training_run(
        strategy_version=settings.strategy_version,
        window_days=window_days,
        sample_size=features.total_outcomes,
        credit_accuracy=features.credit_accuracy,
        fraud_accuracy=features.fraud_accuracy,
        default_rate=features.default_rate,
        new_weights=new_weights,
        weights_path=weights_path,
        tracking_uri=settings.mlflow_tracking_uri,
        experiment_name=settings.mlflow_experiment_name,
    )

    # Invalidate the rules engine cache so the new weights are picked up
    from rules.engine import get_rules_engine
    get_rules_engine.cache_clear()

    logger.info("weights_updated", strategy_version=settings.strategy_version, mlflow_run_id=run_id)
    return {"status": "updated", "new_weights": new_weights, "mlflow_run_id": run_id}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Quarterly weight retrainer")
    parser.add_argument("--window-days", type=int, default=180)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = asyncio.run(run_training(window_days=args.window_days, dry_run=args.dry_run))
    print(result)
    sys.exit(0 if result["status"] in ("updated", "dry_run") else 1)
