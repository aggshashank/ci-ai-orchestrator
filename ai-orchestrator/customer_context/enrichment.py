"""
enrich_with_customer_context — LangGraph node.

Runs as the first node in every workflow before any agent.
Fetches the CustomerProfile for the applicant and adds it to state.
If no customer_id is present, or the lookup fails, an empty profile is used
so downstream agents always have the key available.
"""
from __future__ import annotations

import structlog

logger = structlog.get_logger()


async def enrich_with_customer_context(state: dict) -> dict:
    """Return {customer_profile: dict} partial state update."""
    corr = state.get("correlation_id", "unknown")
    customer_id = _extract_customer_id(state)

    if not customer_id:
        logger.debug("customer_context_skipped_no_id", correlation_id=corr)
        return {"customer_profile": _empty()}

    from config import get_settings
    from customer_context.redis_store import CustomerContextStore
    from customer_context.service import CustomerContextService
    from db.session import get_session

    settings = get_settings()
    store = CustomerContextStore(settings.redis_url)

    try:
        async with get_session() as session:
            svc = CustomerContextService(session, store)
            profile = await svc.get_profile(customer_id)

        logger.info(
            "customer_context_enriched",
            correlation_id=corr,
            customer_id=customer_id,
            profile_version=profile.profile_version,
            is_new=profile.is_new_customer,
            accounts=profile.existing_accounts,
        )
        return {
            "customer_profile": profile.model_dump(mode="json"),
            "customer_context_version": profile.profile_version,
        }

    except Exception as exc:
        logger.error(
            "customer_context_enrichment_failed",
            correlation_id=corr,
            customer_id=customer_id,
            error_type=type(exc).__name__,
        )
        return {"customer_profile": _empty(), "customer_context_version": "error"}


def _extract_customer_id(state: dict) -> str | None:
    # Origination: ApplicationRequest.customerId
    app = state.get("application")
    if app is not None:
        cid = getattr(app, "customerId", None)
        if cid:
            return cid

    # Non-origination workflows store customer_id directly in state
    return state.get("customer_id") or None


def _empty() -> dict:
    from customer_context.models import empty_profile
    return empty_profile().model_dump(mode="json")
