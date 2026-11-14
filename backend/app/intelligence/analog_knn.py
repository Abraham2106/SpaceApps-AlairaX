"""Transparent weighted KNN for historical climate replay, not forecasting."""

from dataclasses import replace
from math import isfinite, sqrt
from statistics import fmean, pstdev

from backend.app.intelligence.features import FEATURE_NAMES, SeasonFeatures


def find_analogs(candidates: list[SeasonFeatures], target: SeasonFeatures, *, k: int = 5,
                 weights: dict[str, float] | None = None) -> dict:
    """Fit scaling only on eligible past candidates and return explained neighbors.

    A target's own year, later years and 2026 are never training candidates.
    Historical backtests therefore cannot accidentally fit on future years.
    """
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError('k must be a positive integer')
    pool = [row for row in candidates if row.year < min(target.year, 2026)]
    if len({row.year for row in pool}) != len(pool):
        raise ValueError('one candidate feature row per year is required')
    if any(row.window_key != target.window_key for row in pool):
        raise ValueError('all candidate windows, heat thresholds and ONI periods must match target')
    if any(row.mock != target.mock for row in pool):
        raise ValueError('cannot mix mock and observed feature rows')
    if len(pool) < k:
        raise ValueError(f'not enough eligible complete years for k={k}: found {len(pool)}')
    resolved = {name: 1.0 for name in FEATURE_NAMES} if weights is None else dict(weights)
    if set(resolved) != set(FEATURE_NAMES):
        raise ValueError('weights must explicitly contain every feature and no unknown fields')
    if any(isinstance(w, bool) or not isinstance(w, (float, int)) or not isfinite(w) or w < 0 for w in resolved.values()) or sum(resolved.values()) <= 0:
        raise ValueError('weights must be finite, nonnegative, and sum to more than zero')
    means = {name: fmean(getattr(row, name) for row in pool) for name in FEATURE_NAMES}
    raw_scales = {name: pstdev(getattr(row, name) for row in pool) for name in FEATURE_NAMES}
    scales = {name: raw_scales[name] or 1.0 for name in FEATURE_NAMES}
    total_weight = sum(resolved.values())
    ranked = []
    for row in pool:
        contributions = {name: resolved[name] / total_weight *
                         ((getattr(row, name) - getattr(target, name)) / scales[name]) ** 2
                         for name in FEATURE_NAMES}
        ranked.append({'year': row.year, 'distance': sqrt(sum(contributions.values())),
                       'squared_distance_contributions': contributions})
    ranked.sort(key=lambda row: (row['distance'], row['year']))
    neighbors = ranked[:k]
    sensitivity = []
    for choice in sorted({max(1, k - 2), k, min(len(pool), k + 2)}):
        years = [row['year'] for row in ranked[:choice]]
        overlap = len(set(years) & {row['year'] for row in neighbors})
        sensitivity.append({'k': choice, 'years': years,
                            'jaccard_vs_selected_k': overlap / (len(years) + k - overlap)})
    return {
        '_mock': target.mock, 'method': 'weighted_standardized_euclidean',
        'interpretation': 'historical replay similarity; distances are not probabilities',
        'k': k, 'target': target.to_dict(), 'candidate_years': sorted(row.year for row in pool),
        'weights': resolved, 'scaler': {'mean': means, 'scale': scales,
            'zero_variance_features': [name for name in FEATURE_NAMES if raw_scales[name] == 0],
            'fit_years': sorted(row.year for row in pool)},
        'neighbors': neighbors, 'k_sensitivity': sensitivity,
    }


def select_scenario(candidates: list[SeasonFeatures], scenario_id: str, *,
                    tracking_2026: SeasonFeatures | None = None, k: int = 5,
                    weights: dict[str, float] | None = None) -> dict:
    """Use a documented seasonal ONI bucket centroid or actual 2026 window.

    These ONI buckets are exploratory labels, not NOAA event declarations.
    The centroid is a synthetic query, not a claimed observation.
    """
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError('k must be a positive integer')
    history = [row for row in candidates if row.year <= 2025]
    if not history:
        raise ValueError('no historical candidates')
    if len({row.year for row in history}) != len(history):
        raise ValueError('one historical row per year is required')
    if scenario_id == 'like_2026':
        if tracking_2026 is None or tracking_2026.year != 2026:
            raise ValueError('like_2026 requires an actual 2026 feature window, never an invented target')
        result = find_analogs(history, tracking_2026, k=k, weights=weights)
        result.update(scenario_id=scenario_id, target_kind='tracking_window',
                      phase_rule=None, warnings=['2026 is tracking only, never an analog.'])
        return result
    filters = {
        'strong_el_nino': (lambda row: row.oni >= 1.5, 'seasonal ONI >= 1.5 C'),
        'neutral': (lambda row: -0.5 < row.oni < 0.5, '-0.5 C < seasonal ONI < 0.5 C'),
        'la_nina': (lambda row: row.oni <= -0.5, 'seasonal ONI <= -0.5 C'),
    }
    if scenario_id not in filters:
        raise ValueError(f'unknown scenario: {scenario_id}')
    predicate, rule = filters[scenario_id]
    group = [row for row in history if predicate(row)]
    if len(group) < k:
        raise ValueError(f'{scenario_id} has {len(group)} eligible years; k={k} unavailable')
    first = group[0]
    if any(row.window_key != first.window_key or row.mock != first.mock for row in history):
        raise ValueError('scenario construction requires aligned windows and data status')
    centroid = {name: fmean(getattr(row, name) for row in group) for name in FEATURE_NAMES}
    target = replace(first, year=2026, start=first.start.replace(year=2026),
                     end=first.end.replace(year=2026), **centroid)
    # Scale on the full past climate population; rank only the requested ONI bucket.
    result = find_analogs(history, target, k=k, weights=weights)
    all_ranked = find_analogs(history, target, k=len(history), weights=weights)['neighbors']
    member_years = {row.year for row in group}
    bucket_ranked = [row for row in all_ranked if row['year'] in member_years]
    result['neighbors'] = bucket_ranked[:k]
    selected = {row['year'] for row in result['neighbors']}
    result['k_sensitivity'] = []
    for choice in sorted({max(1, k - 2), k, min(len(group), k + 2)}):
        years = [row['year'] for row in bucket_ranked[:choice]]
        overlap = len(set(years) & selected)
        result['k_sensitivity'].append({'k': choice, 'years': years,
            'jaccard_vs_selected_k': overlap / (len(years) + k - overlap)})
    result.update(scenario_id=scenario_id, target_kind='historical_bucket_centroid',
                  phase_rule=rule, eligible_phase_years=sorted(member_years),
                  warnings=['Seasonal ONI buckets are not sustained NOAA ENSO event classifications.',
                            'The centroid query is synthetic; no 2026 conditions were inferred.'])
    return result
