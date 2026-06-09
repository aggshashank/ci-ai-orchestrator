"""
Deterministic traffic router for champion/challenger experiments.

Routing is based on a SHA-256 hash of the correlationId so the same
application always routes to the same variant, regardless of which instance
handles it.
"""
from __future__ import annotations

import hashlib


def assign_variant(correlation_id: str, challenger_pct: int) -> str:
    """
    Return "champion" or "challenger" for this correlationId.

    The bucket is deterministic: hash(correlationId) % 100.
    Any correlationId where bucket < challenger_pct routes to challenger.
    """
    if challenger_pct <= 0:
        return "champion"
    if challenger_pct >= 100:
        return "challenger"

    digest = hashlib.sha256(correlation_id.encode("utf-8")).hexdigest()
    bucket = int(digest, 16) % 100
    return "challenger" if bucket < challenger_pct else "champion"
