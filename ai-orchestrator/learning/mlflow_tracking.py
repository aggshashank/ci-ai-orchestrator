"""
MLflow experiment tracking for quarterly weight retraining runs.

Tracks:
  - Parameters: strategy_version, window_days, training_sample_size
  - Metrics:    credit_accuracy, fraud_accuracy, default_rate,
                new_credit_weight, new_fraud_weight, new_policy_weight
  - Artifacts:  updated synthesis_weights.yaml
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

_MLFLOW_AVAILABLE = False
try:
    import mlflow  # type: ignore
    _MLFLOW_AVAILABLE = True
except ImportError:
    logger.warning("mlflow not installed — tracking disabled. pip install mlflow")


def start_run(experiment_name: str, tracking_uri: str) -> Any:
    if not _MLFLOW_AVAILABLE:
        return _NullRun()
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)
    return mlflow.start_run()


def log_training_run(
    *,
    strategy_version: str,
    window_days: int,
    sample_size: int,
    credit_accuracy: float,
    fraud_accuracy: float,
    default_rate: float,
    new_weights: dict,
    weights_path: Path,
    tracking_uri: str,
    experiment_name: str,
) -> str | None:
    """
    Open an MLflow run, log params + metrics, upload the updated weights file
    as an artifact, and return the run_id (or None if MLflow unavailable).
    """
    if not _MLFLOW_AVAILABLE:
        logger.info(
            "mlflow_tracking_skipped",
            strategy_version=strategy_version,
            credit_accuracy=round(credit_accuracy, 4),
            fraud_accuracy=round(fraud_accuracy, 4),
        )
        return None

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)

    with mlflow.start_run(run_name=f"weight-retrain-{strategy_version}") as run:
        mlflow.log_params({
            "strategy_version": strategy_version,
            "window_days":      window_days,
            "sample_size":      sample_size,
        })
        mlflow.log_metrics({
            "credit_accuracy":    round(credit_accuracy, 6),
            "fraud_accuracy":     round(fraud_accuracy, 6),
            "default_rate":       round(default_rate, 6),
            "new_credit_weight":  round(new_weights.get("credit", 0), 6),
            "new_fraud_weight":   round(new_weights.get("fraud", 0), 6),
            "new_policy_weight":  round(new_weights.get("policy", 0), 6),
        })
        if weights_path.exists():
            mlflow.log_artifact(str(weights_path), artifact_path="weights")

        run_id = run.info.run_id

    logger.info("mlflow_run_logged", run_id=run_id, strategy_version=strategy_version)
    return run_id


class _NullRun:
    """No-op context manager used when MLflow is not installed."""
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def __bool__(self): return False
