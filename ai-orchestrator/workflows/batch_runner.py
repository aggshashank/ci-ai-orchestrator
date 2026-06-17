"""
Batch runner — nightly limit review job.

Queries customers with at least one approved origination decision and
publishes a limit.review.triggered Kafka event for each, to be consumed
by the regular consumer loop just like real-time events.

Usage:
  python -m workflows.batch_runner --limit 500 --dry-run

Schedule via cron:
  0 2 * * * python -m workflows.batch_runner --limit 500
"""
from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from datetime import datetime, timezone

import structlog

logger = structlog.get_logger()


async def _run(limit: int, dry_run: bool) -> None:
    from config import get_settings
    from db.models import Decision
    from db.session import get_session, init_db
    from sqlalchemy import select, func

    await init_db()
    settings = get_settings()

    async with get_session() as session:
        # Find customers with approved origination decisions (have an active account)
        stmt = (
            select(
                Decision.customer_id,
                func.max(Decision.created_at).label("last_decision"),
                func.avg(
                    Decision.application_json["utilization"].as_float()
                ).label("avg_util"),
            )
            .where(
                Decision.customer_id.isnot(None),
                Decision.recommendation == "APPROVE",
                Decision.decision_type == "ORIGINATION",
            )
            .group_by(Decision.customer_id)
            .limit(limit)
        )
        result = await session.execute(stmt)
        rows = result.all()

    logger.info("batch_limit_review_candidates", count=len(rows), dry_run=dry_run)

    if dry_run:
        for row in rows:
            logger.info("dry_run_event", customer_id=row.customer_id)
        return

    from kafka import KafkaProducer

    producer = KafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    published = 0
    for row in rows:
        event = {
            "correlationId": str(uuid.uuid4()),
            "triggeredAt": datetime.now(timezone.utc).isoformat(),
            "customerId": row.customer_id,
            "decisionType": "LIMIT_REVIEW",
            "request": {
                "customerId": row.customer_id,
                "currentCreditLimit": 10_000.0,  # would come from core banking API
                "accountAgeMonths": 12,           # would come from core banking API
                "recentUtilizationAvg": float(row.avg_util or 0),
                "paymentsMadeOnTime": 11,         # would come from payment events
                "paymentsCounted": 12,
                "missedPayments": 0,
                "currentBalance": float(row.avg_util or 0) * 100,
            },
            "eventVersion": "1.0",
        }
        producer.send(settings.kafka_topic_limit_review, event)
        published += 1

    producer.flush()
    producer.close()
    logger.info("batch_limit_review_complete", published=published)


def main() -> None:
    parser = argparse.ArgumentParser(description="Nightly limit review batch")
    parser.add_argument("--limit", type=int, default=500, help="Max customers to process")
    parser.add_argument("--dry-run", action="store_true", help="Log events without publishing")
    args = parser.parse_args()

    import logging_config
    logging_config.configure_logging()

    asyncio.run(_run(args.limit, args.dry_run))


if __name__ == "__main__":
    main()
