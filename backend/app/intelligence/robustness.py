"""Empirical quantiles across analog years, not confidence intervals."""

from math import floor

from backend.app.api.schemas.contracts import Quantiles


def summarize(values: list[float | int | None]) -> Quantiles:
    # Do not silently drop a failed year and change the comparison population.
    if not values or any(value is None for value in values):
        return Quantiles(p10=None, p50=None, p90=None, n=0)
    ordered = sorted(values)

    def quantile(p):
        index = (len(ordered) - 1) * p
        lower = floor(index)
        upper = min(lower + 1, len(ordered) - 1)
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)

    return Quantiles(p10=quantile(.1), p50=quantile(.5), p90=quantile(.9), n=len(ordered))
