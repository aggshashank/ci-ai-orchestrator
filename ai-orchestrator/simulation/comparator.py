"""
Chi-squared goodness-of-fit test: does the simulated distribution differ
significantly from the baseline?

Uses a pure-stdlib implementation (no scipy) based on the series expansion
of the regularized lower incomplete gamma function, which is exact for the
chi-squared CDF.

For exactly 3 recommendation categories (df = 2), the survival function
has a closed form: P(χ²(2) ≥ x) = exp(-x/2).
We use the general algorithm for forward compatibility (e.g. adding a 4th category).
"""
from __future__ import annotations

import math


def chi_squared_p_value(
    baseline: dict[str, int],
    simulated: dict[str, int],
) -> float:
    """
    Return the p-value for the null hypothesis that the simulated distribution
    was drawn from the same distribution as the baseline.

    A small p-value (< 0.05) means the distributions differ significantly.
    Returns 1.0 when the test cannot be computed (e.g. all-zero baseline).
    """
    categories = sorted(set(baseline) | set(simulated))
    n_baseline = sum(baseline.values())
    n_simulated = sum(simulated.values())

    if n_baseline == 0 or n_simulated == 0:
        return 1.0

    scale = n_simulated / n_baseline
    chi2 = 0.0
    df = 0

    for cat in categories:
        expected = baseline.get(cat, 0) * scale
        observed = simulated.get(cat, 0)
        if expected > 0:
            chi2 += (observed - expected) ** 2 / expected
            df += 1

    df = max(df - 1, 1)

    return _chi2_survival(chi2, df)


def _chi2_survival(chi2: float, df: int) -> float:
    """P(χ²(df) ≥ chi2) — survival function via regularized incomplete gamma."""
    if chi2 <= 0:
        return 1.0
    # chi2_sf(x, df) = 1 - gammainc_reg(df/2, x/2) = gammainc_reg_upper(df/2, x/2)
    return _gammainc_upper_reg(df / 2.0, chi2 / 2.0)


def _gammainc_upper_reg(a: float, x: float) -> float:
    """Upper regularized incomplete gamma: Q(a, x) = 1 - P(a, x)."""
    return 1.0 - _gammainc_lower_reg(a, x)


def _gammainc_lower_reg(a: float, x: float) -> float:
    """Lower regularized incomplete gamma P(a, x) via series expansion."""
    if x < 0:
        raise ValueError(f"x must be non-negative, got {x}")
    if x == 0:
        return 0.0
    if x > a + 50:
        # For large x relative to a, P(a,x) ≈ 1
        return 1.0

    log_factor = -x + a * math.log(x) - math.lgamma(a)
    term = 1.0 / a
    result = term
    for n in range(1, 500):
        term *= x / (a + n)
        result += term
        if abs(term) < 1e-14 * abs(result):
            break

    return min(math.exp(log_factor) * result, 1.0)


def interpret_p_value(p: float) -> str:
    if p < 0.001:
        return "Highly significant difference (p < 0.001) — strategy changes recommendation distribution markedly."
    if p < 0.01:
        return "Significant difference (p < 0.01) — strategy materially shifts decisions."
    if p < 0.05:
        return "Moderate difference (p < 0.05) — strategy has a detectable impact on decisions."
    if p < 0.10:
        return "Marginal difference (p < 0.10) — slight shift, not statistically significant at 5%."
    return "No significant difference (p ≥ 0.10) — strategy produces similar recommendation distribution."
