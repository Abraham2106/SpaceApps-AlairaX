"""Inspect climate/ONI coverage before ET0; this report never runs KNN."""

import argparse
from datetime import date, datetime, timedelta, timezone
from math import isfinite
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.infrastructure.cache import write_json
from backend.app.api.schemas.contracts import ClimateDay
from backend.app.application.prepare_inputs import ReviewedET0, same_zone_identity
from backend.app.infrastructure.power import PARAMETERS
from backend.app.intelligence.features import ONI_SEASONS
from scripts.build_analogs import (
    SCENARIOS, _oni_period_end, _read, load_normalized_climate, load_normalized_oni, window_options,
)


def _valid_number(value):
    return not isinstance(value, bool) and isinstance(value, (float, int)) and isfinite(value) and value != -999


def inspect_scenarios(climate_files, oni_file, *, start_mmdd, end_mmdd, oni_season,
                      as_of, k=5, strong_el_nino_k=None, et0_file=None):
    first, last = window_options(start_mmdd, end_mmdd, oni_season, as_of, k)
    if strong_el_nino_k is not None and (isinstance(strong_el_nino_k, bool) or not isinstance(strong_el_nino_k, int) or strong_el_nino_k < 1):
        raise ValueError('strong_el_nino_k must be a positive integer')
    documents, provenance, days = load_normalized_climate(climate_files)
    mock, zone = documents[0]['_mock'], documents[0]['zona']
    oni, record, anomalies = load_normalized_oni(oni_file, mock, oni_season)
    provenance.append(record)
    units = {field: unit for field, unit in PARAMETERS.values()}
    for document in documents:
        if any(document.get('units', {}).get(field) != unit for field, unit in units.items()):
            raise ValueError('readiness requires all six normalized POWER unit declarations')
    years = []
    for year in sorted({day.year for day in days}):
        start, end = date(year, *first), date(year, *last)
        expected = [start + timedelta(days=i) for i in range((end - start).days + 1)]
        missing_dates, invalid = [], {field: 0 for field in units}
        inverted_temperature_days = 0
        for day in expected:
            row = days.get(day)
            if row is None:
                missing_dates.append(day.isoformat())
                continue
            for field in units:
                value = row.get(field)
                valid = _valid_number(value)
                if valid and field not in ('tmin_c', 'tmax_c'):
                    valid = value >= 0
                if valid and field == 'relative_humidity_pct':
                    valid = value <= 100
                if not valid:
                    invalid[field] += 1
            if _valid_number(row.get('tmin_c')) and _valid_number(row.get('tmax_c')) and row['tmin_c'] > row['tmax_c']:
                inverted_temperature_days += 1
        climate_complete = not missing_dates and not any(invalid.values()) and not inverted_temperature_days
        anomaly = anomalies.get(year)
        oni_valid = _valid_number(anomaly) and anomaly not in (-99.99, -99.9)
        cutoff_complete = end <= as_of and _oni_period_end(year, oni_season) <= as_of
        reasons = []
        if missing_dates:
            reasons.append('missing climate dates')
        if any(invalid.values()):
            reasons.append('missing or invalid six-variable climate values')
        if inverted_temperature_days:
            reasons.append('inverted daily temperature bounds')
        if not oni_valid:
            reasons.append('selected ONI period unavailable or invalid')
        if not cutoff_complete:
            reasons.append('climate window or ONI period extends beyond as_of')
        years.append({'year': year, 'start': start.isoformat(), 'end': end.isoformat(),
                      'oni_anomaly_c': anomaly, 'oni_period_end': _oni_period_end(year, oni_season).isoformat(),
                      'six_input_climate_complete': climate_complete, 'oni_valid': oni_valid,
                      'within_information_cutoff': cutoff_complete,
                      'climate_oni_eligible_before_et0': climate_complete and oni_valid and cutoff_complete,
                      'et0_reviewed': False, 'missing_climate_dates': missing_dates,
                      'invalid_days_by_field': invalid, 'inverted_temperature_days': inverted_temperature_days,
                      'reasons': reasons})
    history = [row for row in years if row['year'] <= 2025 and row['climate_oni_eligible_before_et0']]
    tracking = next((row for row in years if row['year'] == 2026), None)
    predicates = {
        'strong_el_nino': (lambda value: value >= 1.5, 'seasonal ONI >= 1.5 C'),
        'neutral': (lambda value: -0.5 < value < 0.5, '-0.5 C < seasonal ONI < 0.5 C'),
        'la_nina': (lambda value: value <= -0.5, 'seasonal ONI <= -0.5 C'),
        'like_2026': (lambda value: True, 'all historical years matching the observed tracking window'),
    }
    scenarios = {}
    k_by_scenario = {scenario: strong_el_nino_k if scenario == 'strong_el_nino' and strong_el_nino_k is not None else k for scenario in SCENARIOS}
    for scenario in SCENARIOS:
        predicate, rule = predicates[scenario]
        selected = [row for row in history if predicate(row['oni_anomaly_c'])]
        target_exists = scenario != 'like_2026' or bool(tracking and tracking['climate_oni_eligible_before_et0'])
        supports_k = len(selected) >= k_by_scenario[scenario]
        status = 'blocked_pending_reviewed_et0'
        if not target_exists:
            status = 'tracking_climate_oni_unavailable'
        elif not supports_k:
            status = 'insufficient_climate_oni_years'
        scenarios[scenario] = {
            'status': status, 'phase_rule': rule, 'requested_k': k_by_scenario[scenario],
            'effective_k': None, 'climate_oni_count_before_et0': len(selected),
            'candidate_years_before_et0': [row['year'] for row in selected],
            'climate_oni_supports_requested_k': supports_k, 'tracking_window_complete': target_exists,
            'knn_has_run': False, 'et0_reviewed': False,
            'warnings': ['This is coverage readiness, not a KNN result or ET0 readiness.'] +
                        (['Small analog sample: quantiles remain descriptive and are not confidence intervals.'] if k_by_scenario[scenario] < 5 else []),
        }
    report = {
        'schema_version': '0.1.0', '_mock': mock, 'generado': datetime.now(timezone.utc).isoformat(),
        'zona': zone, 'start_mmdd': start_mmdd, 'end_mmdd': end_mmdd, 'oni_season': oni_season,
        'as_of': as_of.isoformat(), 'k_by_scenario': k_by_scenario,
        'report_kind': 'six_input_climate_and_oni_coverage_before_et0',
        'knn_has_run': False, 'et0_reviewed': False, 'provenance': provenance,
        'source_refs': sorted({url for item in provenance for url in item['source_refs']}),
        'historical_climate_oni_count_before_et0': len(history), 'years': years,
        'scenarios': scenarios,
        'warnings': [
            'Six complete POWER inputs do not certify ET0, soil, crop parameters or kernel readiness.',
            'Current NOAA revisions are retrospective data, not original publication vintages.',
            'A period ending before as_of does not establish its actual publication date.',
            'Seasonal ONI buckets are product rules, not sustained NOAA ENSO event classifications.',
        ],
    }
    if et0_file is not None:
        report['replay_coverage'] = inspect_replay_coverage(report, days, et0_file)
    return report


