"""Pair alternatives with the same baseline climate year before summarizing."""

from datetime import datetime, timezone

from backend.app.api.schemas.contracts import (
    METRICS, AnalogYear, CompareRequest, CompareResponse, MetricSummary,
    RotationComparison, SimulationResult,
)
from backend.app.intelligence.robustness import summarize


def compare_runs(request: CompareRequest, analogs: list[AnalogYear],
                 runs: list[SimulationResult]) -> CompareResponse:
    # Pydantic instances can have been mutated after initial validation.
    request = CompareRequest.model_validate(request.model_dump())
    analogs = [AnalogYear.model_validate(a.model_dump()) for a in analogs]
    runs = [SimulationResult.model_validate(r.model_dump()) for r in runs]
    years = [a.year for a in analogs]
    if len(set(years)) != len(years) or len(years) != request.k:
        raise ValueError('expected k distinct analog years')
    index = {(r.rotation_id, r.year): r for r in runs}
    expected = {(rotation, year) for rotation in request.rotation_ids for year in years}
    if len(index) != len(runs) or set(index) != expected:
        raise ValueError('expected exactly one result per requested rotation and analog year')
    if len({r.mock for r in runs}) != 1:
        raise ValueError('cannot mix mock and real runs')
    if len({r.model_version for r in runs}) != 1:
        raise ValueError('all analog years must use the same model version')
    for run in runs:
        if run.scenario_id != request.scenario_id or run.zona != request.zona:
            raise ValueError('runs must share the requested scenario and zone')
        baseline = index[request.baseline_rotation_id, run.year]
        if (run.environment_id, run.assumptions, run.model_version) != (
                baseline.environment_id, baseline.assumptions, baseline.model_version):
            raise ValueError('paired runs must share environment, assumptions and model version')
    comparisons = []
    warnings = list(dict.fromkeys(w for run in runs for w in run.warnings))
    if len(years) < 5:
        warnings.append(f'Only {len(years)} analog years; descriptive quantiles have limited support.')
    for rotation in request.rotation_ids:
        selected = [index[rotation, year] for year in years]
        absolute, deltas = {}, {}
        for metric in METRICS:
            values, paired = [], []
            for run in selected:
                value = getattr(run.metrics, metric)
                baseline = getattr(index[request.baseline_rotation_id, run.year].metrics, metric)
                values.append(value)
                paired.append(None if value is None or baseline is None else value - baseline)
            absolute[metric], deltas[metric] = summarize(values), summarize(paired)
            if any(v is None for v in values + paired):
                warnings.append(f'{rotation}.{metric}: incomplete years; summary unavailable')
        comparisons.append(RotationComparison(rotation_id=rotation, metrics=MetricSummary(**absolute),
                                               delta_vs_baseline=MetricSummary(**deltas), runs=selected))
    return CompareResponse(
        mock=runs[0].mock, generado=datetime.now(timezone.utc), zona=request.zona,
        source_refs=sorted({s for run in runs for s in run.source_refs}),
        warnings=list(dict.fromkeys(warnings)), scenario_id=request.scenario_id,
        baseline_rotation_id=request.baseline_rotation_id, analog_years=analogs,
        rotations=comparisons, uncertainty_method='empirical_linear_quantiles_across_analog_years',
        limitations=[
            'Estimaciones de modelo. Requieren validación local.',
            'Negative deltas mean lower modeled metrics, not demonstrated water savings.',
            'p10–p90 describes variation across analogs, not a forecast or confidence interval.',
            'No yield, profitability, causal effect or winning rotation is inferred.',
        ],
    )