def inspect_replay_coverage(report, days, et0_file):
    """Count complete May–April replays, retaining the ET0 review flag."""
    payload, provenance = _read(et0_file)
    et0 = ReviewedET0.model_validate(payload)
    if et0.mock != report['_mock'] or not same_zone_identity(et0.zona, report['zona']):
        raise ValueError('ET0 must match the climate zone and mock status')
    if et0.units != 'mm/day':
        raise ValueError('ET0 requires units=mm/day')
    complete_climate_days = set()
    for day, row in days.items():
        try:
            climate = ClimateDay.model_validate(row)
        except ValueError:
            continue
        if all(value is not None for value in climate.model_dump(exclude={'et0_mm'}).values()):
            complete_climate_days.add(day)

    rows = {}
    cutoff = date.fromisoformat(report['as_of'])
    for feature in report['years']:
        year = feature['year']
        if year == 2026:
            continue
        start, end = date(year, 5, 1), date(year + 1, 4, 30)
        replay_dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]
        feature_start = date.fromisoformat(feature['start'])
        feature_end = date.fromisoformat(feature['end'])
        feature_dates = [feature_start + timedelta(days=i)
                         for i in range((feature_end - feature_start).days + 1)]
        missing_climate = [day.isoformat() for day in replay_dates if day not in complete_climate_days]
        missing_et0 = [day.isoformat() for day in replay_dates if et0.values.get(day) is None]
        missing_feature_et0 = [day.isoformat() for day in feature_dates if et0.values.get(day) is None]
        rows[year] = {
            'year': year, 'replay_start': start.isoformat(), 'replay_end': end.isoformat(),
            'within_cutoff': end <= cutoff,
            'feature_et0_complete': not missing_feature_et0,
            'missing_feature_et0_dates': missing_feature_et0,
            'missing_replay_climate_dates': missing_climate, 'missing_replay_et0_dates': missing_et0,
            'feature_and_replay_inputs_complete': feature['climate_oni_eligible_before_et0']
            and not missing_feature_et0 and not missing_climate and not missing_et0 and end <= cutoff,
        }
    tracking = next((row for row in report['years'] if row['year'] == 2026), None)
    tracking_et0_missing = []
    if tracking:
        start, end = date.fromisoformat(tracking['start']), date.fromisoformat(tracking['end'])
        tracking_et0_missing = [day.isoformat() for day in
            (start + timedelta(days=i) for i in range((end - start).days + 1))
            if et0.values.get(day) is None]
    tracking_inputs_complete = bool(tracking and tracking['climate_oni_eligible_before_et0']
                                    and not tracking_et0_missing)
    scenarios = {}
    for scenario, result in report['scenarios'].items():
        eligible = [year for year in result['candidate_years_before_et0']
                    if rows[year]['feature_and_replay_inputs_complete']]
        scenarios[scenario] = {
            'candidate_years_with_complete_inputs': eligible,
            'requested_k': result['requested_k'],
            'historical_pool_supports_requested_k': len(eligible) >= result['requested_k'],
            'tracking_required': scenario == 'like_2026',
        }
    return {
        'et0_reviewed': et0.reviewed, 'et0_model_version': et0.model_version,
        'et0_provenance': provenance, 'knn_has_run': False, 'simulation_run': False,
        'tracking_feature_inputs_complete': tracking_inputs_complete,
        'tracking_missing_feature_et0_dates': tracking_et0_missing,
        'years': list(rows.values()), 'scenarios': scenarios,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--climate', type=Path, nargs='+', required=True)
    parser.add_argument('--oni', type=Path, required=True)
    parser.add_argument('--et0', type=Path, help='Also audit coverage for full May–April replays')
    parser.add_argument('--start-mmdd', required=True)
    parser.add_argument('--end-mmdd', required=True)
    parser.add_argument('--oni-season', choices=ONI_SEASONS, required=True)
    parser.add_argument('--as-of', type=date.fromisoformat, required=True)
    parser.add_argument('--k', type=int, default=5)
    parser.add_argument('--strong-el-nino-k', type=int, default=3)
    parser.add_argument('--output', type=Path, default=ROOT / 'datasets/processed/readiness/scenarios.json')
    args = parser.parse_args(argv)
    try:
        report = inspect_scenarios(args.climate, args.oni, start_mmdd=args.start_mmdd,
                    end_mmdd=args.end_mmdd, oni_season=args.oni_season, as_of=args.as_of,
                    k=args.k, strong_el_nino_k=args.strong_el_nino_k, et0_file=args.et0)
    except (ValueError, KeyError, OSError) as error:
        parser.error(str(error))
    write_json(args.output, report)
    print(f'{report["historical_climate_oni_count_before_et0"]} historical climate/ONI years before reviewed ET0')
    for scenario, result in report['scenarios'].items():
        print(f'{scenario}: {result["climate_oni_count_before_et0"]} candidate years before ET0; requested k={result["requested_k"]}; {result["status"]}')
    if args.et0:
        replay = report['replay_coverage']
        print(f'ET0 reviewed: {replay["et0_reviewed"]}')
        print(f'2026 tracking inputs complete: {replay["tracking_feature_inputs_complete"]}')
        for scenario, result in replay['scenarios'].items():
            print(f'{scenario}: {len(result["candidate_years_with_complete_inputs"])} '
                  f'years with complete feature and replay inputs (k={result["requested_k"]})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
